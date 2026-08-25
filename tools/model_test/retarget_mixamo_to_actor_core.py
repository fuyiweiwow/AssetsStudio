#!/usr/bin/env python3
"""Retarget one Mixamo FBX action to the current one-to-one AccuRIG Actor.

The transfer uses each source bone's world-space rest-to-pose rotation and
re-expresses it in the corresponding target rest basis. Child translations are
never copied, so the Actor keeps its own proportions and connected joints.
The hip is baked in place for game-cycle preview.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector


MIXAMO_TO_ACCURIG = {
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

MOTION_GATE_BONES = (
    "CC_Base_L_Upperarm",
    "CC_Base_R_Upperarm",
    "CC_Base_L_Thigh",
    "CC_Base_R_Thigh",
    "CC_Base_L_Calf",
    "CC_Base_R_Calf",
)
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


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--animation-fbx", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--animation-asset-id", required=True)
    parser.add_argument("--target-armature", default="Armature")
    parser.add_argument("--fps", type=int, default=30)
    return parser.parse_args(argv)


def normalized_mixamo_name(name: str) -> str:
    value = name.replace("mixamorig:", "").replace("mixamorig.", "")
    return value.split(".", 1)[0]


def imported_armature(before: set[str]) -> bpy.types.Object:
    found = [
        obj
        for obj in bpy.data.objects
        if obj.type == "ARMATURE" and obj.name not in before
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one imported Mixamo armature, found {[obj.name for obj in found]}"
        )
    return found[0]


def animated_action(source: bpy.types.Object, before_actions: set[str]):
    action = source.animation_data.action if source.animation_data else None
    if action and action.frame_range[1] > action.frame_range[0]:
        return action
    imported = [
        action
        for action in bpy.data.actions
        if action.name not in before_actions
        and action.frame_range[1] > action.frame_range[0]
    ]
    if not imported:
        raise RuntimeError("Mixamo FBX has no usable animation action")
    return imported[0]


def rotation_angle_degrees(quaternion) -> float:
    value = quaternion.normalized()
    return math.degrees(2.0 * math.acos(min(1.0, abs(value.w))))


def signed_local_x_twist(quaternion) -> float:
    """Return the signed twist around a Mixamo bone's local X axis."""
    value = quaternion.normalized()
    length = math.hypot(value.w, value.x)
    if length < 1.0e-8:
        return 0.0
    return 2.0 * math.atan2(value.x / length, value.w / length)


def reset_target_pose(target: bpy.types.Object) -> None:
    for bone in target.pose.bones:
        bone.rotation_mode = "QUATERNION"
        bone.location = (0.0, 0.0, 0.0)
        bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        bone.scale = (1.0, 1.0, 1.0)


def world_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    points = [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]
    return (
        Vector(tuple(min(point[index] for point in points) for index in range(3))),
        Vector(tuple(max(point[index] for point in points) for index in range(3))),
    )


def make_camera(
    scene: bpy.types.Scene,
    name: str,
    target: Vector,
    location: Vector,
    ortho_scale: float,
) -> bpy.types.Object:
    data = bpy.data.cameras.new(name + "Data")
    data.type = "ORTHO"
    data.ortho_scale = ortho_scale
    camera = bpy.data.objects.new(name, data)
    scene.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = (target - location).to_track_quat("-Z", "Y").to_euler()
    return camera


