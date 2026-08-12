"""Compare the REST Actor upper surface with a GarmentCode collision OBJ.

This is a read-only diagnostic.  It does not alter either source and does not
produce a garment.  The OBJ is expected in GarmentCode metres: (x, y-up,
z-depth), and is mapped to Blender metres as (x, -z-depth, y-up).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


UPPER_GROUPS = {
    "CC_Base_Hip", "CC_Base_Waist", "CC_Base_Spine01", "CC_Base_Spine02",
    "CC_Base_L_Clavicle", "CC_Base_R_Clavicle", "CC_Base_L_Upperarm",
    "CC_Base_R_Upperarm", "CC_Base_L_UpperarmTwist01",
    "CC_Base_L_UpperarmTwist02", "CC_Base_R_UpperarmTwist01",
    "CC_Base_R_UpperarmTwist02",
}


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--proxy-obj", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--z-min", type=float, default=0.50)
    parser.add_argument("--z-max", type=float, default=1.55)
    parser.add_argument("--z-step", type=float, default=0.05)
    parser.add_argument("--band", type=float, default=0.025)
    parser.add_argument("--min-upper-weight", type=float, default=0.20)
    return parser.parse_args(argv)


def bounds(points: list[Vector]) -> list[list[float]]:
    return [
        [min(point[index] for point in points), max(point[index] for point in points)]
        for index in range(3)
    ]


def range_for(points: list[Vector], axis: int) -> list[float] | None:
    if not points:
        return None
    return [min(point[axis] for point in points), max(point[axis] for point in points)]


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def nearest_distances(bvh: BVHTree, points: list[Vector]) -> list[float]:
    distances: list[float] = []
    for point in points:
        nearest = bvh.find_nearest(point)
        if nearest is not None:
            distances.append(float(nearest[3]))
    return distances


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    for armature in (obj for obj in bpy.data.objects if obj.type == "ARMATURE"):
        if armature.animation_data is not None:
            armature.animation_data.action = None
        armature.data.pose_position = "REST"
    bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()

    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    if actor is None or actor.type != "MESH":
        raise RuntimeError("Actor mesh is missing")

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = actor.evaluated_get(depsgraph)
    actor_mesh = evaluated.to_mesh()
    try:
        group_names = {group.index: group.name for group in actor.vertex_groups}
        actor_points_all = [evaluated.matrix_world @ vertex.co for vertex in actor_mesh.vertices]
        actor_points = [
            point
            for index, point in enumerate(actor_points_all)
            if sum(
                assignment.weight
                for assignment in actor.data.vertices[index].groups
                if group_names.get(assignment.group) in UPPER_GROUPS
            ) >= options.min_upper_weight
        ]
        actor_surface_points = actor_points_all
        actor_polygons = [tuple(polygon.vertices) for polygon in actor_mesh.polygons]
        actor_bvh = BVHTree.FromPolygons(actor_surface_points, actor_polygons, all_triangles=False)
    finally:
        evaluated.to_mesh_clear()

    raw_vertices: list[Vector] = []
    proxy_polygons: list[tuple[int, ...]] = []
    for line in options.proxy_obj.read_text(encoding="utf-8").splitlines():
        fields = line.strip().split()
        if not fields:
            continue
        if fields[0] == "v" and len(fields) >= 4:
            raw_vertices.append(Vector((float(fields[1]), float(fields[2]), float(fields[3]))))
        elif fields[0] == "f" and len(fields) >= 4:
            indices: list[int] = []
            for token in fields[1:]:
                index = int(token.split("/", 1)[0])
                indices.append(index - 1 if index > 0 else len(raw_vertices) + index)
            proxy_polygons.append(tuple(indices))
    if not raw_vertices or not proxy_polygons:
        raise RuntimeError("proxy OBJ has no readable vertices/faces")
    proxy_points = [Vector((vertex.x, -vertex.z, vertex.y)) for vertex in raw_vertices]
    proxy_bvh = BVHTree.FromPolygons(proxy_points, proxy_polygons, all_triangles=False)

    normal_dots: list[float] = []
    for polygon in proxy_polygons:
        if len(polygon) < 3:
            continue
        first, second, third = (proxy_points[index] for index in polygon[:3])
        normal = (second - first).cross(third - first)
        if normal.length <= 1e-10:
            continue
        normal.normalize()
        center = sum((proxy_points[index] for index in polygon), Vector()) / len(polygon)
        nearest = actor_bvh.find_nearest(center)
        if nearest is None:
            continue
        actor_normal = nearest[1].normalized()
        normal_dots.append(float(normal.dot(actor_normal)))

    actor_to_proxy = nearest_distances(proxy_bvh, actor_points)
    proxy_to_actor = nearest_distances(actor_bvh, proxy_points)
    actor_gap_records: list[dict[str, object]] = []
    for point in actor_points:
        nearest = proxy_bvh.find_nearest(point)
        if nearest is None:
            continue
        actor_gap_records.append({
            "distance_m": float(nearest[3]),
            "point": [float(value) for value in point],
        })
    actor_gap_records.sort(key=lambda item: float(item["distance_m"]), reverse=True)
    levels: list[dict[str, object]] = []
    level = options.z_min
    while level <= options.z_max + 1e-8:
        actor_ring = [point for point in actor_points if abs(point.z - level) <= options.band]
        proxy_ring = [point for point in proxy_points if abs(point.z - level) <= options.band]
        levels.append({
            "z_m": round(level, 6),
            "actor_count": len(actor_ring),
            "proxy_count": len(proxy_ring),
            "actor_x": range_for(actor_ring, 0),
            "proxy_x": range_for(proxy_ring, 0),
            "actor_y": range_for(actor_ring, 1),
            "proxy_y": range_for(proxy_ring, 1),
        })
        level += options.z_step

    report = {
        "schema": "assetsstudio_actor_rest_collision_envelope_audit_v1",
        "actor_blend": str(options.actor_blend.resolve()),
        "proxy_obj": str(options.proxy_obj.resolve()),
        "pose": "REST",
        "coordinate_mapping": "GarmentCode metres (x,y-up,z-depth) -> Blender metres (x,-z-depth,y-up)",
        "actor_upper_groups": sorted(UPPER_GROUPS),
        "actor_upper_points": len(actor_points),
        "proxy_points": len(proxy_points),
        "actor_bounds_m": bounds(actor_points_all),
        "actor_upper_bounds_m": bounds(actor_points),
        "proxy_bounds_m": bounds(proxy_points),
        "actor_to_proxy_nearest_m": {
            "count": len(actor_to_proxy),
            "median": percentile(actor_to_proxy, 0.50),
            "p95": percentile(actor_to_proxy, 0.95),
            "max": max(actor_to_proxy, default=None),
            "over_0p02_m": sum(value > 0.02 for value in actor_to_proxy),
            "over_0p05_m": sum(value > 0.05 for value in actor_to_proxy),
            "largest_gaps": actor_gap_records[:20],
        },
        "proxy_to_actor_nearest_m": {
            "count": len(proxy_to_actor),
            "median": percentile(proxy_to_actor, 0.50),
            "p95": percentile(proxy_to_actor, 0.95),
            "max": max(proxy_to_actor, default=None),
            "over_0p02_m": sum(value > 0.02 for value in proxy_to_actor),
            "over_0p05_m": sum(value > 0.05 for value in proxy_to_actor),
        },
        "proxy_vs_actor_surface_normals": {
            "count": len(normal_dots),
            "mean_dot": sum(normal_dots) / max(len(normal_dots), 1),
            "negative_dot_count": sum(value < 0.0 for value in normal_dots),
            "below_0p5_dot_count": sum(value < 0.5 for value in normal_dots),
        },
        "levels": levels,
        "status": "review_required",
    }
    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
