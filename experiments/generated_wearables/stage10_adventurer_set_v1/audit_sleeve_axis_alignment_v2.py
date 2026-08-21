from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
STAGE9 = ROOT.parent / "stage9_hunyuan_adapter_transfer_v1"
if str(STAGE9) not in sys.path:
    sys.path.insert(0, str(STAGE9))

import build_hunyuan_jacket_adapter_v1 as compiler  # noqa: E402


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
GARMENT_NAME = "Wearable_Adventurer_TorsoOuterV1"
MASK_NAME = "WearableMask_AdventurerTorsoOuterV1"
FRAMES = [1, 11, 21, 31, 41, 51, 61, 71]
SIDES = {
    "left": (1, "ActorProfile_ArmTransition_L_ChibiActorV1", "CC_Base_L_Upperarm", "CC_Base_L_Forearm", "CC_Base_L_Hand"),
    "right": (-1, "ActorProfile_ArmTransition_R_ChibiActorV1", "CC_Base_R_Upperarm", "CC_Base_R_Forearm", "CC_Base_R_Hand"),
}


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def group_weight(vertex: bpy.types.MeshVertex, group_index: int | None) -> float:
    if group_index is None:
        return 0.0
    return next((item.weight for item in vertex.groups if item.group == group_index), 0.0)


def center(points: list[Vector]) -> Vector:
    return sum(points, Vector()) / len(points)


