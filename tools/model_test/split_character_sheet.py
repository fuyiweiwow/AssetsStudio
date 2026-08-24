"""Split an equal-width character sheet into independent view images."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--names", nargs="+", default=("front", "right", "back"))
    parser.add_argument("--panel-width", type=int)
    parser.add_argument("--starts", nargs="+", type=int)
    parser.add_argument(
        "--mirror",
        action="append",
        default=[],
        metavar="SOURCE=TARGET",
        help="Also save a horizontally mirrored view, for example right=left.",
    )
    args = parser.parse_args()

    with Image.open(args.input).convert("RGBA") as image:
        width, height = image.size
        panel_count = len(args.names)
        if args.panel_width is not None:
            if args.starts is None or len(args.starts) != panel_count:
                raise ValueError("--panel-width requires one --starts value per panel name")
            panel_width = args.panel_width
            starts = args.starts
        else:
            if width % panel_count:
                raise ValueError(f"sheet width must be divisible by panel count {panel_count}, got {width}")
            panel_width = width // panel_count
            starts = [index * panel_width for index in range(panel_count)]
        args.output_dir.mkdir(parents=True, exist_ok=True)
        panels: dict[str, Image.Image] = {}
        for index, name in enumerate(args.names):
            left = starts[index]
            panel = image.crop((left, 0, left + panel_width, height))
            panels[name] = panel
            output = args.output_dir / f"{name}.png"
            panel.save(output)
            print(f"SPLIT_PASS view={name} output={output.resolve()} size={panel.size}")
        for mapping in args.mirror:
            try:
                source_name, target_name = mapping.split("=", 1)
                source = panels[source_name]
            except (ValueError, KeyError) as error:
                raise ValueError(
                    f"invalid --mirror {mapping!r}; expected an existing SOURCE=TARGET"
                ) from error
            mirrored = ImageOps.mirror(source)
            output = args.output_dir / f"{target_name}.png"
            mirrored.save(output)
            print(
                f"MIRROR_PASS source={source_name} view={target_name} "
                f"output={output.resolve()} size={mirrored.size}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
