"""Measure triangle-overlap pairs between an Actor OBJ and garment OBJ."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", type=Path, required=True)
    parser.add_argument("--garment", type=Path, required=True)
    parser.add_argument("--actor-scale", type=float, required=True)
    parser.add_argument("--flip-garment-depth", action="store_true")
    parser.add_argument("--garment-depth-scale", type=float, default=1.0)
    parser.add_argument("--output", type=Path, required=True)
    blender_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(blender_args)


def import_one(path: Path) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(path))
    created = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    if len(created) != 1:
        raise RuntimeError(f"expected one mesh from {path}, got {len(created)}")
    return created[0]


def evaluated_mesh(obj: bpy.types.Object) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        vertices = [tuple(evaluated.matrix_world @ vertex.co) for vertex in mesh.vertices]
        faces = [tuple(poly.vertices) for poly in mesh.polygons]
    finally:
        evaluated.to_mesh_clear()
    return vertices, faces


def main() -> None:
    options = args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    actor = import_one(options.actor)
    actor.scale = (options.actor_scale,) * 3
    garment = import_one(options.garment)
    if options.flip_garment_depth:
        garment.scale.z *= -1.0
    garment.scale.z *= options.garment_depth_scale
    actor_vertices, actor_faces = evaluated_mesh(actor)
    garment_vertices, garment_faces = evaluated_mesh(garment)
    actor_bvh = BVHTree.FromPolygons(actor_vertices, actor_faces, all_triangles=False)
    garment_bvh = BVHTree.FromPolygons(garment_vertices, garment_faces, all_triangles=False)
    overlap_pairs = garment_bvh.overlap(actor_bvh)

    def bounds(vertices):
        return {
            "min": [min(v[i] for v in vertices) for i in range(3)],
            "max": [max(v[i] for v in vertices) for i in range(3)],
        }

    report = {
        "schema": "assetsstudio_obj_pair_overlap_audit_v1",
        "actor": str(options.actor.resolve()),
        "garment": str(options.garment.resolve()),
        "actor_scale": options.actor_scale,
        "flip_garment_depth": options.flip_garment_depth,
        "garment_depth_scale": options.garment_depth_scale,
        "actor_vertices": len(actor_vertices),
        "garment_vertices": len(garment_vertices),
        "actor_bounds": bounds(actor_vertices),
        "garment_bounds": bounds(garment_vertices),
        "triangle_overlap_pairs": len(overlap_pairs),
        "status": "review_required" if overlap_pairs else "no_bvh_overlap",
        "note": "BVH triangle overlap is a coarse rest-state diagnostic, not a cloth simulation result.",
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


main()
