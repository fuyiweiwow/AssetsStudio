#!/usr/bin/env python3
"""Audit front/back landmark alignment for the A93 T-pose Actor Core."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HEAD_CROP_BOTTOM = 443


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


def widest_run(mask: np.ndarray, y: int) -> int:
    runs = row_runs(mask[y])
    if not runs:
        raise RuntimeError(f"No foreground at y={y}")
    start, end = max(runs, key=lambda run: run[1] - run[0])
    return end - start + 1


def tip_center_y(mask: np.ndarray, x_start: int, x_end: int) -> float:
    ys, _ = np.where(mask[:, x_start:x_end])
    if not ys.size:
        raise RuntimeError("Unable to measure arm tip")
    return float(np.median(ys))


def metrics(path: Path) -> dict:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    mask = foreground(image)
    actor_bbox = bounds(mask)
    head = mask.copy()
    head[HEAD_CROP_BOTTOM + 1 :] = False
    head_bbox = bounds(head)
    left_tip_y = tip_center_y(mask, actor_bbox[0], actor_bbox[0] + 6)
    right_tip_y = tip_center_y(mask, actor_bbox[2] - 5, actor_bbox[2] + 1)
    return {
        "path": str(path),
        "actor_bbox_xyxy": actor_bbox,
        "actor_width_px": actor_bbox[2] - actor_bbox[0] + 1,
        "actor_height_px": actor_bbox[3] - actor_bbox[1] + 1,
        "actor_center_x": round((actor_bbox[0] + actor_bbox[2]) / 2.0, 2),
        "head_bbox_xyxy": head_bbox,
        "head_width_px": head_bbox[2] - head_bbox[0] + 1,
        "head_height_px": head_bbox[3] - head_bbox[1] + 1,
        "head_center_x": round((head_bbox[0] + head_bbox[2]) / 2.0, 2),
        "torso_span_y550_px": widest_run(mask, 550),
        "left_tip_center_y": round(left_tip_y, 2),
        "right_tip_center_y": round(right_tip_y, 2),
    }


def font(size: int) -> ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/segoeuib.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def make_review(front: Path, right: Path, back: Path, report: dict, output: Path) -> None:
    entries = [("FRONT B", front), ("RIGHT B", right), ("BACK B CANDIDATE", back)]
    tile = 512
    header = 56
    footer = 100
    canvas = Image.new("RGB", (tile * 3, header + tile + footer), "#202124")
    draw = ImageDraw.Draw(canvas)
    for index, (label, path) in enumerate(entries):
        image = Image.open(path).convert("RGB").resize((tile, tile), Image.Resampling.LANCZOS)
        canvas.paste(image, (index * tile, header))
        draw.text((index * tile + 18, 14), label, font=font(23), fill="white")
    drift = report["drift"]
    summary = (
        f"top/head-bottom/floor drift: {drift['head_top_px']}/{drift['head_bottom_px']}/"
        f"{drift['floor_px']} px | back/front head width: {drift['head_width_ratio']:.3f}\n"
        f"arm span ratio: {drift['arm_span_ratio']:.3f} | back/front torso @550: "
        f"{drift['torso_width_ratio']:.3f} | tip level delta: {drift['back_tip_level_delta_px']:.1f}px | "
        f"automatic pass: {report['automatic_pass']}"
    )
    draw.text((18, header + tile + 22), summary, font=font(18), fill="#e8eaed")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--front", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--back", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()

    front = metrics(args.front)
    back = metrics(args.back)
    front_head = front["head_bbox_xyxy"]
    back_head = back["head_bbox_xyxy"]
    drift = {
        "head_top_px": abs(back_head[1] - front_head[1]),
        "head_bottom_px": abs(back_head[3] - front_head[3]),
        "floor_px": abs(back["actor_bbox_xyxy"][3] - front["actor_bbox_xyxy"][3]),
        "actor_height_ratio_delta": round(
            abs(back["actor_height_px"] - front["actor_height_px"]) / front["actor_height_px"], 6
        ),
        "actor_center_x_px": round(abs(back["actor_center_x"] - front["actor_center_x"]), 2),
        "head_center_x_px": round(abs(back["head_center_x"] - front["head_center_x"]), 2),
        "head_width_ratio": round(back["head_width_px"] / front["head_width_px"], 6),
        "head_height_ratio": round(back["head_height_px"] / front["head_height_px"], 6),
        "arm_span_ratio": round(back["actor_width_px"] / front["actor_width_px"], 6),
        "torso_width_ratio": round(back["torso_span_y550_px"] / front["torso_span_y550_px"], 6),
        "back_tip_level_delta_px": round(
            abs(back["left_tip_center_y"] - back["right_tip_center_y"]), 2
        ),
    }
    gates = {
        "head_top_drift_lte_6px": drift["head_top_px"] <= 6,
        "head_bottom_drift_lte_8px": drift["head_bottom_px"] <= 8,
        "floor_drift_lte_3px": drift["floor_px"] <= 3,
        "actor_height_drift_lte_0_02": drift["actor_height_ratio_delta"] <= 0.02,
        "actor_center_drift_lte_6px": drift["actor_center_x_px"] <= 6,
        "head_center_drift_lte_6px": drift["head_center_x_px"] <= 6,
        "head_width_ratio_0_95_to_1_05": 0.95 <= drift["head_width_ratio"] <= 1.05,
        "head_height_ratio_0_95_to_1_03": 0.95 <= drift["head_height_ratio"] <= 1.03,
        "arm_span_ratio_0_97_to_1_04": 0.97 <= drift["arm_span_ratio"] <= 1.04,
        "torso_width_ratio_0_90_to_1_08": 0.90 <= drift["torso_width_ratio"] <= 1.08,
        "back_tip_level_delta_lte_4px": drift["back_tip_level_delta_px"] <= 4,
    }
    report = {
        "schema": "assetsstudio_actor_core_back_view_gate_v1",
        "status": "human_review_required",
        "front": front,
        "back": back,
        "drift": drift,
        "automatic_gates": gates,
        "automatic_pass": all(gates.values()),
        "human_checks": [
            "strict centered back view with no head turn or facial semantics",
            "full rounded cranium matches the approved front width and height",
            "smooth featureless back and pelvis without spine or buttock groove",
            "open armpits and corrected rounded shoulder roots remain plausible",
            "hand shape is recorded but intentionally deferred until the topology gate",
        ],
        "next_stage_if_approved": "derive left B by deterministic mirroring, freeze four-view hashes, then start the isolated 3D reconstruction probe",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    make_review(args.front, args.right, args.back, report, args.review)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["automatic_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
