#!/usr/bin/env python3
"""Split, register, and reorder generated orthographic character panels."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from analyze_turnaround_sheet import foreground_mask


def parse_labels(value: str) -> list[str]:
    labels = [item.strip() for item in value.split(",") if item.strip()]
    if len(labels) != len(set(labels)):
        raise argparse.ArgumentTypeError("view labels must be unique")
    return labels


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--detected-order", type=parse_labels, required=True)
    parser.add_argument(
        "--canonical-order",
        type=parse_labels,
        default=parse_labels("front,right,back,left"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--montage", type=Path)
    args = parser.parse_args()

    if set(args.detected_order) != set(args.canonical_order):
        parser.error("detected and canonical order must contain the same labels")

    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"Unable to read {args.image}")
    image_height, image_width = image.shape[:2]
    panel_count = len(args.detected_order)
    edges = np.linspace(0, image_width, panel_count + 1, dtype=int)

    panels: dict[str, np.ndarray] = {}
    measurements: list[tuple[np.ndarray, tuple[int, int, int, int]]] = []
    for index in range(panel_count):
        panel = image[:, edges[index] : edges[index + 1]].copy()
        points = cv2.findNonZero(foreground_mask(panel))
        if points is None:
            raise SystemExit(f"No foreground detected in panel {index + 1}")
        measurements.append((panel, cv2.boundingRect(points)))

    target_ground = int(round(np.median([y + h for _, (_, y, _, h) in measurements])))
    for label, (panel, (x, y, width, height)) in zip(
        args.detected_order, measurements, strict=True
    ):
        panel_width = panel.shape[1]
        source_center = x + width / 2
        shift_x = int(round(panel_width / 2 - source_center))
        shift_y = target_ground - (y + height)
        border = max(4, min(panel.shape[:2]) // 64)
        samples = np.concatenate(
            [
                panel[:border].reshape(-1, 3),
                panel[:, :border].reshape(-1, 3),
                panel[:, -border:].reshape(-1, 3),
            ]
        )
        background = tuple(int(v) for v in np.median(samples, axis=0))
        matrix = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
        registered = cv2.warpAffine(
            panel,
            matrix,
            (panel_width, image_height),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=background,
        )
        panels[label] = registered

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for label in args.canonical_order:
        cv2.imwrite(str(args.output_dir / f"{label}.png"), panels[label])
    if args.montage:
        args.montage.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(
            str(args.montage),
            np.concatenate([panels[label] for label in args.canonical_order], axis=1),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
