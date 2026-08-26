#!/usr/bin/env python3
"""Build a binary narrow-torso guide for human Actor Core target labeling.

The output is never a training target or a production asset.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from analyze_turnaround_sheet import foreground_mask
from build_actor_core_repair_mask import build_mask, build_panel_polygons


SCALE_CONTROL_POINTS = (
    (0.43, 0.96),
    (0.50, 0.90),
    (0.63, 0.82),
    (0.73, 0.82),
    (0.83, 0.88),
    (0.89, 0.98),
)


def full_foreground_mask(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    panel_width = width // 3
    result = np.zeros((height, width), dtype=np.uint8)
    for index in range(3):
        left = index * panel_width
        right = width if index == 2 else (index + 1) * panel_width
        result[:, left:right] = foreground_mask(image[:, left:right])
    return result


def build_silhouette(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    height, width = image.shape[:2]
    repair_mask = build_mask(image)
    polygons = build_panel_polygons(image)
    map_x, map_y = np.meshgrid(
        np.arange(width, dtype=np.float32),
        np.arange(height, dtype=np.float32),
    )
    panel_width = width // 3
    for index, polygon in enumerate(polygons):
        left = index * panel_width
        right = width if index == 2 else (index + 1) * panel_width
        panel = image[:, left:right]
        points = cv2.findNonZero(foreground_mask(panel))
        if points is None:
            raise RuntimeError(f"No foreground found in panel {index + 1}")
        _, y, _, box_height = cv2.boundingRect(points)
        center_x = float(polygon[:, 0].mean())
        normalized_y = (
            np.arange(height, dtype=np.float32) - y
        ) / max(1, box_height)
        scales = np.interp(
            normalized_y,
            [item[0] for item in SCALE_CONTROL_POINTS],
            [item[1] for item in SCALE_CONTROL_POINTS],
            left=1.0,
            right=1.0,
        )
        xs = np.arange(left, right, dtype=np.float32)[None, :]
        map_x[:, left:right] = center_x + (xs - center_x) / scales[:, None]

    source_foreground = full_foreground_mask(image)
    repair_foreground = cv2.bitwise_and(source_foreground, repair_mask)
    warped_repair = cv2.remap(
        repair_foreground,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    locked_foreground = cv2.bitwise_and(
        source_foreground, cv2.bitwise_not(repair_mask)
    )
    silhouette = cv2.bitwise_or(locked_foreground, warped_repair)
    silhouette = cv2.morphologyEx(
        silhouette,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)),
    )
    return silhouette, repair_mask


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mask-output", type=Path)
    args = parser.parse_args()

    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Unable to read {args.image}")
    silhouette, repair_mask = build_silhouette(image)
    guide = np.full_like(image, 242)
    guide[silhouette > 0] = (24, 24, 24)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), guide):
        raise RuntimeError(f"Unable to write {args.output}")
    if args.mask_output:
        args.mask_output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.mask_output), repair_mask):
            raise RuntimeError(f"Unable to write {args.mask_output}")
    print(f"silhouette_guide={args.output.resolve()}")
    print("role=human_labeling_guide_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
