"""Build human-review GIFs from the four-view Actor clothing render pass."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


DIRECTIONS = ("front", "right", "back", "left")


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--duration", type=int, default=120)
    return parser.parse_args()


def frames(root: Path, direction: str) -> list[Image.Image]:
    result = []
    for index in range(8):
        source = root / f"{direction}_{index:02d}.png"
        if not source.exists():
            raise FileNotFoundError(source)
        with Image.open(source) as image:
            result.append(image.convert("RGBA"))
    return result


def write_gif(images: list[Image.Image], destination: Path, size: int, duration: int) -> None:
    resized = [image.resize((size, size), Image.Resampling.LANCZOS) for image in images]
    resized[0].save(
        destination,
        save_all=True,
        append_images=resized[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )


def write_contact_sheet(root: Path, destination: Path, size: int) -> None:
    cell = size // 2
    output = Image.new("RGB", (cell * 4, cell * 2), (17, 24, 39))
    draw = ImageDraw.Draw(output)
    for row, direction in enumerate(DIRECTIONS):
        images = frames(root, direction)
        for column in (0, 1):
            image = images[column * 4].convert("RGB").resize((cell, cell), Image.Resampling.LANCZOS)
            x = column * cell * 2
            y = row * 0
            # Keep a compact four-view still sheet: one frame per direction.
            x = (row % 4) * cell
            y = 0 if row < 2 else cell
            output.paste(image, (x, y))
            break
    labels = ("front", "right", "back", "left")
    for index, label in enumerate(labels):
        x = index * cell
        y = 0 if index < 2 else cell
        draw.rectangle((x + 4, y + 4, x + 64, y + 23), fill=(8, 11, 19))
        draw.text((x + 8, y + 7), label, fill=(255, 241, 168))
    output.save(destination)


def main() -> int:
    options = args()
    root = options.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    loaded = {direction: frames(root, direction) for direction in DIRECTIONS}
    write_gif(loaded["front"], root / "front_walk_8frames.gif", options.size, options.duration)
    write_gif(loaded["right"], root / "right_walk_8frames.gif", options.size, options.duration)
    write_gif(
        [image for direction in DIRECTIONS for image in loaded[direction]],
        root / "walk_4way_32frames.gif",
        options.size,
        options.duration,
    )
    # Use the first frame of each view for a quick still comparison.
    cell = options.size // 2
    sheet = Image.new("RGB", (cell * 4, cell), (17, 24, 39))
    draw = ImageDraw.Draw(sheet)
    for index, direction in enumerate(DIRECTIONS):
        image = loaded[direction][0].convert("RGB").resize((cell, cell), Image.Resampling.LANCZOS)
        sheet.paste(image, (index * cell, 0))
        draw.rectangle((index * cell + 4, 4, index * cell + 64, 23), fill=(8, 11, 19))
        draw.text((index * cell + 8, 7), direction, fill=(255, 241, 168))
    sheet.save(root / "four_view_frame00_contact_sheet.png")
    print(f"CLOTHING_REVIEW_GIFS root={root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
