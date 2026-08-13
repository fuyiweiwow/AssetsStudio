"""Audit garment boundary topology and sleeve-to-Actor bone correspondence."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--panel-membership", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--garment-name", default="GarmentCodeShirt_ActorTransfer")
    return parser.parse_args(argv)


def family(panels: list[str]) -> str:
    if any(name.startswith("left_sleeve_") for name in panels):
        return "left_sleeve"
    if any(name.startswith("right_sleeve_") for name in panels):
        return "right_sleeve"
    return "torso"


def main() -> int:
    options = cli_args()
    membership = json.loads(options.panel_membership.resolve().read_text(encoding="utf-8"))
    vertex_panels = membership["vertex_panels"]
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    garment = bpy.data.objects.get(options.garment_name)
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if garment is None or actor is None or armature is None:
        raise RuntimeError("blend is missing garment, Actor, or armature")
    if len(vertex_panels) != len(garment.data.vertices):
        raise RuntimeError("panel-membership/garment vertex count mismatch")

    edge_uses = Counter()
    for polygon in garment.data.polygons:
        for offset, vertex_index in enumerate(polygon.vertices):
            other = polygon.vertices[(offset + 1) % len(polygon.vertices)]
            edge_uses[tuple(sorted((vertex_index, other)))] += 1
    boundary_edges = [edge for edge, count in edge_uses.items() if count == 1]
    adjacency: dict[int, set[int]] = defaultdict(set)
    for start, end in boundary_edges:
        adjacency[start].add(end)
        adjacency[end].add(start)
    unseen = set(adjacency)
    boundary_components = []
    while unseen:
        todo = [unseen.pop()]
        component = []
        while todo:
            vertex_index = todo.pop()
            component.append(vertex_index)
            for neighbour in adjacency[vertex_index]:
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    todo.append(neighbour)
        points = [garment.matrix_world @ garment.data.vertices[index].co for index in component]
        panels = Counter(name for index in component for name in vertex_panels[index])
        boundary_components.append({
            "vertices": len(component),
            "degree_counts": dict(Counter(len(adjacency[index]) for index in component)),
            "bounds_m": [
                [min(point[axis] for point in points) for axis in range(3)],
                [max(point[axis] for point in points) for axis in range(3)],
            ],
            "panel_counts": dict(panels.most_common()),
        })

    actor_group_names = {group.index: group.name for group in actor.vertex_groups}
    garment_group_names = {group.index: group.name for group in garment.vertex_groups}
    action = armature.animation_data.action if armature.animation_data else None
    if action is None:
        raise RuntimeError("Actor armature has no action")
    frames = [int(action.frame_range[0]), 11, 21, 31, 41, 51, 61, int(action.frame_range[1])]
    frame_reports = []
    for frame in frames:
        armature.data.pose_position = "POSE"
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated_actor = actor.evaluated_get(depsgraph)
        evaluated_garment = garment.evaluated_get(depsgraph)
        actor_mesh = evaluated_actor.to_mesh()
        garment_mesh = evaluated_garment.to_mesh()
        actor_points = [evaluated_actor.matrix_world @ vertex.co for vertex in actor_mesh.vertices]
        actor_faces = [tuple(polygon.vertices) for polygon in actor_mesh.polygons]
        bvh = BVHTree.FromPolygons(actor_points, actor_faces, all_triangles=False)
        actor_bones = Counter()
        garment_bones = Counter()
        pair_counts = Counter()
        by_family = defaultdict(Counter)
        for vertex_index, vertex in enumerate(garment_mesh.vertices):
            vertex_family = family(vertex_panels[vertex_index])
            if vertex_family == "torso":
                continue
            point = evaluated_garment.matrix_world @ vertex.co
            nearest = bvh.find_nearest(point)
            if nearest is None:
                continue
            _location, _normal, face_index, _distance = nearest
            actor_weights = Counter()
            for actor_index in actor_faces[face_index]:
                for assignment in actor.data.vertices[actor_index].groups:
                    actor_weights[actor_group_names.get(assignment.group, str(assignment.group))] += assignment.weight
            garment_weights = Counter(
                {
                    garment_group_names.get(assignment.group, str(assignment.group)): assignment.weight
                    for assignment in garment.data.vertices[vertex_index].groups
                }
            )
            actor_bone = actor_weights.most_common(1)[0][0] if actor_weights else "none"
            garment_bone = garment_weights.most_common(1)[0][0] if garment_weights else "none"
            actor_bones[actor_bone] += 1
            garment_bones[garment_bone] += 1
            pair_counts[(actor_bone, garment_bone)] += 1
            by_family[vertex_family][actor_bone] += 1
        frame_reports.append({
            "frame": frame,
            "nearest_actor_bones": dict(actor_bones.most_common()),
            "garment_dominant_bones": dict(garment_bones.most_common()),
            "actor_to_garment_pairs": [
                {"actor": pair[0], "garment": pair[1], "count": count}
                for pair, count in pair_counts.most_common()
            ],
            "nearest_actor_bones_by_family": {
                name: dict(counts.most_common()) for name, counts in by_family.items()
            },
        })
        evaluated_actor.to_mesh_clear()
        evaluated_garment.to_mesh_clear()

    report = {
        "schema": "assetsstudio_actor_garment_seam_and_bones_v1",
        "blend": str(options.blend.resolve()),
        "topology": {
            "vertices": len(garment.data.vertices),
            "polygons": len(garment.data.polygons),
            "edge_use_counts": dict(Counter(edge_uses.values())),
            "boundary_edges": len(boundary_edges),
            "boundary_components": sorted(
                boundary_components, key=lambda item: item["vertices"], reverse=True
            ),
            "nonmanifold_edges": sum(count > 2 for count in edge_uses.values()),
        },
        "frames": frame_reports,
        "status": "review_required",
    }
    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "boundary_components": len(boundary_components),
        "boundary_component_sizes": sorted((item["vertices"] for item in boundary_components), reverse=True),
        "nonmanifold_edges": report["topology"]["nonmanifold_edges"],
        "frame_actor_bones": [
            {"frame": item["frame"], "bones": item["nearest_actor_bones"]}
            for item in frame_reports
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
