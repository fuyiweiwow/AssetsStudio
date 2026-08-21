from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parent

ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
GARMENT_NAME = "Wearable_Adventurer_TorsoOuterV1"
MASK_NAME = "WearableMask_AdventurerTorsoOuterV1"
HAND_GROUPS = {
    "CC_Base_L_Hand",
    "CC_Base_R_Hand",
}
INTERFACE_OBJECTS = {
    "ActorProfile_ArmTransition_L_ChibiActorV1",
    "ActorProfile_ArmTransition_R_ChibiActorV1",
}


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main() -> int:
    options = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    scene = bpy.context.scene
    actor = bpy.data.objects.get(ACTOR_NAME)
    garment = bpy.data.objects.get(GARMENT_NAME)
    failures: list[str] = []
    if actor is None or garment is None:
        raise RuntimeError("Actor or generated torso garment missing")

    interface_report = {}
    for name in sorted(INTERFACE_OBJECTS):
        interface = bpy.data.objects.get(name)
        if interface is None:
            failures.append(f"required ActorProfile sleeve interface missing: {name}")
            continue
        modifiers = [modifier for modifier in interface.modifiers if modifier.type == "ARMATURE"]
        valid_component = interface.get("actor_profile_component") == "short_sleeve_interface_ring"
        valid_size = len(interface.data.polygons) <= 160
        valid_binding = len(modifiers) == 1
        if not valid_component or not valid_size or not valid_binding:
            failures.append(f"invalid ActorProfile sleeve interface: {name}")
        interface_report[name] = {
            "component": interface.get("actor_profile_component"),
            "vertices": len(interface.data.vertices),
            "faces": len(interface.data.polygons),
            "parameter_range": list(interface.get("interface_parameter_range", [])),
            "armature_modifiers": len(modifiers),
        }

    mask = actor.vertex_groups.get(MASK_NAME)
    group_indices = {group.name: group.index for group in actor.vertex_groups}
    masked_hand_vertices = 0
    if mask is None:
        failures.append("torso body mask missing")
    else:
        hand_indices = {group_indices[name] for name in HAND_GROUPS if name in group_indices}
        for vertex in actor.data.vertices:
            is_hand = any(item.group in hand_indices and item.weight >= 0.20 for item in vertex.groups)
            is_masked = any(item.group == mask.index and item.weight > 0.0 for item in vertex.groups)
            masked_hand_vertices += int(is_hand and is_masked)
        if masked_hand_vertices:
            failures.append(f"body mask hides {masked_hand_vertices} hand vertices")

    garment_groups = sorted(group.name for group in garment.vertex_groups)
    required_groups = {
        "CC_Base_L_Upperarm",
        "CC_Base_L_Forearm",
        "CC_Base_R_Upperarm",
        "CC_Base_R_Forearm",
    }
    missing_groups = sorted(required_groups.difference(garment_groups))
    if missing_groups:
        failures.append("generated garment missing semantic sleeve weights: " + ", ".join(missing_groups))

    points = [garment.matrix_world @ vertex.co for vertex in garment.data.vertices]
    collar = [point.z for point in points if abs(point.x) <= 0.18 and point.z >= 1.30]
    shoulder = [point.z for point in points if 0.30 <= abs(point.x) <= 0.48 and point.z >= 1.25]
    collar_p95 = sorted(collar)[round((len(collar) - 1) * 0.95)] if collar else None
    shoulder_p95 = sorted(shoulder)[round((len(shoulder) - 1) * 0.95)] if shoulder else None
    shoulder_margin = None if collar_p95 is None or shoulder_p95 is None else collar_p95 - shoulder_p95
    if shoulder_margin is None or shoulder_margin < 0.008:
        failures.append(f"sleeve shoulder is not below collar: margin={shoulder_margin}")

    report = {
        "schema": "wearable_sleeve_interface_workflow_v1",
        "input_blend": str(options.input_blend.resolve()),
        "actor_class": scene.get("actor_class"),
        "slot": "torso_outer",
        "visible_geometry_source": "Hunyuan3D-2MV garment with ActorProfile boundary rings",
        "actor_profile_interfaces": interface_report,
        "garment_semantic_weights": garment_groups,
        "missing_semantic_weights": missing_groups,
        "masked_hand_vertices": masked_hand_vertices,
        "silhouette": {
            "collar_p95_z": collar_p95,
            "sleeve_shoulder_p95_z": shoulder_p95,
            "collar_above_shoulder_margin": shoulder_margin,
            "minimum_margin": 0.008,
        },
        "failures": failures,
        "status": "pass" if not failures else "fail",
    }
    options.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
