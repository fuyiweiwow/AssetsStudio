"""Extract a clean, largest-component hair wig from four approved RGB views."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


VIEWS = ("front", "right", "back", "left")


def largest_component(mask: np.ndarray) -> tuple[np.ndarray, int]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    candidates = [(index, int(stats[index, cv2.CC_STAT_AREA])) for index in range(1, count)]
    if not candidates:
        raise RuntimeError("No hair component detected")
    selected, area = max(candidates, key=lambda item: item[1])
    return labels == selected, area


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--views-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rgba_dir = args.output_dir / "rgba"
    mask_dir = args.output_dir / "masks"
    rgba_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)
    records = {}

    for view in VIEWS:
        source = args.views_dir / f"{view}.png"
        rgb = np.array(Image.open(source).convert("RGB"))
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        h, s, v = [hsv[:, :, index] for index in range(3)]
        yy = np.arange(rgb.shape[0])[:, None] / rgb.shape[0]
        # The approved hair ends just above the collar/backpack straps.  This
        # hard source boundary prevents touching brown leather from joining the
        # wig component in side/back views.
        raw = (yy < 0.468) & (h <= 28) & (s >= 28) & (v <= 205)
        raw = cv2.morphologyEx(raw.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        raw = cv2.morphologyEx(raw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        mask, area = largest_component(raw)
        alpha = mask.astype(np.uint8) * 255
        ys, xs = np.where(mask)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]
        isolated_rgb = rgb.copy()
        isolated_rgb[~mask] = 255
        output_rgba = np.dstack([isolated_rgb, alpha]).astype(np.uint8)
        Image.fromarray(output_rgba, "RGBA").save(rgba_dir / f"{view}.png")
        Image.fromarray(alpha, "L").save(mask_dir / f"{view}.png")
        records[view] = {
            "source": str(source.resolve()),
            "rgba": str((rgba_dir / f"{view}.png").resolve()),
            "mask": str((mask_dir / f"{view}.png").resolve()),
            "area_px": area,
            "bbox_xyxy": bbox,
            "bbox_size": [bbox[2] - bbox[0], bbox[3] - bbox[1]],
        }

    front_height = records["front"]["bbox_size"][1]
    back_height = records["back"]["bbox_size"][1]
    front_width = records["front"]["bbox_size"][0]
    back_width = records["back"]["bbox_size"][0]
    source_height = 1024
    side_heights = [records["right"]["bbox_size"][1], records["left"]["bbox_size"][1]]
    gates = {
        "one_component_per_view": True,
        "front_back_top_drift_lte_2pct": abs(
            records["front"]["bbox_xyxy"][1] - records["back"]["bbox_xyxy"][1]
        ) / source_height <= 0.02,
        "front_back_width_drift_lte_12pct": abs(front_width - back_width) / max(front_width, back_width) <= 0.12,
        "back_hair_intentionally_longer": back_height > front_height,
        "side_height_drift_lte_8pct": abs(side_heights[0] - side_heights[1]) / max(side_heights) <= 0.08,
    }
    report = {
        "schema": "assetsstudio_actor_v2_hair_source_analysis_v1",
        "status": "pass" if all(gates.values()) else "review",
        "method": "brown HSV range, upper-body crop, morphology, largest connected component",
        "views": records,
        "gates": gates,
    }
    (args.output_dir / "source_analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"ACTOR_V2_HAIR_SOURCE_{report['status'].upper()} output={args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
