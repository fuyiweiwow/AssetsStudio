"""Detect Actor shoulder skin visible in front of armhole cloth from review cameras."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


VIEW_RAYS = {
    # Direction from the review camera into the scene.
    "back": Vector((0.0, -1.0, 0.0)),
    "right": Vector((-1.0, 0.0, 0.0)),
    "left": Vector((1.0, 0.0, 0.0)),
}


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--panel-membership", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--garment-name", default="GarmentCodeShirt_ActorTransfer")
    parser.add_argument("--max-distance", type=float, default=0.02)
    parser.add_argument("--armhole-width", type=float, default=0.05)
    parser.add_argument("--frame-step", type=int, default=1)
    parser.add_argument("--views", default="back,right,left")
    return parser.parse_args(argv)


def sleeve_side(panels: list[str]) -> str | None:
    if any(name.startswith("left_sleeve_") for name in panels):
        return "left"
    if any(name.startswith("right_sleeve_") for name in panels):
        return "right"
    return None


def main() -> int:
    options = cli_args()
    views = tuple(item.strip() for item in options.views.split(",") if item.strip())
    if not views or any(item not in VIEW_RAYS for item in views):
        raise RuntimeError(f"--views must be a subset of {tuple(VIEW_RAYS)}")
    membership = json.loads(options.panel_membership.resolve().read_text(encoding="utf-8"))
    vertex_panels = membership["vertex_panels"]
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    scene = bpy.context.scene
    garment = bpy.data.objects.get(options.garment_name)
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if garment is None or actor is None or armature is None:
        raise RuntimeError("blend is missing garment, Actor, or Armature")
    action = armature.animation_data.action if armature.animation_data else None
    if action is None:
        raise RuntimeError("Actor has no action")
    armature.data.pose_position = "POSE"

    rest_points = [garment.matrix_world @ vertex.co for vertex in garment.data.vertices]
    seams = {"left": [], "right": []}
    for index, panels in enumerate(vertex_panels):
        side = sleeve_side(panels)
        if side and any("torso" in name for name in panels):
            seams[side].append(index)
    seam_center_x = {
        side: sum(rest_points[index].x for index in indices) / len(indices)
        for side, indices in seams.items()
    }
    seam_distance = {
        side: [min((point - rest_points[item]).length for item in indices) for point in rest_points]
        for side, indices in seams.items()
    }
    polygon_side: list[str | None] = []
    for polygon in garment.data.polygons:
        sides = {sleeve_side(vertex_panels[index]) for index in polygon.vertices}
        sides.discard(None)
        selected = None
        if len(sides) == 1:
            side = next(iter(sides))
            if min(seam_distance[side][index] for index in polygon.vertices) <= options.armhole_width:
                selected = side
        polygon_side.append(selected)

    actor_groups = {group.index: group.name for group in actor.vertex_groups}
    actor_bones = []
    for vertex in actor.data.vertices:
        assignments = sorted(vertex.groups, key=lambda item: item.weight, reverse=True)
        actor_bones.append(actor_groups.get(assignments[0].group) if assignments else None)

    first, last = int(action.frame_range[0]), int(action.frame_range[1])
    frames = list(range(first, last + 1, options.frame_step))
    if frames[-1] != last:
        frames.append(last)
    epsilon = 0.00025
    reports = []
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eg = garment.evaluated_get(depsgraph)
        ea = actor.evaluated_get(depsgraph)
        gm = eg.to_mesh()
        am = ea.to_mesh()
        garment_points = [eg.matrix_world @ vertex.co for vertex in gm.vertices]
        garment_faces = [tuple(poly.vertices) for poly in gm.polygons]
        actor_points = [ea.matrix_world @ vertex.co for vertex in am.vertices]
        normal_matrix = ea.matrix_world.to_3x3().inverted().transposed()
        actor_normals = [(normal_matrix @ vertex.normal).normalized() for vertex in am.vertices]
        garment_bvh = BVHTree.FromPolygons(garment_points, garment_faces, all_triangles=False)
        actor_bvh = BVHTree.FromPolygons(
            actor_points,
            [tuple(poly.vertices) for poly in am.polygons],
            all_triangles=False,
        )
        exposed = []
        for view in views:
            ray = VIEW_RAYS[view]
            toward_camera = -ray
            for index, (point, normal) in enumerate(zip(actor_points, actor_normals)):
                bone = actor_bones[index]
                if bone is None or not any(token in bone for token in ("Clavicle", "Upperarm", "Spine02")):
                    continue
                # Ignore the far-facing half of the Actor and vertices hidden
                # by another part of the Actor from this orthographic view.
                if normal.dot(toward_camera) <= 0.05:
                    continue
                actor_occluder = actor_bvh.ray_cast(
                    point + toward_camera * epsilon,
                    toward_camera,
                    0.25,
                )
                if actor_occluder[0] is not None and actor_occluder[3] > epsilon * 2.0:
                    continue
                # Cloth between camera and skin means the Actor point is covered.
                front = garment_bvh.ray_cast(
                    point + toward_camera * epsilon,
                    toward_camera,
                    options.max_distance,
                )
                if front[0] is not None:
                    front_face = front[2]
                    if front_face < len(polygon_side) and polygon_side[front_face] is not None:
                        continue
                # Cloth only behind the Actor point creates a visible skin block.
                behind = garment_bvh.ray_cast(
                    point + ray * epsilon,
                    ray,
                    options.max_distance,
                )
                if behind[0] is None:
                    continue
                location, _normal, face_index, distance = behind
                if face_index >= len(polygon_side):
                    continue
                side = polygon_side[face_index]
                if side is None or point.x * seam_center_x[side] <= 0.0:
                    continue
                exposed.append({
                    "view": view,
                    "actor_vertex": index,
                    "bone": bone,
                    "side": side,
                    "behind_distance_m": float(distance),
                    "point": [float(value) for value in point],
                    "view_ray": [float(value) for value in ray],
                    "garment_face": int(face_index),
                    "garment_vertices": list(garment_faces[face_index]),
                })
        reports.append({
            "frame": frame,
            "exposed_count": len(exposed),
            "view_counts": dict(Counter(item["view"] for item in exposed)),
            "side_counts": dict(Counter(item["side"] for item in exposed)),
            "bone_counts": dict(Counter(item["bone"] for item in exposed).most_common()),
            "items": exposed,
        })
        eg.to_mesh_clear()
        ea.to_mesh_clear()

    report = {
        "schema": "assetsstudio_actor_shoulder_camera_rays_v1",
        "blend": str(options.blend.resolve()),
        "views": views,
        "max_distance_m": options.max_distance,
        "method": "camera-facing Actor vertex with armhole cloth only behind it",
        "frames": reports,
    }
    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "peaks": sorted(
            ({"frame": item["frame"], "count": item["exposed_count"], "views": item["view_counts"]} for item in reports),
            key=lambda item: item["count"],
            reverse=True,
        )[:15],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
