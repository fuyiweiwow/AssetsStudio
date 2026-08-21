from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE_NAME = "Armature"
GARMENT_NAME = "Wearable_Hunyuan2MV_ZipJacket"
MASK_NAME = "WearableMask_HunyuanZipJacketV1"
NECK_SEAL_NAME = "ActorProfile_NeckSeal_ChibiActorV1"
UPPER_TORSO_LIFT = 0.045
SHOULDER_ARM_LIFT = 0.040

TORSO_BONES = ["CC_Base_Waist", "CC_Base_Spine01", "CC_Base_Spine02"]
SIDE_BONES = {
    1: ["CC_Base_L_Clavicle", "CC_Base_L_Upperarm", "CC_Base_L_Forearm", "CC_Base_L_Hand"],
    -1: ["CC_Base_R_Clavicle", "CC_Base_R_Upperarm", "CC_Base_R_Forearm", "CC_Base_R_Hand"],
}
ALLOWED_BONES = TORSO_BONES + SIDE_BONES[1] + SIDE_BONES[-1]

# Semantic centers measured from the accepted Hunyuan2MV jacket.
SOURCE_ARM = [Vector((0.37, 0.0, 0.46)), Vector((0.66, 0.0, -0.02)), Vector((0.89, 0.0, -0.50))]
# Target centers come from the canonical Actor's frame-1 arm chain.
TARGET_ARM = [Vector((0.25, -0.005, 1.355)), Vector((0.45, 0.0, 1.158)), Vector((0.575, -0.005, 0.995))]


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--source-glb", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--decimate-ratio", type=float, default=0.18)
    return parser.parse_args(argv)


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge1 <= edge0:
        return 0.0
    t = min(1.0, max(0.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def bounds(obj: bpy.types.Object) -> dict[str, list[float]]:
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return {
        "low": [round(v, 6) for v in low],
        "high": [round(v, 6) for v in high],
        "size": [round(v, 6) for v in high - low],
    }


def closest_polyline_parameter(point_xz: Vector, centers: list[Vector]) -> tuple[float, Vector, Vector]:
    best = None
    for index in range(len(centers) - 1):
        a = Vector((centers[index].x, centers[index].z))
        b = Vector((centers[index + 1].x, centers[index + 1].z))
        segment = b - a
        local = min(1.0, max(0.0, (point_xz - a).dot(segment) / max(segment.length_squared, 1e-12)))
        projection = a + segment * local
        distance = (point_xz - projection).length_squared
        if best is None or distance < best[0]:
            tangent = segment.normalized()
            best = (distance, (index + local) / (len(centers) - 1), projection, tangent)
    assert best is not None
    return best[1], best[2], best[3]


def sample_polyline(parameter: float, centers: list[Vector]) -> tuple[Vector, Vector]:
    scaled = min(1.0, max(0.0, parameter)) * (len(centers) - 1)
    index = min(len(centers) - 2, int(math.floor(scaled)))
    local = scaled - index
    a = centers[index]
    b = centers[index + 1]
    center = a.lerp(b, local)
    tangent = Vector((b.x - a.x, b.z - a.z)).normalized()
    return center, tangent


def arm_membership(point: Vector) -> float:
    z = min(0.65, max(-0.65, point.z))
    source_arm_center_x = 0.60 - 0.45 * z
    source_torso_half = 0.46 + 0.05 * ((0.71 - z) / 1.43)
    threshold = 0.5 * (source_arm_center_x + source_torso_half)
    return smoothstep(threshold - 0.055, threshold + 0.055, abs(point.x))


def map_torso(point: Vector) -> Vector:
    source_low = -0.720441
    source_high = 0.712618
    target_low = 0.72
    target_high = 1.445
    t = (point.z - source_low) / (source_high - source_low)
    z = target_low + t * (target_high - target_low)
    # Raise only the upper torso shell so the front/back shoulder bridges sit
    # above the Actor clavicles.  The opening beyond this bridge must be the
    # neck, not exposed shoulder skin.  Lower torso, hem, and sleeves retain
    # their accepted placement.
    z += UPPER_TORSO_LIFT * smoothstep(1.30, 1.43, z)
    # Preserve the generated jacket's front/back volume while matching the
    # Actor torso width.  The slight front offset protects the belly/chest.
    return Vector((point.x * 0.64, point.y * 0.66 - 0.008, z))


def map_arm(point: Vector, side: int) -> tuple[Vector, float]:
    source_xz = Vector((abs(point.x), point.z))
    parameter, source_center_xz, source_tangent = closest_polyline_parameter(source_xz, SOURCE_ARM)
    target_centers = [Vector((abs(p.x), p.y, p.z)) for p in TARGET_ARM]
    target_center, target_tangent = sample_polyline(parameter, target_centers)
    source_normal = Vector((-source_tangent.y, source_tangent.x))
    target_normal = Vector((-target_tangent.y, target_tangent.x))
    radial = (source_xz - source_center_xz).dot(source_normal)
    # Keep the sleeve volume at the elbow/cuff, but taper the radial mapping
    # near the shoulder root.  A uniform 0.72 scale lifted the sleeve cap
    # above the generated collar on this chibi Actor.
    radial_scale = 0.42 + 0.30 * smoothstep(0.0, 0.28, parameter)
    mapped_xz = Vector((target_center.x, target_center.z)) + target_normal * (radial * radial_scale)
    # Keep the sleeve-root bridge level with the raised torso shoulder while
    # fading the adjustment out before the upper arm.  This preserves cuff and
    # elbow placement and avoids reopening a skin gap at the outer clavicle.
    mapped_xz.y += SHOULDER_ARM_LIFT * (1.0 - smoothstep(0.0, 0.24, parameter))
    return Vector((side * mapped_xz.x, point.y * 0.72 - 0.006, mapped_xz.y)), parameter


def map_point(point: Vector) -> tuple[Vector, float, float, int]:
    side = 1 if point.x >= 0.0 else -1
    torso = map_torso(point)
    arm, parameter = map_arm(point, side)
    membership = arm_membership(point)
    return torso.lerp(arm, membership), membership, parameter, side


def add_weight(weights: dict[str, float], name: str, value: float) -> None:
    if value > 1e-8:
        weights[name] = weights.get(name, 0.0) + value


def torso_weights(point: Vector) -> dict[str, float]:
    z = point.z
    if z <= 0.86:
        return {"CC_Base_Waist": 0.82, "CC_Base_Spine01": 0.18}
    if z <= 1.02:
        t = (z - 0.86) / 0.16
        return {"CC_Base_Waist": 0.82 * (1.0 - t), "CC_Base_Spine01": 0.18 + 0.82 * t}
    if z <= 1.34:
        t = (z - 1.02) / 0.32
        return {"CC_Base_Spine01": 1.0 - 0.86 * t, "CC_Base_Spine02": 0.86 * t}
    return {"CC_Base_Spine02": 1.0}


def arm_weights(parameter: float, side: int) -> dict[str, float]:
    clavicle, upperarm, forearm, hand = SIDE_BONES[side]
    if parameter <= 0.14:
        t = parameter / 0.14
        return {clavicle: 0.72 * (1.0 - t), upperarm: 0.28 + 0.72 * t}
    if parameter <= 0.58:
        t = (parameter - 0.14) / 0.44
        return {upperarm: 1.0 - 0.72 * t, forearm: 0.72 * t}
    if parameter <= 0.90:
        t = (parameter - 0.58) / 0.32
        return {upperarm: 0.28 * (1.0 - t), forearm: 0.72 + 0.28 * (1.0 - t)}
    t = (parameter - 0.90) / 0.10
    return {forearm: 1.0 - 0.18 * t, hand: 0.18 * t}


def assign_weights(obj: bpy.types.Object, semantics: list[tuple[float, float, int]], armature: bpy.types.Object) -> dict[str, int]:
    groups = {name: obj.vertex_groups.new(name=name) for name in ALLOWED_BONES}
    counts = {name: 0 for name in ALLOWED_BONES}
    for vertex, (membership, parameter, side) in zip(obj.data.vertices, semantics):
        world = obj.matrix_world @ vertex.co
        blended: dict[str, float] = {}
        for name, value in torso_weights(world).items():
            add_weight(blended, name, value * (1.0 - membership))
        for name, value in arm_weights(parameter, side).items():
            add_weight(blended, name, value * membership)
        total = sum(blended.values())
        for name, value in blended.items():
            normalized = value / total
            groups[name].add([vertex.index], normalized, "REPLACE")
            counts[name] += 1
    modifier = obj.modifiers.new("ActorArmature", "ARMATURE")
    modifier.object = armature
    modifier.use_vertex_groups = True
    return counts


def target_arm_coordinates(point: Vector, side: int) -> tuple[float, float]:
    xz = Vector((side * point.x, point.z))
    parameter, projection, _ = closest_polyline_parameter(xz, TARGET_ARM)
    return parameter, (xz - projection).length


def add_body_mask(actor: bpy.types.Object) -> int:
    existing = actor.vertex_groups.get(MASK_NAME)
    if existing is not None:
        actor.vertex_groups.remove(existing)
    group = actor.vertex_groups.new(name=MASK_NAME)
    actor_group_names = {item.index: item.name for item in actor.vertex_groups}
    upper_body_groups = {
        "CC_Base_Spine02",
        "CC_Base_L_Clavicle",
        "CC_Base_R_Clavicle",
        "CC_Base_L_Upperarm",
        "CC_Base_R_Upperarm",
    }
    selected = []
    for vertex in actor.data.vertices:
        point = actor.matrix_world @ vertex.co
        torso = 0.70 <= point.z <= 1.43 and abs(point.x) <= 0.34
        upper_body_weight = sum(
            item.weight
            for item in vertex.groups
            if actor_group_names.get(item.group) in upper_body_groups
        )
        # Hide clavicle/shoulder body surfaces by their original rig semantics,
        # not by a broad spatial cut that could remove the chibi jaw.  The only
        # body surface intentionally exposed through the collar is neck skin.
        clavicle = 1.30 <= point.z <= 1.50 and abs(point.x) <= 0.40 and upper_body_weight >= 0.20
        side = 1 if point.x >= 0.0 else -1
        _, arm_distance = target_arm_coordinates(point, side)
        # End the hidden region inside the generated sleeve instead of at the
        # wrist.  Mask removes boundary-crossing Actor faces, so a short
        # unmasked overlap under the cuff prevents a visible arm/hand gap.
        arm = 0.975 <= point.z <= 1.42 and arm_distance <= 0.13
        if torso or clavicle or arm:
            selected.append(vertex.index)
    if selected:
        group.add(selected, 1.0, "REPLACE")
    return len(selected)


def add_actor_neck_seal(actor: bpy.types.Object, armature: bpy.types.Object) -> bpy.types.Object:
    existing = bpy.data.objects.get(NECK_SEAL_NAME)
    if existing is not None:
        bpy.data.objects.remove(existing, do_unlink=True)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32,
        radius=0.075,
        depth=0.20,
        end_fill_type="NGON",
        location=(0.0, -0.005, 1.42),
    )
    seal = bpy.context.object
    seal.name = NECK_SEAL_NAME
    seal.scale.y = 0.90
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = seal.modifiers.new("NeckSealEdgeSoftening", "BEVEL")
    bevel.width = 0.008
    bevel.segments = 2
    bpy.context.view_layer.objects.active = seal
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    for polygon in seal.data.polygons:
        polygon.use_smooth = True
    if actor.data.materials and actor.data.materials[0] is not None:
        seal.data.materials.append(actor.data.materials[0])

    spine = seal.vertex_groups.new(name="CC_Base_Spine02")
    neck = seal.vertex_groups.new(name="CC_Base_NeckTwist01")
    for vertex in seal.data.vertices:
        world = seal.matrix_world @ vertex.co
        neck_weight = smoothstep(1.36, 1.48, world.z)
        spine.add([vertex.index], 1.0 - neck_weight, "REPLACE")
        neck.add([vertex.index], neck_weight, "REPLACE")
    modifier = seal.modifiers.new("ActorArmature", "ARMATURE")
    modifier.object = armature
    modifier.use_vertex_groups = True
    seal["actor_profile_component"] = "neck_occlusion_seal"
    seal["purpose"] = "occlude opposite garment panels through open collars"
    return seal


def main() -> None:
    args = cli()
    bpy.ops.wm.open_mainfile(filepath=str(args.actor_blend))
    scene = bpy.context.scene
    scene.frame_set(1)
    actor = bpy.data.objects.get(ACTOR_NAME)
    armature = bpy.data.objects.get(ARMATURE_NAME)
    if actor is None or armature is None:
        raise RuntimeError("canonical Actor or Armature missing")
    for name in ALLOWED_BONES:
        if armature.data.bones.get(name) is None:
            raise RuntimeError(f"required Actor bone missing: {name}")

    old = bpy.data.objects.get(GARMENT_NAME)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    existing = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.source_glb))
    imported = [obj for obj in bpy.data.objects if obj not in existing and obj.type == "MESH"]
    if not imported:
        raise RuntimeError("Hunyuan GLB contains no mesh")
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
    bpy.ops.object.modifier_apply(modifier=decimate.name)

    source_points = [vertex.co.copy() for vertex in garment.data.vertices]
    semantics: list[tuple[float, float, int]] = []
    for vertex, source_point in zip(garment.data.vertices, source_points):
        mapped, membership, parameter, side = map_point(source_point)
        vertex.co = mapped
        semantics.append((membership, parameter, side))
    garment.data.update()

    material = bpy.data.materials.get("HunyuanZipJacket_Teal") or bpy.data.materials.new("HunyuanZipJacket_Teal")
    material.diffuse_color = (0.035, 0.45, 0.50, 1.0)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = material.diffuse_color
    principled.inputs["Roughness"].default_value = 0.78
    garment.data.materials.clear()
    garment.data.materials.append(material)

    weight_counts = assign_weights(garment, semantics, armature)
    mask_count = add_body_mask(actor)
    neck_seal = add_actor_neck_seal(actor, armature)
    old_mask_modifier = actor.modifiers.get("PreviewBodyHide_HunyuanZipJacketV1")
    if old_mask_modifier is not None:
        actor.modifiers.remove(old_mask_modifier)
    mask_modifier = actor.modifiers.new("PreviewBodyHide_HunyuanZipJacketV1", "MASK")
    mask_modifier.mode = "VERTEX_GROUP"
    mask_modifier.vertex_group = MASK_NAME
    mask_modifier.invert_vertex_group = True
    garment["source_kind"] = "Hunyuan3D-2MV generated garment"
    garment["source_glb"] = str(args.source_glb)
    garment["adapter_role"] = "semantic fitting coordinates only"
    garment["actor_class"] = "ChibiActorV1"
    garment["wearable_slot"] = "torso_outer"
    garment["wearable_archetype"] = "GeneratedJacketV1"
    garment["body_mask"] = MASK_NAME
    actor["wearable_mask_usage"] = f"hide body covered by {GARMENT_NAME}"
    scene["actor_class"] = "ChibiActorV1"
    scene["wearable_slot"] = "torso_outer"
    scene["wearable_source"] = "Hunyuan3D-2MV"

    cage = bpy.data.objects.get("ActorClothingCage_Outer")
    if cage is not None:
        cage.hide_render = True
        cage.hide_viewport = True

    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend))
    report = {
        "schema": "hunyuan_generated_garment_adapter_v1",
        "actor_class": "ChibiActorV1",
        "slot": "torso_outer",
        "visible_geometry_source": str(args.source_glb),
        "adapter_visible": False,
        "source_vertices": source_vertices,
        "source_faces": source_faces,
        "compiled_vertices": len(garment.data.vertices),
        "compiled_faces": len(garment.data.polygons),
        "decimate_ratio": args.decimate_ratio,
        "bounds_frame_1": bounds(garment),
        "allowed_bones": ALLOWED_BONES,
        "weight_counts": weight_counts,
        "body_mask": {"name": MASK_NAME, "vertex_count": mask_count, "applied_in_review": True},
        "actor_profile_neck_seal": {
            "name": neck_seal.name,
            "vertices": len(neck_seal.data.vertices),
            "faces": len(neck_seal.data.polygons),
            "bones": ["CC_Base_Spine02", "CC_Base_NeckTwist01"],
        },
        "fit_adjustments": {
            "upper_torso_lift": UPPER_TORSO_LIFT,
            "shoulder_arm_lift": SHOULDER_ARM_LIFT,
            "purpose": "place front/back shoulder bridges above Actor clavicles while preserving the neck opening",
        },
        "status": "compiled_motion_and_visual_review_required",
    }
    args.manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
