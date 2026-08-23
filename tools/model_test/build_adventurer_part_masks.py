"""Build first-pass semantic masks from the flat-color adventurer reference."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def clean(mask: np.ndarray, foreground: np.ndarray) -> np.ndarray:
    mask = (mask & foreground).astype(np.uint8) * 255
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    keep = np.zeros_like(mask)
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] >= 80:
            keep[labels == index] = 255
    return keep


def save_rgba(rgb: np.ndarray, alpha: np.ndarray, path: Path) -> None:
    output = np.dstack([rgb, alpha]).astype(np.uint8)
    Image.fromarray(output, "RGBA").save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    source = np.array(Image.open(args.image).convert("RGBA"))
    rgb = source[:, :, :3]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = [hsv[:, :, index] for index in range(3)]
    alpha = source[:, :, 3] > 32
    height, width = alpha.shape
    yy, xx = np.mgrid[:height, :width]
    xn = xx / width
    yn = yy / height

    masks = {
        # Keep the dark hair clumps but explicitly reject the blue eye pixels
        # that share the same upper-head region in the generated reference.
        "hair_wig": (yn < 0.48) & (s > 35) & (v < 215) & ~((h >= 90) & (h <= 130)) & ~((yn > 0.36) & (np.abs(xn - 0.5) < 0.30)),
        "adventurer_jacket": (h >= 90) & (h <= 125) & (s > 55) & (yn > 0.48) & (yn < 0.78),
        "scarf": (h <= 16) & (s > 105) & (yn > 0.48) & (yn < 0.62),
        "belt_and_pouch": (h >= 5) & (h <= 25) & (s > 75) & (v < 205) & (yn > 0.66) & (yn < 0.83),
        "trousers": (h >= 25) & (h <= 60) & (s > 42) & (yn > 0.68) & (yn < 0.90),
        "boots": (h >= 5) & (h <= 25) & (s > 70) & (v < 205) & (yn > 0.80),
        "shirt_and_collar": (s < 105) & (v > 185) & (yn > 0.49) & (yn < 0.74) & (xn > 0.34) & (xn < 0.66),
        "gloves": (s < 95) & (v > 185) & (yn > 0.58) & (yn < 0.80) & ((xn < 0.43) | (xn > 0.57)),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, raw_mask in masks.items():
        mask = clean(raw_mask, alpha)
        mask_path = args.output_dir / f"{name}_mask.png"
        rgba_path = args.output_dir / f"{name}.png"
        Image.fromarray(mask, "L").save(mask_path)
        save_rgba(rgb, mask, rgba_path)
        manifest.append({"id": name, "mask": mask_path.name, "rgba": rgba_path.name, "coverage": int((mask > 0).sum())})

    # A contact sheet makes boundary errors visible before any Hunyuan call.
    previews = []
    for item in manifest:
        image = Image.open(args.output_dir / item["rgba"]).convert("RGBA")
        image.thumbnail((256, 256))
        tile = Image.new("RGBA", (280, 300), (40, 40, 40, 255))
        tile.alpha_composite(image, ((280 - image.width) // 2, 8))
        previews.append(tile)
    sheet = Image.new("RGBA", (280 * 4, 300 * 2), (20, 20, 20, 255))
    for index, tile in enumerate(previews):
        sheet.alpha_composite(tile, ((index % 4) * 280, (index // 4) * 300))
    sheet.convert("RGB").save(args.output_dir / "adventurer_part_masks_contact_sheet.jpg", quality=92)

    import json

    (args.output_dir / "manifest.json").write_text(json.dumps({"schema": "assetsstudio_part_masks_v1", "parts": manifest}, indent=2), encoding="utf-8")
    print(f"PART_MASKS_PASS parts={len(manifest)} output={args.output_dir}")


if __name__ == "__main__":
    main()
