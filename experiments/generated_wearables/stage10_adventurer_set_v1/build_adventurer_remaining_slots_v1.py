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
MASK_NAME = "WearableMask_AdventurerRemainingV1"
MASK_MODIFIER = "PreviewBodyHide_AdventurerRemainingV1"
LEG_TRANSITION_NAMES = {
    "left": "ActorProfile_LegTransition_L_ChibiActorV1",
    "right": "ActorProfile_LegTransition_R_ChibiActorV1",
}


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--feet-glb", required=True, type=Path)
    parser.add_argument("--wrist-glb", required=True, type=Path)
    parser.add_argument("--back-glb", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--decimate-ratio", type=float, default=0.14)
    return parser.parse_args(argv)


def vector(values: list[float]) -> Vector:
    return Vector(tuple(values))


def object_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    return low, high


def import_generated(path: Path, name: str, decimate_ratio: float) -> tuple[bpy.types.Object, dict]:
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    existing = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    imported = [obj for obj in bpy.data.objects if obj not in existing and obj.type == "MESH"]
    if not imported:
        raise RuntimeError(f"Hunyuan GLB contains no mesh: {path}")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in imported:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = imported[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    source = {"vertices": len(obj.data.vertices), "faces": len(obj.data.polygons)}
    modifier = obj.modifiers.new("GeneratedAssetRetopoProxy", "DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = decimate_ratio
    modifier.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    low, high = object_bounds(obj)
    source.update({"low": list(low), "high": list(high), "center": list((low + high) * 0.5)})
    return obj, source


def leather_material() -> bpy.types.Material:
    material = bpy.data.materials.get("AdventurerLeather_Brown") or bpy.data.materials.new(
        "AdventurerLeather_Brown"
    )
    material.diffuse_color = (0.20, 0.075, 0.025, 1.0)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = material.diffuse_color
    principled.inputs["Roughness"].default_value = 0.74
    return material


def set_material(obj: bpy.types.Object, material: bpy.types.Material) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.material_index = 0


def rigid_bind(obj: bpy.types.Object, armature: bpy.types.Object, bone: str, slot: str) -> None:
    group = obj.vertex_groups.new(name=bone)
    group.add([vertex.index for vertex in obj.data.vertices], 1.0, "REPLACE")
    modifier = obj.modifiers.new("ActorArmature", "ARMATURE")
    modifier.object = armature
    modifier.use_vertex_groups = True
    obj["source_kind"] = "Hunyuan3D-2MV generated wearable"
    obj["adapter_role"] = "Actor profile placement and controlled binding only"
    obj["wearable_slot"] = slot
    obj["actor_class"] = "ChibiActorV1"


def normalized_source(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    low, high = object_bounds(obj)
    center = (low + high) * 0.5
    half = (high - low) * 0.5
    return center, half


def fit_axis_aligned(obj: bpy.types.Object, target_center: Vector, target_half: Vector) -> None:
    source_center, source_half = normalized_source(obj)
    for vertex in obj.data.vertices:
        local = vertex.co - source_center
        vertex.co = Vector(
            tuple(target_center[axis] + local[axis] * target_half[axis] / source_half[axis] for axis in range(3))
        )
    obj.data.update()


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = min(1.0, max(0.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def fit_boot_to_ground(
    obj: bpy.types.Object,
    target_center_xy: Vector,
    target_half_xy: Vector,
    target_height: float,
    target_cuff_center: Vector,
) -> dict[str, float]:
    """Fit one generated boot and establish a robust sole contact plane.

    Hunyuan meshes can contain a few low outlier vertices.  Mapping the raw
    minimum to z=0 leaves the visible sole floating.  Use the 2nd percentile
    as the authored sole plane and flatten only the lower outlier tail.
    """
    source_low, source_high = object_bounds(obj)
    source_center = (source_low + source_high) * 0.5
    source_half = (source_high - source_low) * 0.5
    source_z = [vertex.co.z for vertex in obj.data.vertices]
    sole_z = percentile(source_z, 0.02)
    cuff_z = percentile(source_z, 0.99)
    source_height = max(1e-8, cuff_z - sole_z)
    for vertex in obj.data.vertices:
        local = vertex.co - source_center
        base_x = target_center_xy.x + local.x * target_half_xy.x / source_half.x
        base_y = target_center_xy.y + local.y * target_half_xy.y / source_half.y
        normalized_z = (vertex.co.z - sole_z) / source_height
        mapped_z = min(target_height, max(0.0, normalized_z * target_height))
        cuff_weight = smoothstep(0.45, 0.92, mapped_z / target_height)
        cuff_center = target_center_xy.lerp(target_cuff_center, cuff_weight)
        cuff_expansion = 1.0 + 0.14 * cuff_weight
        vertex.co.x = cuff_center.x + (base_x - target_center_xy.x) * cuff_expansion
        vertex.co.y = cuff_center.y + (base_y - target_center_xy.y) * cuff_expansion
        vertex.co.z = mapped_z
    obj.data.update()
    return {"source_sole_p02": sole_z, "source_cuff_p99": cuff_z}


def fit_to_axis(obj: bpy.types.Object, target_center: Vector, axis: Vector, radial_half: Vector, half_length: float) -> None:
    source_center, source_half = normalized_source(obj)
    rotation = Vector((0.0, 0.0, 1.0)).rotation_difference(axis.normalized())
    for vertex in obj.data.vertices:
        local = vertex.co - source_center
        normalized = Vector((local.x / source_half.x, local.y / source_half.y, local.z / source_half.z))
        shaped = Vector((normalized.x * radial_half.x, normalized.y * radial_half.y, normalized.z * half_length))
        vertex.co = target_center + rotation @ shaped
    obj.data.update()


def duplicate_mirrored(source: bpy.types.Object, name: str) -> bpy.types.Object:
    obj = source.copy()
    obj.data = source.data.copy()
    bpy.context.collection.objects.link(obj)
    obj.name = name
    for modifier in list(obj.modifiers):
        obj.modifiers.remove(modifier)
    for group in list(obj.vertex_groups):
        obj.vertex_groups.remove(group)
    for vertex in obj.data.vertices:
        vertex.co.x *= -1.0
    obj.data.update()
    return obj


def weight(vertex: bpy.types.MeshVertex, group_index: int | None) -> float:
    if group_index is None:
        return 0.0
    return next((item.weight for item in vertex.groups if item.group == group_index), 0.0)


def add_leg_transitions(
    actor: bpy.types.Object,
    armature: bpy.types.Object,
    mapping: dict[str, str],
) -> dict[str, int]:
    """Build an ActorProfile skin bridge across segmented leg geometry.

    The legacy Actor has disconnected low-poly limb sections, so extracting its
    surface copies the original joint holes.  This profile component spans from
    inside the shorts to inside the generated boot cuff and blends only the
    semantic thigh/calf/foot chain.  It is fit support, never garment design.
    """
    reports: dict[str, int] = {}
    for side, object_name in LEG_TRANSITION_NAMES.items():
        old = bpy.data.objects.get(object_name)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)
        sign = 1.0 if side == "left" else -1.0
        thigh_name = mapping[f"{side}_thigh"]
        calf_name = mapping[f"{side}_calf"]
        foot_name = mapping[f"{side}_foot"]
        segments = 16
        rings = (
            (0.54, 0.098, 0.090, {thigh_name: 0.72, calf_name: 0.28}),
            (0.43, 0.094, 0.087, {thigh_name: 0.35, calf_name: 0.65}),
            (0.30, 0.089, 0.084, {calf_name: 0.88, foot_name: 0.12}),
            (0.15, 0.084, 0.080, {calf_name: 0.20, foot_name: 0.80}),
        )
        center_x = sign * 0.202
        center_y = 0.008
        inverse_actor = actor.matrix_world.inverted()
        vertices = []
        vertex_weights: list[dict[str, float]] = []
        for z, radius_x, radius_y, weights in rings:
            for index in range(segments):
                angle = 2.0 * math.pi * index / segments
                world = Vector(
                    (
                        center_x + radius_x * math.cos(angle),
                        center_y + radius_y * math.sin(angle),
                        z,
                    )
                )
                vertices.append(inverse_actor @ world)
                vertex_weights.append(weights)
        faces = []
        for ring_index in range(len(rings) - 1):
            first = ring_index * segments
            second = (ring_index + 1) * segments
            for index in range(segments):
                next_index = (index + 1) % segments
                faces.append((first + index, first + next_index, second + next_index, second + index))
        for polygon in actor.data.polygons:
            center = actor.matrix_world @ polygon.center
            if sign * center.x > 0.04 and 0.28 <= center.z <= 0.48:
                skin_material_index = polygon.material_index
                break
        else:
            skin_material_index = 0
        mesh = bpy.data.meshes.new(f"{object_name}_Mesh")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        transition = bpy.data.objects.new(object_name, mesh)
        bpy.context.collection.objects.link(transition)
        transition.matrix_world = actor.matrix_world.copy()
        if actor.data.materials:
            transition.data.materials.append(actor.data.materials[skin_material_index])
        target_groups = {
            thigh_name: transition.vertex_groups.new(name=thigh_name),
            calf_name: transition.vertex_groups.new(name=calf_name),
            foot_name: transition.vertex_groups.new(name=foot_name),
        }
        for vertex_index, weights in enumerate(vertex_weights):
            for bone_name, bone_weight in weights.items():
                target_groups[bone_name].add([vertex_index], bone_weight, "REPLACE")
        modifier = transition.modifiers.new("ActorArmature", "ARMATURE")
        modifier.object = armature
        modifier.use_vertex_groups = True
        transition["actor_profile_component"] = "leg_opening_transition"
        transition["wearable_slots"] = "legs_outer,feet_outer"
        transition["source_actor"] = actor.name
        reports[object_name] = len(faces)
    return reports


def add_body_mask(actor: bpy.types.Object, mapping: dict[str, str], profile: dict) -> int:
    old = actor.vertex_groups.get(MASK_NAME)
    if old is not None:
        actor.vertex_groups.remove(old)
    group = actor.vertex_groups.new(name=MASK_NAME)
    groups = {item.name: item.index for item in actor.vertex_groups}
    selected = []
    left_foot = profile["weighted_surface_regions"]["left_foot"]
    left_calf = profile["weighted_surface_regions"]["left_calf"]
    foot_center = vector(left_foot["center"])
    foot_size = vector(left_foot["size"])
    # The generated source is a high-cuff boot.  Preserve that authored cuff
    # in the feet slot so it closes the lower-leg opening as part of the shoe
    # asset itself; do not manufacture a skin bridge.
    boot_half = Vector((max(0.105, foot_size.x * 0.68), max(0.125, foot_size.y * 1.15), 0.125))
    boot_y = foot_center.y - 0.055
    for vertex in actor.data.vertices:
        point = actor.matrix_world @ vertex.co
        hide = False
        for side in ("left", "right"):
            foot_name = mapping[f"{side}_foot"]
            calf_name = mapping[f"{side}_calf"]
            foot_owned = weight(vertex, groups.get(foot_name)) + weight(vertex, groups.get(calf_name))
            sign = 1.0 if side == "left" else -1.0
            side_token = "_L_" if side == "left" else "_R_"
            toe_owned = sum(
                weight(vertex, index)
                for name, index in groups.items()
                if side_token in name and "Toe" in name
            )
            boot_x = sign * abs(foot_center.x)
            inside_boot_foot = (
                abs(point.x - boot_x) <= boot_half.x * 1.35
                and abs(point.y - boot_y) <= boot_half.y * 1.35
                # Remove complete boundary-crossing faces below the open cuff.
                # The visible calf starts above 0.20; extending the vertex mask
                # slightly past the 0.14 solid core prevents toe/ankle leaks.
                and -0.01 <= point.z <= 0.23
            )
            if inside_boot_foot or (toe_owned >= 0.05 and point.z <= 0.16):
                hide = True

            # Bracers are generated as layered open cuffs.  Keep the Actor's
            # complete forearm and hand visible inside them; masking the arm
            # turns intentional recesses into transparent holes.
        if hide:
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


def main() -> int:
    options = arguments()
    profile = json.loads(options.profile.read_text(encoding="utf-8"))
    if profile.get("status") != "pass" or profile.get("mode") != "animated":
        raise RuntimeError("animated Actor wearable profile has not passed")
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    bpy.context.scene.frame_set(1)
    actor = bpy.data.objects.get(ACTOR_NAME)
    armature = bpy.data.objects.get(ARMATURE_NAME)
    if actor is None or armature is None:
        raise RuntimeError("Actor or Armature missing")
    mapping = profile["bone_mapping"]
    material = leather_material()
    records = {}

    # Remove both sides before importing.  The earlier adapter removed only
    # the left object, so Blender renamed the new mirrored right boot and left
    # the stale V5 right boot active in reviews/audits.
    for obj in list(bpy.data.objects):
        if obj.name.startswith("Wearable_Adventurer_Boot_"):
            bpy.data.objects.remove(obj, do_unlink=True)
    boot, source = import_generated(options.feet_glb, "Wearable_Adventurer_Boot_L_V1", options.decimate_ratio)
    left_foot = profile["weighted_surface_regions"]["left_foot"]
    left_calf = profile["weighted_surface_regions"]["left_calf"]
    foot_size = vector(left_foot["size"])
    foot_center = vector(left_foot["center"])
    boot_half = Vector((max(0.105, foot_size.x * 0.68), max(0.125, foot_size.y * 1.15), 0.125))
    boot_center = Vector((foot_center.x, foot_center.y - 0.055, boot_half.z))
    ground_fit = fit_boot_to_ground(
        boot,
        Vector((boot_center.x, boot_center.y, 0.0)),
        Vector((boot_half.x, boot_half.y, 0.0)),
        boot_half.z * 2.0,
        vector(left_calf["center"]),
    )
    set_material(boot, material)
    rigid_bind(boot, armature, mapping["left_foot"], "feet_outer")
    right_boot = duplicate_mirrored(boot, "Wearable_Adventurer_Boot_R_V1")
    rigid_bind(right_boot, armature, mapping["right_foot"], "feet_outer")
    records["feet_outer"] = {
        "source": source,
        "target_half_size": list(boot_half),
        "left_center": list(boot_center),
        "ground_fit": ground_fit,
    }

    bracer_source, source = import_generated(options.wrist_glb, "Wearable_Adventurer_Bracer_L_V1", options.decimate_ratio)
    left_elbow, left_wrist = vector(profile["arm_chains"]["left"][1]), vector(profile["arm_chains"]["left"][2])
    left_axis = left_elbow - left_wrist
    bracer_center = left_wrist.lerp(left_elbow, 0.22)
    fit_to_axis(bracer_source, bracer_center, left_axis, Vector((0.100, 0.100, 0.0)), left_axis.length * 0.18)
    set_material(bracer_source, material)
    rigid_bind(bracer_source, armature, mapping["left_forearm"], "wrist_accessory")

    right_bracer, _ = import_generated(options.wrist_glb, "Wearable_Adventurer_Bracer_R_V1", options.decimate_ratio)
    right_elbow, right_wrist = vector(profile["arm_chains"]["right"][1]), vector(profile["arm_chains"]["right"][2])
    right_axis = right_elbow - right_wrist
    fit_to_axis(right_bracer, right_wrist.lerp(right_elbow, 0.22), right_axis, Vector((0.100, 0.100, 0.0)), right_axis.length * 0.18)
    set_material(right_bracer, material)
    rigid_bind(right_bracer, armature, mapping["right_forearm"], "wrist_accessory")
    records["wrist_accessory"] = {"source": source, "left_axis_length": left_axis.length, "right_axis_length": right_axis.length}

    backpack, source = import_generated(options.back_glb, "Wearable_Adventurer_Backpack_V1", options.decimate_ratio)
    torso = bpy.data.objects.get("Wearable_Adventurer_TorsoOuterV1")
    if torso is None:
        raise RuntimeError("generated torso garment missing for backpack contact anchor")
    spine_bone = profile["rest_bones"]["spine02"]
    spine_center = (vector(spine_bone["head"]) + vector(spine_bone["tail"])) * 0.5
    backpack_half = Vector((0.230, 0.110, 0.260))
    back_samples = [
        (torso.matrix_world @ vertex.co).y
        for vertex in torso.data.vertices
        if abs((torso.matrix_world @ vertex.co).x) <= 0.22
        and 0.90 <= (torso.matrix_world @ vertex.co).z <= 1.40
        and (torso.matrix_world @ vertex.co).y >= 0.0
    ]
    if not back_samples:
        raise RuntimeError("torso back contact samples missing")
    torso_back_p90 = percentile(back_samples, 0.90)
    backpack_center = Vector((0.0, torso_back_p90 + backpack_half.y + 0.006, spine_center.z - 0.035))
    fit_axis_aligned(backpack, backpack_center, backpack_half)
    backpack_front_p05 = percentile(
        [(backpack.matrix_world @ vertex.co).y for vertex in backpack.data.vertices],
        0.05,
    )
    desired_front = torso_back_p90 + 0.004
    contact_shift = desired_front - backpack_front_p05
    for vertex in backpack.data.vertices:
        vertex.co.y += contact_shift
    backpack.data.update()
    backpack_center.y += contact_shift
    set_material(backpack, material)
    rigid_bind(backpack, armature, mapping["spine02"], "back_accessory")
    records["back_accessory"] = {
        "source": source,
        "target_center": list(backpack_center),
        "target_half_size": list(backpack_half),
        "torso_back_contact_p90": torso_back_p90,
        "source_front_p05_after_initial_fit": backpack_front_p05,
        "contact_shift": contact_shift,
        "clearance": 0.004,
    }

    # Do not ship the former ActorProfile leg bridge as a clothing component.
    # The generated boot cuff and the actual Actor skin/weights must establish
    # this boundary in the reusable workflow.
    for transition_name in LEG_TRANSITION_NAMES.values():
        old_transition = bpy.data.objects.get(transition_name)
        if old_transition is not None:
            bpy.data.objects.remove(old_transition, do_unlink=True)
    leg_transitions = {}
    mask_count = add_body_mask(actor, mapping, profile)
    scene = bpy.context.scene
    scene["wearable_remaining_slots"] = "feet_outer,wrist_accessory,back_accessory"
    options.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output_blend.resolve()))
    report = {
        "schema": "adventurer_remaining_generated_slots_adapter_v1",
        "actor_class": profile["actor_class"],
        "profile": str(options.profile.resolve()),
        "slots": records,
        "body_mask": {"name": MASK_NAME, "vertices": mask_count},
        "leg_transitions": leg_transitions,
        "decimate_ratio": options.decimate_ratio,
        "status": "compiled_motion_and_visual_review_required",
    }
    options.manifest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
