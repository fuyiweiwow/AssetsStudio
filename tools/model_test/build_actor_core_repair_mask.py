#!/usr/bin/env python3
"""Build a deterministic torso repair mask for a three-view Actor Core sheet."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from analyze_turnaround_sheet import foreground_mask


PANEL_POLYGONS = (
    # Front: central torso and pelvis, excluding the head, hands and lower legs.
    ((0.32, 0.43), (0.68, 0.43), (0.70, 0.69), (0.70, 0.89),
     (0.30, 0.89), (0.30, 0.69)),
    # Right profile: cover the body mass while leaving the face and feet intact.
    ((0.31, 0.43), (0.77, 0.43), (0.79, 0.70), (0.74, 0.89),
     (0.30, 0.89), (0.27, 0.69)),
    # Back: symmetric central torso/pelvis repair region.
    ((0.30, 0.43), (0.70, 0.43), (0.73, 0.69), (0.72, 0.89),
     (0.28, 0.89), (0.27, 0.69)),
)


def build_panel_polygons(image: np.ndarray) -> list[np.ndarray]:
    height, width = image.shape[:2]
    panel_width = width // 3
    polygons: list[np.ndarray] = []

    for index, normalized_points in enumerate(PANEL_POLYGONS):
        left = index * panel_width
        right = width if index == 2 else (index + 1) * panel_width
        panel = image[:, left:right]
        mask = foreground_mask(panel)
        points = cv2.findNonZero(mask)
        if points is None:
            raise RuntimeError(f"No foreground found in panel {index + 1}")
        x, y, box_width, box_height = cv2.boundingRect(points)
        polygon = np.array(
            [
                [
                    left + x + int(px * box_width),
                    y + int(py * box_height),
                ]
                for px, py in normalized_points
            ],
            dtype=np.int32,
        )
        polygons.append(polygon)

    return polygons


def build_mask(image: np.ndarray) -> np.ndarray:
    result = np.zeros(image.shape[:2], dtype=np.uint8)
    for polygon in build_panel_polygons(image):
        cv2.fillPoly(result, [polygon], 255)

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()

    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Unable to read {args.image}")
    mask = build_mask(image)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), mask):
        raise RuntimeError(f"Unable to write {args.output}")

    if args.preview:
        preview = image.copy()
        overlay = np.zeros_like(preview)
        overlay[:, :, 2] = mask
        preview = cv2.addWeighted(preview, 0.72, overlay, 0.28, 0)
        contour, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(preview, contour, -1, (0, 0, 255), 2)
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.preview), preview):
            raise RuntimeError(f"Unable to write {args.preview}")

    print(f"mask={args.output.resolve()}")
    if args.preview:
        print(f"preview={args.preview.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
