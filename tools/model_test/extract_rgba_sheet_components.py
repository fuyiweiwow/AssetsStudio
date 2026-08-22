"""Extract left-to-right foreground components from an RGBA multiview sheet."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--names", nargs="+", required=True)
    parser.add_argument("--alpha-threshold", type=int, default=16)
    parser.add_argument("--minimum-area", type=int, default=500)
    args = parser.parse_args()

    with Image.open(args.input).convert("RGBA") as image:
        rgba = np.asarray(image)
    mask = (rgba[:, :, 3] > args.alpha_threshold).astype(np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    components = [
        index
        for index in range(1, count)
        if int(stats[index, cv2.CC_STAT_AREA]) >= args.minimum_area
    ]
    components.sort(key=lambda index: float(centroids[index][0]))
    if len(components) != len(args.names):
        raise RuntimeError(
            f"expected {len(args.names)} foreground components, found {len(components)}"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, index in zip(args.names, components, strict=True):
        x, y, width, height, area = map(int, stats[index])
        component = rgba[y : y + height, x : x + width].copy()
        component_labels = labels[y : y + height, x : x + width]
        component[:, :, 3] = np.where(component_labels == index, component[:, :, 3], 0)
        output = args.output_dir / f"{name}.png"
        Image.fromarray(component).save(output)
        print(
            f"RGBA_COMPONENT_PASS view={name} output={output.resolve()} "
            f"bbox={(x, y, width, height)} area={area}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
