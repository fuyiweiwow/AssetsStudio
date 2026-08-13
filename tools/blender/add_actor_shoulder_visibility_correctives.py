"""Add pose correctives from Actor-normal shoulder visibility ray hits."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


INITIAL_CONFIGS = (
    {
        "name": "ShoulderVisibility_CycleBoundary",
        "frames": (2, 71),
        "keys": ((1, 1.0), (3, 1.0), (7, 0.45), (11, 0.0), (63, 0.0), (67, 0.45), (71, 1.0)),
    },
    {"name": "ShoulderVisibility_R28", "frames": (28,), "keys": ((22, 0.0), (28, 1.0), (34, 0.0))},
    {"name": "ShoulderVisibility_58", "frames": (58,), "keys": ((52, 0.0), (58, 1.0), (64, 0.0))},
)

RESIDUAL_CONFIGS = (
    {"name": "ShoulderVisibility_Residual10", "frames": (10,), "keys": ((6, 0.0), (10, 1.0), (14, 0.0))},
    {"name": "ShoulderVisibility_Residual21", "frames": (21,), "keys": ((13, 0.0), (18, 0.75), (21, 1.0), (25, 0.0))},
    {"name": "ShoulderVisibility_Residual38", "frames": (38,), "keys": ((32, 0.0), (38, 1.0), (44, 0.0))},
    {"name": "ShoulderVisibility_Residual53", "frames": (53,), "keys": ((49, 0.0), (53, 1.0), (58, 0.0))},
    {"name": "ShoulderVisibility_Residual65", "frames": (65,), "keys": ((59, 0.0), (65, 1.0), (69, 0.0))},
)


def args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--ray-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--garment-name", default="GarmentCodeShirt_ActorTransfer")
    parser.add_argument("--clearance", type=float, default=0.0015)
    parser.add_argument("--max-rest-displacement", type=float, default=0.008)
    parser.add_argument("--smooth-iterations", type=int, default=2)
    parser.add_argument("--falloff-rings", type=int, default=1)
    parser.add_argument("--falloff-decay", type=float, default=0.55)
    parser.add_argument("--pass-name", choices=("initial", "residual"), default="initial")
    return parser.parse_args(argv)


def blended_deform_matrix(garment, armature, vertex, group_names) -> Matrix:
    object_to_armature = armature.matrix_world.inverted() @ garment.matrix_world
    armature_to_object = garment.matrix_world.inverted() @ armature.matrix_world
    result = Matrix(((0.0, 0.0, 0.0, 0.0),) * 4)
    total = 0.0
    for assignment in vertex.groups:
        name = group_names.get(assignment.group)
        pose_bone = armature.pose.bones.get(name) if name else None
        rest_bone = armature.data.bones.get(name) if name else None
        if pose_bone is None or rest_bone is None or assignment.weight <= 0.0:
            continue
        result += (
            armature_to_object @ pose_bone.matrix @ rest_bone.matrix_local.inverted() @ object_to_armature
        ) * assignment.weight
        total += assignment.weight
    return result * (1.0 / total) if total > 1e-8 else Matrix.Identity(4)


def main() -> int:
    options = args()
    rays = json.loads(options.ray_report.resolve().read_text(encoding="utf-8"))
    by_frame = {item["frame"]: item for item in rays["frames"]}
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    scene = bpy.context.scene
    garment = bpy.data.objects.get(options.garment_name)
    armature = bpy.data.objects.get("Armature")
    if garment is None or armature is None or garment.data.shape_keys is None:
        raise RuntimeError("source must contain garment, Armature, and Basis shape")
    armature.data.pose_position = "POSE"
    basis = garment.data.shape_keys.key_blocks.get("Basis")
    group_names = {group.index: group.name for group in garment.vertex_groups}
    adjacency = defaultdict(set)
    for edge in garment.data.edges:
        a, b = edge.vertices
        adjacency[a].add(b)
        adjacency[b].add(a)
    reports = []
    configs = INITIAL_CONFIGS if options.pass_name == "initial" else RESIDUAL_CONFIGS

    for config in configs:
        requested: dict[int, Vector] = {}
        source_ray_hits = 0
        for source_frame in config["frames"]:
            frame_report = by_frame.get(source_frame)
            if frame_report is None:
                raise RuntimeError(f"ray report is missing frame {source_frame}")
            scene.frame_set(source_frame)
            bpy.context.view_layer.update()
            source_ray_hits += len(frame_report["items"])
            for item in frame_report["items"]:
                world_delta = Vector(item["actor_normal"]).normalized() * (
                    float(item["behind_distance_m"]) + options.clearance
                )
                for vertex_index in item["garment_vertices"]:
                    local_pose_delta = garment.matrix_world.inverted().to_3x3() @ world_delta
                    deform = blended_deform_matrix(
                        garment, armature, garment.data.vertices[vertex_index], group_names
                    )
                    try:
                        rest_delta = deform.to_3x3().inverted() @ local_pose_delta
                    except ValueError:
                        continue
                    if rest_delta.length > options.max_rest_displacement:
                        rest_delta.normalize()
                        rest_delta *= options.max_rest_displacement
                    previous = requested.get(vertex_index)
                    if previous is None or rest_delta.length > previous.length:
                        requested[vertex_index] = rest_delta

        direct = set(requested)
        accumulated: dict[int, Vector] = defaultdict(Vector)
        accumulated_weights: dict[int, float] = defaultdict(float)
        distances: dict[int, int] = {}
        for source_index, source_delta in requested.items():
            frontier = {source_index}
            visited = {source_index}
            for distance in range(options.falloff_rings + 1):
                weight = options.falloff_decay ** distance
                for index in frontier:
                    accumulated[index] += source_delta * weight
                    accumulated_weights[index] += weight
                    previous_distance = distances.get(index)
                    if previous_distance is None or distance < previous_distance:
                        distances[index] = distance
                next_frontier = {
                    neighbour
                    for index in frontier
                    for neighbour in adjacency[index]
                    if neighbour not in visited
                }
                visited.update(next_frontier)
                frontier = next_frontier
                if not frontier:
                    break
        target = set(accumulated)
        values = {
            index: accumulated[index] / accumulated_weights[index]
            for index in target
        }
        # Keep ray-confirmed vertices exact; extra rings only feather their edge.
        values.update(requested)
        for _ in range(options.smooth_iterations):
            updated = {}
            for index in target:
                neighbours = [item for item in adjacency[index] if item in target]
                average = sum((values[item] for item in neighbours), Vector()) / max(len(neighbours), 1)
                # Preserve most of the ray-confirmed displacement and use the
                # added ring only as a soft falloff.
                direct_weight = 0.92 if index in direct else 0.68
                updated[index] = values[index] * direct_weight + average * (1.0 - direct_weight)
            values = updated

        old = garment.data.shape_keys.key_blocks.get(config["name"])
        if old is not None:
            garment.shape_key_remove(old)
        key = garment.shape_key_add(name=config["name"], from_mix=False)
        moved = 0
        max_delta = 0.0
        for index, delta in values.items():
            if delta.length <= 1e-7:
                continue
            key.data[index].co = basis.data[index].co + delta
            moved += 1
            max_delta = max(max_delta, delta.length)
        key.value = 0.0
        for frame, value in config["keys"]:
            key.value = value
            key.keyframe_insert(data_path="value", frame=frame, group="ActorShoulderVisibility")
        action = key.id_data.animation_data.action if key.id_data.animation_data else None
        if action is not None:
            for curve in action.fcurves:
                if curve.data_path.endswith(f'key_blocks["{key.name}"].value'):
                    for point in curve.keyframe_points:
                        point.interpolation = "BEZIER"
        key.value = 0.0
        reports.append({
            "name": key.name,
            "source_frames": config["frames"],
            "source_ray_hits": source_ray_hits,
            "direct_vertices": len(direct),
            "moved_vertices": moved,
            "max_rest_displacement_m": max_delta,
            "falloff_ring_counts": dict(Counter(distances.values())),
            "influence_keys": config["keys"],
        })

    garment["assetsstudio_shoulder_visibility_correctives"] = "Actor-normal inward-only ray diagnostic v1"
    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    report = {
        "schema": "assetsstudio_actor_shoulder_visibility_correctives_v1",
        "source": str(options.blend.resolve()),
        "ray_report": str(options.ray_report.resolve()),
        "output": str(output),
        "clearance_m": options.clearance,
        "falloff_rings": options.falloff_rings,
        "falloff_decay": options.falloff_decay,
        "pass_name": options.pass_name,
        "policy": "GarmentCode Basis unchanged; removable fixed-action pose keys driven only by Actor-normal visibility rays",
        "correctives": reports,
    }
    report_path = options.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
