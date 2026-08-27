#!/usr/bin/env python3
"""Isotropically align turnaround panels to a reference canvas and placement."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from analyze_turnaround_sheet import foreground_mask
from normalize_turnaround_panel_centers import background_color


def foreground_box(panel: np.ndarray) -> tuple[int, int, int, int]:
    points = cv2.findNonZero(foreground_mask(panel))
    if points is None:
        raise RuntimeError("No foreground detected in turnaround panel")
    return tuple(int(value) for value in cv2.boundingRect(points))


def normalize_geometry(
    image_path: Path,
    reference_path: Path,
    output_path: Path,
    panel_count: int,
) -> dict:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    reference = cv2.imread(str(reference_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(image_path)
    if reference is None:
        raise FileNotFoundError(reference_path)

    output_height, output_width = reference.shape[:2]
    source_edges = np.linspace(0, image.shape[1], panel_count + 1, dtype=int)
    reference_edges = np.linspace(0, output_width, panel_count + 1, dtype=int)
    output = np.empty_like(reference)
    panels: list[dict] = []

    for index in range(panel_count):
        source_left, source_right = int(source_edges[index]), int(source_edges[index + 1])
        target_left, target_right = (
            int(reference_edges[index]),
            int(reference_edges[index + 1]),
        )
        panel = image[:, source_left:source_right]
        reference_panel = reference[:, target_left:target_right]
        x, y, width, height = foreground_box(panel)
        ref_x, ref_y, ref_width, ref_height = foreground_box(reference_panel)
        scale = ref_height / height
        source_center_x = x + width / 2
        source_ground_y = y + height
        reference_center_x = ref_x + ref_width / 2
        reference_ground_y = ref_y + ref_height
        transform = np.array(
            [
                [scale, 0.0, reference_center_x - scale * source_center_x],
                [0.0, scale, reference_ground_y - scale * source_ground_y],
            ],
            dtype=np.float32,
        )
        output[:, target_left:target_right] = cv2.warpAffine(
            panel,
            transform,
            (target_right - target_left, output_height),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=background_color(panel),
        )
        panels.append(
            {
                "panel": index + 1,
                "uniform_scale": round(scale, 8),
                "source_foreground_bbox": [x, y, width, height],
                "reference_foreground_bbox": [ref_x, ref_y, ref_width, ref_height],
                "target_center_x": round(reference_center_x, 3),
                "target_ground_y": reference_ground_y,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), output):
        raise RuntimeError(f"Failed to write {output_path}")
    return {
        "schema": "assetsstudio_turnaround_panel_geometry_normalization_v1",
        "input": str(image_path.resolve()),
        "reference": str(reference_path.resolve()),
        "output": str(output_path.resolve()),
        "output_size": [output_width, output_height],
        "panel_count": panel_count,
        "operation": "per-panel uniform scale plus x/y translation only; no deformation",
        "panels": panels,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--panels", type=int, default=3)
    args = parser.parse_args()
    report = normalize_geometry(args.image, args.reference, args.output, args.panels)
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
