"""Downsample AccuRIG walk-test renders to nearest-neighbour pixel frames."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--size", type=int, default=64)
    parser.add_argument("--frame-count", type=int, default=8)
    parser.add_argument("--fps", type=float, default=8.0)
    args = parser.parse_args()
    if args.size <= 0:
        raise SystemExit("size must be positive")
    if args.frame_count < 2 or args.fps <= 0.0:
        raise SystemExit("frame count must be at least two and fps must be positive")
    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    directions = ("front", "right", "back", "left")
    frame_count = args.frame_count
    sheets: dict[str, str] = {}
    frames: list[dict[str, object]] = []

    for direction in directions:
        sheet = Image.new("RGBA", (args.size * frame_count, args.size), (0, 0, 0, 0))
        gif_frames: list[Image.Image] = []
        for frame in range(frame_count):
            source = args.render_dir / f"{direction}_{frame:02d}.png"
            if not source.is_file():
                raise RuntimeError(f"missing render: {source}")
            image = Image.open(source).convert("RGBA")
            if image.size != (256, 256):
                raise RuntimeError(f"unexpected render size: {image.size}")
            pixel = image.resize((args.size, args.size), Image.Resampling.NEAREST)
            target_dir = args.output_dir / direction / f"frame_{frame:02d}"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / "pixel.png"
            pixel.save(target)
            sheet.paste(pixel, (frame * args.size, 0), pixel)
            gif_frames.append(pixel.copy())
            bbox = pixel.getchannel("A").getbbox()
            frames.append(
                {
                    "direction": direction,
                    "frame": frame,
                    "path": str(target.relative_to(args.output_dir)),
                    "alpha_bbox": list(bbox) if bbox else None,
                }
            )
        sheet_path = args.output_dir / f"{direction}_sheet.png"
        sheet.save(sheet_path)
        sheets[direction] = sheet_path.name
        gif_frames[0].save(
            args.output_dir / f"{direction}.gif",
            save_all=True,
            append_images=gif_frames[1:],
            duration=round(1000.0 / args.fps),
            loop=0,
            disposal=2,
        )

    manifest = {
        "schema": "assetslab_accurig_chibi_walk_pixel_test_v1",
        "source_render_dir": str(args.render_dir),
        "canvas_px": [args.size, args.size],
        "directions": list(directions),
        "frame_count": frame_count,
        "sheets": sheets,
        "frames": frames,
        "runtime_ready": False,
        "purpose": "binding_and_motion_diagnostic_only",
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"ACCURIG_WALK_PIXEL_PASS frames={len(frames)} output={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
