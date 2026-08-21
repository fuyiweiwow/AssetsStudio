from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
STAGE9 = ROOT.parent / "stage9_hunyuan_adapter_transfer_v1"
if str(STAGE9) not in sys.path:
    sys.path.insert(0, str(STAGE9))

import build_hunyuan_jacket_adapter_v1 as compiler  # noqa: E402


compiler.GARMENT_NAME = "Wearable_Adventurer_TorsoOuterV1"
compiler.MASK_NAME = "WearableMask_AdventurerTorsoOuterV1"
compiler.SOURCE_ARM = [
    Vector((0.38, 0.0, 0.55)),
    Vector((0.62, 0.0, 0.28)),
    Vector((0.82, 0.0, 0.05)),
]
compiler.TARGET_ARM = [
    Vector((0.25, -0.005, 1.355)),
    Vector((0.34, 0.0, 1.270)),
    Vector((0.43, -0.002, 1.180)),
]
_TARGET_ARM_CALIBRATED = False

SOURCE_LOW = -0.905797
SOURCE_HIGH = 0.901176
TARGET_LOW = 0.750
TARGET_HIGH = 1.490
UPPER_SHOULDER_LIFT = 0.0
SLEEVE_ROOT_LIFT = 0.0
SLEEVE_TRANSITION_OFFSET = 0.008
OUTER_SHOULDER_RELAX = 0.035
ARM_TRANSITION_NAMES = {
    1: "ActorProfile_ArmTransition_L_ChibiActorV1",
    -1: "ActorProfile_ArmTransition_R_ChibiActorV1",
}


def arm_membership(point: Vector) -> float:
    z = min(0.65, max(0.02, point.z))
    source_arm_center_x = 0.86 - 0.82 * z
    source_torso_half = 0.45 + 0.05 * ((SOURCE_HIGH - z) / (SOURCE_HIGH - SOURCE_LOW))
    threshold = 0.5 * (source_arm_center_x + source_torso_half)
    return compiler.smoothstep(threshold - 0.055, threshold + 0.055, abs(point.x))


def calibrate_target_arm_from_actor() -> None:
    """Derive the short-sleeve centerline from the active Actor's rig."""
    global _TARGET_ARM_CALIBRATED
    if _TARGET_ARM_CALIBRATED:
        return
    armature = bpy.data.objects.get(compiler.ARMATURE_NAME)
    if armature is None:
        raise RuntimeError("Actor armature missing during sleeve calibration")
    upperarm_name = compiler.SIDE_BONES[1][1]
    forearm_name = compiler.SIDE_BONES[1][2]
    upperarm = armature.data.bones.get(upperarm_name)
    forearm = armature.data.bones.get(forearm_name)
    if upperarm is None or forearm is None:
        raise RuntimeError("Actor upperarm/forearm semantics missing during sleeve calibration")
    shoulder = armature.matrix_world @ upperarm.head_local
    elbow = armature.matrix_world @ forearm.head_local
    compiler.TARGET_ARM = [
        Vector((abs(shoulder.x), shoulder.y, shoulder.z)),
        Vector((abs(shoulder.lerp(elbow, 0.45).x), shoulder.lerp(elbow, 0.45).y, shoulder.lerp(elbow, 0.45).z)),
        Vector((abs(shoulder.lerp(elbow, 0.90).x), shoulder.lerp(elbow, 0.90).y, shoulder.lerp(elbow, 0.90).z)),
    ]
    _TARGET_ARM_CALIBRATED = True


