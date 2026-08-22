"""Extract visible default-human ear regions from the approved turnaround."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


# Panel-space context crops.  They intentionally retain adjacent hair/head so
# the root seam and occlusion policy remain visible during review.
REGIONS = {
    "front_viewer_left": (76, 350, 148, 458),
    "front_viewer_right": (350, 350, 432, 458),
    "right_visible": (222, 350, 305, 458),
    "back_viewer_left": (54, 350, 133, 458),
    "back_viewer_right": (326, 350, 414, 458),
    "left_visible": (270, 350, 352, 458),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--views-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = {}
    for label, bbox in REGIONS.items():
        view = label.split("_")[0]
        source = args.views_dir / f"{view}.png"
        with Image.open(source).convert("RGB") as image:
            crop = image.crop(bbox)
        output = args.output_dir / f"{label}.png"
        crop.save(output)
        records[label] = {
            "source": str(source.resolve()),
            "context_bbox_xyxy": list(bbox),
            "crop": str(output.resolve()),
        }
    report = {
        "schema": "assetsstudio_actor_v2_earpair_source_analysis_v1",
        "source_panel_size": [512, 1024],
        "observed_ear_height_px": [58, 68],
        "observed_actor_height_px": [660, 675],
        "ear_to_actor_height_ratio": [0.086, 0.103],
        "shape": "small rounded human ear with one broad inner bowl; low-frequency toy-like volume",
        "regions": records,
    }
    (args.output_dir / "reference_measurements.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
