from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector


BONE_ALIASES = {
    "pelvis": ["CC_Base_Pelvis", "Hips", "mixamorig:Hips"],
    "waist": ["CC_Base_Waist", "Spine", "mixamorig:Spine"],
    "spine01": ["CC_Base_Spine01", "Spine1", "mixamorig:Spine1"],
    "spine02": ["CC_Base_Spine02", "Spine2", "Chest", "mixamorig:Spine2"],
    "neck": ["CC_Base_NeckTwist01", "Neck", "mixamorig:Neck"],
    "head": ["CC_Base_Head", "Head", "mixamorig:Head"],
    "left_clavicle": ["CC_Base_L_Clavicle", "LeftShoulder", "mixamorig:LeftShoulder"],
    "left_upperarm": ["CC_Base_L_Upperarm", "LeftArm", "mixamorig:LeftArm"],
    "left_forearm": ["CC_Base_L_Forearm", "LeftForeArm", "mixamorig:LeftForeArm"],
    "left_hand": ["CC_Base_L_Hand", "LeftHand", "mixamorig:LeftHand"],
    "right_clavicle": ["CC_Base_R_Clavicle", "RightShoulder", "mixamorig:RightShoulder"],
    "right_upperarm": ["CC_Base_R_Upperarm", "RightArm", "mixamorig:RightArm"],
    "right_forearm": ["CC_Base_R_Forearm", "RightForeArm", "mixamorig:RightForeArm"],
    "right_hand": ["CC_Base_R_Hand", "RightHand", "mixamorig:RightHand"],
    "left_thigh": ["CC_Base_L_Thigh", "LeftUpLeg", "mixamorig:LeftUpLeg"],
    "left_calf": ["CC_Base_L_Calf", "LeftLeg", "mixamorig:LeftLeg"],
    "left_foot": ["CC_Base_L_Foot", "LeftFoot", "mixamorig:LeftFoot"],
    "right_thigh": ["CC_Base_R_Thigh", "RightUpLeg", "mixamorig:RightUpLeg"],
    "right_calf": ["CC_Base_R_Calf", "RightLeg", "mixamorig:RightLeg"],
    "right_foot": ["CC_Base_R_Foot", "RightFoot", "mixamorig:RightFoot"],
}
ANIMATED_REQUIRED = list(BONE_ALIASES)


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--actor", default="ChibiBaseMesh_AccuRIG_InputMesh")
    parser.add_argument("--armature", default="Armature")
    parser.add_argument("--actor-class", required=True)
    return parser.parse_args(argv)


def normalized(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def resolve_bones(armature: bpy.types.Object | None) -> tuple[dict[str, str], list[str]]:
    if armature is None:
        return {}, ANIMATED_REQUIRED.copy()
    by_normalized = {normalized(bone.name): bone.name for bone in armature.data.bones}
    resolved = {}
    missing = []
    for semantic, aliases in BONE_ALIASES.items():
        found = next((by_normalized[normalized(alias)] for alias in aliases if normalized(alias) in by_normalized), None)
        if found is None:
            missing.append(semantic)
        else:
            resolved[semantic] = found
    return resolved, missing


def vector(value: Vector) -> list[float]:
    return [round(item, 6) for item in value]


def point_bounds(points: list[Vector]) -> dict | None:
    if not points:
        return None
    low = Vector(tuple(min(point[index] for point in points) for index in range(3)))
    high = Vector(tuple(max(point[index] for point in points) for index in range(3)))
    return {
        "count": len(points),
        "low": vector(low),
        "high": vector(high),
        "center": vector((low + high) * 0.5),
        "size": vector(high - low),
    }


def main() -> int:
    options = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    bpy.context.scene.frame_set(1)
    actor = bpy.data.objects.get(options.actor)
    armature = bpy.data.objects.get(options.armature)
    if actor is None or actor.type != "MESH":
        raise RuntimeError(f"Actor mesh missing: {options.actor}")
    if armature is not None and armature.type != "ARMATURE":
        armature = None

    mapping, missing = resolve_bones(armature)
    # Fitting coordinates live in the bind/rest mesh.  Animated evaluated
    # points are audited separately and must not be baked into slot placement.
    world_points = [actor.matrix_world @ vertex.co for vertex in actor.data.vertices]
    group_by_name = {group.name: group.index for group in actor.vertex_groups}
    weighted_regions = {}
    for semantic, bone_name in mapping.items():
        group_index = group_by_name.get(bone_name)
        if group_index is None:
            weighted_regions[semantic] = None
            continue
        points = [
            world_points[vertex.index]
            for vertex in actor.data.vertices
            if any(item.group == group_index and item.weight >= 0.25 for item in vertex.groups)
        ]
        weighted_regions[semantic] = point_bounds(points)

    rest_bones = {}
    if armature is not None:
        for semantic, bone_name in mapping.items():
            bone = armature.data.bones[bone_name]
            head = armature.matrix_world @ bone.head_local
            tail = armature.matrix_world @ bone.tail_local
            rest_bones[semantic] = {
                "name": bone_name,
                "head": vector(head),
                "tail": vector(tail),
                "length": round((tail - head).length, 6),
            }

    arm_chains = {}
    for side in ("left", "right"):
        keys = [f"{side}_clavicle", f"{side}_upperarm", f"{side}_forearm", f"{side}_hand"]
        if all(key in rest_bones for key in keys):
            arm_chains[side] = [
                rest_bones[f"{side}_upperarm"]["head"],
                rest_bones[f"{side}_forearm"]["head"],
                rest_bones[f"{side}_hand"]["head"],
            ]

    profile = {
        "schema": "actor_wearable_profile_v1",
        "actor_class": options.actor_class,
        "source_blend": str(options.input_blend.resolve()),
        "actor_object": actor.name,
        "armature_object": armature.name if armature else None,
        "mode": "animated" if not missing else "static_only",
        "body_bounds": point_bounds(world_points),
        "bone_mapping": mapping,
        "missing_animated_semantics": missing,
        "rest_bones": rest_bones,
        "weighted_surface_regions": weighted_regions,
        "arm_chains": arm_chains,
        "portability_contract": {
            "static_fit": "requires one visible Actor mesh and regenerated surface envelopes",
            "animated_fit": "requires the semantic bone map, compatible rest pose, and transferred or compiled slot weights",
            "new_actor_action": "run this extractor, resolve any missing aliases, regenerate ActorProfile adapters and masks, then repeat slot audits",
        },
        "status": "pass" if not missing else "incomplete_for_animation",
    }
    options.output.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(profile, ensure_ascii=False))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
