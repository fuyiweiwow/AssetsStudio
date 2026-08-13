"""Detect Actor shoulder skin in front of garment using surface-normal rays."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree


def args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--panel-membership", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--garment-name", default="GarmentCodeShirt_ActorTransfer")
    parser.add_argument("--max-distance", type=float, default=0.015)
    parser.add_argument("--armhole-width", type=float, default=0.05)
    parser.add_argument("--frame-step", type=int, default=1)
    return parser.parse_args(argv)


def sleeve_side(panels: list[str]) -> str | None:
    if any(name.startswith("left_sleeve_") for name in panels):
        return "left"
    if any(name.startswith("right_sleeve_") for name in panels):
        return "right"
    return None


def main() -> int:
    options = args()
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
    polygon_side = []
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
    epsilon = 0.0002
    reports = []
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eg = garment.evaluated_get(depsgraph)
        ea = actor.evaluated_get(depsgraph)
        gm = eg.to_mesh()
        am = ea.to_mesh()
        gp = [eg.matrix_world @ vertex.co for vertex in gm.vertices]
        gf = [tuple(poly.vertices) for poly in gm.polygons]
        ap = [ea.matrix_world @ vertex.co for vertex in am.vertices]
        normal_matrix = ea.matrix_world.to_3x3().inverted().transposed()
        an = [(normal_matrix @ vertex.normal).normalized() for vertex in am.vertices]
        bvh = BVHTree.FromPolygons(gp, gf, all_triangles=False)
        exposed = []
        covered = 0
        for index, (point, normal) in enumerate(zip(ap, an)):
            bone = actor_bones[index]
            if bone is None or not any(token in bone for token in ("Clavicle", "Upperarm", "Spine02")):
                continue
            outward = bvh.ray_cast(point + normal * epsilon, normal, options.max_distance)
            if outward[0] is not None:
                face_index = outward[2]
                if face_index < len(polygon_side) and polygon_side[face_index] is not None:
                    covered += 1
                continue
            inward = bvh.ray_cast(point - normal * epsilon, -normal, options.max_distance)
            if inward[0] is None:
                continue
            location, _hit_normal, face_index, distance = inward
            if face_index >= len(polygon_side):
                continue
            side = polygon_side[face_index]
            if side is None or point.x * seam_center_x[side] <= 0.0:
                continue
            exposed.append({
                "actor_vertex": index,
                "bone": bone,
                "side": side,
                "behind_distance_m": float(distance),
                "point": [float(value) for value in point],
                "actor_normal": [float(value) for value in normal],
                "garment_face": int(face_index),
                "garment_vertices": list(gf[face_index]),
            })
        reports.append({
            "frame": frame,
            "covered_actor_vertices": covered,
            "exposed_count": len(exposed),
            "side_counts": dict(Counter(item["side"] for item in exposed)),
            "bone_counts": dict(Counter(item["bone"] for item in exposed).most_common()),
            "items": exposed,
        })
        eg.to_mesh_clear()
        ea.to_mesh_clear()

    report = {
        "schema": "assetsstudio_actor_shoulder_visibility_rays_v1",
        "blend": str(options.blend.resolve()),
        "max_distance_m": options.max_distance,
        "method": "outward ray means covered; inward-only armhole hit means Actor skin is in front",
        "frames": reports,
    }
    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "peaks": sorted(
            ({"frame": item["frame"], "count": item["exposed_count"], "sides": item["side_counts"]} for item in reports),
            key=lambda item: item["count"], reverse=True,
        )[:15],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
