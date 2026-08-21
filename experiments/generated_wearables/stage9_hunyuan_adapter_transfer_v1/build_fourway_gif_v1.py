from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DIRECTIONS = [
    ("front", "FRONT", (0, 0)),
    ("right", "RIGHT", (1, 0)),
    ("back", "BACK", (0, 1)),
    ("left", "LEFT", (1, 1)),
]


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--frames", type=int, default=71)
    parser.add_argument("--duration-ms", type=int, default=70)
    return parser.parse_args()


def main() -> None:
    args = cli()
    font = ImageFont.load_default()
    canvases: list[Image.Image] = []
    for frame_index in range(args.frames):
        images = {
            key: Image.open(args.input / f"{key}_{frame_index:02d}.png").convert("RGB")
            for key, _, _ in DIRECTIONS
        }
        width, height = images["front"].size
        canvas = Image.new("RGB", (width * 2, height * 2), (0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        for key, label, (column, row) in DIRECTIONS:
            x, y = column * width, row * height
            canvas.paste(images[key], (x, y))
            draw.rectangle((x + 5, y + 5, x + 50, y + 20), fill=(10, 15, 19))
            draw.text((x + 9, y + 7), label, fill=(225, 238, 247), font=font)
        draw.rectangle((width - 19, height * 2 - 20, width + 19, height * 2 - 5), fill=(10, 15, 19))
        draw.text((width - 14, height * 2 - 18), f"F{frame_index + 1:02d}", fill=(126, 226, 184), font=font)
        canvases.append(canvas)

    palette = canvases[0].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    gif_frames = [
        frame.quantize(palette=palette, dither=Image.Dither.NONE)
        for frame in canvases
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    gif_frames[0].save(
        args.output,
        save_all=True,
        append_images=gif_frames[1:],
        duration=args.duration_ms,
        loop=0,
        disposal=2,
        optimize=False,
    )
    print(f"GIF_PASS frames={len(gif_frames)} size={gif_frames[0].size} output={args.output}")


if __name__ == "__main__":
    main()
