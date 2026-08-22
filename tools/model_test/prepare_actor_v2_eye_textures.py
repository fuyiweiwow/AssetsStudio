"""Derive Actor V2 blink textures by recoloring the V1 eyebrow to warm brown."""

from __future__ import annotations

import argparse
import colorsys
import json
from pathlib import Path

from PIL import Image


TEXTURES = (
    "eye_left.png",
    "eye_right.png",
    "eye_half_left.png",
    "eye_half_right.png",
    "eye_closed_left.png",
    "eye_closed_right.png",
)


def recolor_eyebrow(source: Path, target: Path) -> int:
    image = Image.open(source).convert("RGBA")
    pixels = image.load()
    changed = 0
    eyebrow_limit = round(image.height * 0.24)
    for y in range(eyebrow_limit):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha <= 4:
                continue
            _, _, value = colorsys.rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
            new_red, new_green, new_blue = colorsys.hsv_to_rgb(0.075, 0.62, max(0.12, value * 0.72))
            pixels[x, y] = (
                round(new_red * 255),
                round(new_green * 255),
                round(new_blue * 255),
                alpha,
            )
            changed += 1
    image.save(target)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for name in TEXTURES:
        source = args.source_dir / name
        target = args.output_dir / name
        outputs[name] = {
            "source": str(source.resolve()),
            "output": str(target.resolve()),
            "recolored_pixels": recolor_eyebrow(source, target),
        }
    manifest = {
        "schema": "assetsstudio_actor_v2_eye_textures_v1",
        "method": "preserve accepted V1 eye and blink shapes; deterministic HSV eyebrow recolor",
        "style_authority": "references/actor_v2/actor_v2_ratio_style_anchor_user_v1.png",
        "outputs": outputs,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
