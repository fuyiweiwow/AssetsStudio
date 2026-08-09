"""Validate the static, head-local random-face review output."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


STYLE_COUNT = 4
DIRECTIONS = ("front", "right", "back", "left")


def stable_style(seed: int) -> int:
    digest = hashlib.blake2b(str(seed).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % STYLE_COUNT


def read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise RuntimeError(f"missing JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def validate_pixel(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"missing pixel frame: {path}")
    image = Image.open(path).convert("RGBA")
    if image.size != (64, 64):
        raise RuntimeError(f"pixel frame has unexpected size {image.size}: {path}")
    if image.getchannel("A").getbbox() is None:
        raise RuntimeError(f"pixel frame is fully transparent: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--frame-count", type=int, default=2)
    args = parser.parse_args()
    if args.frame_count < 1:
        raise SystemExit("frame count must be positive")

    root = args.root.resolve()
    candidates = sorted(path for path in root.glob("seed_*") if path.is_dir())
    if not candidates:
        raise RuntimeError(f"no seed directories found: {root}")
    style_ids: set[int] = set()
    for candidate in candidates:
        metadata = read_json(candidate / "render" / "face_variant.json")
        if metadata.get("schema") != "assetslab_chibi_face_variant_v1":
            raise RuntimeError(f"unexpected face schema: {candidate}")
        seed = metadata.get("appearance_seed")
        style = metadata.get("style")
        if not isinstance(seed, int) or not isinstance(style, dict) or not isinstance(style.get("id"), int):
            raise RuntimeError(f"invalid seed/style metadata: {candidate}")
        style_id = style["id"]
        if not 0 <= style_id < STYLE_COUNT or style_id != stable_style(seed):
            raise RuntimeError(f"seed-to-style mapping is not reproducible: {candidate}")
        if metadata.get("ear_policy") != "locked_verified_attachment":
            raise RuntimeError(f"ear policy changed outside this face-only stage: {candidate}")
        if metadata.get("brow_policy") != "generated_head_bone_layer":
            raise RuntimeError(f"brow head-anchor policy missing: {candidate}")
        pixel_manifest = read_json(candidate / "pixel" / "manifest.json")
        if pixel_manifest.get("frame_count") != args.frame_count:
            raise RuntimeError(f"unexpected pixel frame count: {candidate}")
        for direction in DIRECTIONS:
            for frame in range(args.frame_count):
                validate_pixel(candidate / "pixel" / direction / f"frame_{frame:02d}" / "pixel.png")
        style_ids.add(style_id)

    if style_ids != set(range(STYLE_COUNT)):
        raise RuntimeError(f"review must cover all styles; got {sorted(style_ids)}")
    sheet = root / "face_randomization_contact_sheet.png"
    if not sheet.is_file():
        raise RuntimeError(f"missing contact sheet: {sheet}")
    print(
        "CHIBI_FACE_RANDOMIZATION_VALIDATE_PASS "
        f"seeds={len(candidates)} styles={len(style_ids)} frames={len(candidates) * len(DIRECTIONS) * args.frame_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
