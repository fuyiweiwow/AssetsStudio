#!/usr/bin/env python3
"""Audit front/right landmark alignment for the A93 T-pose Actor Core."""

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


def metrics(path: Path) -> dict:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    mask = foreground(image)
    actor_bbox = bounds(mask)
    head = mask.copy()
    head[HEAD_CROP_BOTTOM + 1 :] = False
    head_bbox = bounds(head)
    return {
        "path": str(path),
        "actor_bbox_xyxy": actor_bbox,
        "actor_height_px": actor_bbox[3] - actor_bbox[1] + 1,
        "head_bbox_xyxy": head_bbox,
        "head_width_px": head_bbox[2] - head_bbox[0] + 1,
        "head_height_px": head_bbox[3] - head_bbox[1] + 1,
        "head_center_x": round((head_bbox[0] + head_bbox[2]) / 2.0, 2),
        "torso_span_y550_px": widest_run(mask, 550),
    }


def font(size: int) -> ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/segoeuib.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def make_review(front: Path, right: Path, raw_right: Path | None, report: dict, output: Path) -> None:
    entries = [("FRONT A", front)]
    if raw_right:
        entries.append(("RIGHT RAW", raw_right))
    entries.append(("RIGHT A CLEAN", right))
    tile = 512 if len(entries) == 3 else 640
    header = 56
    footer = 100
    canvas = Image.new("RGB", (tile * len(entries), header + tile + footer), "#202124")
    draw = ImageDraw.Draw(canvas)
    for index, (label, path) in enumerate(entries):
        image = Image.open(path).convert("RGB").resize((tile, tile), Image.Resampling.LANCZOS)
        canvas.paste(image, (index * tile, header))
        draw.text((index * tile + 18, 14), label, font=font(23), fill="white")
    drift = report["drift"]
    summary = (
        f"top/head-bottom/floor drift: {drift['head_top_px']}/{drift['head_bottom_px']}/"
        f"{drift['floor_px']} px | side-depth/front-width: {drift['head_depth_to_front_width']:.3f}\n"
        f"head center drift: {drift['head_center_x_px']:.1f} px | "
        f"side torso/front torso @550: {drift['torso_depth_to_front_width']:.3f} | "
        f"automatic pass: {report['automatic_pass']}"
    )
    draw.text((18, header + tile + 22), summary, font=font(18), fill="#e8eaed")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--front", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--raw-right", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()

    front = metrics(args.front)
    right = metrics(args.right)
    front_head = front["head_bbox_xyxy"]
    right_head = right["head_bbox_xyxy"]
    drift = {
        "head_top_px": abs(right_head[1] - front_head[1]),
        "head_bottom_px": abs(right_head[3] - front_head[3]),
        "floor_px": abs(right["actor_bbox_xyxy"][3] - front["actor_bbox_xyxy"][3]),
        "actor_height_ratio": round(
            abs(right["actor_height_px"] - front["actor_height_px"]) / front["actor_height_px"], 6
        ),
        "head_center_x_px": round(abs(right["head_center_x"] - front["head_center_x"]), 2),
        "head_depth_to_front_width": round(right["head_width_px"] / front["head_width_px"], 6),
        "head_height_ratio": round(right["head_height_px"] / front["head_height_px"], 6),
        "torso_depth_to_front_width": round(
            right["torso_span_y550_px"] / front["torso_span_y550_px"], 6
        ),
    }
    gates = {
        "head_top_drift_lte_6px": drift["head_top_px"] <= 6,
        "head_bottom_drift_lte_10px": drift["head_bottom_px"] <= 10,
        "floor_drift_lte_3px": drift["floor_px"] <= 3,
        "actor_height_drift_lte_0_02": drift["actor_height_ratio"] <= 0.02,
        "head_center_drift_lte_8px": drift["head_center_x_px"] <= 8,
        "head_depth_ratio_0_85_to_1_05": 0.85 <= drift["head_depth_to_front_width"] <= 1.05,
        "head_height_ratio_0_95_to_1_03": 0.95 <= drift["head_height_ratio"] <= 1.03,
        "torso_depth_ratio_0_75_to_1_05": 0.75 <= drift["torso_depth_to_front_width"] <= 1.05,
    }
    report = {
        "schema": "assetsstudio_actor_core_right_view_gate_v1",
        "status": "human_review_required",
        "front": front,
        "right": right,
        "drift": drift,
        "automatic_gates": gates,
        "automatic_pass": all(gates.values()),
        "human_checks": [
            "strict 90-degree profile rather than three-quarter view",
            "full rounded back cranium and shallow directional face plane",
            "no ear, nose, mouth or semantic residue",
            "T-pose arm projection remains plausible and shoulder height is preserved",
            "torso depth and foot profile retain the approved chibi shape language",
        ],
        "next_stage_if_approved": "derive a blank-face right view, then isolate the back view",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    make_review(args.front, args.right, args.raw_right, report, args.review)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["automatic_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
