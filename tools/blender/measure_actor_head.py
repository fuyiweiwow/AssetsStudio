"""Measure an Actor head from the mesh's head bone weights.

The output keeps raw Blender-world dimensions and an optional centimetre
calibration derived from the existing Actor body-height contract. This avoids
guessing hood dimensions from a generic human head.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", default="ChibiBaseMesh_AccuRIG_InputMesh")
    parser.add_argument("--head-bone", default="CC_Base_Head")
    parser.add_argument("--weight-threshold", type=float, default=0.25)
    parser.add_argument("--body-measurements", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    blender_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = parser.parse_args(blender_args)

    obj = bpy.data.objects.get(args.mesh)
    if obj is None or obj.type != "MESH":
        raise RuntimeError(f"Mesh not found: {args.mesh}")
    group = obj.vertex_groups.get(args.head_bone)
    if group is None:
        raise RuntimeError(f"Vertex group not found: {args.head_bone}")

    world_vertices = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    selected = []
    for vertex, world in zip(obj.data.vertices, world_vertices):
        if any(item.group == group.index and item.weight >= args.weight_threshold for item in vertex.groups):
            selected.append(world)
    if len(selected) < 10:
        raise RuntimeError(f"Too few head-weighted vertices: {len(selected)}")

    minimum = [min(vertex[index] for vertex in selected) for index in range(3)]
    maximum = [max(vertex[index] for vertex in selected) for index in range(3)]
    raw_dimensions = [maximum[index] - minimum[index] for index in range(3)]

    payload = {
        "schema": "assetsstudio_actor_head_measurements_v1",
        "source_mesh": args.mesh,
        "source_head_bone": args.head_bone,
        "weight_threshold": args.weight_threshold,
        "vertex_count": len(selected),
        "world_bbox": {"min": minimum, "max": maximum},
        "world_dimensions": {"x": raw_dimensions[0], "y": raw_dimensions[1], "z": raw_dimensions[2]},
        "calibration": None,
    }
    if args.body_measurements:
        body_payload = json.loads(args.body_measurements.read_text(encoding="utf-8"))
        body_height_cm = float(body_payload["body"]["height"])
        mesh_vertices = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
        mesh_height = max(vertex.z for vertex in mesh_vertices) - min(vertex.z for vertex in mesh_vertices)
        scale_cm_per_world_unit = body_height_cm / mesh_height
        payload["calibration"] = {
            "body_height_cm": body_height_cm,
            "mesh_height_world": mesh_height,
            "cm_per_world_unit": scale_cm_per_world_unit,
            "dimensions_cm": {axis: value * scale_cm_per_world_unit for axis, value in zip(("x", "y", "z"), raw_dimensions)},
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


main()
