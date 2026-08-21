from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE_NAME = "Armature"
MASK_NAME = "WearableMask_AdventurerRemainingV1"
FRAMES = [1, 11, 21, 31, 41, 51, 61, 71]
OBJECTS = {
    "boot_left": ("Wearable_Adventurer_Boot_L_V1", "CC_Base_L_Foot", "feet_outer"),
    "boot_right": ("Wearable_Adventurer_Boot_R_V1", "CC_Base_R_Foot", "feet_outer"),
    "bracer_left": ("Wearable_Adventurer_Bracer_L_V1", "CC_Base_L_Forearm", "wrist_accessory"),
    "bracer_right": ("Wearable_Adventurer_Bracer_R_V1", "CC_Base_R_Forearm", "wrist_accessory"),
    "backpack": ("Wearable_Adventurer_Backpack_V1", "CC_Base_Spine02", "back_accessory"),
}
BRACER_CHAINS = {
    "bracer_left": ("CC_Base_L_Forearm", "CC_Base_L_Hand"),
    "bracer_right": ("CC_Base_R_Forearm", "CC_Base_R_Hand"),
}


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def bounds(points: list[Vector]) -> tuple[Vector, Vector]:
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    return low, high


def center(points: list[Vector]) -> Vector:
    return sum(points, Vector()) / len(points)


def group_weight(vertex: bpy.types.MeshVertex, group_index: int | None) -> float:
    if group_index is None:
        return 0.0
    return next((item.weight for item in vertex.groups if item.group == group_index), 0.0)


def main() -> int:
    options = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    scene = bpy.context.scene
    actor = bpy.data.objects.get(ACTOR_NAME)
    armature = bpy.data.objects.get(ARMATURE_NAME)
    if actor is None or armature is None:
        raise RuntimeError("Actor or Armature missing")
    failures = []
    object_report = {}
    for key, (name, expected_bone, expected_slot) in OBJECTS.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{key}: object missing")
            continue
        used_groups = sorted(group.name for group in obj.vertex_groups if any(
            group.index == item.group and item.weight > 0.0
            for vertex in obj.data.vertices for item in vertex.groups
        ))
        modifiers = [modifier for modifier in obj.modifiers if modifier.type == "ARMATURE"]
        if used_groups != [expected_bone]:
            failures.append(f"{key}: expected rigid {expected_bone}, got {used_groups}")
        if len(modifiers) != 1 or modifiers[0].object != armature:
            failures.append(f"{key}: invalid Actor armature binding")
        if obj.get("wearable_slot") != expected_slot or "Hunyuan3D-2MV" not in obj.get("source_kind", ""):
            failures.append(f"{key}: generated-source slot metadata missing")
        object_report[key] = {
            "object": name,
            "vertices": len(obj.data.vertices),
            "faces": len(obj.data.polygons),
            "used_groups": used_groups,
            "slot": obj.get("wearable_slot"),
            "source_kind": obj.get("source_kind"),
        }

    mask = actor.vertex_groups.get(MASK_NAME)
    if mask is None:
        failures.append("remaining-slot body mask missing")
        masked_hands = None
    else:
        group_indices = {group.name: group.index for group in actor.vertex_groups}
        masked_hands = {}
        for side in ("L", "R"):
            hand_index = group_indices.get(f"CC_Base_{side}_Hand")
            count = sum(
                group_weight(vertex, hand_index) >= 0.15 and group_weight(vertex, mask.index) > 0.0
                for vertex in actor.data.vertices
            )
            masked_hands[side] = count
            if count:
                failures.append(f"{side}: remaining-slot mask hides {count} hand vertices")

    frame_reports = {}
    topology = {}
    for frame in FRAMES:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        actor_eval = actor.evaluated_get(depsgraph)
        actor_mesh = actor_eval.to_mesh()
        visible_actor_points = [actor_eval.matrix_world @ vertex.co for vertex in actor_mesh.vertices]
        report = {"visible_actor_vertices": len(visible_actor_points), "objects": {}}
        evaluated = {}
        for key, (name, _bone, _slot) in OBJECTS.items():
            obj = bpy.data.objects.get(name)
            if obj is None:
                continue
            obj_eval = obj.evaluated_get(depsgraph)
            mesh = obj_eval.to_mesh()
            points = [obj_eval.matrix_world @ vertex.co for vertex in mesh.vertices]
            current_topology = [len(mesh.vertices), len(mesh.polygons)]
            if key not in topology:
                topology[key] = current_topology
            elif topology[key] != current_topology:
                failures.append(f"frame {frame} {key}: evaluated topology changed")
            low, high = bounds(points)
            item = {"center": list(center(points)), "low": list(low), "high": list(high), "topology": current_topology}
            if key.startswith("boot_"):
                inset_low = low + (high - low) * 0.08
                # The top 44% is the intentional open ankle/calf cuff.  The
                # generated boot's solid toe/sole core ends at 56% height.
                # Reject visible Actor geometry only inside the boot's solid
                # lower core, not inside the open terminal band.
                inset_high = high - (high - low) * Vector((0.08, 0.08, 0.44))
                inside_points = [
                    point for point in visible_actor_points
                    if inset_low.x <= point.x <= inset_high.x
                    and inset_low.y <= point.y <= inset_high.y
                    and inset_low.z <= point.z <= inset_high.z
                ]
                visible_inside = len(inside_points)
                item["visible_actor_vertices_inside_boot"] = visible_inside
                item["visible_inside_samples"] = [list(point) for point in inside_points[:8]]
                if visible_inside:
                    failures.append(f"frame {frame} {key}: {visible_inside} visible Actor vertices remain inside boot")
            if key in BRACER_CHAINS:
                elbow_bone, wrist_bone = BRACER_CHAINS[key]
                elbow = armature.matrix_world @ armature.pose.bones[elbow_bone].head
                wrist = armature.matrix_world @ armature.pose.bones[wrist_bone].head
                center_offset = (center(points) - elbow.lerp(wrist, 0.50)).length
                item["center_to_forearm_axis_midpoint"] = center_offset
                if center_offset > 0.065:
                    failures.append(f"frame {frame} {key}: bracer not centered on forearm ({center_offset})")
            report["objects"][key] = item
            evaluated[key] = (obj_eval, mesh)
        for obj_eval, mesh in evaluated.values():
            obj_eval.to_mesh_clear()
        actor_eval.to_mesh_clear()
        frame_reports[str(frame)] = report

    result = {
        "schema": "adventurer_remaining_generated_slots_audit_v1",
        "input_blend": str(options.input_blend.resolve()),
        "objects": object_report,
        "masked_hand_vertices": masked_hands,
        "frames": frame_reports,
        "limits": {"visible_actor_vertices_inside_boot": 0, "maximum_bracer_center_offset": 0.065},
        "failures": failures,
        "status": "pass" if not failures else "fail",
    }
    options.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
