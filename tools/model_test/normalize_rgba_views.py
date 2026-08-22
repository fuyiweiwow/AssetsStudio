"""Keep each RGBA view's main component and center all views at one shared scale."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def main_component(image: Image.Image, threshold: int) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA"))
    mask = (rgba[:, :, 3] > threshold).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        raise RuntimeError("RGBA input has no foreground component")
    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, width, height, _ = map(int, stats[index])
    crop = rgba[y : y + height, x : x + width].copy()
    crop_labels = labels[y : y + height, x : x + width]
    crop[:, :, 3] = np.where(crop_labels == index, crop[:, :, 3], 0)
    return Image.fromarray(crop)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--names", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--canvas", type=int, default=512)
    parser.add_argument("--fill-ratio", type=float, default=0.80)
    parser.add_argument("--alpha-threshold", type=int, default=16)
    args = parser.parse_args()
    if len(args.inputs) != len(args.names):
        parser.error("--inputs and --names must have the same length")

    components = []
    for path in args.inputs:
        with Image.open(path) as image:
            components.append(main_component(image, args.alpha_threshold))
    shared_max = max(max(image.size) for image in components)
    scale = args.canvas * args.fill_ratio / shared_max

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, source in zip(args.names, components, strict=True):
        size = tuple(max(1, round(value * scale)) for value in source.size)
        resized = source.resize(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (args.canvas, args.canvas), (255, 255, 255, 0))
        offset = ((args.canvas - size[0]) // 2, (args.canvas - size[1]) // 2)
        canvas.alpha_composite(resized, offset)
        output = args.output_dir / f"{name}.png"
        canvas.save(output)
        print(
            f"RGBA_NORMALIZE_PASS view={name} output={output.resolve()} "
            f"source_size={source.size} normalized_size={size} shared_scale={scale:.6f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
