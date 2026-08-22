"""Render a declared Actor frame as four orthographic head-slot close-ups."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


DIRECTIONS = {
    "front": (0.0, -12.0),
    "right": (12.0, 0.0),
    "back": (0.0, 12.0),
    "left": (-12.0, 0.0),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--frame", type=int, default=1)
    parser.add_argument("--resolution", type=int, default=768)
    parser.add_argument("--ortho-scale", type=float, default=1.45)
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw)

    bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))
    scene = bpy.context.scene
    scene.frame_set(args.frame)
    bpy.context.view_layer.update()
    armature = next(obj for obj in scene.objects if obj.type == "ARMATURE")
    bone = armature.pose.bones.get("CC_Base_Head")
    if bone is None:
        raise RuntimeError("CC_Base_Head is missing")
    center = armature.matrix_world @ bone.center
    center.z += 0.04

    for obj in list(bpy.data.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    world = scene.world or bpy.data.worlds.new("ActorHeadReviewWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background:
        background.inputs["Color"].default_value = (0.12, 0.14, 0.18, 1.0)
        background.inputs["Strength"].default_value = 0.50
    for name, location, energy, size in (
        ("HeadReviewKey", (-4.0, -5.0, 5.5), 520.0, 5.0),
        ("HeadReviewFill", (4.0, -2.0, 3.5), 360.0, 4.0),
        ("HeadReviewRim", (0.0, 4.0, 4.5), 420.0, 3.0),
    ):
        data = bpy.data.lights.new(name + "Data", "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    args.output_dir.mkdir(parents=True, exist_ok=True)
    renders = {}
    for direction, (x, y) in DIRECTIONS.items():
        data = bpy.data.cameras.new(f"HeadReview_{direction}_Data")
        data.type = "ORTHO"
        data.ortho_scale = args.ortho_scale
        camera = bpy.data.objects.new(f"HeadReview_{direction}", data)
        scene.collection.objects.link(camera)
        camera.location = (center.x + x, center.y + y, center.z)
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = camera
        output = args.output_dir / f"{direction}.png"
        scene.render.filepath = str(output.resolve())
        bpy.ops.render.render(write_still=True)
        renders[direction] = str(output.resolve())
        bpy.data.objects.remove(camera, do_unlink=True)
    report = {
        "schema": "assetsstudio_actor_v2_head_slot_review_v1",
        "status": "rendered_review_required",
        "input": str(args.input.resolve()),
        "frame": args.frame,
        "head_center": [float(value) for value in center],
        "renders": renders,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"ACTOR_V2_HEAD_SLOT_REVIEW_PASS output={args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
