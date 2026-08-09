"""Validate the deterministic AssetsStudio eight-frame eye/walk review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


DIRECTIONS = ("front", "right", "back", "left")
EXPECTED_STATES = ("open", "half", "closed", "half", "open", "open", "open", "open")
EXPECTED_AMOUNTS = (0.0, 0.5, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0)
EXPECTED_BODY_FRAMES = (1, 11, 21, 31, 41, 51, 61, 71)


def cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    options = cli_args()
    render_dir = options.render_dir.resolve()
    manifest = json.loads((render_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "assetsstudio_eye_assembly_blink_walk_v1":
        raise RuntimeError("unexpected blink walk manifest schema")
    if tuple(manifest.get("directions", [])) != DIRECTIONS:
        raise RuntimeError(f"unexpected directions: {manifest.get('directions')}")
    if tuple(manifest.get("body_sample_frames", [])) != EXPECTED_BODY_FRAMES:
        raise RuntimeError(f"body sample changed: {manifest.get('body_sample_frames')}")
    if tuple(manifest.get("eye_state_by_frame", [])) != EXPECTED_STATES:
        raise RuntimeError(f"eye schedule changed: {manifest.get('eye_state_by_frame')}")
    if tuple(manifest.get("blink_amount_by_frame", [])) != EXPECTED_AMOUNTS:
        raise RuntimeError(f"blink amount curve changed: {manifest.get('blink_amount_by_frame')}")
    frames = manifest.get("frames", [])
    if len(frames) != 32:
        raise RuntimeError(f"expected 32 rendered frames, found {len(frames)}")
    for item in frames:
        path = render_dir / item["path"]
        if not path.is_file():
            raise RuntimeError(f"missing rendered frame: {path}")
        with Image.open(path) as image:
            if image.size != (256, 256):
                raise RuntimeError(f"unexpected frame size {image.size}: {path}")
    print("EYE_ASSEMBLY_BLINK_WALK_VALIDATION_PASS directions=4 frames=8 body_sampling=unchanged eye_schedule=deterministic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
