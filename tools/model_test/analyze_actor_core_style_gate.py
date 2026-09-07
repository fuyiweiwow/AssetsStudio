#!/usr/bin/env python3
"""Measure and render the relaxed-pose Actor Core style-shape gate.

The accepted user concept is the visual authority.  Its hair and clothes mean
the measurements are an outer-envelope comparison, not inferred naked anatomy.
This gate deliberately checks only broad proportions; semantic cleanup and
T-pose conversion remain separate later stages.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def largest_saturated_component(image: np.ndarray) -> np.ndarray:
    saturation = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
    # The matte renders have saturated warm body colors and a low-saturation
    # gray floor.  A threshold of 35 excludes the warm contact shadow that can
    # otherwise inflate total height while retaining the peach silhouette.
    mask = (saturation > 35).astype(np.uint8) * 255
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        np.ones((7, 7), np.uint8),
        iterations=2,
    )
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count < 2:
        raise ValueError("Could not isolate a foreground component")
    component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == component


def horizontal_span(row: np.ndarray) -> int:
    xs = np.flatnonzero(row)
    return int(xs[-1] - xs[0] + 1) if xs.size else 0


def analyze(path: Path) -> dict:
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(path)
    mask = largest_saturated_component(image)
    ys, xs = np.where(mask)
    left, top, right, bottom = (
        int(xs.min()),
        int(ys.min()),
        int(xs.max()),
        int(ys.max()),
    )
    width = right - left + 1
    height = bottom - top + 1
    spans = np.array([horizontal_span(mask[y]) for y in range(top, bottom + 1)])
    smooth = np.convolve(spans, np.ones(15) / 15.0, mode="same")
    neck_start = round(height * 0.50)
    neck_end = round(height * 0.62)
    neck_offset = neck_start + int(np.argmin(smooth[neck_start:neck_end]))
    neck_y = top + neck_offset
    head_height = neck_y - top + 1
    head_width = int(spans[: neck_offset + 1].max())

    center_x = (left + right) // 2
    leg_split = None
    for y in range(top + round(height * 0.72), bottom + 1):
        if mask[y, max(0, center_x - 2) : center_x + 3].sum() == 0:
            left_present = mask[y, left:center_x].any()
            right_present = mask[y, center_x + 1 : right + 1].any()
            if left_present and right_present:
                leg_split = y
                break
    leg_fraction = (
        (bottom - leg_split + 1) / height if leg_split is not None else None
    )

    return {
        "path": str(path),
        "canvas": [int(image.shape[1]), int(image.shape[0])],
        "subject_bbox": [left, top, right, bottom],
        "subject_height_px": height,
        "head_envelope": {
            "neck_y": neck_y,
            "height_px": head_height,
            "width_px": head_width,
            "total_heads": round(height / head_height, 4),
            "width_height": round(head_width / head_height, 4),
        },
        "leg_split_y": leg_split,
        "leg_length_fraction": round(leg_fraction, 4) if leg_fraction else None,
    }


def font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def make_review(source: Path, candidates: list[Path], metrics: list[dict], output: Path) -> None:
    tile = 560
    header = 58
    footer = 110
    canvas = Image.new("RGB", (tile * (len(candidates) + 1), header + tile + footer), "#202124")
    draw = ImageDraw.Draw(canvas)
    title_font = font(25)
    info_font = font(18)
    entries = [("STYLE AUTHORITY", source), *[(f"CANDIDATE {p.stem.split('202609')[-1]}", p) for p in candidates]]
    for index, ((label, path), item) in enumerate(zip(entries, metrics)):
        image = Image.open(path).convert("RGB").resize((tile, tile), Image.Resampling.LANCZOS)
        x = index * tile
        canvas.paste(image, (x, header))
        draw.text((x + 18, 15), label, font=title_font, fill="white")
        head = item["head_envelope"]
        info = (
            f"visual heads: {head['total_heads']:.2f}   "
            f"head W/H: {head['width_height']:.2f}\n"
            f"leg fraction: {item['leg_length_fraction'] if item['leg_length_fraction'] is not None else 'n/a'}"
        )
        draw.multiline_text((x + 18, header + tile + 18), info, font=info_font, fill="#e8eaed", spacing=8)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, action="append", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()

    source_metrics = analyze(args.source)
    candidate_metrics = [analyze(path) for path in args.candidate]
    source_head = source_metrics["head_envelope"]
    source_leg = source_metrics["leg_length_fraction"]
    for item in candidate_metrics:
        head = item["head_envelope"]
        checks = {
            "visual_total_heads": abs(head["total_heads"] - source_head["total_heads"]) <= 0.22,
            "head_width_height": abs(head["width_height"] - source_head["width_height"]) <= 0.10,
            "leg_length_fraction": (
                source_leg is not None
                and item["leg_length_fraction"] is not None
                and abs(item["leg_length_fraction"] - source_leg) <= 0.05
            ),
        }
        item["automatic_shape_checks"] = checks
        item["automatic_shape_pass"] = all(checks.values())

    report = {
        "schema": "assetsstudio_actor_core_relaxed_style_gate_v1",
        "status": "human_review_required",
        "measurement_scope": "outer visual envelope in the same relaxed front pose",
        "caveat": "The authority head includes hair and its body includes clothing; metrics reject gross drift but do not infer naked anatomy or replace human style review.",
        "source": source_metrics,
        "candidates": candidate_metrics,
        "next_stage_if_approved": "isolated pose transfer to T-pose while retaining the approved shape authority",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    make_review(args.source, args.candidate, [source_metrics, *candidate_metrics], args.review)
    print(f"report={args.report.resolve()}")
    print(f"review={args.review.resolve()}")
    for item in candidate_metrics:
        print(f"candidate={item['path']} pass={item['automatic_shape_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
