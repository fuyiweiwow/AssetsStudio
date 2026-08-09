"""Render a close-up human-review sheet for an Actor footwear candidate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from render_eye_assembly_blink_walk import configure_lighting  # noqa: E402
from render_procedural_anime_eye_on_accurig import make_camera  # noqa: E402


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--resolution", type=int, default=512)
    parser.add_argument("--frame", type=int, default=1)
    return parser.parse_args(argv)


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    scene = bpy.context.scene
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    target = Vector((0.0, 0.0, 0.105))
    configure_lighting(scene, target, "soft_flat")
    scene.view_settings.exposure = 0.35
    scene.render.resolution_x = options.resolution
    scene.render.resolution_y = options.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.frame_set(options.frame)
    directions = {
        "front": (0.0, -2.5),
        "right": (2.5, 0.0),
        "back": (0.0, 2.5),
        "left": (-2.5, 0.0),
    }
    for name, (x, y) in directions.items():
        camera = make_camera(scene, target, f"FootwearCloseup_{name}", (x, y, target.z), 0.55)
        scene.camera = camera
        scene.render.filepath = str(output / f"{name}_frame{options.frame:03d}.png")
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(camera, do_unlink=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
