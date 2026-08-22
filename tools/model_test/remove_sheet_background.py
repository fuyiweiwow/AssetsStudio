"""Remove a flat sheet background from character panels using border flood fill."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


VIEWS = ("front", "right", "back", "left")


def remove_background(source: Path, target: Path, threshold: int, largest_only: bool) -> None:
    rgb = np.array(Image.open(source).convert("RGB"))
    height, width = rgb.shape[:2]
    seed = rgb[0, 0].astype(np.int16)
    distance = np.linalg.norm(rgb.astype(np.int16) - seed, axis=2)
    candidate = (distance <= threshold).astype(np.uint8)
    flood = np.zeros((height + 2, width + 2), dtype=np.uint8)
    background = np.zeros((height, width), dtype=np.uint8)
    for x, y in [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]:
        if candidate[y, x]:
            flood.fill(0)
            cv2.floodFill(candidate, flood, (x, y), 2, loDiff=0, upDiff=0, flags=4)
    background = candidate == 2
    foreground = ~background
    if largest_only:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            foreground.astype(np.uint8), 8
        )
        candidates = [
            (index, int(stats[index, cv2.CC_STAT_AREA]))
            for index in range(1, count)
        ]
        if not candidates:
            raise RuntimeError(f"No foreground component found in {source}")
        selected, _ = max(candidates, key=lambda item: item[1])
        foreground = labels == selected
        background = ~foreground
    isolated_rgb = rgb.copy()
    isolated_rgb[background] = 255
    rgba = np.dstack([isolated_rgb, np.where(background, 0, 255).astype(np.uint8)])
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(target)
    print(f"ALPHA_PASS input={source} output={target} foreground={int((~background).sum())}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threshold", type=int, default=24)
    parser.add_argument(
        "--largest-component",
        action="store_true",
        help="discard disconnected neighbouring-panel fragments after background removal",
    )
    args = parser.parse_args()
    for name in VIEWS:
        remove_background(
            args.input_dir / f"{name}.png",
            args.output_dir / f"{name}.png",
            args.threshold,
            args.largest_component,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
