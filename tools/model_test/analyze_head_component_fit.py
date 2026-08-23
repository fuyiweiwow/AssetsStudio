"""Measure Actor head-slot geometry and surface contact in a Blender file.

This is a read-only diagnostic. It reports evaluated world bounds and nearest
surface distances for eye and ear components so fit revisions can use explicit
gates instead of visual-only placement.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    return parser.parse_args(raw)


def evaluated_vertices(obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph) -> list[Vector]:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def world_bvh(obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph) -> BVHTree:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        polygons = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
        return BVHTree.FromPolygons(vertices, polygons, all_triangles=True)
    finally:
        evaluated.to_mesh_clear()


def world_bounds(points: list[Vector]) -> dict[str, list[float]]:
    low = [min(point[axis] for point in points) for axis in range(3)]
    high = [max(point[axis] for point in points) for axis in range(3)]
    return {
        "min": low,
        "max": high,
        "center": [(low[axis] + high[axis]) * 0.5 for axis in range(3)],
        "dimensions": [high[axis] - low[axis] for axis in range(3)],
    }


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def nearest_distances(points: list[Vector], target: BVHTree) -> list[float]:
    distances = []
    for point in points:
        nearest = target.find_nearest(point)
        if nearest is not None:
            distances.append(float(nearest[3]))
    return distances


def distance_summary(distances: list[float]) -> dict[str, float]:
    return {
        "min_m": min(distances, default=0.0),
        "median_m": statistics.median(distances) if distances else 0.0,
        "p90_m": percentile(distances, 0.90),
        "max_m": max(distances, default=0.0),
        "within_2mm_fraction": sum(value <= 0.002 for value in distances) / max(len(distances), 1),
        "within_5mm_fraction": sum(value <= 0.005 for value in distances) / max(len(distances), 1),
    }


def image_alpha_bounds(image: bpy.types.Image) -> dict[str, object] | None:
    width, height = image.size
    if width <= 0 or height <= 0 or not image.has_data:
        return None
    pixels = list(image.pixels)
    xs: list[int] = []
    ys: list[int] = []
    for index in range(width * height):
        if pixels[index * 4 + 3] > 0.02:
            xs.append(index % width)
            ys.append(index // width)
    if not xs:
        return None
    low_x, high_x = min(xs), max(xs)
    low_y, high_y = min(ys), max(ys)
    return {
        "image": image.filepath,
        "size_px": [width, height],
        "alpha_bbox_px": [low_x, low_y, high_x, high_y],
        "alpha_fraction_xy": [(high_x - low_x + 1) / width, (high_y - low_y + 1) / height],
    }


def actor_mesh(scene: bpy.types.Scene) -> bpy.types.Object:
    candidates = [
        obj for obj in scene.objects
        if obj.type == "MESH" and (
            obj.name.startswith("ChibiBaseMesh")
            or any(mod.type == "ARMATURE" and mod.object for mod in obj.modifiers)
        )
    ]
    if not candidates:
        raise RuntimeError("No Actor body mesh found")
    return max(candidates, key=lambda obj: len(obj.data.vertices))


def main() -> int:
    options = parse_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    scene = bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    body = actor_mesh(scene)
    body_bvh = world_bvh(body, depsgraph)
    body_points = evaluated_vertices(body, depsgraph)

    report: dict[str, object] = {
        "schema": "assetsstudio_head_component_fit_diagnostic_v1",
        "blend": str(options.blend.resolve()),
        "body": {"object": body.name, "bounds": world_bounds(body_points)},
        "components": {},
    }
    components: dict[str, object] = report["components"]  # type: ignore[assignment]
    for obj in sorted((item for item in scene.objects if item.type == "MESH"), key=lambda item: item.name):
        if not obj.name.startswith(("EyeAssembly", "EarPair_", "MikuEar_", "Hair")):
            continue
        points = evaluated_vertices(obj, depsgraph)
        item: dict[str, object] = {
            "bounds": world_bounds(points),
            "vertex_count": len(points),
            "surface_distance": distance_summary(nearest_distances(points, body_bvh)),
            "parent": obj.parent.name if obj.parent else None,
            "parent_type": obj.parent_type,
            "parent_bone": obj.parent_bone,
        }
        if obj.name.startswith(("EarPair_", "MikuEar_")):
            bounds = item["bounds"]
            assert isinstance(bounds, dict)
            center_x = bounds["center"][0]
            dimensions_x = bounds["dimensions"][0]
            root_points = [
                point for point in points
                if abs(point.x) <= abs(center_x) - dimensions_x * 0.25
            ]
            item["root_vertex_count"] = len(root_points)
            item["root_surface_distance"] = distance_summary(nearest_distances(root_points, body_bvh))
        if obj.name.startswith("EyeAssembly"):
            images = []
            for slot in obj.material_slots:
                material = slot.material
                if material is None or not material.use_nodes:
                    continue
                for node in material.node_tree.nodes:
                    if node.type == "TEX_IMAGE" and node.image is not None:
                        alpha = image_alpha_bounds(node.image)
                        if alpha is not None:
                            images.append(alpha)
            item["texture_alpha"] = images
        components[obj.name] = item

    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
