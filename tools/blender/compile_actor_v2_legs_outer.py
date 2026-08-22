"""Compile generated Actor V2 cuffed shorts into the legs_outer slot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE_NAME = "Armature"
GARMENT_NAME = "LegsOuter_DefaultAdventurer_V1"
MASK_NAME = "WearableMask_ActorV2_LegsOuter_DefaultAdventurer_V1"
HIP_BONE = "CC_Base_Hip"
LEFT_THIGH = "CC_Base_L_Thigh"
RIGHT_THIGH = "CC_Base_R_Thigh"

TARGET_X_RADIUS = 0.25
TARGET_Y_RADIUS = 0.235
TARGET_Z_LOW = 0.27
TARGET_Z_HIGH = 0.54
TARGET_Y_CENTER = 0.008


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--source-glb", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--decimate-ratio", type=float, default=0.08)
    return parser.parse_args(argv)


def smoothstep(low: float, high: float, value: float) -> float:
    t = min(1.0, max(0.0, (value - low) / max(high - low, 1e-8)))
    return t * t * (3.0 - 2.0 * t)


def make_toon_material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.80
    return material


def mesh_bounds(obj: bpy.types.Object) -> dict[str, list[float]]:
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    low = [min(point[axis] for point in points) for axis in range(3)]
    high = [max(point[axis] for point in points) for axis in range(3)]
    return {
        "low": [round(value, 6) for value in low],
        "high": [round(value, 6) for value in high],
        "size": [round(high[i] - low[i], 6) for i in range(3)],
    }


def add_body_mask(actor: bpy.types.Object) -> int:
    old = actor.vertex_groups.get(MASK_NAME)
    if old is not None:
        actor.vertex_groups.remove(old)
    group = actor.vertex_groups.new(name=MASK_NAME)
    selected: list[int] = []
    for vertex in actor.data.vertices:
        point = actor.matrix_world @ vertex.co
        if (
            0.265 <= point.z <= 0.545
            and abs(point.x) <= 0.34
        ):
            selected.append(vertex.index)
    if selected:
        group.add(selected, 1.0, "REPLACE")
    old_modifier = actor.modifiers.get("PreviewBodyHide_ActorV2_LegsOuter")
    if old_modifier is not None:
        actor.modifiers.remove(old_modifier)
    modifier = actor.modifiers.new("PreviewBodyHide_ActorV2_LegsOuter", "MASK")
    modifier.mode = "VERTEX_GROUP"
    modifier.vertex_group = MASK_NAME
    modifier.invert_vertex_group = True
    return len(selected)


def assign_weights(garment: bpy.types.Object, armature: bpy.types.Object) -> dict[str, int]:
    for name in (HIP_BONE, LEFT_THIGH, RIGHT_THIGH):
        if armature.data.bones.get(name) is None:
            raise RuntimeError(f"required bone missing: {name}")
    groups = {name: garment.vertex_groups.new(name=name) for name in (HIP_BONE, LEFT_THIGH, RIGHT_THIGH)}
    counts = {name: 0 for name in groups}
    for vertex in garment.data.vertices:
        point = vertex.co
        thigh_weight = 1.0 - smoothstep(0.34, 0.50, point.z)
        hip_weight = 1.0 - thigh_weight
        if abs(point.x) <= 0.045:
            # Keep the crotch bridge connected while allowing both legs to move.
            hip_weight = max(hip_weight, 0.55)
            remaining = 1.0 - hip_weight
            weights = {HIP_BONE: hip_weight, LEFT_THIGH: remaining * 0.5, RIGHT_THIGH: remaining * 0.5}
        else:
            thigh_bone = LEFT_THIGH if point.x > 0.0 else RIGHT_THIGH
            weights = {HIP_BONE: hip_weight, thigh_bone: thigh_weight}
        for name, weight in weights.items():
            if weight > 1e-5:
                groups[name].add([vertex.index], weight, "REPLACE")
                counts[name] += 1
    modifier = garment.modifiers.new("ActorArmature", "ARMATURE")
    modifier.object = armature
    modifier.use_vertex_groups = True
    return counts


def main() -> int:
    args = cli()
    bpy.ops.wm.open_mainfile(filepath=str(args.actor_blend.resolve()))
    bpy.context.scene.frame_set(1)
    actor = bpy.data.objects.get(ACTOR_NAME)
    armature = bpy.data.objects.get(ARMATURE_NAME)
    if actor is None or armature is None:
        raise RuntimeError("Actor V2 body or armature is missing")

    old = bpy.data.objects.get(GARMENT_NAME)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    existing = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.source_glb.resolve()))
    imported = [obj for obj in bpy.data.objects if obj not in existing and obj.type == "MESH"]
    if not imported:
        raise RuntimeError("Hunyuan legs_outer GLB contains no mesh")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in imported:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = imported[0]
    bpy.ops.object.join()
    garment = bpy.context.object
    garment.name = GARMENT_NAME
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    source_vertices = len(garment.data.vertices)
    source_faces = len(garment.data.polygons)

    decimate = garment.modifiers.new("GeneratedAssetRetopoProxy", "DECIMATE")
    decimate.decimate_type = "COLLAPSE"
    decimate.ratio = args.decimate_ratio
    decimate.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = garment
    bpy.ops.object.modifier_apply(modifier=decimate.name)

    points = [vertex.co.copy() for vertex in garment.data.vertices]
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    center = (low + high) * 0.5
    half = (high - low) * 0.5
    cuff_faces = 0
    green_faces = 0
    garment.data.materials.clear()
    garment.data.materials.append(make_toon_material("LegsOuter_Olive", (0.19, 0.27, 0.075, 1.0)))
    garment.data.materials.append(make_toon_material("LegsOuter_KhakiCuff", (0.48, 0.34, 0.12, 1.0)))
    for vertex in garment.data.vertices:
        point = vertex.co.copy()
        x = (point.x - center.x) / max(half.x, 1e-8) * TARGET_X_RADIUS
        y = (point.y - center.y) / max(half.y, 1e-8) * TARGET_Y_RADIUS + TARGET_Y_CENTER
        z_unit = (point.z - low.z) / max(high.z - low.z, 1e-8)
        vertex.co = Vector((x, y, TARGET_Z_LOW + z_unit * (TARGET_Z_HIGH - TARGET_Z_LOW)))
    garment.data.update()
    for polygon in garment.data.polygons:
        if polygon.center.z <= TARGET_Z_LOW + (TARGET_Z_HIGH - TARGET_Z_LOW) * 0.19:
            polygon.material_index = 1
            cuff_faces += 1
        else:
            polygon.material_index = 0
            green_faces += 1
        polygon.use_smooth = True
    garment.data.update()

    weight_counts = assign_weights(garment, armature)
    mask_count = add_body_mask(actor)
    garment["source_kind"] = "Hunyuan3D-2MV generated cuffed shorts"
    garment["source_glb"] = str(args.source_glb.resolve())
    garment["actor_class"] = "ActorV2"
    garment["wearable_slot"] = "legs_outer"
    garment["body_mask"] = MASK_NAME

    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    report = {
        "schema": "assetsstudio_actor_v2_legs_outer_compile_v1",
        "status": "compiled_motion_and_visual_review_required",
        "slot": "legs_outer",
        "source_glb": str(args.source_glb.resolve()),
        "source_vertices": source_vertices,
        "source_faces": source_faces,
        "compiled_vertices": len(garment.data.vertices),
        "compiled_faces": len(garment.data.polygons),
        "decimate_ratio": args.decimate_ratio,
        "bounds_frame_1": mesh_bounds(garment),
        "target_radii": [TARGET_X_RADIUS, TARGET_Y_RADIUS],
        "target_vertical_range": [TARGET_Z_LOW, TARGET_Z_HIGH],
        "weight_counts": weight_counts,
        "body_mask": {"name": MASK_NAME, "vertex_count": mask_count},
        "material_face_counts": {"olive": green_faces, "khaki_cuff": cuff_faces},
    }
    args.manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"ACTOR_V2_LEGS_OUTER_COMPILE_PASS vertices={len(garment.data.vertices)} "
        f"faces={len(garment.data.polygons)} output={args.output_blend.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
