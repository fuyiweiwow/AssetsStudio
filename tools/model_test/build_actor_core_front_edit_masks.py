#!/usr/bin/env python3
"""Build deterministic local-edit masks for the compact front A/B experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def draw_rounded_regions(
    regions: list[tuple[int, int, int, int]],
    output: Path,
) -> None:
    image = Image.new("L", (768, 768), 0)
    draw = ImageDraw.Draw(image)
    for region in regions:
        radius = min(region[2] - region[0], region[3] - region[1]) // 3
        draw.rounded_rectangle(region, radius=radius, fill=255)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    ear_regions = [
        (202, 188, 272, 302),
        (496, 188, 566, 302),
    ]
    hand_regions = [
        (143, 370, 214, 450),
        (554, 370, 625, 450),
    ]
    cleanup_regions = [
        *ear_regions,
        *hand_regions,
    ]
    face_regions = [(238, 135, 530, 310)]
    ears = args.output_dir / "a_remove_ears_mask_v1.png"
    hands = args.output_dir / "a_restore_hands_mask_v1.png"
    cleanup = args.output_dir / "a_cleanup_ears_hands_mask_v1.png"
    face = args.output_dir / "b_remove_eye_brow_mask_v1.png"
    draw_rounded_regions(ear_regions, ears)
    draw_rounded_regions(hand_regions, hands)
    draw_rounded_regions(cleanup_regions, cleanup)
    draw_rounded_regions(face_regions, face)

    report = {
        "schema": "assetsstudio_actor_core_front_edit_masks_v1",
        "status": "candidate_input_only",
        "canvas": [768, 768],
        "ear_removal": {
            "path": str(ears),
            "regions": ear_regions,
            "intent": "remove ears while preserving the original hand terminals",
        },
        "hand_restore": {
            "path": str(hands),
            "regions": hand_regions,
            "intent": "restore the accepted compact terminals after isolated ear editing",
        },
        "cleanup": {
            "path": str(cleanup),
            "regions": cleanup_regions,
            "intent": "remove ears and reshape spherical hand terminals",
        },
        "face_removal": {
            "path": str(face),
            "regions": face_regions,
            "intent": "remove eyes, eye lines and eyebrows without touching silhouette",
        },
    }
    report_path = args.output_dir / "front_edit_masks_v1.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"ear_mask={ears.resolve()}")
    print(f"hand_mask={hands.resolve()}")
    print(f"cleanup_mask={cleanup.resolve()}")
    print(f"face_mask={face.resolve()}")
    print(f"report={report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
