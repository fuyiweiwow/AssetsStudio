"""Render selected OverScore Proxy parts against the bundled proxy base model."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--parts", nargs="+")
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    parsed, _ = parser.parse_known_args(argv)
    parsed.blend = parsed.blend or Path(os.environ["OVERSCORE_PROXY_BLEND"])
    parsed.output_dir = parsed.output_dir or Path(os.environ["OVERSCORE_PARTS_OUTPUT_DIR"])
    parsed.parts = parsed.parts or os.environ["OVERSCORE_PROXY_PARTS"].split("|")
    return parsed


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))), Vector(
        (max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))
    )


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def main() -> None:
    options = args()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    selected = [bpy.data.objects.get(name) for name in options.parts]
    if any(obj is None for obj in selected):
        raise RuntimeError(f"missing requested Proxy part: {options.parts}")
    base = bpy.data.objects.get("Base Model")
    if base is None:
        raise RuntimeError("Proxy base model not found")
    for obj in bpy.context.scene.objects:
        obj.hide_render = obj not in {*selected, base}
    low, high = bounds(base)
    target = (low + high) * 0.5
    span = max((high - low).x, (high - low).y, (high - low).z)
    for label, location in {
        "front": (0.0, -span * 4.0, target.z),
        "three_quarter": (span * 3.5, -span * 3.5, target.z),
        "side": (span * 4.0, 0.0, target.z),
    }.items():
        camera_data = bpy.data.cameras.new(f"ProxyPartCamera_{label}")
        camera = bpy.data.objects.new(f"ProxyPartCamera_{label}", camera_data)
        bpy.context.scene.collection.objects.link(camera)
        camera.location = location
        camera.data.lens = 55
        look_at(camera, target)
        bpy.context.scene.camera = camera
        bpy.context.scene.render.filepath = str(options.output_dir / f"proxy_{'_'.join(options.parts)}_{label}.png")
        bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
        bpy.context.scene.render.resolution_x = 512
        bpy.context.scene.render.resolution_y = 512
        bpy.context.scene.render.resolution_percentage = 100
        bpy.context.scene.render.image_settings.file_format = "PNG"
        bpy.context.scene.world.color = (0.035, 0.035, 0.05)
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(camera, do_unlink=True)


if __name__ == "__main__":
    main()