def map_torso(point: Vector) -> Vector:
    t = (point.z - SOURCE_LOW) / (SOURCE_HIGH - SOURCE_LOW)
    z = TARGET_LOW + t * (TARGET_HIGH - TARGET_LOW)
    # The generated tunic flares at hand height.  Keep the accepted shoulder
    # width, but taper the lower shell enough that the Actor's forearms can
    # swing beside it without crossing the side seams.
    x_scale = 0.47 + 0.03 * compiler.smoothstep(0.88, 1.10, z) + 0.14 * compiler.smoothstep(1.12, 1.34, z)
    x = point.x * x_scale
    # Lift the generated shoulder bridges, not the inner collar rim.  The
    # source already has a valid neck hole, so a uniform top-shell offset
    # would move the collar toward the Actor's jaw again.
    z += (
        UPPER_SHOULDER_LIFT
        * compiler.smoothstep(1.28, 1.44, z)
        * compiler.smoothstep(0.055, 0.22, abs(x))
    )
    # The source reconstruction carries a rounded shoulder mound.  Relax only
    # the outer top shell; the inner collar rim is deliberately excluded.
    z -= (
        OUTER_SHOULDER_RELAX
        * compiler.smoothstep(1.31, 1.47, z)
        * compiler.smoothstep(0.21, 0.38, abs(x))
    )
    lower_shell = 1.0 - compiler.smoothstep(0.88, 1.12, z)
    # The 2MV chest reconstruction is deeper than this Actor's torso envelope
    # and reads as a side bulge.  Compress depth more than width; the front
    # folds remain generated geometry while the Actor controls the silhouette.
    # Keep the torso/shorts depth relationship from the accepted V6
    # silhouette.  The stronger 0.36 compression made the unchanged
    # pants read as an abnormally thick block in side view.
    y_scale = 0.42 - 0.025 * lower_shell
    return Vector((x, point.y * y_scale - 0.008, z))


def map_arm(point: Vector, side: int) -> tuple[Vector, float]:
    calibrate_target_arm_from_actor()
    source_xz = Vector((abs(point.x), point.z))
    parameter, source_center_xz, source_tangent = compiler.closest_polyline_parameter(
        source_xz, compiler.SOURCE_ARM
    )
    target_centers = [Vector((abs(item.x), item.y, item.z)) for item in compiler.TARGET_ARM]
    target_center, target_tangent = compiler.sample_polyline(parameter, target_centers)
    source_normal = Vector((-source_tangent.y, source_tangent.x))
    target_normal = Vector((-target_tangent.y, target_tangent.x))
    radial = (source_xz - source_center_xz).dot(source_normal)
    # Keep the generated sleeve connected at the shoulder but narrow and move
    # its terminal opening away from the torso.  The previous wide terminal
    # tube touched the chest and visually swallowed the upper arm.
    radial_scale = 0.38 + 0.06 * compiler.smoothstep(0.0, 0.55, parameter)
    mapped_xz = Vector((target_center.x, target_center.z)) + target_normal * (radial * radial_scale)
    mapped_xz.x += 0.020 * compiler.smoothstep(0.18, 0.78, parameter)
    mapped_xz.y -= 0.012 * (1.0 - compiler.smoothstep(0.0, 0.32, parameter))
    mapped_xz.y += SLEEVE_ROOT_LIFT * (1.0 - compiler.smoothstep(0.0, 0.28, parameter))
    return Vector((side * mapped_xz.x, point.y * 0.55 - 0.006, mapped_xz.y)), parameter


def arm_weights(parameter: float, side: int) -> dict[str, float]:
    clavicle, upperarm, forearm, _hand = compiler.SIDE_BONES[side]
    if parameter <= 0.18:
        t = parameter / 0.18
        return {clavicle: 0.72 * (1.0 - t), upperarm: 0.28 + 0.72 * t}
    t = (parameter - 0.18) / 0.82
    return {upperarm: 1.0 - 0.35 * t, forearm: 0.35 * t}


