"""Retarget a Mixamo-style FBX action to the prepared AccuRIG actor.

The source skeleton is imported temporarily. Mixamo pose rotations are
converted into the actor's rest pose and baked onto ``Armature``. Preserving
the source pose offset is important here because the downloaded clip starts
with the arms lowered while the prepared actor is in a T pose. The standard
``mixamorig:`` prefix is optional.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion


MIXAMO_TO_CC_BASE = {
    "Hips": "CC_Base_Hip",
    "Spine": "CC_Base_Waist",
    "Spine1": "CC_Base_Spine01",
    "Spine2": "CC_Base_Spine02",
    "Neck": "CC_Base_NeckTwist01",
    "Head": "CC_Base_Head",
    "LeftShoulder": "CC_Base_L_Clavicle",
    "LeftArm": "CC_Base_L_Upperarm",
    "LeftForeArm": "CC_Base_L_Forearm",
    "LeftHand": "CC_Base_L_Hand",
    "RightShoulder": "CC_Base_R_Clavicle",
    "RightArm": "CC_Base_R_Upperarm",
    "RightForeArm": "CC_Base_R_Forearm",
    "RightHand": "CC_Base_R_Hand",
    "LeftUpLeg": "CC_Base_L_Thigh",
    "LeftLeg": "CC_Base_L_Calf",
    "LeftFoot": "CC_Base_L_Foot",
    "LeftToeBase": "CC_Base_L_ToeBase",
    "RightUpLeg": "CC_Base_R_Thigh",
    "RightLeg": "CC_Base_R_Calf",
    "RightFoot": "CC_Base_R_Foot",
    "RightToeBase": "CC_Base_R_ToeBase",
}

ARM_CHAIN = {
    "CC_Base_L_Clavicle",
    "CC_Base_L_Upperarm",
    "CC_Base_L_Forearm",
    "CC_Base_L_Hand",
    "CC_Base_R_Clavicle",
    "CC_Base_R_Upperarm",
    "CC_Base_R_Forearm",
    "CC_Base_R_Hand",
}

FOOT_CHAIN = {
    "CC_Base_L_Foot",
    "CC_Base_L_ToeBase",
    "CC_Base_R_Foot",
    "CC_Base_R_ToeBase",
}


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--mixamo-fbx", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target-armature", default="Armature")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument(
        "--global-axis-deg",
        type=float,
        default=0.0,
        help="extra rotation around X after Blender's FBX Y-up import conversion",
    )
    parser.add_argument(
        "--source-pose-mode",
        choices=("delta", "absolute"),
        default="absolute",
        help="use first-frame-relative motion or preserve Mixamo pose offset",
    )
    parser.add_argument(
        "--arm-neutral-deg",
        type=float,
        default=60.0,
        help="local Z correction that places the actor's arms beside the body",
    )
    parser.add_argument(
        "--arm-global-axis-deg",
        type=float,
        default=90.0,
        help="extra X-axis basis rotation used only for Mixamo arm swing",
    )
    parser.add_argument(
        "--arm-neutral-before-motion",
        action="store_true",
        help="apply the lowered-arm neutral pose before the mapped swing (diagnostic candidate)",
    )
    parser.add_argument(
        "--foot-inward-deg",
        type=float,
        default=0.0,
        help="small side-signed local-Z correction for foot/toe heading",
    )
    parser.add_argument(
        "--world-rest-basis",
        action="store_true",
        help="build the retarget basis from armature-world rest matrices, including FBX object rotation",
    )
    parser.add_argument(
        "--arm-swing-world-axis",
        action="store_true",
        help="diagnostic mode: extract Mixamo arm swing and apply it around actor world Z",
    )
    parser.add_argument(
        "--arm-swing-scale",
        type=float,
        default=1.0,
        help="scale for the world-Z arm swing in diagnostic mode",
    )
    return parser.parse_args(argv)


def normalized(name: str) -> str:
    value = name.replace("mixamorig:", "").replace("mixamorig.", "")
    return value.split(".", 1)[0]


def find_imported_armature(before: set[str]) -> bpy.types.Object:
    found = [obj for obj in bpy.data.objects if obj.type == "ARMATURE" and obj.name not in before]
    if len(found) != 1:
        raise RuntimeError(f"expected one imported Mixamo armature, found {[obj.name for obj in found]}")
    return found[0]


def rotation_only(matrix: Matrix) -> Matrix:
    """Return a rotation-only matrix while preserving the matrix's columns."""
    value = matrix.to_3x3()
    columns = [value.col[index].normalized() for index in range(3)]
    return Matrix(columns).transposed()


