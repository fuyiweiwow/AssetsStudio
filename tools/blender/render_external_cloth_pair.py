"""Render a clothing mesh and its source body from an external Blender file."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path)
    parser.add_argument("--cloth", default="lone_cloth")
    parser.add_argument("--body", default="lone_skin")
    parser.add_argument("--output-dir", type=Path)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    options, _ = parser.parse_known_args(argv)
    options.blend = options.blend or Path(os.environ["EXTERNAL_PAIR_BLEND"])
    options.output_dir = options.output_dir or Path(os.environ["EXTERNAL_PAIR_OUTPUT_DIR"])
    return options


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))), Vector(
        (max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))
    )


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def main() -> None:
    options = parse_args()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    cloth = bpy.data.objects.get(options.cloth)
    body = bpy.data.objects.get(options.body)
    if cloth is None or body is None:
        raise RuntimeError(f"missing cloth/body: {options.cloth}, {options.body}")
    for obj in bpy.context.scene.objects:
        obj.hide_render = obj not in {cloth, body}
    low, high = bounds(body)
    target = (low + high) * 0.5
    span = max((high - low).x, (high - low).y, (high - low).z)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.035, 0.035, 0.05)
    for label, location in {
        "front": (0.0, -span * 4.0, target.z),
        "three_quarter": (span * 3.5, -span * 3.5, target.z),
        "side": (span * 4.0, 0.0, target.z),
    }.items():
        camera_data = bpy.data.cameras.new(f"ExternalPairCamera_{label}")
        camera = bpy.data.objects.new(f"ExternalPairCamera_{label}", camera_data)
        scene.collection.objects.link(camera)
        camera.location = location
        camera.data.lens = 55
        look_at(camera, target)
        scene.camera = camera
        scene.render.filepath = str(options.output_dir / f"external_pair_{label}.png")
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(camera, do_unlink=True)


if __name__ == "__main__":
    main()