def add_actor_arm_transitions(actor: bpy.types.Object, armature: bpy.types.Object) -> dict[str, int]:
    """Compile a clean ActorProfile cuff between generated sleeve and skin.

    The old Actor has sparse, irregular arm topology, so copying its body faces
    produces visible rectangular patches.  This narrow open tube is instead
    derived from the calibrated arm axis and circumference.  It is an adapter
    boundary, not authored garment artwork, and is rebuilt for each Actor.
    """
    calibrate_target_arm_from_actor()
    garment = bpy.data.objects.get(compiler.GARMENT_NAME)
    if garment is None or not garment.data.materials:
        raise RuntimeError("generated garment material missing before arm transition")

    ring_parameters = [0.42, 0.52, 0.62, 0.72, 0.82]
    radial_segments = 20
    target_centers = [Vector((abs(item.x), item.y, item.z)) for item in compiler.TARGET_ARM]
    reports = {}
    for side, object_name in ARM_TRANSITION_NAMES.items():
        old = bpy.data.objects.get(object_name)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)

        vertices = []
        vertex_parameters = []
        for parameter in ring_parameters:
            center, _ = compiler.sample_polyline(parameter, target_centers)
            previous, _ = compiler.sample_polyline(max(0.0, parameter - 0.01), target_centers)
            following, _ = compiler.sample_polyline(min(1.0, parameter + 0.01), target_centers)
            center = Vector((side * center.x, center.y, center.z))
            axis = Vector((side * (following.x - previous.x), following.y - previous.y, following.z - previous.z)).normalized()
            depth_axis = Vector((0.0, 1.0, 0.0))
            radial_axis = depth_axis.cross(axis).normalized()
            local = (parameter - ring_parameters[0]) / (ring_parameters[-1] - ring_parameters[0])
            radial_radius = 0.086 * (1.0 - local) + 0.076 * local
            depth_radius = 0.082 * (1.0 - local) + 0.072 * local
            for segment in range(radial_segments):
                angle = 2.0 * math.pi * segment / radial_segments
                vertices.append(
                    center
                    + radial_axis * (math.cos(angle) * radial_radius)
                    + depth_axis * (math.sin(angle) * depth_radius)
                )
                vertex_parameters.append(parameter)

        faces = []
        for ring_index in range(len(ring_parameters) - 1):
            first = ring_index * radial_segments
            second = (ring_index + 1) * radial_segments
            for segment in range(radial_segments):
                following = (segment + 1) % radial_segments
                faces.append((first + segment, first + following, second + following, second + segment))

        mesh = bpy.data.meshes.new(f"{object_name}_Mesh")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        transition = bpy.data.objects.new(object_name, mesh)
        bpy.context.collection.objects.link(transition)
        transition.data.materials.append(garment.data.materials[0])
        for target_polygon in transition.data.polygons:
            target_polygon.material_index = 0
            target_polygon.use_smooth = True

        groups = {name: transition.vertex_groups.new(name=name) for name in compiler.ALLOWED_BONES}
        for vertex_index, parameter in enumerate(vertex_parameters):
            for name, weight in arm_weights(parameter, side).items():
                groups[name].add([vertex_index], weight, "REPLACE")
        modifier = transition.modifiers.new("ActorArmature", "ARMATURE")
        modifier.object = armature
        modifier.use_vertex_groups = True
        transition["actor_profile_component"] = "short_sleeve_interface_ring"
        transition["wearable_slot"] = "torso_outer"
        transition["source_actor"] = actor.name
        transition["interface_parameter_range"] = list((ring_parameters[0], ring_parameters[-1]))
        reports[object_name] = len(faces)
    return reports


def add_neck_and_arm_transitions(
    actor: bpy.types.Object,
    armature: bpy.types.Object,
) -> bpy.types.Object:
    for object_name in ARM_TRANSITION_NAMES.values():
        old_transition = bpy.data.objects.get(object_name)
        if old_transition is not None:
            bpy.data.objects.remove(old_transition, do_unlink=True)
    neck_seal = compiler._adventurer_original_add_actor_neck_seal(actor, armature)
    # Hunyuan reconstruction supplies the styled sleeve shell.  The active
    # ActorProfile supplies only the narrow skin-following interface ring; this
    # is rebuilt for every Actor and must never be treated as garment artwork.
    transition_report = add_actor_arm_transitions(actor, armature)
    neck_seal["arm_transition_face_counts"] = json.dumps(transition_report, sort_keys=True)
    return neck_seal


