from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
HAIR_NAME = "Wearable_Adventurer_HeadHairV1"
MASK_MODIFIER = "PreviewBodyHide_AdventurerHeadHairV1"
HEAD_CENTER = Vector((0.0, 0.025, 2.299))
ORTHO_SCALE = 1.92


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--show-hair", action="store_true")
    return parser.parse_args(argv)


def make_camera(scene: bpy.types.Scene, name: str, location: tuple[float, float, float]) -> bpy.types.Object:
    data = bpy.data.cameras.new(f"{name}Data")
    data.type = "ORTHO"
    data.ortho_scale = ORTHO_SCALE
    camera = bpy.data.objects.new(name, data)
    scene.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = (HEAD_CENTER - camera.location).to_track_quat("-Z", "Y").to_euler()
    return camera


def configure_lighting(scene: bpy.types.Scene) -> None:
    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)
    world = scene.world or bpy.data.worlds.new("ActorHeadCalibrationWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.12, 0.12, 0.12, 1.0)
    background.inputs["Strength"].default_value = 0.8
    for name, location, energy, size in (
        ("CalibrationKey", (4.0, -5.0, 6.0), 900.0, 5.0),
        ("CalibrationFill", (-4.0, -2.0, 4.0), 650.0, 5.0),
        ("CalibrationRim", (0.0, 4.0, 5.0), 450.0, 4.0),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.size = size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (HEAD_CENTER - light.location).to_track_quat("-Z", "Y").to_euler()


def main() -> int:
    args = cli()
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    scene = bpy.context.scene
    scene.frame_set(1)
    actor = bpy.data.objects.get(ACTOR_NAME)
    if actor is None:
        raise RuntimeError(f"missing Actor mesh: {ACTOR_NAME}")

    # The production Actor currently uses a nearly white diagnostic material.
    # Give only its skin mesh a temporary peach calibration colour so ImageGen
    # can read the exact silhouette; the Blend file itself is never saved.
    for material in actor.data.materials:
        material.diffuse_color = (0.58, 0.30, 0.24, 1.0)
        if material.use_nodes:
            principled = material.node_tree.nodes.get("Principled BSDF")
            if principled is not None:
                principled.inputs["Base Color"].default_value = (0.58, 0.30, 0.24, 1.0)
                principled.inputs["Roughness"].default_value = 0.9

    hidden = []
    for obj in bpy.data.objects:
        if not args.show_hair and (obj.name == HAIR_NAME or "HeadHair" in obj.name):
            hidden.append(obj.name)
            obj.hide_render = True
    mask_modifier = actor.modifiers.get(MASK_MODIFIER)
    mask_render_before = None
    if mask_modifier is not None and not args.show_hair:
        mask_render_before = mask_modifier.show_render
        mask_modifier.show_render = False

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.look = "AgX - Medium High Contrast"
    configure_lighting(scene)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cameras = {
        "front": (0.0, -12.0, HEAD_CENTER.z),
        "right": (12.0, 0.025, HEAD_CENTER.z),
        "back": (0.0, 12.0, HEAD_CENTER.z),
        "left": (-12.0, 0.025, HEAD_CENTER.z),
    }
    for name, location in cameras.items():
        scene.camera = make_camera(scene, f"ActorHeadCalibration_{name}", location)
        scene.render.filepath = str(output / f"{name}.png")
        bpy.ops.render.render(write_still=True)

    manifest = {
        "schema": "actor_head_imagegen_calibration_v1",
        "input_blend": str(args.input_blend.resolve()),
        "frame": 1,
        "directions": list(cameras),
        "resolution": [1024, 1024],
        "projection": "orthographic",
        "ortho_scale": ORTHO_SCALE,
        "head_center": list(HEAD_CENTER),
        "hidden_hair_objects": hidden,
        "disabled_actor_mask_modifier": MASK_MODIFIER if mask_modifier is not None else None,
        "mask_render_state_before": mask_render_before,
        "purpose": "Exact current-Actor head and face proportion reference for ImageGen hair fitting.",
        "show_hair": args.show_hair,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"ACTOR_HEAD_CALIBRATION_PASS output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