def render_motion_samples(
    actor: bpy.types.Object,
    output_dir: Path,
    start: int,
    end: int,
    sample_count: int = 8,
) -> dict[str, list[str]]:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.render.resolution_x = 320
    scene.render.resolution_y = 320
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.055, 0.075, 0.105)
    scene.frame_set(start)
    bpy.context.view_layer.update()
    low, high = world_bounds(actor)
    target = (low + high) * 0.5
    height = max(high.z - low.z, 0.1)
    distance = height * 4.0
    camera_specs = {
        "front": target + Vector((0.0, -distance, 0.0)),
        "right": target + Vector((distance, 0.0, 0.0)),
        "back": target + Vector((0.0, distance, 0.0)),
        "left": target + Vector((-distance, 0.0, 0.0)),
    }
    cameras = {
        name: make_camera(scene, f"Animation_{name}", target, location, height * 1.28)
        for name, location in camera_specs.items()
    }
    frames = sorted(
        {
            round(start + index * (end - start) / max(sample_count - 1, 1))
            for index in range(sample_count)
        }
    )
    preview_dir = output_dir / "preview_frames"
    preview_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, list[str]] = {}
    for direction, camera in cameras.items():
        scene.camera = camera
        outputs[direction] = []
        for index, frame in enumerate(frames):
            scene.frame_set(frame)
            path = preview_dir / f"{direction}_{index:02d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            outputs[direction].append(str(path))
    return outputs