def main() -> int:
    options = cli_args()
    actor_path = options.actor.resolve()
    source_path = options.mixamo_fbx.resolve()
    output_path = options.output.resolve()
    bpy.ops.wm.open_mainfile(filepath=str(actor_path))
    target = bpy.data.objects.get(options.target_armature)
    if target is None or target.type != "ARMATURE":
        raise RuntimeError(f"target armature not found: {options.target_armature}")

    before_objects = {obj.name for obj in bpy.data.objects}
    before_actions = {action.name for action in bpy.data.actions}
    bpy.ops.import_scene.fbx(filepath=str(source_path), use_anim=True)
    source = find_imported_armature(before_objects)
    source_action = source.animation_data.action if source.animation_data else None
    if source_action is None:
        imported = [action for action in bpy.data.actions if action.name not in before_actions]
        source_action = next((action for action in imported if action.frame_range[1] > action.frame_range[0]), None)
    if source_action is None:
        raise RuntimeError("Mixamo FBX has no usable animation action")

    source_bones = {normalized(bone.name): bone.name for bone in source.data.bones}
    mapping: dict[str, str] = {}
    for mixamo_name, target_name in MIXAMO_TO_CC_BASE.items():
        source_name = source_bones.get(mixamo_name)
        if source_name and target.pose.bones.get(target_name):
            mapping[target_name] = source_name
    if len(mapping) < 10:
        raise RuntimeError(f"only {len(mapping)} Mixamo bones mapped; expected at least 10")

    start, end = (int(source_action.frame_range[0]), int(source_action.frame_range[1]))
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = start, end

    # Keep the actor's existing rest pose while preserving the source action's
    # initial pose offset. The actor is T-pose based, but Mixamo's clip begins
    # with lowered arms; dropping the source offset recreates the old T-pose
    # failure.
    target.animation_data_clear()
    for target_name in mapping:
        target.pose.bones[target_name].rotation_mode = "QUATERNION"
    bpy.context.view_layer.update()
    scene.frame_set(start)
    bpy.context.view_layer.update()
    target_base_rotation = {
        target_name: target.pose.bones[target_name].rotation_quaternion.copy()
        for target_name in mapping
    }
    source_base_rotation = {
        target_name: source.pose.bones[source_name].rotation_quaternion.copy()
        for target_name, source_name in mapping.items()
    }
    # Mixamo and AccuRIG bone-local axes/rolls are different. Convert each
    # source-local delta through the two bones' rest matrices before applying
    # it to the target pose; otherwise arm swing commonly becomes vertical and
    # leg swing becomes a nearly invisible twist.
    # Blender's FBX importer has already converted the downloaded Mixamo
    # armature into the scene basis. Keep the extra axis correction at zero by
    # default; it remains a CLI option for files imported with another basis.
    source_to_target_world = Matrix.Rotation(
        math.radians(options.global_axis_deg), 4, "X"
    ).to_3x3()
    axis_maps = {}
    arm_axis_maps = {}
    arm_source_to_target_world = Matrix.Rotation(
        math.radians(options.arm_global_axis_deg), 4, "X"
    ).to_3x3()
    for target_name, source_name in mapping.items():
        target_rest = target.data.bones[target_name].matrix_local.to_3x3()
        source_rest = source.data.bones[source_name].matrix_local.to_3x3()
        if options.world_rest_basis:
            target_rest = rotation_only(target.matrix_world.to_3x3() @ target_rest)
            source_rest = rotation_only(source.matrix_world.to_3x3() @ source_rest)
        axis_maps[target_name] = (
            target_rest.inverted() @ source_to_target_world @ source_rest
        ).to_quaternion()
        arm_axis_maps[target_name] = (
            target_rest.inverted() @ arm_source_to_target_world @ source_rest
        ).to_quaternion()
    target_hip = target.pose.bones["CC_Base_Hip"]
    target_base_location = target_hip.location.copy()

    target_action = bpy.data.actions.new(f"Mixamo_{source_action.name}_on_{target.name}")
    target_action.use_fake_user = True
    target.animation_data_create()
    target.animation_data.action = target_action
    for frame in range(start, end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        for target_name in mapping:
            bone = target.pose.bones[target_name]
            source_bone = source.pose.bones[mapping[target_name]]
            axis_map = (
                arm_axis_maps[target_name]
                if target_name in ARM_CHAIN
                else axis_maps[target_name]
            )
            if target_name in ARM_CHAIN:
                delta = source_base_rotation[target_name].inverted() @ source_bone.rotation_quaternion
                if options.arm_swing_world_axis:
                    # The Mixamo walk's useful arm swing is primarily a twist
                    # around its local X axis, which is the character vertical
                    # axis in the imported source. The actor's lowered arm
                    # bones have a diagonal local X axis, so copying that local
                    # axis directly creates lateral/front-view waving. Extract
                    # the signed source swing and reapply it around actor world
                    # Z, preserving forward/back motion for the chibi pose.
                    source_axis, source_angle = delta.to_axis_angle()
                    source_sign = -1.0 if source_axis.x < 0.0 else 1.0
                    signed_angle = source_angle * source_sign * options.arm_swing_scale
                    world_swing = Quaternion((0.0, 0.0, 1.0), signed_angle)
                    target_rest_matrix = rotation_only(
                        target.matrix_world.to_3x3()
                        @ target.data.bones[target_name].matrix_local.to_3x3()
                    )
                    target_rest_quat = target_rest_matrix.to_quaternion()
                    mapped_pose = target_rest_quat.inverted() @ world_swing @ target_rest_quat
                else:
                    mapped_pose = axis_map @ delta @ axis_map.inverted()
                neutral = Quaternion((1.0, 0.0, 0.0, 0.0))
                if target_name.endswith("_Upperarm"):
                    side_sign = -1.0 if target_name.startswith("CC_Base_L_") else 1.0
                    half_angle = math.radians(options.arm_neutral_deg * side_sign) * 0.5
                    neutral = Quaternion((math.cos(half_angle), 0.0, 0.0, math.sin(half_angle)))
                # Keep the source swing axes in the actor basis, then apply
                # the fixed down-at-the-side neutral pose. Applying neutral
                # first rotates the Y-axis swing into an unwanted lateral
                # movement.
                if options.arm_neutral_before_motion:
                    bone.rotation_quaternion = target_base_rotation[target_name] @ neutral @ mapped_pose
                else:
                    bone.rotation_quaternion = target_base_rotation[target_name] @ mapped_pose @ neutral
            elif target_name in FOOT_CHAIN and options.foot_inward_deg:
                side_sign = 1.0 if target_name.startswith("CC_Base_L_") else -1.0
                half_angle = math.radians(options.foot_inward_deg * side_sign) * 0.5
                inward = Quaternion((math.cos(half_angle), 0.0, 0.0, math.sin(half_angle)))
                bone.rotation_quaternion = target_base_rotation[target_name] @ mapped_pose @ inward
            elif options.source_pose_mode == "absolute":
                mapped_pose = axis_map @ source_bone.rotation_quaternion @ axis_map.inverted()
                bone.rotation_quaternion = target_base_rotation[target_name] @ mapped_pose
            else:
                delta = source_base_rotation[target_name].inverted() @ source_bone.rotation_quaternion
                mapped_delta = axis_map @ delta @ axis_map.inverted()
                bone.rotation_quaternion = target_base_rotation[target_name] @ mapped_delta
            bone.keyframe_insert("rotation_quaternion", frame=frame, group=target_name)
        # The downloaded clips are intended as in-place game cycles. Keep the
        # actor root stationary; locomotion speed will be controlled by the
        # runtime/pixel-asset tool rather than baked into the sprite cycle.
        target_hip.location = target_base_location
        target_hip.keyframe_insert("location", frame=frame, group="CC_Base_Hip")

    imported_objects = [obj for obj in bpy.data.objects if obj.name not in before_objects]
    for obj in imported_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    manifest = {
        "schema": "assetslab_mixamo_retarget_v1",
        "actor_source": str(actor_path),
        "mixamo_source": str(source_path),
        "source_action": source_action.name,
        "target_action": target_action.name,
        "frame_range": [start, end],
        "mapped_bones": mapping,
        "retarget_mode": f"{options.source_pose_mode}_rotation_baked_in_place",
        "global_axis_deg": options.global_axis_deg,
        "source_pose_mode": options.source_pose_mode,
        "arm_neutral_deg": options.arm_neutral_deg,
        "arm_global_axis_deg": options.arm_global_axis_deg,
        "arm_neutral_before_motion": options.arm_neutral_before_motion,
        "foot_inward_deg": options.foot_inward_deg,
        "world_rest_basis": options.world_rest_basis,
        "arm_swing_world_axis": options.arm_swing_world_axis,
        "arm_swing_scale": options.arm_swing_scale,
        "features": "existing eye, brow and ear head attachments preserved",
    }
    output_path.with_suffix(".json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        "MIXAMO_RETARGET_PASS "
        f"action={source_action.name} frames={start}-{end} mapped_bones={len(mapping)} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
