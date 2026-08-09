"""Measure front-view body exposure inside a fitted mesh's crown region.

This is a generic projection-space validator for fitted head shells. It casts
rays from the front, records body hits that are not occluded by the fitted
mesh, and writes a deterministic JSON report for before/after comparison.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--fitted-object", required=True)
    parser.add_argument("--body-object", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--half-width", type=float, default=0.16)
    parser.add_argument("--top-depth", type=float, default=0.36)
    parser.add_argument("--samples-x", type=int, default=65)
    parser.add_argument("--samples-z", type=int, default=97)
    return parser.parse_args(argv)


def evaluated_world_mesh(obj: bpy.types.Object) -> tuple[list[Vector], list[tuple[int, ...]]]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
        return vertices, polygons
    finally:
        evaluated.to_mesh_clear()


def world_bvh(obj: bpy.types.Object) -> tuple[BVHTree, Vector, Vector]:
    vertices, polygons = evaluated_world_mesh(obj)
    if not vertices or not polygons:
        raise RuntimeError(f"object has no evaluated surface: {obj.name}")
    low = Vector(tuple(min(point[axis] for point in vertices) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in vertices) for axis in range(3)))
    return BVHTree.FromPolygons(vertices, polygons, all_triangles=False), low, high


def ray_distance(tree: BVHTree, origin: Vector) -> float | None:
    hit = tree.ray_cast(origin, Vector((0.0, 1.0, 0.0)))
    return float(hit[3]) if hit[0] is not None else None


def main() -> int:
    options = cli_args()
    if options.samples_x < 3 or options.samples_z < 3:
        raise RuntimeError("sample counts must be at least three")
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    fitted = bpy.data.objects.get(options.fitted_object)
    body = bpy.data.objects.get(options.body_object)
    if fitted is None or fitted.type != "MESH":
        raise RuntimeError(f"missing fitted mesh: {options.fitted_object}")
    if body is None or body.type != "MESH":
        raise RuntimeError(f"missing body mesh: {options.body_object}")
    bpy.context.scene.frame_set(int(bpy.context.scene.frame_start))
    bpy.context.view_layer.update()
    fitted_bvh, fitted_low, fitted_high = world_bvh(fitted)
    body_bvh, body_low, _ = world_bvh(body)
    origin_y = min(fitted_low.y, body_low.y) - 1.0
    gaps: list[dict[str, float]] = []
    body_samples = 0
    covered_samples = 0
    centerline: list[dict[str, float | bool | None]] = []
    for z_index in range(options.samples_z):
        z = fitted_high.z - options.top_depth * z_index / (options.samples_z - 1)
        for x_index in range(options.samples_x):
            x = -options.half_width + 2.0 * options.half_width * x_index / (options.samples_x - 1)
            origin = Vector((x, origin_y, z))
            body_distance = ray_distance(body_bvh, origin)
            fitted_distance = ray_distance(fitted_bvh, origin)
            if body_distance is None:
                continue
            body_samples += 1
            covered = fitted_distance is not None and fitted_distance < body_distance - 0.001
            if covered:
                covered_samples += 1
            else:
                gaps.append({"x": round(x, 6), "z": round(z, 6)})
            if x_index == options.samples_x // 2:
                centerline.append(
                    {
                        "z": round(z, 6),
                        "covered": covered,
                        "body_distance": round(body_distance, 6),
                        "fitted_distance": round(fitted_distance, 6) if fitted_distance is not None else None,
                    }
                )
    report = {
        "schema": "assetsstudio_front_surface_coverage_v1",
        "blend": str(options.blend.resolve()),
        "fitted_object": fitted.name,
        "body_object": body.name,
        "region": {
            "half_width": options.half_width,
            "top_depth": options.top_depth,
            "samples_x": options.samples_x,
            "samples_z": options.samples_z,
        },
        "fitted_bounds": {
            "low": [round(value, 6) for value in fitted_low],
            "high": [round(value, 6) for value in fitted_high],
        },
        "body_samples": body_samples,
        "covered_samples": covered_samples,
        "gap_samples": len(gaps),
        "coverage_ratio": round(covered_samples / body_samples, 6) if body_samples else None,
        "gap_bounds": {
            "x_min": min((point["x"] for point in gaps), default=None),
            "x_max": max((point["x"] for point in gaps), default=None),
            "z_min": min((point["z"] for point in gaps), default=None),
            "z_max": max((point["z"] for point in gaps), default=None),
        },
        "centerline": centerline,
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "FRONT_SURFACE_COVERAGE_PASS "
        f"body_samples={body_samples} gaps={len(gaps)} ratio={report['coverage_ratio']} "
        f"output={options.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
