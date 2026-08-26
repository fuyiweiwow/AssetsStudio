#!/usr/bin/env python3
"""Align turnaround panel foreground centers to a reference without deformation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from analyze_turnaround_sheet import foreground_mask


def foreground_center_x(panel: np.ndarray) -> float:
    points = cv2.findNonZero(foreground_mask(panel))
    if points is None:
        raise RuntimeError("No foreground detected in turnaround panel")
    x, _y, width, _height = cv2.boundingRect(points)
    return x + width / 2.0


def background_color(panel: np.ndarray) -> tuple[int, int, int]:
    border = max(2, min(panel.shape[:2]) // 100)
    samples = np.concatenate(
        (
            panel[:border].reshape(-1, 3),
            panel[-border:].reshape(-1, 3),
            panel[:, :border].reshape(-1, 3),
            panel[:, -border:].reshape(-1, 3),
        ),
        axis=0,
    )
    median = np.median(samples, axis=0).round().astype(np.uint8)
    return tuple(int(value) for value in median)


def normalize_centers(
    image_path: Path, reference_path: Path, output_path: Path, panel_count: int
) -> dict[str, object]:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    reference = cv2.imread(str(reference_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(image_path)
    if reference is None:
        raise FileNotFoundError(reference_path)
    if image.shape[:2] != reference.shape[:2]:
        raise ValueError(
            "Image and reference must have identical dimensions; resize explicitly before "
            "normalizing panel centers"
        )

    height, width = image.shape[:2]
    edges = np.linspace(0, width, panel_count + 1, dtype=int)
    output = image.copy()
    shifts: list[dict[str, int | float]] = []

    for index in range(panel_count):
        left, right = int(edges[index]), int(edges[index + 1])
        panel = image[:, left:right]
        reference_panel = reference[:, left:right]
        source_center = foreground_center_x(panel)
        reference_center = foreground_center_x(reference_panel)
        shift_x = int(round(reference_center - source_center))
        transform = np.float32([[1, 0, shift_x], [0, 1, 0]])
        output[:, left:right] = cv2.warpAffine(
            panel,
            transform,
            (right - left, height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=background_color(panel),
        )
        shifts.append(
            {
                "panel": index + 1,
                "source_center_x": round(source_center, 2),
                "reference_center_x": round(reference_center, 2),
                "shift_x_px": shift_x,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), output):
        raise RuntimeError(f"Failed to write {output_path}")

    return {
        "input": str(image_path.resolve()),
        "reference": str(reference_path.resolve()),
        "output": str(output_path.resolve()),
        "image_size": [width, height],
        "panel_count": panel_count,
        "operation": "integer horizontal translation only; no scaling or deformation",
        "shifts": shifts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--panels", type=int, default=3)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    report = normalize_centers(
        args.image, args.reference, args.output, args.panels
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
