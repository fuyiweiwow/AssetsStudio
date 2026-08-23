"""Derive eye-socket and ear-root anchors from the current Actor head surface.

The output is a dimensionless, head-relative placement contract plus resolved
world-space anchors.  It replaces copied world coordinates from older Actors.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


HEAD_GROUP = "CC_Base_Head"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--debug-blend", type=Path)
    parser.add_argument("--frame", type=int, default=1)
    parser.add_argument("--head-weight-min", type=float, default=0.50)
    parser.add_argument("--eye-center-x-ratio", type=float, default=0.41)
    parser.add_argument("--eye-center-z-ratio", type=float, default=0.35)
    parser.add_argument("--eye-width-ratio", type=float, default=0.26)
    parser.add_argument("--eye-height-ratio", type=float, default=0.30)
    parser.add_argument("--ear-center-z-below-eye-ratio", type=float, default=0.035)
    parser.add_argument("--ear-forward-ratio", type=float, default=0.04)
    parser.add_argument("--ear-height-ratio", type=float, default=0.19)
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    return parser.parse_args(raw)


def actor_mesh() -> bpy.types.Object:
    result = next(
        (
            obj
            for obj in bpy.context.scene.objects
            if obj.type == "MESH" and obj.name.startswith("ChibiBaseMesh")
        ),
        None,
    )
    if result is None:
        raise RuntimeError("current Actor mesh was not found")
    return result


def evaluated_world_mesh(obj: bpy.types.Object) -> tuple[bpy.types.Mesh, list[Vector]]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    return mesh, points


def head_points(obj: bpy.types.Object, evaluated_points: list[Vector], threshold: float) -> list[Vector]:
    group = obj.vertex_groups.get(HEAD_GROUP)
    if group is None:
        raise RuntimeError(f"Actor mesh has no {HEAD_GROUP} vertex group")
    result = []
    for index, point in enumerate(evaluated_points):
        weight = next(
            (
                membership.weight
                for membership in obj.data.vertices[index].groups
                if membership.group == group.index
            ),
            0.0,
        )
        if weight >= threshold:
            result.append(point)
    if len(result) < 100:
        raise RuntimeError(f"head calibration found only {len(result)} weighted vertices")
    return result


def vector_min(points: list[Vector]) -> Vector:
    return Vector(tuple(min(point[axis] for point in points) for axis in range(3)))


def vector_max(points: list[Vector]) -> Vector:
    return Vector(tuple(max(point[axis] for point in points) for axis in range(3)))


def world_bvh(mesh: bpy.types.Mesh, points: list[Vector]) -> BVHTree:
    polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
    return BVHTree.FromPolygons(points, polygons, all_triangles=False)


def front_hit(bvh: BVHTree, low: Vector, high: Vector, x: float, z: float):
    margin = max(high.y - low.y, 0.25)
    return bvh.ray_cast(Vector((x, low.y - margin, z)), Vector((0.0, 1.0, 0.0)), margin * 3.0)


def side_hit(bvh: BVHTree, low: Vector, high: Vector, sign: float, y: float, z: float):
    margin = max(high.x - low.x, 0.25)
    origin_x = high.x + margin if sign > 0.0 else low.x - margin
    direction = Vector((-sign, 0.0, 0.0))
    return bvh.ray_cast(Vector((origin_x, y, z)), direction, margin * 3.0)


def marker(name: str, point: Vector, size: float) -> None:
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = point
    obj.empty_display_type = "SPHERE"
    obj.empty_display_size = size
    obj["assetsstudio_calibration_marker"] = True


def as_list(value: Vector | None) -> list[float] | None:
    return [float(component) for component in value] if value is not None else None


def main() -> int:
    options = parse_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.input.resolve()))
    scene = bpy.context.scene
    scene.frame_set(options.frame)
    bpy.context.view_layer.update()
    actor = actor_mesh()
    mesh, evaluated_points = evaluated_world_mesh(actor)
    try:
        weighted = head_points(actor, evaluated_points, options.head_weight_min)
        low = vector_min(weighted)
        high = vector_max(weighted)
        center = (low + high) * 0.5
        dimensions = high - low
        bvh = world_bvh(mesh, evaluated_points)

        eye_center_x = dimensions.x * options.eye_center_x_ratio * 0.5
        eye_center_z = low.z + dimensions.z * options.eye_center_z_ratio
        eye_width = dimensions.x * options.eye_width_ratio
        eye_height = dimensions.z * options.eye_height_ratio
        eye_anchors = {}
        eye_surface_samples = {}
        for side, sign in (("L", 1.0), ("R", -1.0)):
            x = sign * eye_center_x + center.x
            hit, normal, _, _ = front_hit(bvh, low, high, x, eye_center_z)
            if hit is None:
                raise RuntimeError(f"front surface ray missed {side} eye anchor")
            eye_anchors[side] = Vector((x, hit.y, eye_center_z))
            samples = []
            for ux, uz in ((-0.5, -0.5), (0.0, -0.5), (0.5, -0.5), (-0.5, 0.0), (0.0, 0.0), (0.5, 0.0), (-0.5, 0.5), (0.0, 0.5), (0.5, 0.5)):
                sx = x + ux * eye_width
                sz = eye_center_z + uz * eye_height
                sample_hit, sample_normal, _, _ = front_hit(bvh, low, high, sx, sz)
                samples.append({"x": sx, "z": sz, "point": as_list(sample_hit), "normal": as_list(sample_normal)})
            eye_surface_samples[side] = samples

        ear_center_z = eye_center_z - dimensions.z * options.ear_center_z_below_eye_ratio
        ear_y = center.y - dimensions.y * options.ear_forward_ratio
        ear_height = dimensions.z * options.ear_height_ratio
        ear_anchors = {}
        ear_normals = {}
        for side, sign in (("L", 1.0), ("R", -1.0)):
            hit, normal, _, _ = side_hit(bvh, low, high, sign, ear_y, ear_center_z)
            if hit is None:
                raise RuntimeError(f"side surface ray missed {side} ear root")
            ear_anchors[side] = hit
            ear_normals[side] = normal

        report = {
            "schema": "assetsstudio_actor_v2_head_feature_calibration_v1",
            "status": "calibrated_review_required",
            "input": str(options.input.resolve()),
            "frame": options.frame,
            "actor_object": actor.name,
            "head_vertex_group": HEAD_GROUP,
            "head_weight_min": options.head_weight_min,
            "head_weighted_vertex_count": len(weighted),
            "coordinate_contract": {
                "front": "-Y",
                "back": "+Y",
                "actor_left": "+X",
                "actor_right": "-X",
                "up": "+Z",
            },
            "head_bounds": {"min": as_list(low), "max": as_list(high), "center": as_list(center), "dimensions": as_list(dimensions)},
            "normalized_recipe": {
                "eye_center_x_ratio_of_half_width": options.eye_center_x_ratio,
                "eye_center_z_ratio_from_bottom": options.eye_center_z_ratio,
                "eye_width_ratio_of_head_width": options.eye_width_ratio,
                "eye_height_ratio_of_head_height": options.eye_height_ratio,
                "ear_center_z_below_eye_ratio": options.ear_center_z_below_eye_ratio,
                "ear_forward_ratio_of_head_depth": options.ear_forward_ratio,
                "ear_height_ratio_of_head_height": options.ear_height_ratio,
            },
            "eye": {
                "builder_values": {
                    "left_center_x": eye_anchors["L"].x,
                    "right_center_x": eye_anchors["R"].x,
                    "eye_center_z": eye_center_z,
                    "eye_width": eye_width,
                    "eye_height": eye_height,
                    "clearance": 0.006,
                },
                "surface_anchors": {side: as_list(point) for side, point in eye_anchors.items()},
                "surface_samples": eye_surface_samples,
            },
            "ear": {
                "target_height": ear_height,
                "root_clearance": 0.004,
                "root_anchors": {side: as_list(point) for side, point in ear_anchors.items()},
                "outward_normals": {side: as_list(normal) for side, normal in ear_normals.items()},
            },
            "validation_thresholds": {
                "eye_surface_median_distance_max_m": 0.008,
                "eye_surface_p95_distance_max_m": 0.015,
                "ear_root_median_distance_max_m": 0.008,
                "ear_root_max_distance_max_m": 0.020,
                "head_relative_motion_drift_max_m": 0.0001,
                "required_views": ["front", "right", "back", "left"],
            },
        }
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        scene["assetsstudio_head_feature_calibration"] = str(options.output.resolve())
        for side, point in eye_anchors.items():
            marker(f"CAL_Eye_{side}", point, eye_width * 0.08)
        for side, point in ear_anchors.items():
            marker(f"CAL_EarRoot_{side}", point, ear_height * 0.08)
        if options.debug_blend:
            options.debug_blend.parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=str(options.debug_blend.resolve()))
        print(
            "ACTOR_V2_HEAD_FEATURE_CALIBRATION_PASS "
            f"head_dims={tuple(round(value, 6) for value in dimensions)} "
            f"eye={eye_width:.6f}x{eye_height:.6f} ear_height={ear_height:.6f}"
        )
        return 0
    finally:
        actor.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()


if __name__ == "__main__":
    raise SystemExit(main())
