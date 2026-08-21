from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE_NAME = "Armature"
GARMENT_NAME = "Wearable_Adventurer_LegsOuterV1"
MASK_NAME = "WearableMask_AdventurerLegsOuterV1"
MASK_MODIFIER = "PreviewBodyHide_AdventurerLegsOuterV1"
ALLOWED_BONES = [
    "CC_Base_Pelvis",
    "CC_Base_Spine01",
    "CC_Base_L_Thigh",
    "CC_Base_R_Thigh",
]
TARGET_CENTER = Vector((0.0, -0.002, 0.56))
TARGET_HALF_SIZE = Vector((0.355, 0.270, 0.220))


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--source-glb", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--decimate-ratio", type=float, default=0.16)
    return parser.parse_args(argv)


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    return low, high


def assign_weights(garment: bpy.types.Object, armature: bpy.types.Object) -> dict[str, int]:
    groups = {name: garment.vertex_groups.new(name=name) for name in ALLOWED_BONES}
    counts = {name: 0 for name in ALLOWED_BONES}
    for vertex in garment.data.vertices:
        point = garment.matrix_world @ vertex.co
        height = min(1.0, max(0.0, (point.z - 0.34) / 0.44))
        center_bridge = max(0.0, 1.0 - abs(point.x) / 0.11)
        pelvis_ownership = max(center_bridge, min(1.0, max(0.0, (height - 0.50) / 0.25)))
        side_name = "CC_Base_L_Thigh" if point.x >= 0.0 else "CC_Base_R_Thigh"
        weights = {
            "CC_Base_Pelvis": 0.18 + 0.64 * pelvis_ownership,
            side_name: 0.82 * (1.0 - pelvis_ownership),
        }
        if height >= 0.78:
            spine = 0.18 * (height - 0.78) / 0.22
            weights["CC_Base_Pelvis"] -= spine
            weights["CC_Base_Spine01"] = spine
        total = sum(weights.values())
        for name, value in weights.items():
            normalized = value / total
            if normalized <= 1e-8:
                continue
            groups[name].add([vertex.index], normalized, "REPLACE")
            counts[name] += 1
    modifier = garment.modifiers.new("ActorArmature", "ARMATURE")
    modifier.object = armature
    modifier.use_vertex_groups = True
    return counts


def add_body_mask(actor: bpy.types.Object) -> int:
    old = actor.vertex_groups.get(MASK_NAME)
    if old is not None:
        actor.vertex_groups.remove(old)
    group = actor.vertex_groups.new(name=MASK_NAME)
    names = {item.index: item.name for item in actor.vertex_groups}
    lower_groups = {
        "CC_Base_Hip",
        "CC_Base_Pelvis",
        "CC_Base_Spine01",
        "CC_Base_L_Thigh",
        "CC_Base_R_Thigh",
    }
    selected = []
    for vertex in actor.data.vertices:
        point = actor.matrix_world @ vertex.co
        lower_weight = sum(
            item.weight for item in vertex.groups if names.get(item.group) in lower_groups
        )
        if (
            0.335 <= point.z <= 0.790
            and abs(point.x) <= 0.345
            and -0.265 <= point.y <= 0.250
            and lower_weight >= 0.18
        ):
            selected.append(vertex.index)
    if selected:
        group.add(selected, 1.0, "REPLACE")
    old_modifier = actor.modifiers.get(MASK_MODIFIER)
    if old_modifier is not None:
        actor.modifiers.remove(old_modifier)
    modifier = actor.modifiers.new(MASK_MODIFIER, "MASK")
    modifier.mode = "VERTEX_GROUP"
    modifier.vertex_group = MASK_NAME
    modifier.invert_vertex_group = True
    return len(selected)


def main() -> None:
    args = cli()
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    scene = bpy.context.scene
    scene.frame_set(1)
    actor = bpy.data.objects.get(ACTOR_NAME)
    armature = bpy.data.objects.get(ARMATURE_NAME)
    if actor is None or armature is None:
        raise RuntimeError("canonical Actor or Armature missing")
    for name in ALLOWED_BONES:
        if armature.data.bones.get(name) is None:
            raise RuntimeError(f"required lower-body bone missing: {name}")
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
    source_low, source_high = bounds(garment)
    source_center = (source_low + source_high) * 0.5
    source_half = (source_high - source_low) * 0.5
    scale = Vector(tuple(TARGET_HALF_SIZE[axis] / source_half[axis] for axis in range(3)))
    for vertex in garment.data.vertices:
        local = vertex.co - source_center
        vertex.co = Vector(
            tuple(TARGET_CENTER[axis] + local[axis] * scale[axis] for axis in range(3))
        )
    garment.data.update()

    material = bpy.data.materials.get("AdventurerShorts_DarkBrown") or bpy.data.materials.new(
        "AdventurerShorts_DarkBrown"
    )
    material.diffuse_color = (0.105, 0.048, 0.025, 1.0)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = material.diffuse_color
    principled.inputs["Roughness"].default_value = 0.78
    garment.data.materials.clear()
    garment.data.materials.append(material)
    weight_counts = assign_weights(garment, armature)
    mask_count = add_body_mask(actor)
    garment["source_kind"] = "Hunyuan3D-2MV generated garment"
    garment["source_glb"] = str(args.source_glb.resolve())
    garment["adapter_role"] = "semantic fitting coordinates only"
    garment["actor_class"] = "ChibiActorV1"
    garment["wearable_slot"] = "legs_outer"
    garment["body_mask"] = MASK_NAME
    scene["wearable_legs_outer"] = GARMENT_NAME
    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    final_low, final_high = bounds(garment)
    report = {
        "schema": "hunyuan_generated_legs_outer_adapter_v1",
        "actor_class": "ChibiActorV1",
        "slot": "legs_outer",
        "visible_geometry_source": str(args.source_glb.resolve()),
        "source_vertices": source_vertices,
        "source_faces": source_faces,
        "compiled_vertices": len(garment.data.vertices),
        "compiled_faces": len(garment.data.polygons),
        "decimate_ratio": args.decimate_ratio,
        "transform": {
            "source_center": list(source_center),
            "source_half_size": list(source_half),
            "target_center": list(TARGET_CENTER),
            "target_half_size": list(TARGET_HALF_SIZE),
            "scale": list(scale),
        },
        "bounds_frame_1": {"low": list(final_low), "high": list(final_high)},
        "allowed_bones": ALLOWED_BONES,
        "weight_counts": weight_counts,
        "body_mask": {"name": MASK_NAME, "vertex_count": mask_count},
        "status": "compiled_motion_and_visual_review_required",
    }
    args.manifest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
