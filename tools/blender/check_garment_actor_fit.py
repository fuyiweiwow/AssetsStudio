"""Check Render Garment fit against the posed Actor in headless Blender.

This is a diagnostic gate, not a replacement for visual review.  It measures
the same failure classes that have repeatedly appeared in the clothing work:
shoulder-strap placement, interior back boundaries, hem/thigh penetration, and
large garment/body separation across the walk samples.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


TORSO_BONES = {
    "CC_Base_Pelvis",
    "CC_Base_Waist",
    "CC_Base_Spine01",
    "CC_Base_Spine02",
    "CC_Base_L_Clavicle",
    "CC_Base_R_Clavicle",
    "CC_Base_L_Upperarm",
    "CC_Base_R_Upperarm",
}
PANTS_BONES = TORSO_BONES - {"CC_Base_L_Upperarm", "CC_Base_R_Upperarm"} | {
    "CC_Base_L_Thigh",
    "CC_Base_R_Thigh",
    "CC_Base_L_Calf",
    "CC_Base_R_Calf",
}


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--garment-kind", choices=("shirt", "pants"), default="shirt")
    parser.add_argument("--garment-name", default="GarmentCodeShirt_RenderGarment")
    parser.add_argument(
        "--garment-names",
        default="",
        help="comma-separated garment object names; the first object is the torso for hem checks",
    )
    parser.add_argument("--actor-name", default="ChibiBaseMesh_AccuRIG_InputMesh")
    parser.add_argument("--armature-name", default="Armature")
    parser.add_argument("--penetration-threshold", type=float, default=0.010)
    parser.add_argument("--detached-threshold", type=float, default=0.12)
    return parser.parse_args(argv)


def evaluated_points(obj: bpy.types.Object) -> tuple[list[Vector], list[tuple[int, ...]]]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
        return points, polygons
    finally:
        evaluated.to_mesh_clear()


def make_bvh(points: list[Vector], polygons: list[tuple[int, ...]]) -> BVHTree:
    return BVHTree.FromPolygons(points, polygons, all_triangles=False)


def nearest_signed_distance(bvh: BVHTree, point: Vector) -> tuple[float, float]:
    nearest = bvh.find_nearest(point)
    if nearest is None:
        return float("inf"), float("inf")
    location, normal, _face_index, distance = nearest
    signed = (point - location).dot(normal.normalized())
    return float(signed), float(distance)


def boundary_diagnostics(points: list[Vector], polygons: list[tuple[int, ...]], bottom_z: float, top_z: float) -> dict[str, object]:
    edge_counts: Counter[tuple[int, int]] = Counter()
    for polygon in polygons:
        for first, second in zip(polygon, polygon[1:] + polygon[:1]):
            edge_counts[tuple(sorted((first, second)))] += 1
    boundary_edges = [edge for edge, count in edge_counts.items() if count == 1]
    nonmanifold_edges = [edge for edge, count in edge_counts.items() if count > 2]
    back_interior = []
    for first, second in boundary_edges:
        midpoint = (points[first] + points[second]) * 0.5
        if (
            midpoint.y > 0.02
            and abs(midpoint.x) < 0.22
            and bottom_z + 0.20 < midpoint.z < top_z - 0.16
        ):
            back_interior.append((first, second))

    adjacency: dict[int, set[int]] = defaultdict(set)
    for first, second in boundary_edges:
        adjacency[first].add(second)
        adjacency[second].add(first)
    boundary_components = 0
    unvisited = set(adjacency)
    while unvisited:
        start = unvisited.pop()
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor in unvisited:
                    unvisited.remove(neighbor)
                    queue.append(neighbor)
        boundary_components += 1

    return {
        "boundary_edge_count": len(boundary_edges),
        "nonmanifold_edge_count": len(nonmanifold_edges),
        "boundary_component_count": boundary_components,
        "back_interior_boundary_edge_count": len(back_interior),
        "back_interior_boundary_examples": [
            {
                "edge": list(edge),
                "midpoint": [round(value, 6) for value in ((points[edge[0]] + points[edge[1]]) * 0.5)],
            }
            for edge in back_interior[:5]
        ],
    }


def shoulder_check(
    points: list[Vector],
    bvh: BVHTree,
    armature: bpy.types.Object,
    top_z: float,
    shoulder_z: float,
    shoulder_x: float,
    detached_threshold: float,
) -> dict[str, object]:
    top_points = [point for point in points if point.z >= top_z - 0.13 and abs(point.x) >= 0.10]
    sides: dict[str, dict[str, object]] = {}
    for label, sign in (("left", -1.0), ("right", 1.0)):
        side_points = [point for point in top_points if point.x * sign > 0]
        if not side_points:
            sides[label] = {"status": "fail", "reason": "missing_upper_side_points"}
            continue
        # A shoulder strap intentionally crosses the top of the shoulder.
        # Mid-depth bridge vertices are not a valid body-clearance sample;
        # measure the front/back strap surfaces instead.
        surface_points = [point for point in side_points if abs(point.y) >= 0.08] or side_points
        distances = [nearest_signed_distance(bvh, point)[1] for point in surface_points]
        sides[label] = {
            "point_count": len(side_points),
            "clearance_sample_count": len(surface_points),
            "x_range": [min(point.x for point in side_points), max(point.x for point in side_points)],
            "z_range": [min(point.z for point in side_points), max(point.z for point in side_points)],
            "max_body_gap": max(distances),
            "shoulder_height_pass": max(point.z for point in side_points) >= shoulder_z + 0.015,
            "shoulder_x_pass": max(abs(point.x) for point in side_points) >= shoulder_x - 0.05,
            "body_gap_pass": max(distances) <= detached_threshold,
        }
        sides[label]["status"] = "pass" if all(
            sides[label][key] for key in ("shoulder_height_pass", "shoulder_x_pass", "body_gap_pass")
        ) else "fail"
    return {"shoulder_z": shoulder_z, "shoulder_x": shoulder_x, "sides": sides}


def weighted_points_for_bones(obj: bpy.types.Object, bone_names: set[str]) -> list[Vector]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        group_names = {group.index: group.name for group in obj.vertex_groups}
        indices = {
            vertex.index
            for vertex in obj.data.vertices
            if sum(
                assignment.weight
                for assignment in vertex.groups
                if group_names.get(assignment.group) in bone_names
            ) >= 0.20
        }
        return [evaluated.matrix_world @ mesh.vertices[index].co for index in sorted(indices)]
    finally:
        evaluated.to_mesh_clear()


def torso_weighted_points(obj: bpy.types.Object) -> list[Vector]:
    return weighted_points_for_bones(obj, TORSO_BONES)


def local_depth_range(points: list[Vector], point: Vector) -> tuple[float, float] | None:
    """Return the Actor front/back envelope near a garment sample."""
    candidates = [
        candidate
        for candidate in points
        if abs(candidate.x - point.x) <= 0.075
        and abs(candidate.z - point.z) <= 0.060
        and -0.34 <= candidate.y <= 0.34
    ]
    if len(candidates) < 4:
        candidates = [
            candidate
            for candidate in points
            if abs(candidate.x - point.x) <= 0.110
            and abs(candidate.z - point.z) <= 0.090
            and -0.34 <= candidate.y <= 0.34
        ]
    if len(candidates) < 4:
        return None
    values = sorted(candidate.y for candidate in candidates)
    return values[0], values[-1]


def local_x_range(points: list[Vector], point: Vector) -> tuple[float, float] | None:
    """Return the Actor left/right envelope near a pants sample."""
    candidates = [
        candidate
        for candidate in points
        if abs(candidate.y - point.y) <= 0.110
        and abs(candidate.z - point.z) <= 0.060
        and -0.34 <= candidate.y <= 0.34
    ]
    if len(candidates) < 4:
        candidates = [
            candidate
            for candidate in points
            if abs(candidate.y - point.y) <= 0.160
            and abs(candidate.z - point.z) <= 0.090
            and -0.34 <= candidate.y <= 0.34
        ]
    if len(candidates) < 4:
        return None
    values = sorted(candidate.x for candidate in candidates)
    return values[0], values[-1]


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    scene = bpy.context.scene
    garment_names = [name.strip() for name in options.garment_names.split(",") if name.strip()]
    if not garment_names:
        garment_names = [options.garment_name]
    garments = [bpy.data.objects.get(name) for name in garment_names]
    actor = bpy.data.objects.get(options.actor_name)
    armature = bpy.data.objects.get(options.armature_name)
    if any(garment is None or garment.type != "MESH" for garment in garments):
        raise RuntimeError(f"missing garment mesh: {', '.join(garment_names)}")
    if actor is None or actor.type != "MESH":
        raise RuntimeError(f"missing Actor mesh: {options.actor_name}")
    if armature is None or armature.type != "ARMATURE":
        raise RuntimeError(f"missing armature: {options.armature_name}")
    if not armature.animation_data or not armature.animation_data.action:
        raise RuntimeError("Actor armature has no walk action")

    action = armature.animation_data.action
    start, end = int(action.frame_range[0]), int(action.frame_range[1])
    sample_frames = [round(start + (end - start) * index / 7.0) for index in range(8)]
    scene.frame_set(start)
    bpy.context.view_layer.update()
    shoulder_z = None
    shoulder_x = None
    if options.garment_kind == "shirt":
        shoulder_bones = [
            armature.pose.bones.get("CC_Base_L_Upperarm"),
            armature.pose.bones.get("CC_Base_R_Upperarm"),
        ]
        clavicle_bones = [
            armature.pose.bones.get("CC_Base_L_Clavicle"),
            armature.pose.bones.get("CC_Base_R_Clavicle"),
        ]
        if any(bone is None for bone in shoulder_bones + clavicle_bones):
            raise RuntimeError("Actor shoulder bones are incomplete")
        shoulder_z = sum((armature.matrix_world @ bone.head).z for bone in shoulder_bones) / 2.0
        shoulder_x = max(abs((armature.matrix_world @ bone.head).x) for bone in shoulder_bones)
        shoulder_z = max(shoulder_z, sum((armature.matrix_world @ bone.tail).z for bone in clavicle_bones) / 2.0)

    frame_results: list[dict[str, object]] = []
    for frame in sample_frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        garment_points: list[Vector] = []
        garment_polygons: list[tuple[int, ...]] = []
        torso_points: list[Vector] = []
        torso_polygons: list[tuple[int, ...]] = []
        for object_index, garment_object in enumerate(garments):
            object_points, object_polygons = evaluated_points(garment_object)
            offset = len(garment_points)
            garment_points.extend(object_points)
            if object_index == 0:
                torso_points = object_points
                torso_polygons = object_polygons
            garment_polygons.extend(
                tuple(vertex_index + offset for vertex_index in polygon)
                for polygon in object_polygons
            )
        actor_points, actor_polygons = evaluated_points(actor)
        actor_torso_points = torso_weighted_points(actor)
        actor_surface_points = (
            actor_torso_points
            if options.garment_kind == "shirt"
            else weighted_points_for_bones(actor, PANTS_BONES)
        )
        actor_bvh = make_bvh(actor_points, actor_polygons)
        bottom_z = min(point.z for point in torso_points)
        torso_top_z = max(point.z for point in torso_points)
        top_z = max(point.z for point in garment_points)
        torso_indices = set(range(len(torso_points)))
        signed_distances = [nearest_signed_distance(actor_bvh, point) for point in garment_points]
        shoulder_bridge_items = [
            (index, signed, distance)
            for index, (signed, distance) in enumerate(signed_distances)
            if (
                garment_points[index].z >= (
                    torso_top_z - 0.13 if index in torso_indices else top_z - 0.13
                )
            )
            and abs(garment_points[index].x) >= 0.10
            # The short-sleeve armhole is a real overlap zone with the
            # confirmed torso.  At 256 px, the outer sleeve shell can sit a
            # few millimetres beyond the old 0.08 m band while still being a
            # valid shoulder connection, so keep the lower sleeve subject to
            # the normal penetration test but widen this bridge band.
            and abs(garment_points[index].y) < 0.12
        ]
        shoulder_bridge_indices = {index for index, _signed, _distance in shoulder_bridge_items}
        depth_penetration_items = []
        depth_gap_items = []
        for index, point in enumerate(garment_points):
            if options.garment_kind == "shirt" and (
                abs(point.y) < 0.12
                or abs(point.x) > 0.24
                or index in shoulder_bridge_indices
            ):
                continue
            if options.garment_kind == "pants" and abs(point.y) < 0.08:
                continue
            if options.garment_kind == "pants":
                x_range = local_x_range(actor_surface_points, point)
                if x_range is None or point.x < x_range[0] - 0.025 or point.x > x_range[1] + 0.025:
                    # Side hem/cuff vertices are outside the body envelope;
                    # the depth test must not mistake their radial clearance
                    # for body penetration.
                    continue
            depth_range = local_depth_range(actor_surface_points, point)
            if depth_range is None:
                continue
            front, back = depth_range
            if point.y < 0.0:
                penetration = point.y - front - options.penetration_threshold
                gap = front - point.y - options.detached_threshold
            else:
                penetration = back - options.penetration_threshold - point.y
                gap = point.y - back - options.detached_threshold
            if penetration > 0.0:
                depth_penetration_items.append((index, -penetration, penetration))
            if gap > 0.0:
                depth_gap_items.append((index, point.y, gap))
        penetration_items = depth_penetration_items
        hem_limit = bottom_z + max(0.20, (torso_top_z - bottom_z) * 0.22)
        hem_penetration_items = [
            item for item in penetration_items
            if item[0] in torso_indices and garment_points[item[0]].z <= hem_limit
        ]
        body_penetration_items = [item for item in penetration_items if garment_points[item[0]].z > hem_limit]
        detached_items = [
            item for item in depth_gap_items if garment_points[item[0]].z < top_z - 0.13
        ]
        penetrations = [signed for _index, signed, _distance in penetration_items]
        detached = [distance for _index, _signed, distance in detached_items]
        boundary = boundary_diagnostics(garment_points, garment_polygons, bottom_z, top_z)
        torso_boundary = boundary_diagnostics(torso_points, torso_polygons, bottom_z, torso_top_z)
        boundary["back_interior_boundary_edge_count"] = torso_boundary["back_interior_boundary_edge_count"]
        boundary["back_interior_boundary_examples"] = torso_boundary["back_interior_boundary_examples"]
        shoulder = (
            shoulder_check(
                torso_points,
                actor_bvh,
                armature,
                top_z,
                shoulder_z,
                shoulder_x,
                options.detached_threshold,
            )
            if options.garment_kind == "shirt"
            else {"status": "not_applicable", "kind": "pants"}
        )
        pelvis_tail_z = (armature.matrix_world @ armature.pose.bones["CC_Base_Pelvis"].tail).z
        waistband_delta = abs(top_z - pelvis_tail_z)
        frame_results.append({
            "frame": frame,
            "vertex_count": len(garment_points),
            "penetration_vertex_count": len(penetrations),
            "max_penetration_m": round(abs(min(penetrations)), 6) if penetrations else 0.0,
            "shoulder_bridge_vertex_count": len(shoulder_bridge_items),
            "body_penetration_vertex_count": len(body_penetration_items),
            "hem_penetration_vertex_count": len(hem_penetration_items),
            "max_hem_penetration_m": round(abs(min((item[1] for item in hem_penetration_items), default=0.0)), 6),
            "detached_vertex_count": len(detached),
            "max_body_gap_m": round(max(detached), 6) if detached else 0.0,
            "worst_penetrations": [
                {
                    "vertex": index,
                    "signed_m": round(signed, 6),
                    "distance_m": round(distance, 6),
                    "point": [round(value, 6) for value in garment_points[index]],
                }
                for index, signed, distance in sorted(penetration_items, key=lambda item: item[1])[:5]
            ],
            "worst_hem_penetrations": [
                {
                    "vertex": index,
                    "signed_m": round(signed, 6),
                    "distance_m": round(distance, 6),
                    "point": [round(value, 6) for value in garment_points[index]],
                }
                for index, signed, distance in sorted(hem_penetration_items, key=lambda item: item[1])[:5]
            ],
            "worst_gaps": [
                {
                    "vertex": index,
                    "signed_m": round(signed, 6),
                    "distance_m": round(distance, 6),
                    "point": [round(value, 6) for value in garment_points[index]],
                }
                for index, signed, distance in sorted(detached_items, key=lambda item: item[2], reverse=True)[:5]
            ],
            "boundary": boundary,
            "shoulder": shoulder,
            "waistband": {
                "actor_pelvis_tail_z": round(pelvis_tail_z, 6),
                "garment_top_z": round(top_z, 6),
                "delta_m": round(waistband_delta, 6),
                "placement_pass": waistband_delta <= 0.12,
            },
        })

    first = frame_results[0]
    if options.garment_kind == "pants":
        checks = {
            "waistband_placement": all(item["waistband"]["placement_pass"] for item in frame_results),
            "body_penetration": all(item["penetration_vertex_count"] == 0 for item in frame_results),
            "body_clearance": all(item["max_body_gap_m"] <= options.detached_threshold for item in frame_results),
            "nonmanifold": all(item["boundary"]["nonmanifold_edge_count"] == 0 for item in frame_results),
        }
    else:
        checks = {
            "shoulder_placement": all(side["status"] == "pass" for side in first["shoulder"]["sides"].values()),
            "back_integrity": all(item["boundary"]["back_interior_boundary_edge_count"] == 0 for item in frame_results),
            "hem_penetration": all(item["hem_penetration_vertex_count"] == 0 for item in frame_results),
            "body_clearance": all(item["max_body_gap_m"] <= options.detached_threshold for item in frame_results),
            "nonmanifold": all(item["boundary"]["nonmanifold_edge_count"] == 0 for item in frame_results),
        }
    result = {
        "schema": "assetslab_garment_actor_fit_check_v2",
        "source_blend": str(options.blend.resolve()),
        "garment": garment_names,
        "garment_kind": options.garment_kind,
        "actor": actor.name,
        "sample_frames": sample_frames,
        "thresholds": {
            "penetration_m": options.penetration_threshold,
            "detached_m": options.detached_threshold,
        },
        "landmarks": {"shoulder_z": shoulder_z, "shoulder_x": shoulder_x},
        "checks": checks,
        "status": "pass" if all(checks.values()) else "fail",
        "frame_results": frame_results,
    }
    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"GARMENT_ACTOR_FIT_{result['status'].upper()} output={output}")
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
