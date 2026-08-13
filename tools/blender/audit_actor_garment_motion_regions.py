"""Audit Actor garment penetration by stable rest-space garment zones.

The legacy local audit groups most vertices as ``other``.  This report keeps
the garment vertex index stable across frames, compares every pose with REST,
and records both the GarmentCode panel zone and nearest Actor bone region.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--panel-membership", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--garment-name", default="GarmentCodeShirt_ActorTransfer")
    parser.add_argument("--threshold", type=float, default=0.01)
    parser.add_argument(
        "--frame-step",
        type=int,
        default=0,
        help="audit the complete action at this step; zero keeps the standard eight review frames",
    )
    return parser.parse_args(argv)


def panel_family(panels: list[str]) -> str:
    if any(name.startswith("left_sleeve_") or name.startswith("sl_left_cuff_") for name in panels):
        return "left_sleeve"
    if any(name.startswith("right_sleeve_") or name.startswith("sl_right_cuff_") for name in panels):
        return "right_sleeve"
    return "torso"


def garment_zone(rest_point, family: str) -> str:
    if family == "torso":
        if rest_point.z >= 1.42:
            return "neckline"
        if rest_point.z <= 0.64:
            return "hem"
        if rest_point.z >= 1.22 and abs(rest_point.x) >= 0.18:
            return "shoulder"
        return "torso"
    absolute_x = abs(rest_point.x)
    side = "left" if family == "left_sleeve" else "right"
    if absolute_x <= 0.34:
        return f"{side}_armhole"
    if absolute_x >= 0.43:
        return f"{side}_cuff"
    return f"{side}_sleeve_mid"


def main() -> int:
    options = cli_args()
    if options.threshold <= 0.0:
        raise ValueError("--threshold must be positive")
    membership = json.loads(options.panel_membership.resolve().read_text(encoding="utf-8"))
    if membership.get("schema") != "assetsstudio_garmentcode_panel_membership_v1":
        raise RuntimeError("unsupported panel-membership schema")
    vertex_panels = membership["vertex_panels"]

    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    scene = bpy.context.scene
    garment = bpy.data.objects.get(options.garment_name)
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if garment is None or actor is None or armature is None:
        raise RuntimeError("blend is missing garment, Actor, or armature")
    if len(vertex_panels) != len(garment.data.vertices):
        raise RuntimeError("panel-membership/garment vertex count mismatch")
    action = armature.animation_data.action if armature.animation_data else None
    if action is None:
        raise RuntimeError("Actor armature has no action")

    garment_group_names = {group.index: group.name for group in garment.vertex_groups}
    actor_group_names = {group.index: group.name for group in actor.vertex_groups}
    rest_points = [garment.matrix_world @ vertex.co for vertex in garment.data.vertices]
    families = [panel_family(panels) for panels in vertex_panels]
    zones = [garment_zone(point, family) for point, family in zip(rest_points, families)]
    shared_armhole_indices: dict[str, list[int]] = {"left_sleeve": [], "right_sleeve": []}
    membership_roles: list[str] = []
    for vertex_index, panels in enumerate(vertex_panels):
        family = families[vertex_index]
        is_torso = any("torso" in name for name in panels)
        if family in shared_armhole_indices and is_torso:
            shared_armhole_indices[family].append(vertex_index)
            membership_roles.append("shared_armhole_seam")
        elif family in shared_armhole_indices:
            membership_roles.append("sleeve_only")
        else:
            membership_roles.append("torso_only")

    seam_distances: list[float | None] = []
    for vertex_index, (point, family) in enumerate(zip(rest_points, families)):
        seam_indices = shared_armhole_indices.get(family, [])
        seam_distances.append(
            min(
                ((point - rest_points[seam_index]).length for seam_index in seam_indices),
                default=None,
            )
        )

    def evaluate(frame: int, pose_position: str) -> list[dict[str, object]]:
        armature.data.pose_position = pose_position
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated_garment = garment.evaluated_get(depsgraph)
        evaluated_actor = actor.evaluated_get(depsgraph)
        garment_mesh = evaluated_garment.to_mesh()
        actor_mesh = evaluated_actor.to_mesh()
        garment_points = [evaluated_garment.matrix_world @ vertex.co for vertex in garment_mesh.vertices]
        actor_points = [evaluated_actor.matrix_world @ vertex.co for vertex in actor_mesh.vertices]
        actor_faces = [tuple(polygon.vertices) for polygon in actor_mesh.polygons]
        bvh = BVHTree.FromPolygons(actor_points, actor_faces, all_triangles=False)
        penetrating: list[dict[str, object]] = []
        for vertex_index, point in enumerate(garment_points):
            nearest = bvh.find_nearest(point)
            if nearest is None:
                continue
            location, normal, face_index, distance = nearest
            signed = (point - location).dot(normal.normalized())
            if signed >= -options.threshold:
                continue
            body_weights = Counter()
            for actor_index in actor_faces[face_index]:
                for assignment in actor.data.vertices[actor_index].groups:
                    body_weights[actor_group_names.get(assignment.group, str(assignment.group))] += assignment.weight
            garment_weights = sorted(
                (
                    (garment_group_names.get(assignment.group, str(assignment.group)), assignment.weight)
                    for assignment in garment.data.vertices[vertex_index].groups
                ),
                key=lambda item: item[1],
                reverse=True,
            )
            penetrating.append({
                "vertex": vertex_index,
                "point": [float(value) for value in point],
                "depth_m": float(-signed),
                "distance_m": float(distance),
                "family": families[vertex_index],
                "zone": zones[vertex_index],
                "panels": vertex_panels[vertex_index],
                "membership_role": membership_roles[vertex_index],
                "rest_armhole_seam_distance_m": seam_distances[vertex_index],
                "nearest_actor_face": int(face_index),
                "nearest_actor_bone": body_weights.most_common(1)[0][0] if body_weights else None,
                "garment_weights": garment_weights[:4],
            })
        evaluated_garment.to_mesh_clear()
        evaluated_actor.to_mesh_clear()
        return penetrating

    rest_frame = int(action.frame_range[0])
    rest_items = evaluate(rest_frame, "REST")
    rest_indices = {item["vertex"] for item in rest_items}
    if options.frame_step < 0:
        raise ValueError("--frame-step must be non-negative")
    if options.frame_step:
        last_frame = int(action.frame_range[1])
        sample_frames = list(range(rest_frame, last_frame + 1, options.frame_step))
        if sample_frames[-1] != last_frame:
            sample_frames.append(last_frame)
    else:
        sample_frames = [rest_frame, 11, 21, 31, 41, 51, 61, int(action.frame_range[1])]
    frame_reports = []
    for frame in sample_frames:
        items = evaluate(frame, "POSE")
        zone_counts = Counter(item["zone"] for item in items)
        bone_counts = Counter(item["nearest_actor_bone"] for item in items)
        current_indices = {item["vertex"] for item in items}
        motion_only = current_indices - rest_indices
        persistent = current_indices & rest_indices
        frame_reports.append({
            "frame": frame,
            "penetration_count": len(items),
            "persistent_from_rest_count": len(persistent),
            "motion_only_count": len(motion_only),
            "rest_resolved_count": len(rest_indices - current_indices),
            "zone_counts": dict(zone_counts.most_common()),
            "nearest_actor_bone_counts": dict(bone_counts.most_common()),
            "armhole_items": sorted(
                (item for item in items if item["zone"].endswith("_armhole")),
                key=lambda item: item["depth_m"],
                reverse=True,
            ),
            "worst": sorted(items, key=lambda item: item["depth_m"], reverse=True)[:20],
        })

    report = {
        "schema": "assetsstudio_actor_garment_motion_regions_v1",
        "blend": str(options.blend.resolve()),
        "panel_membership": str(options.panel_membership.resolve()),
        "threshold_m": options.threshold,
        "zone_policy": {
            "rest_space": True,
            "neckline_z_min": 1.42,
            "hem_z_max": 0.64,
            "shoulder_z_min": 1.22,
            "shoulder_abs_x_min": 0.18,
            "armhole_abs_x_max": 0.34,
            "cuff_abs_x_min": 0.43,
        },
        "rest": {
            "penetration_count": len(rest_items),
            "zone_counts": dict(Counter(item["zone"] for item in rest_items).most_common()),
            "nearest_actor_bone_counts": dict(Counter(item["nearest_actor_bone"] for item in rest_items).most_common()),
            "worst": sorted(rest_items, key=lambda item: item["depth_m"], reverse=True)[:20],
        },
        "frames": frame_reports,
        "status": "review_required",
    }
    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "rest_count": len(rest_items),
        "frames": [
            {
                "frame": item["frame"],
                "count": item["penetration_count"],
                "persistent": item["persistent_from_rest_count"],
                "motion_only": item["motion_only_count"],
                "zones": item["zone_counts"],
            }
            for item in frame_reports
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
