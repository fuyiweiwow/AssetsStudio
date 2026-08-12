"""Localize Actor-transfer penetration by garment region and walk frame."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--garment-name", default="GarmentCodeShirt_ActorTransfer")
    parser.add_argument("--rest-only", action="store_true")
    parser.add_argument("--panel-membership", type=Path)
    return parser.parse_args(argv)


def main() -> int:
    options = args()
    panel_memberships = None
    if options.panel_membership is not None:
        membership = json.loads(options.panel_membership.resolve().read_text(encoding="utf-8"))
        if membership.get("schema") != "assetsstudio_garmentcode_panel_membership_v1":
            raise RuntimeError("unsupported panel-membership schema")
        panel_memberships = membership["vertex_panels"]
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    scene = bpy.context.scene
    garment = bpy.data.objects.get(options.garment_name)
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if garment is None or actor is None or armature is None:
        raise RuntimeError("blend is missing garment, Actor, or armature")
    # Surface-ring candidates are authored in REST mode, but this audit is a
    # motion audit.  Always evaluate the active action in POSE mode; otherwise
    # every sampled frame can silently reuse the rest pose and produce a false
    # impression of constant penetration.
    armature.data.pose_position = "REST" if options.rest_only else "POSE"
    action = armature.animation_data.action if armature.animation_data else None
    if action is None:
        raise RuntimeError("Actor armature has no action")
    group_names = {group.index: group.name for group in garment.vertex_groups}
    samples = [scene.frame_current] if options.rest_only else [int(action.frame_range[0]), 11, 21, 31, 41, 51, 61, int(action.frame_range[1])]
    frame_results = []
    for frame in samples:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eg = garment.evaluated_get(depsgraph)
        ea = actor.evaluated_get(depsgraph)
        gm = eg.to_mesh()
        am = ea.to_mesh()
        garment_points = [eg.matrix_world @ vertex.co for vertex in gm.vertices]
        actor_points = [ea.matrix_world @ vertex.co for vertex in am.vertices]
        actor_faces = [tuple(poly.vertices) for poly in am.polygons]
        bvh = BVHTree.FromPolygons(actor_points, actor_faces, all_triangles=False)
        regions = {"armpit_left": [], "armpit_right": [], "back_neck": [], "other": []}
        penetration = []
        family_counts = Counter()
        family_depths: dict[str, list[float]] = {"torso": [], "left_sleeve": [], "right_sleeve": []}
        for vertex_index, vertex in enumerate(garment_points):
            nearest = bvh.find_nearest(vertex)
            if nearest is None:
                continue
            location, normal, _face, distance = nearest
            signed = (vertex - location).dot(normal.normalized())
            if signed >= -0.01:
                continue
            if vertex.z >= 1.25 and vertex.y > 0.04 and abs(vertex.x) < 0.20:
                region = "back_neck"
            elif vertex.z >= 1.12 and vertex.z <= 1.42 and vertex.y < 0.04 and abs(vertex.x) >= 0.18:
                region = "armpit_left" if vertex.x > 0 else "armpit_right"
            else:
                region = "other"
            penetration.append({"point": [float(value) for value in vertex], "signed_m": float(signed), "distance_m": float(distance), "region": region})
            regions[region].append(penetration[-1])
            if panel_memberships is not None:
                panels = panel_memberships[vertex_index]
                if any(name.startswith("left_sleeve_") or name.startswith("sl_left_cuff_") for name in panels):
                    family = "left_sleeve"
                elif any(name.startswith("right_sleeve_") or name.startswith("sl_right_cuff_") for name in panels):
                    family = "right_sleeve"
                else:
                    family = "torso"
                family_counts[family] += 1
                family_depths[family].append(-float(signed))
        group_counter = Counter()
        for index, vertex in enumerate(garment.data.vertices):
            if index >= len(garment_points):
                continue
            if any(item["point"] == [float(value) for value in garment_points[index]] for item in penetration):
                for assignment in vertex.groups:
                    group_counter[group_names.get(assignment.group, str(assignment.group))] += assignment.weight
        frame_results.append({
            "frame": frame,
            "penetration_count": len(penetration),
            "regions": {
                name: {
                    "count": len(items),
                    "max_depth_m": max((-item["signed_m"] for item in items), default=0.0),
                    "examples": sorted(items, key=lambda item: item["signed_m"])[:5],
                }
                for name, items in regions.items()
            },
            "panel_family_penetration": {
                name: {
                    "count": family_counts[name],
                    "max_depth_m": max(family_depths[name], default=0.0),
                    "over_0p01_m": sum(value > 0.01 for value in family_depths[name]),
                }
                for name in ("torso", "left_sleeve", "right_sleeve")
            } if panel_memberships is not None else None,
            "penetrating_weight_totals": group_counter.most_common(12),
        })
        eg.to_mesh_clear()
        ea.to_mesh_clear()
    report = {
        "schema": "assetsstudio_actor_garment_local_penetration_audit_v1",
        "blend": str(options.blend.resolve()),
        "pose_mode": "REST" if options.rest_only else "POSE",
        "panel_membership": str(options.panel_membership.resolve()) if options.panel_membership else None,
        "frames": frame_results,
        "status": "review_required",
    }
    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
