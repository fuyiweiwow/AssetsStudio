from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE_NAME = "Armature"
HAIR_NAME = "Wearable_Adventurer_HeadHairV1"
HEAD_BONE = "CC_Base_Head"
MASK_NAME = "WearableMask_AdventurerHeadHairV1"
MASK_MODIFIER = "PreviewBodyHide_AdventurerHeadHairV1"
# Actor-fit V2 is reconstructed from hair views authored directly over the
# current Actor's exact head renders.  These bounds belong to that generated
# source and must not be mixed with the rejected normal-head V1 source.
SOURCE_LOW = Vector((-0.997753, -0.939402, -0.861212))
SOURCE_HIGH = Vector((0.990013, 0.952975, 0.871767))
SOURCE_CENTER = (SOURCE_LOW + SOURCE_HIGH) * 0.5
TARGET_CENTER = Vector((0.0, 0.025, 2.360))
# Actor head weighted bounds are 1.524 x 1.492 x 1.575.  Keep a deliberate
# outer-shell allowance on every axis instead of fitting only to the face.
TARGET_SCALE = Vector((0.87, 0.88, 0.98))
HEAD_CENTER = Vector((0.0, 0.025, 2.299))
SHELL_RADIAL_CLEARANCE = 0.17
SIDE_TEMPLE_CLEARANCE = 0.0
FRONT_LOCK_SOURCE_Y_INNER = -0.70
FRONT_LOCK_SOURCE_Y_OUTER = -0.86
FRONT_LOCK_FORWARD = 0.105
FRONT_LOCK_DROP = 0.050


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--source-glb", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--decimate-ratio", type=float, default=0.14)
    return parser.parse_args(argv)


