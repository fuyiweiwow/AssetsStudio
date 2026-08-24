"""Remove an image background with Hunyuan3D's official rembg wrapper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from hunyuan_environment import discover_code_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-root", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    args.code_root = discover_code_root(args.code_root)
    print(f"HUNYUAN_ENV code_root={args.code_root}", flush=True)

    single_mode = args.input is not None or args.output is not None
    directory_mode = args.input_dir is not None or args.output_dir is not None
    if single_mode == directory_mode:
        parser.error("provide either --input/--output or --input-dir/--output-dir")
    if single_mode and (args.input is None or args.output is None):
        parser.error("single mode requires both --input and --output")
    if directory_mode and (args.input_dir is None or args.output_dir is None):
        parser.error("directory mode requires both --input-dir and --output-dir")

    sys.path.insert(0, str(args.code_root.resolve()))
    from hy3dgen.rembg import BackgroundRemover

    remover = BackgroundRemover()
    if single_mode:
        pairs = [(args.input, args.output)]
    else:
        inputs = sorted(args.input_dir.glob("*.png"))
        if not inputs:
            raise RuntimeError(f"no PNG inputs found: {args.input_dir}")
        pairs = [(input_path, args.output_dir / input_path.name) for input_path in inputs]
    for input_path, output_path in pairs:
        with Image.open(input_path) as source:
            rgba = remover(source.convert("RGB")).convert("RGBA")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rgba.save(output_path)
        alpha_bbox = rgba.getchannel("A").getbbox()
        if alpha_bbox is None:
            raise RuntimeError(f"background removal produced an empty foreground: {input_path}")
        print(
            f"HUNYUAN_REMBG_PASS input={input_path.resolve()} "
            f"output={output_path.resolve()} alpha_bbox={alpha_bbox}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
