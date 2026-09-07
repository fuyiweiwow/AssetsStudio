#!/usr/bin/env python3
"""Build deterministic local-edit masks for the relaxed-pose style gate.

These masks are specific to the 768 px seed-20260985 diagnostic candidate.
They isolate semantic cleanup from the already accepted-for-review silhouette:
first remove the ears, then remove the shorts-like hip seam.  The output stays
in the ignored local workspace and is never an asset-library registration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


CANVAS = (768, 768)


def save_mask(path: Path, draw_regions) -> None:
    image = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(image)
    draw_regions(draw)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--source",
        type=Path,
        help="Optional 768 px candidate used to build an earless inpaint guide",
    )
    args = parser.parse_args()

    ear_boxes = [(166, 282, 246, 405), (522, 282, 602, 405)]
    hip_box = (278, 548, 490, 686)

    ear_path = args.output_dir / "seed20260985_remove_ears_mask.png"
    hip_path = args.output_dir / "seed20260985_smooth_hip_mask.png"

    save_mask(
        ear_path,
        lambda draw: [draw.ellipse(box, fill=255) for box in ear_boxes],
    )
    save_mask(
        hip_path,
        lambda draw: draw.rounded_rectangle(hip_box, radius=42, fill=255),
    )

    prepaint_path = None
    if args.source:
        source = Image.open(args.source).convert("RGB")
        if source.size != CANVAS:
            raise ValueError(f"Expected {CANVAS}, got {source.size}")

        # This is an inpaint guide, never the delivered candidate.  Remove only
        # the parts of the ears outside a broad fitted cranium ellipse and let
        # FLUX reconstruct the final pixels inside the same local mask.
        head_ellipse = (190, 45, 578, 470)
        keep = Image.new("L", CANVAS, 0)
        ImageDraw.Draw(keep).ellipse(head_ellipse, fill=255)
        ears = Image.open(ear_path).convert("L")
        replace = ears.copy()
        ear_pixels = ears.load()
        keep_pixels = keep.load()

        reconstruction = Image.new("RGB", CANVAS)
        source_pixels = source.load()
        reconstruction_pixels = reconstruction.load()
        for y in range(CANVAS[1]):
            left_sample = source_pixels[118, y]
            right_sample = source_pixels[650, y]
            for x in range(CANVAS[0]):
                mix = x / (CANVAS[0] - 1)
                background_color = tuple(
                    round(left_sample[channel] * (1.0 - mix) + right_sample[channel] * mix)
                    for channel in range(3)
                )
                if ear_pixels[x, y] and keep_pixels[x, y]:
                    # Continue the cheek/cranium material through the portion
                    # of the fitted head ellipse previously occupied by an ear.
                    reconstruction_pixels[x, y] = source_pixels[CANVAS[0] // 2, y]
                else:
                    reconstruction_pixels[x, y] = background_color

        alpha = replace.filter(ImageFilter.GaussianBlur(radius=1.5))
        prepaint = Image.composite(reconstruction, source, alpha)
        prepaint_path = args.output_dir / "seed20260985_earless_inpaint_guide.png"
        prepaint.save(prepaint_path)

    report = {
        "schema": "assetsstudio_actor_core_style_gate_masks_v1",
        "status": "diagnostic_candidate_only",
        "canvas": list(CANVAS),
        "source_candidate": "relaxed_seed20260985.png",
        "ear_cleanup": {"path": str(ear_path), "regions": ear_boxes},
        "hip_cleanup": {"path": str(hip_path), "regions": [hip_box]},
        "earless_inpaint_guide": str(prepaint_path) if prepaint_path else None,
    }
    report_path = args.output_dir / "style_gate_masks_v1.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"ear_mask={ear_path.resolve()}")
    print(f"hip_mask={hip_path.resolve()}")
    if prepaint_path:
        print(f"earless_inpaint_guide={prepaint_path.resolve()}")
    print(f"report={report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
