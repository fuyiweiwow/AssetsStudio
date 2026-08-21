from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


ACTOR = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE = "Armature"
REQUIRED_OBJECTS = {
    ACTOR: "MESH",
    ARMATURE: "ARMATURE",
    "Wearable_Adventurer_TorsoOuterV1": "MESH",
    "Wearable_Adventurer_WaistAccessoryV1": "MESH",
    "Wearable_Adventurer_LegsOuterV1": "MESH",
    "Wearable_Adventurer_Boot_L_V1": "MESH",
    "Wearable_Adventurer_Boot_R_V1": "MESH",
    "Wearable_Adventurer_Bracer_L_V1": "MESH",
    "Wearable_Adventurer_Bracer_R_V1": "MESH",
    "Wearable_Adventurer_Backpack_V1": "MESH",
    "Wearable_Adventurer_HeadHairV1": "MESH",
}
SEMANTIC_BONES = {
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
    "CC_Base_R_Thigh",
    "CC_Base_R_Calf",
    "CC_Base_R_Foot",
}
GENERATED_HEAD_OBJECT = "Wearable_Adventurer_HeadHairV1"


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main() -> int:
    options = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    failures: list[str] = []

    object_report: dict[str, dict[str, object]] = {}
    for name, expected_type in REQUIRED_OBJECTS.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"missing object: {name}")
            continue
        object_report[name] = {
            "type": obj.type,
            "vertices": len(obj.data.vertices) if obj.type == "MESH" else None,
        }
        if obj.type != expected_type:
            failures.append(f"{name}: expected {expected_type}, got {obj.type}")

    armature = bpy.data.objects.get(ARMATURE)
    missing_bones = sorted(
        SEMANTIC_BONES - set(armature.data.bones.keys())
        if armature is not None and armature.type == "ARMATURE"
        else SEMANTIC_BONES
    )
    if missing_bones:
        failures.append(f"missing semantic bones: {missing_bones}")

    action_name = None
    action_frame_range = None
    if armature is not None and armature.animation_data is not None:
        action = armature.animation_data.action
        if action is not None:
            action_name = action.name
            action_frame_range = list(action.frame_range)
    if action_name is None:
        failures.append("Armature has no active action")
    elif action_frame_range is None or action_frame_range[1] < 71:
        failures.append(f"active action does not cover frame 71: {action_frame_range}")

    linked_libraries = []
    for library in bpy.data.libraries:
        resolved = Path(bpy.path.abspath(library.filepath))
        linked_libraries.append({"path": str(resolved), "exists": resolved.exists()})
        if not resolved.exists():
            failures.append(f"missing linked library: {resolved}")

    # V3 restored the pre-headscarf Actor-fit generated hair. The same object
    # name was reused during headwear experiments, so verify its active slot and
    # source contract instead of relying on the name alone.
    generated_head = bpy.data.objects.get(GENERATED_HEAD_OBJECT)
    generated_head_contract = {
        "present": generated_head is not None,
        "wearable_slot": generated_head.get("wearable_slot") if generated_head else None,
        "source_kind": generated_head.get("source_kind") if generated_head else None,
        "binding_mode": generated_head.get("binding_mode") if generated_head else None,
    }
    if generated_head is not None:
        if generated_head.get("wearable_slot") != "head_hair":
            failures.append("active head object is not the head_hair slot")
        if generated_head.get("binding_mode") != "rigid_head_bone":
            failures.append("active head_hair does not use rigid_head_bone binding")

    report = {
        "schema": "assetslab_reproducible_checkpoint_audit_v1",
        "input_blend": str(options.input_blend.resolve()),
        "actor_class": "ChibiActorV1",
        "checkpoint": "AdventurerSetV1/V3",
        "objects": object_report,
        "semantic_bones": {
            "required": len(SEMANTIC_BONES),
            "missing": missing_bones,
        },
        "animation": {
            "action": action_name,
            "frame_range": action_frame_range,
            "review_frames": [1, 11, 21, 31, 41, 51, 61, 71],
        },
        "linked_libraries": linked_libraries,
        "generated_head_contract": generated_head_contract,
        "failures": failures,
        "status": "pass" if not failures else "fail",
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
