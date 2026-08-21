from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE_NAME = "Armature"
FRAMES = [1, 11, 21, 31, 41, 51, 61, 71]


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def make_tree(points: list[Vector]) -> KDTree:
    tree = KDTree(len(points))
    for index, point in enumerate(points):
        tree.insert(point, index)
    tree.balance()
    return tree


def bone_world_point(armature: bpy.types.Object, bone_name: str, head: bool) -> Vector:
    pose_bone = armature.pose.bones.get(bone_name)
    if pose_bone is None:
        raise RuntimeError(f"required pose bone missing: {bone_name}")
    return armature.matrix_world @ (pose_bone.head if head else pose_bone.tail)


def main() -> int:
    args = cli()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    scene = bpy.context.scene
    actor = bpy.data.objects.get(ACTOR_NAME)
    armature = bpy.data.objects.get(ARMATURE_NAME)
    garment = bpy.data.objects.get(contract["garment"])
    if actor is None or armature is None or garment is None:
        raise RuntimeError("Actor, Armature, or contract garment missing")

    group_indices = {group.name: group.index for group in garment.vertex_groups}
    actor_group_indices = {group.name: group.index for group in actor.vertex_groups}
    actor_mask = actor.vertex_groups.get(contract["body_mask"])
    if actor_mask is None:
        raise RuntimeError(f"body mask missing: {contract['body_mask']}")
    selection = contract["cuff_selection"]
    cuff_indices: dict[str, list[int]] = {}
    failures: list[str] = []
    for side_name, side in contract["sides"].items():
        forearm_index = group_indices.get(side["forearm_bone"])
        sign = 1.0 if side_name == "left" else -1.0
        indices = []
        if forearm_index is not None:
            for vertex in garment.data.vertices:
                forearm_weight = next(
                    (item.weight for item in vertex.groups if item.group == forearm_index),
                    0.0,
                )
                if (
                    forearm_weight >= selection["minimum_forearm_weight"]
                    and sign * vertex.co.x >= selection["minimum_side_x"]
                ):
                    indices.append(vertex.index)
        cuff_indices[side_name] = indices
        if not indices:
            failures.append(f"{side_name}: no semantic cuff vertices")

    limits = contract["continuity_limits"]
    masked_terminal_report = {}
    for side_name, side in contract["sides"].items():
        transition = bpy.data.objects.get(side["transition_object"])
        if transition is None:
            failures.append(f"{side_name}: ActorProfile arm transition missing")
        forearm_index = actor_group_indices.get(side["forearm_bone"])
        hand_index = actor_group_indices.get(side["hand_bone"])
        masked_forearm = 0
        masked_hand = 0
        for vertex in actor.data.vertices:
            mask_weight = next(
                (item.weight for item in vertex.groups if item.group == actor_mask.index),
                0.0,
            )
            if mask_weight <= 0.0:
                continue
            forearm_weight = next(
                (item.weight for item in vertex.groups if item.group == forearm_index),
                0.0,
            )
            hand_weight = next(
                (item.weight for item in vertex.groups if item.group == hand_index),
                0.0,
            )
            masked_forearm += forearm_weight >= 0.50
            masked_hand += hand_weight >= 0.20
        masked_terminal_report[side_name] = {
            "masked_forearm_vertices": masked_forearm,
            "masked_hand_vertices": masked_hand,
        }
        if masked_forearm > limits["maximum_masked_forearm_vertices_per_side"]:
            failures.append(f"{side_name}: body mask removes forearm vertices")
        if masked_hand > limits["maximum_masked_hand_vertices_per_side"]:
            failures.append(f"{side_name}: body mask removes hand vertices")
    frame_reports: dict[str, dict] = {}
    for frame in FRAMES:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        actor_eval = actor.evaluated_get(depsgraph)
        actor_mesh = actor_eval.to_mesh()
        actor_points = [actor_eval.matrix_world @ vertex.co for vertex in actor_mesh.vertices]
        transition_evaluated = []
        for side in contract["sides"].values():
            transition = bpy.data.objects.get(side["transition_object"])
            if transition is None:
                continue
            transition_eval = transition.evaluated_get(depsgraph)
            transition_mesh = transition_eval.to_mesh()
            actor_points.extend(
                transition_eval.matrix_world @ vertex.co
                for vertex in transition_mesh.vertices
            )
            transition_evaluated.append((transition_eval, transition_mesh))
        actor_tree = make_tree(actor_points)
        garment_eval = garment.evaluated_get(depsgraph)
        garment_mesh = garment_eval.to_mesh()
        garment_points = [garment_eval.matrix_world @ vertex.co for vertex in garment_mesh.vertices]

        side_reports = {}
        for side_name, side in contract["sides"].items():
            cuff_points = [garment_points[index] for index in cuff_indices[side_name]]
            cuff_distances = [actor_tree.find(point)[2] for point in cuff_points]
            cuff_center = (
                sum(cuff_points, Vector()) / len(cuff_points)
                if cuff_points
                else bone_world_point(armature, side["upperarm_bone"], False)
            )
            cuff_center_distance = actor_tree.find(cuff_center)[2]
            hand_center = bone_world_point(armature, side["hand_bone"], True)
            chain_distances = []
            chain_samples = 7
            for sample_index in range(1, chain_samples + 1):
                t = sample_index / (chain_samples + 1)
                sample = cuff_center.lerp(hand_center, t)
                chain_distances.append(actor_tree.find(sample)[2])
            exposed_samples = sum(
                distance <= limits["maximum_sample_to_visible_skin"]
                for distance in chain_distances
            )
            cuff_minimum = min(cuff_distances) if cuff_distances else None
            chain_maximum = max(chain_distances) if chain_distances else None
            side_reports[side_name] = {
                "semantic_cuff_vertices": len(cuff_points),
                "cuff_to_visible_skin_minimum": cuff_minimum,
                "cuff_to_visible_skin_p50": percentile(cuff_distances, 0.50),
                "cuff_to_visible_skin_p90": percentile(cuff_distances, 0.90),
                "cuff_center_to_visible_skin": cuff_center_distance,
                "exposed_chain_samples": exposed_samples,
                "chain_sample_count": len(chain_distances),
                "chain_to_visible_skin_maximum": chain_maximum,
            }
            if cuff_center_distance > limits["maximum_cuff_center_to_visible_skin"]:
                failures.append(f"frame {frame} {side_name}: sleeve cuff has no visible skin overlap")
            if exposed_samples < limits["minimum_exposed_chain_samples"]:
                failures.append(f"frame {frame} {side_name}: exposed forearm-to-hand chain is discontinuous")
        frame_reports[str(frame)] = side_reports
        garment_eval.to_mesh_clear()
        for transition_eval, _transition_mesh in transition_evaluated:
            transition_eval.to_mesh_clear()
        actor_eval.to_mesh_clear()

    report = {
        "schema": "wearable_limb_transition_audit_v1",
        "input_blend": str(args.input_blend.resolve()),
        "contract": str(args.contract.resolve()),
        "actor_class": contract["actor_class"],
        "slot": contract["slot"],
        "frames": frame_reports,
        "limits": limits,
        "masked_terminal_vertices": masked_terminal_report,
        "summary": {
            "cuff_vertices": {name: len(indices) for name, indices in cuff_indices.items()},
            "failures": failures,
        },
        "status": "pass" if not failures else "fail",
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
