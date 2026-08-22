"""Validate the deterministic Actor V2 layered hair in a compiled Blend."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--object", default="HeadHair_DefaultAdventurer_V2_Layered")
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(raw)


def connected_components(obj: bpy.types.Object) -> int:
    adjacency: list[list[int]] = [[] for _ in obj.data.vertices]
    for edge in obj.data.edges:
        a, b = edge.vertices
        adjacency[a].append(b)
        adjacency[b].append(a)
    unseen = set(range(len(adjacency)))
    count = 0
    while unseen:
        count += 1
        stack = [unseen.pop()]
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
    return count


def main() -> int:
    options = args()
    bpy.ops.wm.open_mainfile(filepath=str(options.input.resolve()))
    hair = bpy.data.objects.get(options.object)
    if hair is None or hair.type != "MESH":
        raise RuntimeError(f"layered hair object not found: {options.object}")
    edge_face_counts = [0] * len(hair.data.edges)
    edge_lookup = {tuple(sorted(edge.vertices)): edge.index for edge in hair.data.edges}
    for polygon in hair.data.polygons:
        vertices = list(polygon.vertices)
        for index, first in enumerate(vertices):
            second = vertices[(index + 1) % len(vertices)]
            edge_face_counts[edge_lookup[tuple(sorted((first, second)))]] += 1
    world_points = [hair.matrix_world @ vertex.co for vertex in hair.data.vertices]
    front_points = [point for point in world_points if point.y <= -0.25]
    minimum = Vector(tuple(min(point[axis] for point in world_points) for axis in range(3)))
    maximum = Vector(tuple(max(point[axis] for point in world_points) for axis in range(3)))
    old_hair = [
        obj.name
        for obj in bpy.data.objects
        if obj != hair and (obj.name == "HairCandidate_Blend" or obj.get("assetsstudio_asset_id") == "head_hair/default_adventurer_v1")
    ]
    gates = {
        "finite_geometry": all(math.isfinite(value) for point in world_points for value in point),
        "closed_manifold_components": all(count == 2 for count in edge_face_counts),
        "one_runtime_object": not old_hair,
        "slot_metadata": hair.get("assetsstudio_slot_id") == "head_hair",
        "head_bone_parent": hair.parent is not None and hair.parent.type == "ARMATURE" and hair.parent_type == "BONE" and hair.parent_bone == "CC_Base_Head",
        "bounded_actor_scale": maximum.x - minimum.x <= 1.25 and maximum.z - minimum.z <= 1.15,
        # Back hair intentionally reaches the nape, so the global Z minimum
        # cannot diagnose eye coverage.  Only the front-facing envelope owns
        # the eye/forehead clearance gate.
        "front_envelope_above_eyes": bool(front_points) and min(point.z for point in front_points) >= 1.40,
    }
    report = {
        "schema": "assetsstudio_actor_v2_layered_hair_validation_v1",
        "status": "pass" if all(gates.values()) else "review",
        "input": str(options.input.resolve()),
        "object": hair.name,
        "vertices": len(hair.data.vertices),
        "faces": len(hair.data.polygons),
        "components": connected_components(hair),
        "non_manifold_edge_count": sum(count != 2 for count in edge_face_counts),
        "bounds_min": list(minimum),
        "bounds_max": list(maximum),
        "old_hair_objects": old_hair,
        "gates": gates,
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ACTOR_V2_LAYERED_HAIR_VALIDATION_{report['status'].upper()} report={options.output.resolve()}")
    if report["status"] != "pass":
        raise RuntimeError(json.dumps(gates, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