def object_bounds(obj: bpy.types.Object) -> dict[str, list[float]]:
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    low = Vector(tuple(min(point[i] for point in points) for i in range(3)))
    high = Vector(tuple(max(point[i] for point in points) for i in range(3)))
    return {
        "low": [round(value, 6) for value in low],
        "high": [round(value, 6) for value in high],
        "size": [round(value, 6) for value in high - low],
    }


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = min(1.0, max(0.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def add_scalp_mask(
    actor: bpy.types.Object,
    hair: bpy.types.Object,
    accessory_mode: bool = False,
) -> dict[str, int]:
    existing = actor.vertex_groups.get(MASK_NAME)
    if existing is not None:
        actor.vertex_groups.remove(existing)
    group = actor.vertex_groups.new(name=MASK_NAME)
    names = {item.index: item.name for item in actor.vertex_groups}
    selected = []
    for vertex in actor.data.vertices:
        point = actor.matrix_world @ vertex.co
        head_weight = sum(
            item.weight
            for item in vertex.groups
            if names.get(item.group) == HEAD_BONE
        )
        # The fringe needs the forehead skin to remain visible.  Hide crown,
        # rear scalp, and the high temples that are fully enclosed by the
        # generated inner hair cap.  Ears are separate feature objects.
        crown = point.z >= 2.56
        rear_scalp = (
            (point.z >= 1.78 and point.y >= -0.02)
            or (point.z >= 1.68 and point.y >= 0.12)
        )
        # Do not expand this vertex mask into the temples or jaw.  The legacy
        # Actor shares low-poly face and eye topology there; masking those
        # vertices fragments the visible face.  Accessory-side clearance is
        # solved by deforming the generated asset below.
        if head_weight >= 0.20 and (crown or rear_scalp):
            selected.append(vertex.index)

    # The generated pointed fringe is intentionally in front of the forehead.
    # Both meshes are rigid to the same head bone, so their frame-1 overlap is
    # invariant through the action.  Add only the actually covered forehead
    # triangles to the scalp occlusion mask instead of deleting a broad face
    # band (which previously removed visible eyes/cheeks).
    actor_points = [actor.matrix_world @ vertex.co for vertex in actor.data.vertices]
    actor_faces = [list(polygon.vertices) for polygon in actor.data.polygons]
    hair_points = [hair.matrix_world @ vertex.co for vertex in hair.data.vertices]
    hair_faces = [list(polygon.vertices) for polygon in hair.data.polygons]
    actor_bvh = BVHTree.FromPolygons(actor_points, actor_faces, all_triangles=False)
    hair_bvh = BVHTree.FromPolygons(hair_points, hair_faces, all_triangles=False)
    fringe_face_indices = set()
    for actor_face_index, _hair_face_index in actor_bvh.overlap(hair_bvh):
        polygon = actor.data.polygons[actor_face_index]
        center = sum((actor_points[index] for index in polygon.vertices), Vector()) / len(polygon.vertices)
        if center.y <= 0.02 and center.z >= 2.10 and abs(center.x) <= 0.60:
            fringe_face_indices.add(actor_face_index)
            selected.extend(polygon.vertices)
    selected = sorted(set(selected))
    if selected:
        group.add(selected, 1.0, "REPLACE")

    old_modifier = actor.modifiers.get(MASK_MODIFIER)
    if old_modifier is not None:
        actor.modifiers.remove(old_modifier)
    modifier = actor.modifiers.new(MASK_MODIFIER, "MASK")
    modifier.mode = "VERTEX_GROUP"
    modifier.vertex_group = MASK_NAME
    modifier.invert_vertex_group = True
    return {
        "vertex_count": len(selected),
        "fringe_occlusion_faces": len(fringe_face_indices),
    }


def main() -> None:
    args = cli()
    accessory_mode = "accessory" in args.source_glb.stem.lower()
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    scene = bpy.context.scene
    scene.frame_set(1)
    actor = bpy.data.objects.get(ACTOR_NAME)
    armature = bpy.data.objects.get(ARMATURE_NAME)
    if actor is None or armature is None or armature.data.bones.get(HEAD_BONE) is None:
        raise RuntimeError("canonical Actor, Armature, or head bone missing")

    old = bpy.data.objects.get(HAIR_NAME)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    existing = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.source_glb.resolve()))
    imported = [obj for obj in bpy.data.objects if obj not in existing and obj.type == "MESH"]
    if not imported:
        raise RuntimeError("Hunyuan hair GLB contains no mesh")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in imported:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = imported[0]
    bpy.ops.object.join()
    hair = bpy.context.object
    hair.name = HAIR_NAME
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    source_vertices = len(hair.data.vertices)
    source_faces = len(hair.data.polygons)
    source_points = [vertex.co.copy() for vertex in hair.data.vertices]
    source_low = Vector(tuple(min(point[axis] for point in source_points) for axis in range(3)))
    source_high = Vector(tuple(max(point[axis] for point in source_points) for axis in range(3)))
    source_center = (source_low + source_high) * 0.5 if accessory_mode else SOURCE_CENTER
    target_scale = Vector((0.88, 0.78, 0.94)) if accessory_mode else TARGET_SCALE
    shell_clearance = 0.060 if accessory_mode else SHELL_RADIAL_CLEARANCE

    decimate = hair.modifiers.new("GeneratedAssetRetopoProxy", "DECIMATE")
    decimate.decimate_type = "COLLAPSE"
    decimate.ratio = args.decimate_ratio
    decimate.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = hair
    bpy.ops.object.modifier_apply(modifier=decimate.name)

    for vertex in hair.data.vertices:
        local = vertex.co - source_center
        mapped = Vector(
            (
                TARGET_CENTER.x + local.x * target_scale.x,
                TARGET_CENTER.y + local.y * target_scale.y,
                TARGET_CENTER.z + local.z * target_scale.z,
            )
        )
        # The Actor-fit images establish the correct unusual skull shape, but
        # the watertight 2mv reconstruction still places part of its inner cap
        # inside the Actor surface.  Inflate every generated point along the
        # current Actor's head radial, preserving the generated lock topology
        # while creating a real wearable shell instead of a face-sized patch.
        radial = mapped - HEAD_CENTER
        if radial.length > 1e-8:
            mapped += radial.normalized() * shell_clearance
        if accessory_mode:
            # Keep the face-opening depth at its proven-safe V1 scale while
            # expanding only generated rear and side surfaces.  This achieves
            # real skull enclosure without moving a watertight reconstruction
            # across the eyes or hiding face vertices.
            mapped.y += 0.17 * smoothstep(0.0, 0.62, local.y)
            side_clearance = (
                0.105
                * smoothstep(0.34, 0.66, abs(mapped.x))
                * smoothstep(1.58, 1.76, mapped.z)
                * (1.0 - smoothstep(2.54, 2.70, mapped.z))
            )
            mapped.x += side_clearance if mapped.x >= 0.0 else -side_clearance
        # Hunyuan produced both a compact inner cap and visible pointed front
        # locks.  Uniform radial fitting pushed those outer locks behind the
        # Actor's forehead and left only a straight cap edge visible.  Source
        # Y separates the truly frontmost locks from the inner cap, so expose
        # only that generated outer layer and leave the cap fitted to the head.
        front_lock = 0.0 if accessory_mode else 1.0 - smoothstep(
            FRONT_LOCK_SOURCE_Y_OUTER,
            FRONT_LOCK_SOURCE_Y_INNER,
            local.y,
        )
        lower_fringe = 1.0 - smoothstep(2.64, 2.82, mapped.z)
        mapped.y -= FRONT_LOCK_FORWARD * front_lock
        mapped.z -= FRONT_LOCK_DROP * front_lock * lower_fringe

        # Preserve the face skin and eyebrow occlusion plane.  The remaining
        # V3 contacts were confined to the generated side locks crossing the
        # Actor temples, so move only that narrow band laterally outward.
        temple_clearance = (
            SIDE_TEMPLE_CLEARANCE
            * smoothstep(0.52, 0.76, abs(mapped.x))
            * (1.0 - smoothstep(-0.08, 0.10, mapped.y))
            * smoothstep(1.86, 2.02, mapped.z)
            * (1.0 - smoothstep(2.46, 2.62, mapped.z))
        )
        if mapped.x < 0.0:
            mapped.x -= temple_clearance
        else:
            mapped.x += temple_clearance

        # Keep the generated inner cap compact, but move only the side-fringe
        # transition outside the visible temples.  This is an adapter-space
        # clearance correction; the generated locks and silhouette remain the
        # visible asset geometry.
        xy = Vector((mapped.x, mapped.y))
        clearance = (
            -0.070
            * smoothstep(0.28, 0.44, abs(mapped.x))
            * (1.0 - smoothstep(-0.20, -0.05, mapped.y))
            * smoothstep(1.92, 2.10, mapped.z)
            * (1.0 - smoothstep(2.58, 2.72, mapped.z))
            * (1.0 - front_lock)
        )
        if abs(clearance) > 0.0 and xy.length > 1e-8:
            direction = xy.normalized()
            mapped.x += direction.x * clearance
            mapped.y += direction.y * clearance
        vertex.co = mapped
    hair.data.update()

    material = bpy.data.materials.get("AdventurerHair_Chestnut") or bpy.data.materials.new(
        "AdventurerHair_Chestnut"
    )
    material.diffuse_color = (0.21, 0.075, 0.028, 1.0)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = material.diffuse_color
    principled.inputs["Roughness"].default_value = 0.72
    hair.data.materials.clear()
    if accessory_mode:
        cloth = bpy.data.materials.get("AdventurerHeadscarf_Teal") or bpy.data.materials.new(
            "AdventurerHeadscarf_Teal"
        )
        cloth.diffuse_color = (0.035, 0.34, 0.37, 1.0)
        cloth.use_nodes = True
        cloth_principled = cloth.node_tree.nodes.get("Principled BSDF")
        cloth_principled.inputs["Base Color"].default_value = cloth.diffuse_color
        cloth_principled.inputs["Roughness"].default_value = 0.82
        hair.data.materials.append(cloth)
        hair.data.materials.append(material)
        for polygon in hair.data.polygons:
            polygon.material_index = 0 if polygon.center.z >= 2.50 else 1
    else:
        hair.data.materials.append(material)

    head_group = hair.vertex_groups.new(name=HEAD_BONE)
    head_group.add([vertex.index for vertex in hair.data.vertices], 1.0, "REPLACE")
    armature_modifier = hair.modifiers.new("ActorArmature", "ARMATURE")
    armature_modifier.object = armature
    armature_modifier.use_vertex_groups = True
    mask_report = add_scalp_mask(actor, hair, accessory_mode=accessory_mode)

    hair["source_kind"] = (
        "Hunyuan3D-2MV generated integrated head-hair accessory"
        if accessory_mode
        else "Hunyuan3D-2MV generated hair"
    )
    hair["source_glb"] = str(args.source_glb.resolve())
    hair["actor_class"] = "ChibiActorV1"
    hair["wearable_slot"] = "head_hair_accessory" if accessory_mode else "head_hair"
    hair["binding_mode"] = "rigid_head_bone"
    hair["body_mask"] = MASK_NAME
    scene["wearable_head_hair"] = HAIR_NAME

    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    report = {
        "schema": "hunyuan_generated_head_hair_adapter_actorfit_v2",
        "actor_class": "ChibiActorV1",
        "slot": "head_hair_accessory" if accessory_mode else "head_hair",
        "visible_geometry_source": str(args.source_glb.resolve()),
        "source_vertices": source_vertices,
        "source_faces": source_faces,
        "compiled_vertices": len(hair.data.vertices),
        "compiled_faces": len(hair.data.polygons),
        "decimate_ratio": args.decimate_ratio,
        "bounds_frame_1": object_bounds(hair),
        "binding": {"bone": HEAD_BONE, "weight": 1.0},
        "scalp_mask": {"name": MASK_NAME, **mask_report},
        "transform": {
            "source_center": list(source_center),
            "target_center": list(TARGET_CENTER),
            "scale": list(target_scale),
            "head_center": list(HEAD_CENTER),
            "shell_radial_clearance": shell_clearance,
            "integrated_head_accessory_mode": accessory_mode,
            "side_temple_clearance": SIDE_TEMPLE_CLEARANCE,
            "front_lock_envelope": {
                "source_y_inner": FRONT_LOCK_SOURCE_Y_INNER,
                "source_y_outer": FRONT_LOCK_SOURCE_Y_OUTER,
                "forward": FRONT_LOCK_FORWARD,
                "drop": FRONT_LOCK_DROP,
                "purpose": "keep generated outer fringe in front of the Actor face while the inner cap remains fitted",
            },
        },
        "status": "compiled_motion_and_visual_review_required",
    }
    args.manifest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
