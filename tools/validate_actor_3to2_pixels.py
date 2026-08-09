"""Validate a local Actor 3-to-2 pixel-review package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


EXPECTED_DIRECTIONS = ["front", "right", "back", "left"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-dir", required=True, type=Path)
    return parser.parse_args()


def fail(message: str) -> None:
    raise SystemExit(f"ACTOR_3TO2_VALIDATE_FAIL {message}")


def main() -> int:
    asset_dir = parse_args().asset_dir.resolve()
    manifest_path = asset_dir / "manifest.json"
    if not manifest_path.is_file():
        fail(f"missing manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("schema") != "assetsstudio_actor_3to2_pixels_v1":
        fail("unexpected manifest schema")
    canvas = manifest.get("canvas_px")
    if not isinstance(canvas, list) or len(canvas) != 2 or canvas[0] != canvas[1] or int(canvas[0]) <= 0:
        fail(f"invalid square canvas: {canvas}")
    expected_size = (int(canvas[0]), int(canvas[1]))
    if manifest.get("directions") != EXPECTED_DIRECTIONS:
        fail(f"unexpected directions: {manifest.get('directions')}")
    expected_frame_count = int(manifest.get("frame_count", 0))
    if expected_frame_count < 2:
        fail(f"invalid frame count: {expected_frame_count}")
    if manifest.get("filter") != "nearest" or manifest.get("transparent") is not True:
        fail("runtime filter/transparent contract is invalid")

    frames = manifest.get("frames", [])
    expected_frames = len(EXPECTED_DIRECTIONS) * expected_frame_count
    if len(frames) != expected_frames:
        fail(f"manifest frame entries={len(frames)} expected={expected_frames}")

    for frame in frames:
        frame_path = asset_dir / str(frame["path"])
        if not frame_path.is_file():
            fail(f"missing frame: {frame_path}")
        with Image.open(frame_path) as image:
            if image.size != expected_size:
                fail(f"invalid frame size {image.size}: {frame_path}")
            if image.mode not in ("RGBA", "LA"):
                fail(f"frame is not transparent RGBA/LA: {frame_path}")

    for direction in EXPECTED_DIRECTIONS:
        sheet_name = str(manifest["sprite_sheets"][direction])
        sheet_path = asset_dir / sheet_name
        if not sheet_path.is_file():
            fail(f"missing sprite sheet: {sheet_path}")
        with Image.open(sheet_path) as image:
            if image.size != (expected_size[0] * expected_frame_count, expected_size[1]):
                fail(f"invalid sheet size {image.size}: {sheet_path}")
        preview_path = asset_dir / str(manifest["preview_gifs"][direction])
        if not preview_path.is_file():
            fail(f"missing preview GIF: {preview_path}")

    print(
        "ACTOR_3TO2_VALIDATE_PASS directions=%d frames=%d size=%d"
        % (len(EXPECTED_DIRECTIONS), expected_frames, expected_size[0])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
