"""Clean, audit, render, and save an Actor V2 AccuRIG FBX baseline."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


REQUIRED_BONES = (
    "CC_Base_Hip",
    "CC_Base_Pelvis",
    "CC_Base_Waist",
    "CC_Base_Spine01",
    "CC_Base_Spine02",
    "CC_Base_NeckTwist01",
    "CC_Base_Head",
    "CC_Base_L_Clavicle",
    "CC_Base_L_Upperarm",
    "CC_Base_L_Forearm",
    "CC_Base_L_Hand",
    "CC_Base_R_Clavicle",
    "CC_Base_R_Upperarm",
    "CC_Base_R_Forearm",
    "CC_Base_R_Hand",
    "CC_Base_L_Thigh",
    "CC_Base_L_Calf",
    "CC_Base_L_Foot",
    "CC_Base_L_ToeBase",
    "CC_Base_R_Thigh",
    "CC_Base_R_Calf",
    "CC_Base_R_Foot",
    "CC_Base_R_ToeBase",
)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    return (
        Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))),
        Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))),
    )


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def neutral_material():
    mat = bpy.data.materials.new("ActorV2_RigValidation")
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = (0.26, 0.38, 0.58, 1.0)
        principled.inputs["Roughness"].default_value = 0.78
    return mat


def weight_audit(actor: bpy.types.Object) -> dict:
    group_names = {group.index: group.name for group in actor.vertex_groups}
    unweighted = []
    non_normalized = []
    over_four = 0
    max_influences = 0
    minimum_sum = math.inf
    maximum_sum = 0.0
    group_usage = {name: 0 for name in group_names.values()}
    for vertex in actor.data.vertices:
        weights = [assignment.weight for assignment in vertex.groups if assignment.weight > 1e-8]
        for assignment in vertex.groups:
            if assignment.weight > 1e-8:
                group_usage[group_names[assignment.group]] += 1
        if not weights:
            unweighted.append(vertex.index)
            continue
        total = sum(weights)
        minimum_sum = min(minimum_sum, total)
        maximum_sum = max(maximum_sum, total)
        if abs(total - 1.0) > 0.01:
            non_normalized.append(vertex.index)
        count = len(weights)
        max_influences = max(max_influences, count)
        if count > 4:
            over_four += 1
    return {
        "vertex_groups": sorted(group_usage),
        "group_usage": group_usage,
        "unweighted_vertices": len(unweighted),
        "unweighted_sample": unweighted[:20],
        "non_normalized_vertices": len(non_normalized),
        "non_normalized_sample": non_normalized[:20],
        "minimum_weight_sum": 0.0 if minimum_sum == math.inf else minimum_sum,
        "maximum_weight_sum": maximum_sum,
        "max_influences_per_vertex": max_influences,
        "vertices_over_four_influences": over_four,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--asset-id", default="actor_v2_base_v1")
    parser.add_argument("--resolution", type=int, default=1024)
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw_args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    preview_dir = args.output_dir / "rest_preview"
    preview_dir.mkdir(parents=True, exist_ok=True)

    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(args.input.resolve()), use_anim=False)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    rigged_meshes = [
        obj for obj in meshes if any(mod.type == "ARMATURE" for mod in obj.modifiers)
    ]
    if len(armatures) != 1 or len(rigged_meshes) != 1:
        raise RuntimeError(
            f"Expected one armature and one rigged mesh; armatures={len(armatures)} rigged={len(rigged_meshes)}"
        )
    armature = armatures[0]
    actor = rigged_meshes[0]
    extras = [obj for obj in bpy.context.scene.objects if obj not in {armature, actor}]
    removed_extras = [{"name": obj.name, "type": obj.type} for obj in extras]
    for obj in extras:
        bpy.data.objects.remove(obj, do_unlink=True)

    armature.name = "Armature"
    actor.name = "ChibiBaseMesh_AccuRIG_InputMesh"
    actor.data.name = "ActorV2_BaseShape"
    armature.animation_data_clear()
    for bone in armature.pose.bones:
        bone.rotation_mode = "QUATERNION"

    armature_modifiers = [mod for mod in actor.modifiers if mod.type == "ARMATURE"]
    missing_bones = [name for name in REQUIRED_BONES if name not in armature.data.bones]
    weights = weight_audit(actor)
    minimum, maximum = world_bounds([actor])
    dimensions = maximum - minimum
    height = dimensions.z
    x_center = (minimum.x + maximum.x) / 2.0

    bone_landmarks = {}
    for name in REQUIRED_BONES:
        bone = armature.data.bones.get(name)
        if bone:
            bone_landmarks[name] = {
                "head_world": list(armature.matrix_world @ bone.head_local),
                "tail_world": list(armature.matrix_world @ bone.tail_local),
                "parent": bone.parent.name if bone.parent else None,
                "deform": bone.use_deform,
            }

    gates = {
        "one_actor_mesh": len(rigged_meshes) == 1,
        "one_armature": len(armatures) == 1,
        "required_bones_present": not missing_bones,
        "armature_modifier_bound": len(armature_modifiers) == 1 and armature_modifiers[0].object == armature,
        "no_unweighted_vertices": weights["unweighted_vertices"] == 0,
        "weights_normalized_1pct": weights["non_normalized_vertices"] == 0,
        "max_eight_influences": weights["max_influences_per_vertex"] <= 8,
        "grounded_z": abs(minimum.z) <= height * 0.005,
        "centered_x": abs(x_center) <= height * 0.005,
        "z_is_long_axis": dimensions.z > dimensions.x * 1.5,
    }

    actor.data.materials.clear()
    actor.data.materials.append(neutral_material())
    world = bpy.context.scene.world or bpy.data.worlds.new("ActorV2_RigValidationWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.025, 0.035, 0.055, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35

    light_data = bpy.data.lights.new("Key", type="AREA")
    light_data.energy = 350.0
    light_data.size = height
    light = bpy.data.objects.new("Key", light_data)
    bpy.context.collection.objects.link(light)
    light.location = (height, -height, height * 1.4)
    center = (minimum + maximum) / 2.0
    look_at(light, center)

    camera_data = bpy.data.cameras.new("RigValidationCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = height / 0.74
    camera = bpy.data.objects.new("RigValidationCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.look = "AgX - Medium High Contrast"
    directions = {
        "front": Vector((0, -1, 0)),
        "right": Vector((1, 0, 0)),
        "back": Vector((0, 1, 0)),
        "left": Vector((-1, 0, 0)),
    }
    for name, direction in directions.items():
        camera.location = center + direction * height * 3.0
        camera.location.z = center.z
        look_at(camera, center)
        scene.render.filepath = str((preview_dir / f"{name}.png").resolve())
        bpy.ops.render.render(write_still=True)

    blend_path = args.output_dir / f"{args.asset_id}_accurig_rest.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path.resolve()))
    report = {
        "schema": "assetsstudio_actor_v2_accurig_validation_v1",
        "asset_id": args.asset_id,
        "status": "pass" if all(gates.values()) else "fail",
        "input": str(args.input.resolve()),
        "blend": str(blend_path.resolve()),
        "actor_object": actor.name,
        "armature_object": armature.name,
        "removed_export_extras": removed_extras,
        "mesh": {
            "vertices": len(actor.data.vertices),
            "faces": len(actor.data.polygons),
            "bounds_min": list(minimum),
            "bounds_max": list(maximum),
            "dimensions": list(dimensions),
        },
        "armature": {
            "bones": len(armature.data.bones),
            "missing_required_bones": missing_bones,
            "required_landmarks": bone_landmarks,
        },
        "weights": weights,
        "gates": gates,
        "previews": {name: str((preview_dir / f"{name}.png").resolve()) for name in directions},
    }
    report_path = args.output_dir / "validation.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["status"] != "pass":
        raise RuntimeError(f"Actor V2 AccuRIG validation failed: {gates}")
    print(
        f"ACTOR_V2_ACCURIG_VALIDATION_PASS bones={len(armature.data.bones)} "
        f"vertices={len(actor.data.vertices)} output={blend_path.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
