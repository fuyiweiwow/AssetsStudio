"""Create an unweighted Actor V2 armature and four-view landmark preview.

This is a calibration artifact only. It deliberately does not bind weights or
retarget animation until the joint locations have been visually approved.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def material(name: str, color: tuple[float, float, float, float], emission: bool = False):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    principled = nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.78
        principled.inputs["Alpha"].default_value = color[3]
        if emission:
            principled.inputs["Emission Color"].default_value = color
            principled.inputs["Emission Strength"].default_value = 2.5
    if color[3] < 1.0:
        mat.surface_render_method = "DITHERED"
    return mat


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def guide_segment(name: str, head: Vector, tail: Vector, radius: float, mat) -> bpy.types.Object:
    direction = tail - head
    length = max(direction.length, radius * 2.0)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=length, location=(head + tail) / 2.0)
    obj = bpy.context.object
    obj.name = f"Guide_{name}"
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    obj.data.materials.append(mat)
    return obj


def guide_joint(name: str, point: Vector, radius: float, mat) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=radius, location=point)
    obj = bpy.context.object
    obj.name = f"Joint_{name}"
    obj.data.materials.append(mat)
    return obj


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--asset-id", default="actor_v2_base_v1")
    parser.add_argument("--resolution", type=int, default=1024)
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw_args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    preview_dir = args.output_dir / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(args.input.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh was imported")

    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    minimum = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maximum = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    height = maximum.z - minimum.z
    if abs(minimum.z) > height * 0.01:
        raise RuntimeError(f"Actor must be grounded before rig calibration; z_min={minimum.z}")

    body_mat = material("ActorV2_CalibrationBody", (0.20, 0.28, 0.42, 0.28))
    for obj in meshes:
        obj.name = "ActorV2_BaseShape"
        obj.data.materials.clear()
        obj.data.materials.append(body_mat)

    h = height
    # Coordinates are proportions of this approved 2.10H candidate. Front is
    # -Y, actor-left is +X, and the feet rest on Z=0.
    specs = {
        "CC_Base_Hip": ((0, 0, 0.02*h), (0, 0, 0.275*h), None, "torso"),
        "CC_Base_Pelvis": ((0, 0, 0.275*h), (0, 0, 0.34*h), "CC_Base_Hip", "torso"),
        "CC_Base_Waist": ((0, 0, 0.34*h), (0, 0, 0.405*h), "CC_Base_Pelvis", "torso"),
        "CC_Base_Spine01": ((0, 0, 0.405*h), (0, 0, 0.465*h), "CC_Base_Waist", "torso"),
        "CC_Base_Spine02": ((0, 0, 0.465*h), (0, 0, 0.505*h), "CC_Base_Spine01", "torso"),
        "CC_Base_NeckTwist01": ((0, 0, 0.505*h), (0, 0, 0.545*h), "CC_Base_Spine02", "head"),
        "CC_Base_Head": ((0, 0, 0.545*h), (0, 0, 0.88*h), "CC_Base_NeckTwist01", "head"),
        "CC_Base_L_Clavicle": ((0, 0, 0.495*h), (0.08*h, 0, 0.49*h), "CC_Base_Spine02", "arm"),
        "CC_Base_L_Upperarm": ((0.08*h, 0, 0.49*h), (0.15*h, 0, 0.38*h), "CC_Base_L_Clavicle", "arm"),
        "CC_Base_L_Forearm": ((0.15*h, 0, 0.38*h), (0.215*h, 0, 0.255*h), "CC_Base_L_Upperarm", "arm"),
        "CC_Base_L_Hand": ((0.215*h, 0, 0.255*h), (0.235*h, 0, 0.225*h), "CC_Base_L_Forearm", "arm"),
        "CC_Base_R_Clavicle": ((0, 0, 0.495*h), (-0.08*h, 0, 0.49*h), "CC_Base_Spine02", "arm"),
        "CC_Base_R_Upperarm": ((-0.08*h, 0, 0.49*h), (-0.15*h, 0, 0.38*h), "CC_Base_R_Clavicle", "arm"),
        "CC_Base_R_Forearm": ((-0.15*h, 0, 0.38*h), (-0.215*h, 0, 0.255*h), "CC_Base_R_Upperarm", "arm"),
        "CC_Base_R_Hand": ((-0.215*h, 0, 0.255*h), (-0.235*h, 0, 0.225*h), "CC_Base_R_Forearm", "arm"),
        "CC_Base_L_Thigh": ((0.055*h, 0, 0.28*h), (0.06*h, 0, 0.15*h), "CC_Base_Pelvis", "leg"),
        "CC_Base_L_Calf": ((0.06*h, 0, 0.15*h), (0.065*h, 0, 0.055*h), "CC_Base_L_Thigh", "leg"),
        "CC_Base_L_Foot": ((0.065*h, 0, 0.055*h), (0.065*h, -0.11*h, 0.025*h), "CC_Base_L_Calf", "leg"),
        "CC_Base_R_Thigh": ((-0.055*h, 0, 0.28*h), (-0.06*h, 0, 0.15*h), "CC_Base_Pelvis", "leg"),
        "CC_Base_R_Calf": ((-0.06*h, 0, 0.15*h), (-0.065*h, 0, 0.055*h), "CC_Base_R_Thigh", "leg"),
        "CC_Base_R_Foot": ((-0.065*h, 0, 0.055*h), (-0.065*h, -0.11*h, 0.025*h), "CC_Base_R_Calf", "leg"),
    }

    armature_data = bpy.data.armatures.new("ActorV2_ArmatureData")
    armature = bpy.data.objects.new("Armature", armature_data)
    bpy.context.collection.objects.link(armature)
    armature.show_in_front = True
    armature_data.display_type = "OCTAHEDRAL"
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = {}
    for name, (head, tail, _parent, _group) in specs.items():
        bone = armature_data.edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        edit_bones[name] = bone
    for name, (_head, _tail, parent, _group) in specs.items():
        if parent:
            edit_bones[name].parent = edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")

    guide_materials = {
        "torso": material("Guide_Torso", (1.0, 0.68, 0.08, 1.0), True),
        "head": material("Guide_Head", (0.30, 1.0, 0.38, 1.0), True),
        "arm": material("Guide_Arm", (0.05, 0.86, 1.0, 1.0), True),
        "leg": material("Guide_Leg", (1.0, 0.18, 0.62, 1.0), True),
        "ear": material("Guide_EarRoot", (1.0, 0.35, 0.05, 1.0), True),
    }
    for name, (head, tail, _parent, group) in specs.items():
        head_v, tail_v = Vector(head), Vector(tail)
        guide_segment(name, head_v, tail_v, h * 0.006, guide_materials[group])
        guide_joint(name, head_v, h * 0.011, guide_materials[group])

    ear_roots = {
        "EarRoot_L": (0.22*h, 0.0, 0.76*h),
        "EarRoot_R": (-0.22*h, 0.0, 0.76*h),
    }
    for name, location in ear_roots.items():
        empty = bpy.data.objects.new(name, None)
        empty.empty_display_type = "SPHERE"
        empty.empty_display_size = h * 0.025
        empty.location = location
        empty.parent = armature
        bpy.context.collection.objects.link(empty)
        guide_joint(name, Vector(location), h * 0.016, guide_materials["ear"])

    world = bpy.context.scene.world or bpy.data.worlds.new("ActorV2_CalibrationWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.025, 0.035, 0.055, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.45

    light_data = bpy.data.lights.new("CalibrationKey", type="AREA")
    light_data.energy = 350.0
    light_data.size = h * 1.2
    light = bpy.data.objects.new("CalibrationKey", light_data)
    bpy.context.collection.objects.link(light)
    light.location = (h, -h, h * 1.5)
    look_at(light, Vector((0, 0, h * 0.6)))

    camera_data = bpy.data.cameras.new("CalibrationCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = h / 0.78
    camera = bpy.data.objects.new("CalibrationCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    bpy.context.scene.camera = camera

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "AgX - Medium High Contrast"

    center = Vector(((minimum.x + maximum.x) / 2.0, (minimum.y + maximum.y) / 2.0, h / 2.0))
    directions = {
        "front": Vector((0, -1, 0)),
        "right": Vector((1, 0, 0)),
        "back": Vector((0, 1, 0)),
        "left": Vector((-1, 0, 0)),
    }
    for name, direction in directions.items():
        camera.location = center + direction * h * 3.0
        camera.location.z = center.z
        look_at(camera, center)
        scene.render.filepath = str((preview_dir / f"{name}.png").resolve())
        bpy.ops.render.render(write_still=True)

    blend_path = args.output_dir / f"{args.asset_id}_rig_calibration.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path.resolve()))
    report = {
        "schema": "assetsstudio_actor_v2_rig_calibration_v1",
        "asset_id": args.asset_id,
        "input": str(args.input.resolve()),
        "blend": str(blend_path.resolve()),
        "status": "needs_human_landmark_confirmation",
        "coordinate_contract": {"up": "+Z", "front": "-Y", "actor_left": "+X", "ground_z": 0.0},
        "bounds": {"min": list(minimum), "max": list(maximum), "height": height},
        "bones": {
            name: {"head": list(head), "tail": list(tail), "parent": parent, "group": group}
            for name, (head, tail, parent, group) in specs.items()
        },
        "ear_roots": {name: list(location) for name, location in ear_roots.items()},
        "required_confirmation": [
            "pelvis/spine/neck/head chain",
            "shoulders/elbows/wrists",
            "hips/knees/ankles/toe direction",
            "EarRoot_L/R height and side seam",
        ],
        "binding_performed": False,
        "animation_retarget_performed": False,
        "previews": {name: str((preview_dir / f"{name}.png").resolve()) for name in directions},
    }
    report_path = args.output_dir / "rig_calibration.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ACTOR_V2_RIG_CALIBRATION_READY blend={blend_path.resolve()} report={report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
