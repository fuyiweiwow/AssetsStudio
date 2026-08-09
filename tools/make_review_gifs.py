"""Package numbered PNG review frames into small looping GIFs."""

from pathlib import Path
import sys

from PIL import Image, ImageOps, ImageDraw


def make_gif(folder: Path, direction: str, output: Path) -> None:
    frames = [Image.open(folder / f"{direction}_{index:02d}.png").convert("RGBA") for index in range(8)]
    frames[0].save(output, save_all=True, append_images=frames[1:], duration=140, loop=0, disposal=2)


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("milestones/shoes/cartoon_sneaker_v10")
    for direction in ("front", "right", "back", "left"):
        make_gif(folder, direction, folder / f"{direction}_walk_8frames.gif")
    frames = []
    for direction in ("front", "right", "back", "left"):
        frames.extend(Image.open(folder / f"{direction}_{index:02d}.png").convert("RGBA") for index in range(8))
    frames[0].save(folder / "walk_4way_32frames.gif", save_all=True, append_images=frames[1:], duration=110, loop=0, disposal=2)

    thumbs = []
    for direction in ("front", "right", "back", "left"):
        image = Image.open(folder / f"{direction}_00.png").convert("RGB").resize((256, 256))
        canvas = Image.new("RGB", (256, 282), "#18243a")
        canvas.paste(image, (0, 0))
        ImageDraw.Draw(canvas).text((10, 263), direction, fill="white")
        thumbs.append(canvas)
    sheet = Image.new("RGB", (512, 564), "#101827")
    for index, image in enumerate(thumbs):
        sheet.paste(image, ((index % 2) * 256, (index // 2) * 282))
    sheet.save(folder / "four_view_contact_sheet.png")


if __name__ == "__main__":
    main()
