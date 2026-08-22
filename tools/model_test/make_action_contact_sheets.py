"""Build per-view contact sheets from an Actor action review render set."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-dir", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=4)
    args = parser.parse_args()

    for view in ("front", "right", "back", "left"):
        paths = sorted((args.review_dir / "frames" / view).glob("frame_*.png"))
        if not paths:
            raise RuntimeError(f"No rendered frames found for {view}")
        with Image.open(paths[0]) as first:
            width, height = first.size
        rows = (len(paths) + args.columns - 1) // args.columns
        canvas = Image.new("RGB", (width * args.columns, height * rows), (14, 18, 28))
        draw = ImageDraw.Draw(canvas)
        for index, path in enumerate(paths):
            x = index % args.columns * width
            y = index // args.columns * height
            with Image.open(path) as image:
                canvas.paste(image.convert("RGB"), (x, y))
            draw.rectangle((x, y, x + 86, y + 24), fill=(14, 18, 28))
            draw.text((x + 8, y + 5), path.stem, fill=(240, 240, 245))
        canvas.save(args.review_dir / f"{view}_contact_sheet.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
