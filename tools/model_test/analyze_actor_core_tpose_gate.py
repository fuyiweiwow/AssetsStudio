#!/usr/bin/env python3
"""Audit shape preservation for the relaxed-A93 to front T-pose conversion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


CENTER_X = 384
HEAD_BOTTOM = 443


def foreground(image: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] > 30) & (hsv[:, :, 2] > 125)).astype(np.uint8)
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count < 2:
        raise RuntimeError("Unable to isolate actor")
    component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == component


def bounds(mask: np.ndarray) -> list[int]:
    ys, xs = np.where(mask)
    if not xs.size:
        raise RuntimeError("Empty mask")
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def row_runs(row: np.ndarray) -> list[tuple[int, int]]:
    changes = np.diff(np.pad(row.astype(np.int8), (1, 1)))
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0] - 1
    return [(int(start), int(end)) for start, end in zip(starts, ends)]


def central_width(mask: np.ndarray, y: int) -> int:
    for start, end in row_runs(mask[y]):
        if start <= CENTER_X <= end:
            return end - start + 1
    raise RuntimeError(f"No central torso run at y={y}")


def leg_width(mask: np.ndarray, y: int) -> float:
    widths = sorted((end - start + 1 for start, end in row_runs(mask[y])), reverse=True)
    if len(widths) < 2:
        raise RuntimeError(f"Expected two leg runs at y={y}")
    return float(sum(widths[:2]) / 2.0)


def column_runs(mask: np.ndarray, x: int, top: int = 440, bottom: int = 550) -> list[tuple[int, int]]:
    changes = np.diff(np.pad(mask[top:bottom, x].astype(np.int8), (1, 1)))
    starts = np.where(changes == 1)[0] + top
    ends = np.where(changes == -1)[0] - 1 + top
    return [(int(start), int(end)) for start, end in zip(starts, ends)]


def shoulder_metrics(
    baseline_image: np.ndarray,
    baseline_mask: np.ndarray,
    candidate_image: np.ndarray,
    candidate_mask: np.ndarray,
    edit_mask: np.ndarray,
) -> dict:
    root_columns = {"left": 310, "right": 458}
    gap_columns = {"left": 315, "right": 453}
    root = {}
    gaps = {}
    for side, x in root_columns.items():
        before = column_runs(baseline_mask, x)[0]
        after = column_runs(candidate_mask, x)[0]
        before_height = before[1] - before[0] + 1
        after_height = after[1] - after[0] + 1
        root[side] = {
            "sample_x": x,
            "before_px": before_height,
            "after_px": after_height,
            "increase_px": after_height - before_height,
        }
    for side, x in gap_columns.items():
        runs = column_runs(candidate_mask, x)
        gap = runs[1][0] - runs[0][1] - 1 if len(runs) >= 2 else 0
        gaps[side] = {"sample_x": x, "open_gap_px": int(gap)}

    effective = cv2.dilate(
        (edit_mask > 0).astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)),
    ) > 0
    difference = np.abs(candidate_image.astype(np.int16) - baseline_image.astype(np.int16))
    outside = np.logical_not(effective)
    changed = np.max(difference, axis=2) > 8
    return {
        "root_vertical_thickness": root,
        "underarm_open_gap": gaps,
        "outside_effective_mask_rgb_mae_0_255": round(float(difference[outside].mean()), 6),
        "outside_effective_mask_changed_ratio_gt_8": round(float(changed[outside].mean()), 6),
    }


def basic_metrics(path: Path) -> tuple[np.ndarray, dict, np.ndarray]:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    mask = foreground(image)
    actor_bbox = bounds(mask)
    head = mask.copy()
    head[HEAD_BOTTOM + 1 :] = False
    head_bbox = bounds(head)
    return image, {
        "path": str(path),
        "actor_y_bounds": [actor_bbox[1], actor_bbox[3]],
        "actor_height_px": actor_bbox[3] - actor_bbox[1] + 1,
        "head_bbox_xyxy": head_bbox,
        "head_width_px": head_bbox[2] - head_bbox[0] + 1,
        "head_height_px": head_bbox[3] - head_bbox[1] + 1,
        # Sample below the relaxed arms. At y=520/530 the source arms still
        # touch the torso row and would falsely inflate its width.
        "torso_widths_px": {str(y): central_width(mask, y) for y in (550, 575, 595)},
        "lower_leg_width_px": leg_width(mask, 665),
    }, mask


def tpose_metrics(mask: np.ndarray) -> dict:
    left_y, left_x = np.where(mask & (np.indices(mask.shape)[1] < 300) & (np.indices(mask.shape)[0] >= 444) & (np.indices(mask.shape)[0] <= 505))
    right_y, right_x = np.where(mask & (np.indices(mask.shape)[1] > 468) & (np.indices(mask.shape)[0] >= 444) & (np.indices(mask.shape)[0] <= 505))
    if not left_x.size or not right_x.size:
        raise RuntimeError("Unable to isolate horizontal arms")
    left_tip = left_y[left_x <= left_x.min() + 24]
    right_tip = right_y[right_x >= right_x.max() - 24]
    left_center = float(np.median(left_tip))
    right_center = float(np.median(right_tip))
    return {
        "arm_span_x": [int(left_x.min()), int(right_x.max())],
        "arm_span_px": int(right_x.max() - left_x.min() + 1),
        "left_tip_center_y": round(left_center, 2),
        "right_tip_center_y": round(right_center, 2),
        "tip_level_delta_px": round(abs(left_center - right_center), 2),
        "tip_to_shoulder_y_px": {
            "left": round(left_center - 458.0, 2),
            "right": round(right_center - 458.0, 2),
        },
    }


def font(size: int) -> ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/segoeuib.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def review(
    source: Path,
    candidate: Path,
    report: dict,
    output: Path,
    baseline_tpose: Path | None = None,
) -> None:
    entries = [("A93 RELAXED SHAPE", source)]
    if baseline_tpose:
        entries.append(("T-POSE BEFORE", baseline_tpose))
    entries.append(("T-POSE CANDIDATE", candidate))
    tile = 512 if baseline_tpose else 640
    header = 56
    footer = 100
    canvas = Image.new("RGB", (tile * len(entries), header + tile + footer), "#202124")
    draw = ImageDraw.Draw(canvas)
    for index, (label, path) in enumerate(entries):
        image = Image.open(path).convert("RGB").resize((tile, tile), Image.Resampling.LANCZOS)
        canvas.paste(image, (index * tile, header))
        draw.text((index * tile + 18, 14), label, font=font(24), fill="white")
    metrics = report["candidate"]
    pose = metrics["tpose"]
    summary = (
        f"head {metrics['head_width_px']}x{metrics['head_height_px']} px | "
        f"body H {metrics['actor_height_px']} px | arm span {pose['arm_span_px']} px\n"
        f"torso W @550/575/595: {list(metrics['torso_widths_px'].values())} | "
        f"leg W {metrics['lower_leg_width_px']:.1f} px | level delta {pose['tip_level_delta_px']:.1f} px"
    )
    draw.text((18, header + tile + 22), summary, font=font(18), fill="#e8eaed")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline-tpose", type=Path)
    parser.add_argument("--edit-mask", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()

    _, source_metrics, _ = basic_metrics(args.source)
    candidate_image, candidate_metrics, candidate_mask = basic_metrics(args.candidate)
    candidate_metrics["tpose"] = tpose_metrics(candidate_mask)

    head_edge_drift = [
        abs(a - b) for a, b in zip(source_metrics["head_bbox_xyxy"], candidate_metrics["head_bbox_xyxy"])
    ]
    torso_drift = {
        y: round(abs(candidate_metrics["torso_widths_px"][y] - width) / width, 6)
        for y, width in source_metrics["torso_widths_px"].items()
    }
    height_drift = abs(candidate_metrics["actor_height_px"] - source_metrics["actor_height_px"]) / source_metrics["actor_height_px"]
    leg_drift = abs(candidate_metrics["lower_leg_width_px"] - source_metrics["lower_leg_width_px"]) / source_metrics["lower_leg_width_px"]
    pose = candidate_metrics["tpose"]
    gates = {
        "head_bbox_max_edge_drift_lte_6px": max(head_edge_drift) <= 6,
        "actor_height_drift_lte_0_01": height_drift <= 0.01,
        "torso_width_drift_each_lte_0_06": all(value <= 0.06 for value in torso_drift.values()),
        "lower_leg_width_drift_lte_0_06": leg_drift <= 0.06,
        "arm_span_440_to_490px": 440 <= pose["arm_span_px"] <= 490,
        "arm_tip_level_delta_lte_4px": pose["tip_level_delta_px"] <= 4,
        "arm_tip_shoulder_offset_abs_lte_14px": all(abs(value) <= 14 for value in pose["tip_to_shoulder_y_px"].values()),
    }
    shoulder = None
    if args.baseline_tpose or args.edit_mask:
        if not args.baseline_tpose or not args.edit_mask:
            parser.error("--baseline-tpose and --edit-mask must be provided together")
        baseline_image, _, baseline_mask = basic_metrics(args.baseline_tpose)
        edit_mask = cv2.imread(str(args.edit_mask), cv2.IMREAD_GRAYSCALE)
        if edit_mask is None or edit_mask.shape != candidate_mask.shape:
            raise ValueError("Shoulder edit mask is missing or has the wrong dimensions")
        shoulder = shoulder_metrics(
            baseline_image,
            baseline_mask,
            candidate_image,
            candidate_mask,
            edit_mask,
        )
        increases = [
            item["increase_px"] for item in shoulder["root_vertical_thickness"].values()
        ]
        gaps = [item["open_gap_px"] for item in shoulder["underarm_open_gap"].values()]
        gates.update(
            {
                "shoulder_root_increase_each_8_to_30px": all(8 <= value <= 30 for value in increases),
                "underarm_open_gap_each_gte_18px": all(value >= 18 for value in gaps),
                "outside_shoulder_edit_rgb_mae_lte_0_1": shoulder[
                    "outside_effective_mask_rgb_mae_0_255"
                ] <= 0.1,
                "outside_shoulder_edit_changed_ratio_lte_0_001": shoulder[
                    "outside_effective_mask_changed_ratio_gt_8"
                ] <= 0.001,
            }
        )
    report_data = {
        "schema": "assetsstudio_actor_core_tpose_shape_gate_v1",
        "status": "human_review_required",
        "source": source_metrics,
        "candidate": candidate_metrics,
        "drift": {
            "head_bbox_edges_px": head_edge_drift,
            "actor_height_ratio": round(height_drift, 6),
            "torso_width_ratios": torso_drift,
            "lower_leg_width_ratio": round(leg_drift, 6),
        },
        "shoulder_repair": shoulder,
        "automatic_gates": gates,
        "automatic_pass": all(gates.values()),
        "human_checks": [
            "shoulders remain below the head and connect naturally",
            "armpits are open with no webbing or fused triangles",
            "hands remain compact mitten ends without separated fingers",
            "head, torso, legs and feet retain A93 style proportions",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review(args.source, args.candidate, report_data, args.review, args.baseline_tpose)
    print(json.dumps(report_data, ensure_ascii=False, indent=2))
    return 0 if report_data["automatic_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