def add_body_mask(actor: bpy.types.Object) -> int:
    """Hide only Actor surfaces physically covered by this short tunic.

    Stage 9's mask follows a long sleeve down to the elbow.  This slot ends at
    the upper arm, so it needs rig-semantic selection: torso and clavicle skin
    can be hidden broadly under the shell while forearms and hands remain
    visible even when they cross the chest during the walk cycle.
    """
    calibrate_target_arm_from_actor()
    existing = actor.vertex_groups.get(compiler.MASK_NAME)
    if existing is not None:
        actor.vertex_groups.remove(existing)
    group = actor.vertex_groups.new(name=compiler.MASK_NAME)
    group_names = {item.index: item.name for item in actor.vertex_groups}
    torso_bones = {"CC_Base_Waist", "CC_Base_Spine01", "CC_Base_Spine02"}
    clavicle_bones = {"CC_Base_L_Clavicle", "CC_Base_R_Clavicle"}
    upperarm_bones = {"CC_Base_L_Upperarm", "CC_Base_R_Upperarm"}
    forearm_bones = {"CC_Base_L_Forearm", "CC_Base_R_Forearm"}
    hand_bones = {"CC_Base_L_Hand", "CC_Base_R_Hand"}

    selected: list[int] = []
    for vertex in actor.data.vertices:
        point = actor.matrix_world @ vertex.co
        weights = {
            group_names.get(item.group): item.weight
            for item in vertex.groups
            if group_names.get(item.group) is not None
        }
        torso_weight = sum(weights.get(name, 0.0) for name in torso_bones)
        clavicle_weight = sum(weights.get(name, 0.0) for name in clavicle_bones)
        upperarm_weight = sum(weights.get(name, 0.0) for name in upperarm_bones)
        forearm_weight = sum(weights.get(name, 0.0) for name in forearm_bones)
        hand_weight = sum(weights.get(name, 0.0) for name in hand_bones)
        upper_body_weight = torso_weight + clavicle_weight + upperarm_weight

        # A sleeve may overlap the wrist ring, but it must never hide the hand
        # to manufacture continuity.  Mixed wrist vertices remain visible as
        # soon as they carry meaningful hand ownership.
        if hand_weight >= 0.15:
            continue

        side = 1 if point.x >= 0.0 else -1
        parameter, arm_distance = compiler.target_arm_coordinates(point, side)
        limb_weight = upperarm_weight + forearm_weight
        # Preserve the proven spatial sleeve core for sparse/mixed-weight
        # shoulder vertices.  The ActorProfile ring now hides the coarse mask
        # edge, while this core prevents skin leaking through the sleeve wall.
        base_arm = 1.16 <= point.z <= 1.42 and arm_distance <= 0.13
        if base_arm:
            selected.append(vertex.index)
            continue
        # Hide only the upper-arm section covered by the interface ring.  The
        # complete forearm and hand remain visible; keeping the whole upper arm
        # would expose it through the generated shoulder shell in motion.
        if abs(point.x) >= 0.24 and limb_weight >= 0.08:
            if parameter <= 0.74 and arm_distance <= 0.245:
                selected.append(vertex.index)
            continue

        # Preserve the accepted V11 spatial core because some vertices in the
        # Actor body mesh have blended/non-torso rig semantics.  Add the
        # semantic expansion around it instead of replacing it.
        base_torso = 0.70 <= point.z <= 1.43 and abs(point.x) <= 0.34
        semantic_torso = (
            0.68 <= point.z <= 1.47
            and abs(point.x) <= 0.43
            and torso_weight >= 0.18
        )
        base_clavicle = (
            1.30 <= point.z <= 1.50
            and abs(point.x) <= 0.40
            and upper_body_weight >= 0.20
        )
        semantic_clavicle = (
            1.18 <= point.z <= 1.51
            and abs(point.x) <= 0.44
            and clavicle_weight >= 0.12
        )
        if (
            base_torso
            or semantic_torso
            or base_clavicle
            or semantic_clavicle
        ):
            selected.append(vertex.index)
    if selected:
        group.add(selected, 1.0, "REPLACE")
    return len(selected)


compiler.arm_membership = arm_membership
compiler.map_torso = map_torso
compiler.map_arm = map_arm
compiler.arm_weights = arm_weights
compiler.add_body_mask = add_body_mask
compiler._adventurer_original_add_actor_neck_seal = compiler.add_actor_neck_seal
compiler.add_actor_neck_seal = add_neck_and_arm_transitions
compiler.UPPER_TORSO_LIFT = UPPER_SHOULDER_LIFT
compiler.SHOULDER_ARM_LIFT = SLEEVE_ROOT_LIFT


if __name__ == "__main__":
    compiler.main()
