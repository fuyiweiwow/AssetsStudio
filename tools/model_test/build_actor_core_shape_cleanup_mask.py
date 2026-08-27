#!/usr/bin/env python3
"""Build a head and lower-leg cleanup mask for an Actor Core candidate."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from analyze_turnaround_sheet import foreground_mask


def build_mask(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    edges = np.linspace(0, width, 4, dtype=int)
    result = np.zeros((height, width), dtype=np.uint8)
    for index in range(3):
        left, right = int(edges[index]), int(edges[index + 1])
        panel = image[:, left:right]
        points = cv2.findNonZero(foreground_mask(panel))
        if points is None:
            raise RuntimeError(f"No foreground detected in panel {index + 1}")
        x, y, box_width, box_height = cv2.boundingRect(points)
        pad = round(box_width * 0.08)
        cv2.rectangle(
            result,
            (max(left, left + x - pad), max(0, y - pad)),
            (
                min(right - 1, left + x + box_width + pad),
                min(height - 1, y + round(box_height * 0.48)),
            ),
            255,
            -1,
        )
        cv2.rectangle(
            result,
            (max(left, left + x - pad), y + round(box_height * 0.77)),
            (
                min(right - 1, left + x + box_width + pad),
                min(height - 1, y + box_height + pad),
            ),
            255,
            -1,
        )
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
        overlay = np.zeros_like(image)
        overlay[:, :, 2] = mask
        preview = cv2.addWeighted(image, 0.72, overlay, 0.28, 0)
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.preview), preview):
            raise RuntimeError(f"Unable to write {args.preview}")
    print(f"mask={args.output.resolve()}")
    if args.preview:
        print(f"preview={args.preview.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