def main() -> int:
    options = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    scene = bpy.context.scene
    scene.frame_set(1)
    actor = bpy.data.objects.get(ACTOR_NAME)
    garment = bpy.data.objects.get(GARMENT_NAME)
    if actor is None or garment is None:
        raise RuntimeError("Actor or generated torso garment missing")

    failures: list[str] = []
    mask = actor.vertex_groups.get(MASK_NAME)
    if mask is None:
        raise RuntimeError("torso body mask missing")

    garment_points = [garment.matrix_world @ vertex.co for vertex in garment.data.vertices]
    collar_heights = [point.z for point in garment_points if abs(point.x) <= 0.18 and point.z >= 1.30]
    shoulder_heights = [point.z for point in garment_points if 0.30 <= abs(point.x) <= 0.48 and point.z >= 1.25]
    collar_p95 = percentile(collar_heights, 0.95)
    shoulder_p95 = percentile(shoulder_heights, 0.95)
    shoulder_margin = None if collar_p95 is None or shoulder_p95 is None else collar_p95 - shoulder_p95
    if shoulder_margin is None or shoulder_margin < 0.008:
        failures.append(f"sleeve shoulder is not below collar: margin={shoulder_margin}")

    group_indices = {group.name: group.index for group in actor.vertex_groups}
    rest_actor_points = [actor.matrix_world @ vertex.co for vertex in actor.data.vertices]
    selections: dict[str, dict[str, list[int]]] = {}
    for side_name, (side, transition_name, upperarm_name, forearm_name, hand_name) in SIDES.items():
        transition = bpy.data.objects.get(transition_name)
        if transition is None:
            failures.append(f"{side_name}: sleeve transition missing")
            continue
        if transition.get("actor_profile_component") != "short_sleeve_cloth_transition":
            failures.append(f"{side_name}: transition is not the cloth terminal band")
        if not transition.data.materials or not garment.data.materials or transition.data.materials[0] != garment.data.materials[0]:
            failures.append(f"{side_name}: transition does not use garment material")

        terminal_indices = []
        for vertex in transition.data.vertices:
            world = transition.matrix_world @ vertex.co
            parameter, distance = compiler.target_arm_coordinates(world, side)
            if parameter >= 0.90 and distance <= 0.27:
                terminal_indices.append(vertex.index)

        upperarm_index = group_indices.get(upperarm_name)
        forearm_index = group_indices.get(forearm_name)
        actor_ring_indices = []
        for vertex, world in zip(actor.data.vertices, rest_actor_points):
            parameter, distance = compiler.target_arm_coordinates(world, side)
            limb_weight = group_weight(vertex, upperarm_index) + group_weight(vertex, forearm_index)
            if parameter >= 0.88 and distance <= 0.24 and limb_weight >= 0.30:
                actor_ring_indices.append(vertex.index)

        masked_hand = sum(
            group_weight(vertex, group_indices.get(hand_name)) >= 0.20
            and group_weight(vertex, mask.index) > 0.0
            for vertex in actor.data.vertices
        )
        if len(terminal_indices) < 12:
            failures.append(f"{side_name}: terminal sleeve ring is incomplete")
        if len(actor_ring_indices) < 12:
            failures.append(f"{side_name}: Actor arm ring is incomplete")
        if masked_hand:
            failures.append(f"{side_name}: body mask hides {masked_hand} hand vertices")
        selections[side_name] = {
            "terminal": terminal_indices,
            "actor_ring": actor_ring_indices,
            "masked_hand": masked_hand,
        }

    # The runtime body mask changes evaluated topology.  Disable it only for
    # the semantic arm-ring measurement so rest vertex indices remain stable.
    mask_modifiers = [modifier for modifier in actor.modifiers if modifier.type == "MASK"]
    mask_states = [(modifier, modifier.show_viewport, modifier.show_render) for modifier in mask_modifiers]
    for modifier in mask_modifiers:
        modifier.show_viewport = False
        modifier.show_render = False

    frame_reports: dict[str, dict] = {}
    for frame in FRAMES:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        actor_eval = actor.evaluated_get(depsgraph)
        actor_mesh = actor_eval.to_mesh()
        actor_points = [actor_eval.matrix_world @ vertex.co for vertex in actor_mesh.vertices]
        frame_report = {}
        for side_name, (_side, transition_name, *_bones) in SIDES.items():
            if side_name not in selections:
                continue
            transition = bpy.data.objects[transition_name]
            transition_eval = transition.evaluated_get(depsgraph)
            transition_mesh = transition_eval.to_mesh()
            transition_points = [transition_eval.matrix_world @ vertex.co for vertex in transition_mesh.vertices]
            terminal_points = [transition_points[index] for index in selections[side_name]["terminal"]]
            ring_points = [actor_points[index] for index in selections[side_name]["actor_ring"]]
            center_offset = (center(terminal_points) - center(ring_points)).length
            radii = [(point - center(ring_points)).length for point in terminal_points]
            frame_report[side_name] = {
                "terminal_vertices": len(terminal_points),
                "actor_ring_vertices": len(ring_points),
                "terminal_center_to_actor_arm_center": center_offset,
                "terminal_radius_p10": percentile(radii, 0.10),
                "terminal_radius_p90": percentile(radii, 0.90),
                "masked_hand_vertices": selections[side_name]["masked_hand"],
            }
            if center_offset > 0.035:
                failures.append(f"frame {frame} {side_name}: arm does not pass through sleeve center ({center_offset})")
            transition_eval.to_mesh_clear()
        actor_eval.to_mesh_clear()
        frame_reports[str(frame)] = frame_report

    for modifier, show_viewport, show_render in mask_states:
        modifier.show_viewport = show_viewport
        modifier.show_render = show_render

    report = {
        "schema": "wearable_sleeve_axis_alignment_v2",
        "input_blend": str(options.input_blend.resolve()),
        "actor_class": scene.get("actor_class"),
        "slot": "torso_outer",
        "silhouette": {
            "collar_p95_z": collar_p95,
            "sleeve_shoulder_p95_z": shoulder_p95,
            "collar_above_shoulder_margin": shoulder_margin,
            "minimum_margin": 0.008,
        },
        "frames": frame_reports,
        "limits": {"maximum_terminal_center_offset": 0.035, "maximum_masked_hand_vertices": 0},
        "failures": failures,
        "status": "pass" if not failures else "fail",
    }
    options.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