def main() -> int:
    args = cli_args()
    actor_path = args.actor_blend.resolve()
    source_path = args.animation_fbx.resolve()
    output_dir = args.output_dir.resolve()
    if not actor_path.is_file() or not source_path.is_file():
        raise FileNotFoundError(actor_path if not actor_path.is_file() else source_path)

    bpy.ops.wm.open_mainfile(filepath=str(actor_path))
    target = bpy.data.objects.get(args.target_armature)
    if target is None or target.type != "ARMATURE":
        raise RuntimeError(f"target armature not found: {args.target_armature}")
    meshes = [
        obj
        for obj in bpy.data.objects
        if obj.type == "MESH"
        and any(mod.type == "ARMATURE" and mod.object == target for mod in obj.modifiers)
    ]
    if len(meshes) != 1:
        raise RuntimeError(f"expected one mesh bound to target armature, found {len(meshes)}")
    actor = meshes[0]
    target.data.pose_position = "POSE"
    target.animation_data_clear()
    reset_target_pose(target)

    before_objects = {obj.name for obj in bpy.data.objects}
    before_actions = {action.name for action in bpy.data.actions}
    bpy.ops.import_scene.fbx(filepath=str(source_path), use_anim=True)
    source = imported_armature(before_objects)
    source_action = animated_action(source, before_actions)
    source_action_name = source_action.name
    source.animation_data_create()
    source.animation_data.action = source_action
    source_bones = {
        normalized_mixamo_name(bone.name): bone.name for bone in source.data.bones
    }
    mapping = {
        target_name: source_bones[source_name]
        for source_name, target_name in MIXAMO_TO_ACCURIG.items()
        if source_name in source_bones and target_name in target.data.bones
    }
    missing_source = [name for name in MIXAMO_TO_ACCURIG if name not in source_bones]
    missing_target = [
        name for name in MIXAMO_TO_ACCURIG.values() if name not in target.data.bones
    ]
    if missing_source or missing_target or len(mapping) != len(MIXAMO_TO_ACCURIG):
        raise RuntimeError(
            f"incomplete Mixamo mapping source={missing_source} target={missing_target}"
        )

    scene = bpy.context.scene
    scene.render.fps = args.fps
    start = int(math.floor(source_action.frame_range[0]))
    end = int(math.ceil(source_action.frame_range[1]))
    scene.frame_start = start
    scene.frame_end = end
    scene.frame_set(start)
    bpy.context.view_layer.update()

    source_rest_world = {
        target_name: source.matrix_world @ source.data.bones[source_name].matrix_local
        for target_name, source_name in mapping.items()
    }
    target_rest_world = {
        target_name: target.matrix_world @ target.data.bones[target_name].matrix_local
        for target_name in mapping
    }
    target_to_world_inverse = target.matrix_world.inverted()
    upperarm_names = ("CC_Base_L_Upperarm", "CC_Base_R_Upperarm")
    arm_swing_radians: dict[str, dict[int, float]] = {
        name: {} for name in upperarm_names
    }
    for frame in range(start, end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        for target_name in upperarm_names:
            source_bone = source.pose.bones[mapping[target_name]]
            arm_swing_radians[target_name][frame] = signed_local_x_twist(
                source_bone.matrix_basis.to_quaternion()
            )
    for target_name, values in arm_swing_radians.items():
        center = (min(values.values()) + max(values.values())) * 0.5
        arm_swing_radians[target_name] = {
            frame: value - center for frame, value in values.items()
        }
    action_name = args.animation_asset_id
    target_action = bpy.data.actions.new(action_name)
    target_action.use_fake_user = True
    target.animation_data_create()
    target.animation_data.action = target_action
    rotation_samples: dict[str, list[float]] = {name: [] for name in mapping}
    hand_lateral_separation: list[float] = []
    hand_depth_pairs: list[list[float]] = []

    for frame in range(start, end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        reset_target_pose(target)
        for target_name, source_name in mapping.items():
            pose_bone = target.pose.bones[target_name]
            if target_name in ARM_CHAIN:
                if target_name in upperarm_names:
                    parent = pose_bone.parent
                    rest_relative = (
                        parent.bone.matrix_local.inverted()
                        @ pose_bone.bone.matrix_local
                    )
                    base_object = parent.matrix @ rest_relative
                    base_world = target.matrix_world @ base_object
                    world_swing = Quaternion(
                        (0.0, 0.0, 1.0), arm_swing_radians[target_name][frame]
                    )
                    desired_world = (
                        world_swing @ base_world.to_quaternion()
                    ).to_matrix().to_4x4()
                    desired_world.translation = base_world.translation
                    pose_bone.matrix = target_to_world_inverse @ desired_world
                    mapped_rotation = pose_bone.matrix_basis.to_quaternion().normalized()
                    pose_bone.rotation_quaternion = mapped_rotation
                else:
                    mapped_rotation = Quaternion((1.0, 0.0, 0.0, 0.0))
                    pose_bone.rotation_quaternion = mapped_rotation
                pose_bone.location = (0.0, 0.0, 0.0)
                pose_bone.scale = (1.0, 1.0, 1.0)
                pose_bone.keyframe_insert(
                    "rotation_quaternion", frame=frame, group=target_name
                )
                rotation_samples[target_name].append(
                    rotation_angle_degrees(mapped_rotation)
                )
                continue
            source_pose_world = source.matrix_world @ source.pose.bones[source_name].matrix
            # Re-express the source pose in the target bone's rest basis.
            desired_world_rotation = (
                target_rest_world[target_name].to_quaternion()
                @ source_rest_world[target_name].to_quaternion().inverted()
                @ source_pose_world.to_quaternion()
            )
            desired_world = desired_world_rotation.to_matrix().to_4x4()
            desired_world.translation = target_rest_world[target_name].translation
            pose_bone.matrix = target_to_world_inverse @ desired_world
            mapped_rotation = pose_bone.matrix_basis.to_quaternion().normalized()
            pose_bone.location = (0.0, 0.0, 0.0)
            pose_bone.rotation_quaternion = mapped_rotation
            pose_bone.scale = (1.0, 1.0, 1.0)
            pose_bone.keyframe_insert(
                "rotation_quaternion", frame=frame, group=target_name
            )
            if target_name == "CC_Base_Hip":
                pose_bone.keyframe_insert("location", frame=frame, group=target_name)
            rotation_samples[target_name].append(rotation_angle_degrees(mapped_rotation))
        left_hand = target.matrix_world @ target.pose.bones["CC_Base_L_Hand"].tail
        right_hand = target.matrix_world @ target.pose.bones["CC_Base_R_Hand"].tail
        hip = target.matrix_world @ target.pose.bones["CC_Base_Hip"].head
        hand_lateral_separation.append(left_hand.x - right_hand.x)
        hand_depth_pairs.append([
            left_hand.y - hip.y,
            right_hand.y - hip.y,
        ])

    motion_ranges = {
        name: round(max(values) - min(values), 4)
        for name, values in rotation_samples.items()
    }
    left_depth = [pair[0] for pair in hand_depth_pairs]
    right_depth = [pair[1] for pair in hand_depth_pairs]
    left_mean = sum(left_depth) / len(left_depth)
    right_mean = sum(right_depth) / len(right_depth)
    covariance = sum(
        (left - left_mean) * (right - right_mean)
        for left, right in hand_depth_pairs
    )
    correlation_denominator = math.sqrt(
        sum((value - left_mean) ** 2 for value in left_depth)
        * sum((value - right_mean) ** 2 for value in right_depth)
    )
    hand_depth_correlation = (
        covariance / correlation_denominator
        if correlation_denominator > 1.0e-8
        else 0.0
    )
    both_hands_behind_fraction = sum(
        left > 0.0 and right > 0.0 for left, right in hand_depth_pairs
    ) / len(hand_depth_pairs)
    gates = {
        "complete_22_bone_mapping": len(mapping) == 22,
        "usable_frame_range": end - start + 1 >= 20,
        "left_arm_motion": motion_ranges["CC_Base_L_Upperarm"] >= 5.0,
        "right_arm_motion": motion_ranges["CC_Base_R_Upperarm"] >= 5.0,
        "left_leg_motion": motion_ranges["CC_Base_L_Thigh"] >= 5.0,
        "right_leg_motion": motion_ranges["CC_Base_R_Thigh"] >= 5.0,
        "hands_keep_left_right_order": min(hand_lateral_separation) > 0.0,
        "hands_counter_swing": hand_depth_correlation <= -0.5,
        "hands_not_together_behind_back": both_hands_behind_fraction <= 0.05,
    }

    imported = [obj for obj in bpy.data.objects if obj.name not in before_objects]
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
    for action in list(bpy.data.actions):
        if action.name in before_actions or action == target_action:
            continue
        bpy.data.actions.remove(action)

    output_dir.mkdir(parents=True, exist_ok=True)
    blend_path = output_dir / "retargeted.blend"
    glb_path = output_dir / "retargeted.glb"
    report_path = output_dir / "retarget.json"
    preview_frames = render_motion_samples(actor, output_dir, start, end)
    scene.frame_set(start)
    bpy.context.preferences.filepaths.save_version = 0
    for stale in (blend_path, blend_path.with_name(blend_path.name + "1")):
        if stale.is_file():
            stale.unlink()
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.object.select_all(action="DESELECT")
    actor.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=True,
        export_skins=True,
        export_animations=True,
        export_materials="EXPORT",
    )
    report = {
        "schema": "assetsstudio_mixamo_actor_core_retarget_v1",
        "status": "pass" if all(gates.values()) else "fail",
        "actor_id": args.actor_id,
        "animation_asset_id": args.animation_asset_id,
        "actor_source": str(actor_path),
        "animation_source": str(source_path),
        "source_action": source_action_name,
        "target_action": target_action.name,
        "frame_range": [start, end],
        "fps": args.fps,
        "loop": True,
        "root_motion": "in_place",
        "mapped_bones": mapping,
        "motion_ranges_degrees": motion_ranges,
        "hand_trajectory": {
            "minimum_left_right_separation": round(min(hand_lateral_separation), 6),
            "maximum_left_right_separation": round(max(hand_lateral_separation), 6),
            "left_depth_range": [round(min(left_depth), 6), round(max(left_depth), 6)],
            "right_depth_range": [round(min(right_depth), 6), round(max(right_depth), 6)],
            "depth_correlation": round(hand_depth_correlation, 6),
            "both_hands_behind_fraction": round(both_hands_behind_fraction, 6),
        },
        "retarget_strategy": "rest_basis_body_with_centered_world_z_chibi_arm_swing",
        "gates": gates,
        "outputs": {"blend": str(blend_path), "glb": str(glb_path)},
        "preview_frames": preview_frames,
        "next_required_gate": "manual four-direction deformation review",
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not all(gates.values()):
        raise RuntimeError(f"retarget automatic gates failed: {gates}")
    print(
        "MIXAMO_ACTOR_CORE_RETARGET_PASS "
        f"animation={args.animation_asset_id} frames={start}-{end} "
        f"mapped={len(mapping)} output={glb_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
