"""Convert Actor four-direction renders into local pixel-review assets."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = (ROOT / "workspace").resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--size", type=int, default=64)
    parser.add_argument("--frame-count", type=int, default=8)
    parser.add_argument("--fps", type=float, default=8.0)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace an existing output directory; only permitted under workspace/.",
    )
    args = parser.parse_args()
    if args.size <= 0:
        raise SystemExit("size must be positive")
    if args.frame_count < 2 or args.fps <= 0.0:
        raise SystemExit("frame count must be at least two and fps must be positive")
    render_dir = args.render_dir.resolve()
    output_dir = args.output_dir.resolve()
    try:
        output_dir.relative_to(WORKSPACE)
    except ValueError as exc:
        raise SystemExit(f"output directory must stay under {WORKSPACE}: {output_dir}") from exc
    if output_dir.exists():
        if not args.replace:
            raise SystemExit(f"output directory exists; pass --replace to rebuild: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    directions = ("front", "right", "back", "left")
    frame_count = args.frame_count
    sheets: dict[str, str] = {}
    previews: dict[str, str] = {}
    frames: list[dict[str, object]] = []

    for direction in directions:
        sheet = Image.new("RGBA", (args.size * frame_count, args.size), (0, 0, 0, 0))
        gif_frames: list[Image.Image] = []
        for frame in range(frame_count):
            source = render_dir / f"{direction}_{frame:02d}.png"
            if not source.is_file():
                raise RuntimeError(f"missing render: {source}")
            image = Image.open(source).convert("RGBA")
            if image.size != (256, 256):
                raise RuntimeError(f"unexpected render size: {image.size}")
            pixel = image.resize((args.size, args.size), Image.Resampling.NEAREST)
            target_dir = output_dir / direction / f"frame_{frame:02d}"
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
                    "path": str(target.relative_to(output_dir)),
                    "alpha_bbox": list(bbox) if bbox else None,
                }
            )
        sheet_path = output_dir / f"{direction}_sheet.png"
        sheet.save(sheet_path)
        sheets[direction] = sheet_path.name
        preview_path = output_dir / f"{direction}.gif"
        gif_frames[0].save(
            preview_path,
            save_all=True,
            append_images=gif_frames[1:],
            duration=round(1000.0 / args.fps),
            loop=0,
            disposal=2,
        )
        previews[direction] = preview_path.name

    manifest = {
        "schema": "assetsstudio_actor_3to2_pixels_v1",
        "source_render_dir": str(render_dir),
        "canvas_px": [args.size, args.size],
        "directions": list(directions),
        "frame_count": frame_count,
        "fps": args.fps,
        "filter": "nearest",
        "transparent": True,
        "sprite_sheets": sheets,
        "preview_gifs": previews,
        "frames": frames,
        "status": "local_candidate",
        "storage_policy": "local",
        "purpose": "actor_3to2_visual_review",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"ACTOR_3TO2_PIXEL_PASS frames={len(frames)} output={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
