from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent


def resolve_blender_tools() -> Path:
    for parent in (ROOT, *ROOT.parents):
        candidate = parent / "tools" / "blender"
        if (candidate / "render_accurig_chibi_walk_test.py").exists():
            return candidate
    fallback = Path(r"D:\Apps\CodeXApp\Tests\AssetsLab\tools\blender")
    if fallback.exists():
        return fallback
    raise FileNotFoundError("AssetsLab tools/blender directory was not found")


TOOLS = resolve_blender_tools()
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from render_accurig_chibi_walk_test import configure_soft_toon_lighting  # noqa: E402


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--frame-count", type=int, default=8)
    parser.add_argument("--target-z", type=float, default=1.30)
    parser.add_argument("--ortho-scale", type=float, default=1.22)
    return parser.parse_args(argv)


def camera(scene: bpy.types.Scene, name: str, target: Vector, location: Vector, ortho_scale: float) -> bpy.types.Object:
    data = bpy.data.cameras.new(f"{name}Data")
    data.type = "ORTHO"
    data.ortho_scale = ortho_scale
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (target - location).to_track_quat("-Z", "Y").to_euler()
    return obj


def main() -> int:
    options = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        raise RuntimeError(f"expected one armature, found {[obj.name for obj in armatures]}")
    armature = armatures[0]
    action = armature.animation_data.action if armature.animation_data else None
    if action is None:
        raise RuntimeError("Actor has no active action")

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = True
    scene.view_settings.look = "AgX - Medium High Contrast"
    configure_soft_toon_lighting(scene)

    target = Vector((0.0, -0.01, options.target_z))
    cameras = {
        "front": camera(scene, "UpperFront", target, Vector((0.0, -8.0, options.target_z)), options.ortho_scale),
        "right": camera(scene, "UpperRight", target, Vector((8.0, 0.0, options.target_z)), options.ortho_scale),
        "back": camera(scene, "UpperBack", target, Vector((0.0, 8.0, options.target_z)), options.ortho_scale),
        "left": camera(scene, "UpperLeft", target, Vector((-8.0, 0.0, options.target_z)), options.ortho_scale),
    }
    start, end = action.frame_range
    frames = [
        round(start + (end - start) * index / (options.frame_count - 1))
        for index in range(options.frame_count)
    ]
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for direction, active_camera in cameras.items():
        scene.camera = active_camera
        for index, frame in enumerate(frames):
            scene.frame_set(frame)
            scene.render.filepath = str(output / f"{direction}_{index:02d}.png")
            bpy.ops.render.render(write_still=True)
    manifest = {
        "schema": "upperbody_transition_review_v1",
        "input_blend": str(options.input_blend.resolve()),
        "action": action.name,
        "frames": frames,
        "directions": list(cameras),
        "camera_target": list(target),
        "ortho_scale": options.ortho_scale,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"UPPERBODY_TRANSITION_REVIEW_PASS output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
