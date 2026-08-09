"""Build a phone-readable contact sheet for rendered chibi face-style seeds."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


DISPLAY_SIZE = 128
LABEL_HEIGHT = 34


def load_frame(path: Path) -> Image.Image:
    if not path.is_file():
        raise RuntimeError(f"missing pixel preview frame: {path}")
    image = Image.open(path).convert("RGBA")
    if image.size != (64, 64):
        raise RuntimeError(f"expected 64px source frame, got {image.size}: {path}")
    return image.resize((DISPLAY_SIZE, DISPLAY_SIZE), Image.Resampling.NEAREST)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    records: list[dict[str, object]] = []
    previews: list[tuple[Image.Image, Image.Image]] = []

    for candidate in sorted(path for path in root.glob("seed_*") if path.is_dir()):
        metadata_path = candidate / "render" / "face_variant.json"
        if not metadata_path.is_file():
            raise RuntimeError(f"missing rendered face metadata: {metadata_path}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        style = metadata.get("style", {})
        seed = metadata.get("appearance_seed")
        if not isinstance(seed, int) or not isinstance(style, dict) or not isinstance(style.get("id"), int):
            raise RuntimeError(f"invalid face metadata: {metadata_path}")
        front_path = candidate / "pixel" / "front" / "frame_00" / "pixel.png"
        right_path = candidate / "pixel" / "right" / "frame_00" / "pixel.png"
        previews.append((load_frame(front_path), load_frame(right_path)))
        records.append(
            {
                "seed": seed,
                "style_id": style["id"],
                "style_name": style.get("name"),
                "front": str(front_path.relative_to(root)),
                "right": str(right_path.relative_to(root)),
                "ear_policy": metadata.get("ear_policy"),
            }
        )

    if not records:
        raise RuntimeError(f"no seed_* directories found in {root}")
    ordered = sorted(zip(records, previews), key=lambda entry: int(entry[0]["style_id"]))
    records = [entry[0] for entry in ordered]
    previews = [entry[1] for entry in ordered]
    style_ids = [record["style_id"] for record in records]
    if len(set(style_ids)) != len(style_ids):
        raise RuntimeError("preview set must not contain duplicate face-style ids")

    width = len(records) * DISPLAY_SIZE * 2
    height = DISPLAY_SIZE + LABEL_HEIGHT
    sheet = Image.new("RGBA", (width, height), (33, 22, 25, 255))
    draw = ImageDraw.Draw(sheet)
    for index, (record, (front, right)) in enumerate(zip(records, previews)):
        x = index * DISPLAY_SIZE * 2
        sheet.alpha_composite(front, (x, 0))
        sheet.alpha_composite(right, (x + DISPLAY_SIZE, 0))
        draw.text((x + 4, DISPLAY_SIZE + 3), f"{record['style_name']} / {record['seed']}", fill=(246, 230, 220, 255))
        draw.text((x + 4, DISPLAY_SIZE + 17), "front              side", fill=(198, 171, 160, 255))

    output = root / "face_randomization_contact_sheet.png"
    sheet.save(output)
    manifest = {
        "schema": "assetslab_chibi_face_randomization_preview_v1",
        "source": "render_accurig_chibi_walk_test.py",
        "canvas_px": [width, height],
        "frame_policy": "frame_00 only; static face-style review",
        "records": records,
    }
    (root / "face_randomization_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"CHIBI_FACE_RANDOMIZATION_PREVIEW_PASS styles={len(records)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
