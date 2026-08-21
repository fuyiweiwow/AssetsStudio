"""Clip official-rembg Actor views to previously validated silhouette masks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


VIEWS = ("front", "right", "back", "left")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rgb-dir", type=Path, required=True)
    parser.add_argument("--official-rgba-dir", type=Path, required=True)
    parser.add_argument("--mask-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mask-dilate-px", type=int, default=2)
    return parser.parse_args()


def alpha_bbox(alpha: np.ndarray) -> list[int] | None:
    points = cv2.findNonZero((alpha > 0).astype(np.uint8))
    if points is None:
        return None
    x, y, width, height = cv2.boundingRect(points)
    return [int(x), int(y), int(x + width), int(y + height)]


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.mask_dilate_px < 0:
        raise ValueError("--mask-dilate-px must be non-negative")
    kernel_size = args.mask_dilate_px * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    records: list[dict[str, object]] = []

    for view in VIEWS:
        rgb = np.array(Image.open(args.rgb_dir / f"{view}.png").convert("RGB"))
        official = np.array(
            Image.open(args.official_rgba_dir / f"{view}_rgba.png").convert("RGBA")
        )
        validated = cv2.imread(
            str(args.mask_dir / f"{view}_mask.png"), cv2.IMREAD_GRAYSCALE
        )
        if validated is None:
            raise FileNotFoundError(args.mask_dir / f"{view}_mask.png")
        allowed = cv2.dilate((validated > 0).astype(np.uint8), kernel)
        alpha = np.where(allowed > 0, official[:, :, 3], 0).astype(np.uint8)
        rgba = np.dstack((rgb, alpha))
        output = args.output_dir / f"{view}_rgba.png"
        Image.fromarray(rgba, "RGBA").save(output)
        records.append(
            {
                "view": view,
                "output": str(output.resolve()),
                "official_alpha_pixels": int(np.count_nonzero(official[:, :, 3])),
                "clean_alpha_pixels": int(np.count_nonzero(alpha)),
                "removed_alpha_pixels": int(
                    np.count_nonzero(official[:, :, 3]) - np.count_nonzero(alpha)
                ),
                "alpha_bbox": alpha_bbox(alpha),
            }
        )

    report = {
        "schema": "assetsstudio_validated_actor_rgba_v1",
        "mask_dilate_px": args.mask_dilate_px,
        "view_order": ["front", "left", "back", "right"],
        "records": records,
        "status": "pass",
    }
    report_path = args.output_dir / "manifest.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"VALIDATED_RGBA_PASS manifest={report_path.resolve()}")


if __name__ == "__main__":
    main()
