"""Build human-review GIFs from the four-view Actor clothing render pass."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw


DIRECTIONS = ("front", "right", "back", "left")


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--frame-count", type=int, default=8)
    parser.add_argument(
        "--directions",
        default=",".join(DIRECTIONS),
        help="comma-separated subset of front,right,back,left",
    )
    parser.add_argument(
        "--upper-body-crop",
        action="store_true",
        help="also write enlarged upper-body GIFs and contact sheets for seam review",
    )
    return parser.parse_args()


def frames(root: Path, direction: str, frame_count: int) -> list[Image.Image]:
    result = []
    for index in range(frame_count):
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


def write_direction_frame_sheet(
    images: list[Image.Image], destination: Path, size: int, direction: str
) -> None:
    cell = size // 2
    columns = min(6, len(images))
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (cell * columns, cell * rows), (17, 24, 39))
    draw = ImageDraw.Draw(sheet)
    for index, source in enumerate(images):
        x = (index % columns) * cell
        y = (index // columns) * cell
        sheet.paste(source.convert("RGB").resize((cell, cell), Image.Resampling.LANCZOS), (x, y))
        draw.rectangle((x + 4, y + 4, x + 92, y + 23), fill=(8, 11, 19))
        draw.text((x + 8, y + 7), f"{direction} {index}", fill=(255, 241, 168))
    sheet.save(destination)


def upper_body_frames(images: list[Image.Image]) -> list[Image.Image]:
    cropped = []
    for image in images:
        width, height = image.size
        # The deterministic Actor camera keeps the shoulder/armhole region in
        # this central window for every walk frame and all four directions.
        box = (
            round(width * 0.14),
            round(height * 0.18),
            round(width * 0.86),
            round(height * 0.70),
        )
        cropped.append(image.crop(box))
    return cropped


def write_contact_sheet(root: Path, destination: Path, size: int, frame_count: int) -> None:
    cell = size // 2
    output = Image.new("RGB", (cell * 4, cell * 2), (17, 24, 39))
    draw = ImageDraw.Draw(output)
    for row, direction in enumerate(DIRECTIONS):
        images = frames(root, direction, frame_count)
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
    if options.frame_count < 2:
        raise ValueError("--frame-count must be at least two")
    directions = tuple(item.strip() for item in options.directions.split(",") if item.strip())
    if not directions or any(item not in DIRECTIONS for item in directions):
        raise ValueError(f"--directions must be a comma-separated subset of {DIRECTIONS}")
    loaded = {
        direction: frames(root, direction, options.frame_count)
        for direction in directions
    }
    frame_label = f"{options.frame_count}frames"
    for direction in directions:
        write_gif(loaded[direction], root / f"{direction}_walk_{frame_label}.gif", options.size, options.duration)
    for direction in directions:
        write_direction_frame_sheet(
            loaded[direction], root / f"{direction}_{frame_label}_contact_sheet.png", options.size, direction
        )
        if options.upper_body_crop:
            upper = upper_body_frames(loaded[direction])
            write_gif(
                upper,
                root / f"{direction}_upper_body_walk_{frame_label}.gif",
                options.size,
                options.duration,
            )
            write_direction_frame_sheet(
                upper,
                root / f"{direction}_upper_body_{frame_label}_contact_sheet.png",
                options.size,
                f"{direction} upper",
            )
    write_gif(
        [image for direction in directions for image in loaded[direction]],
        root / f"walk_{len(directions)}way_{options.frame_count * len(directions)}frames.gif",
        options.size,
        options.duration,
    )
    # Use the first frame of each view for a quick still comparison.
    cell = options.size // 2
    sheet = Image.new("RGB", (cell * len(directions), cell), (17, 24, 39))
    draw = ImageDraw.Draw(sheet)
    for index, direction in enumerate(directions):
        image = loaded[direction][0].convert("RGB").resize((cell, cell), Image.Resampling.LANCZOS)
        sheet.paste(image, (index * cell, 0))
        draw.rectangle((index * cell + 4, 4, index * cell + 64, 23), fill=(8, 11, 19))
        draw.text((index * cell + 8, 7), direction, fill=(255, 241, 168))
    sheet.save(root / f"{len(directions)}view_frame00_contact_sheet.png")
    print(f"CLOTHING_REVIEW_GIFS root={root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
