"""Export an Actor upper-body collision source in GarmentCode coordinates.

GarmentCode uses X=width, Y=up and Z=front/back.  The Blender Actor uses
X=width, Y=depth and Z=up, so this exporter maps (x, y, z) to (x, z, -y)
after applying the Actor's centimetre-like object scale.

Only torso, clavicle and upper-arm weighted faces are kept.  Head, forearm,
hand and leg geometry is intentionally excluded before the downstream voxel
closure step.  The exported surface is an intermediate source; the closed
proxy is created by the AssetsLab GarmentCode proxy builder.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--segmentation", type=Path, help="Optional official six-label vertex segmentation JSON")
    parser.add_argument("--object", default="ChibiBaseMesh_AccuRIG_InputMesh")
    parser.add_argument("--frame", type=int, default=1)
    parser.add_argument("--rest-pose", action="store_true", help="Clear the active action and export the armature rest pose")
    parser.add_argument("--z-min", type=float, default=0.45, help="Blender world Z in metres")
    parser.add_argument("--z-max", type=float, default=1.60, help="Blender world Z in metres")
    parser.add_argument("--min-allowed-weight", type=float, default=0.32)
    parser.add_argument("--max-abs-depth", type=float, default=0.32, help="Actor world Y depth limit in metres")
    parser.add_argument("--torso-only", action="store_true", help="Exclude clavicle/upper-arm groups for a collision-only torso diagnostic")
    parser.add_argument("--arms-only", action="store_true", help="Keep only clavicle/upper-arm groups for an isolated arm collision diagnostic")
    parser.add_argument("--exclude-arm-faces-below-z", type=float, default=None, help="Exclude faces whose arm weighting dominates below this Actor world Z")
    parser.add_argument("--include-any-vertex-weight", action="store_true", help="Keep a face when any vertex meets the weight threshold; diagnostic for section measurement")
    return parser.parse_args(argv)


def main() -> int:
    options = cli_args()
    if options.torso_only and options.arms_only:
        raise RuntimeError("--torso-only and --arms-only are mutually exclusive")
    bpy.ops.wm.open_mainfile(filepath=str(options.actor.resolve()))
    if options.rest_pose:
        for armature in (obj for obj in bpy.data.objects if obj.type == "ARMATURE"):
            if armature.animation_data is not None:
                armature.animation_data.action = None
            armature.data.pose_position = "REST"
        bpy.context.scene.frame_set(0)
    else:
        bpy.context.scene.frame_set(options.frame)
    bpy.context.view_layer.update()
    actor = bpy.data.objects.get(options.object)
    if actor is None or actor.type != "MESH":
        raise RuntimeError(f"Actor mesh not found: {options.object}")

    evaluated = actor.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        if len(mesh.vertices) != len(actor.data.vertices):
            raise RuntimeError("evaluated mesh changed vertex indexing; proxy export must be audited")
        group_names = {group.index: group.name for group in actor.vertex_groups}
        if options.torso_only:
            allowed_tokens = ("Hip", "Waist", "Spine", "NeckTwist")
        elif options.arms_only:
            allowed_tokens = ("Clavicle", "Upperarm")
        else:
            allowed_tokens = (
                "Hip", "Waist", "Spine", "NeckTwist", "Clavicle", "Upperarm"
            )
        allowed_names = {
            name for name in group_names.values()
            if any(token in name for token in allowed_tokens)
        }
        selected_faces = []
        selected_vertices = set()
        for polygon in mesh.polygons:
            center = sum(
                (evaluated.matrix_world @ mesh.vertices[index].co for index in polygon.vertices),
                start=Vector((0.0, 0.0, 0.0)),
            )
            center /= max(len(polygon.vertices), 1)
            if not (options.z_min <= center.z <= options.z_max):
                continue
            if abs(center.y) > options.max_abs_depth:
                continue
            weights = []
            arm_weights = []
            for index in polygon.vertices:
                source = actor.data.vertices[index]
                weights.append(sum(
                    assignment.weight
                    for assignment in source.groups
                    if group_names.get(assignment.group) in allowed_names
                ))
                arm_weights.append(sum(
                    assignment.weight
                    for assignment in source.groups
                    if group_names.get(assignment.group) and any(
                        token in group_names.get(assignment.group, "")
                        for token in ("Clavicle", "Upperarm")
                    )
                ))
            if (
                options.exclude_arm_faces_below_z is not None
                and center.z < options.exclude_arm_faces_below_z
                and sum(arm_weights) / max(len(arm_weights), 1) > sum(weights) / max(len(weights), 1) * 0.35
            ):
                continue
            face_weight = max(weights) if options.include_any_vertex_weight else sum(weights) / max(len(weights), 1)
            if face_weight < options.min_allowed_weight:
                continue
            selected_faces.append(tuple(polygon.vertices))
            selected_vertices.update(polygon.vertices)

        if len(selected_faces) < 20:
            raise RuntimeError(f"too few upper-body faces selected: {len(selected_faces)}")

        indices = {source: index for index, source in enumerate(sorted(selected_vertices), start=1)}
        vertices_gc = []
        for source_index in sorted(selected_vertices):
            point = evaluated.matrix_world @ mesh.vertices[source_index].co
            # Actor world metres -> source centimetres, then Blender axes ->
            # GarmentCode axes (X width, Y up, Z front).
            x_cm = point.x * 100.0
            y_cm = point.z * 100.0
            z_cm = -point.y * 100.0
            vertices_gc.append((x_cm, y_cm, z_cm))

        output = options.output.resolve()
        report_path = options.report.resolve()
        segmentation_path = options.segmentation.resolve() if options.segmentation else None
        output.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# AssetsStudio Actor upper-body GarmentCode source\n"]
        lines.extend(f"v {x:.8f} {y:.8f} {z:.8f}\n" for x, y, z in vertices_gc)
        for face in selected_faces:
            # Blender polygons are generally triangles/quads; OBJ accepts both.
            lines.append("f " + " ".join(str(indices[index]) for index in face) + "\n")
        output.write_text("".join(lines), encoding="utf-8")

        if segmentation_path is not None:
            labels = {
                "body": [], "left_arm": [], "right_arm": [],
                "left_leg": [], "right_leg": [], "face_internal": [],
            }
            for source_index in sorted(selected_vertices):
                vertex = actor.data.vertices[source_index]
                scores = {
                    "left_arm": sum(
                        assignment.weight
                        for assignment in vertex.groups
                        if any(token in group_names.get(assignment.group, "")
                               for token in ("L_Clavicle", "L_Upperarm"))
                    ),
                    "right_arm": sum(
                        assignment.weight
                        for assignment in vertex.groups
                        if any(token in group_names.get(assignment.group, "")
                               for token in ("R_Clavicle", "R_Upperarm"))
                    ),
                }
                label, score = max(scores.items(), key=lambda item: item[1])
                labels[label if score > 0.0 else "body"].append(indices[source_index] - 1)
            segmentation_path.parent.mkdir(parents=True, exist_ok=True)
            segmentation_path.write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
        mins = [min(vertex[index] for vertex in vertices_gc) for index in range(3)]
        maxs = [max(vertex[index] for vertex in vertices_gc) for index in range(3)]
        report = {
            "schema": "assetsstudio_actor_upper_body_proxy_source_v1",
            "source_actor": str(options.actor.resolve()),
            "source_object": actor.name,
            "frame": 0 if options.rest_pose else options.frame,
            "pose_mode": "REST" if options.rest_pose else "POSE",
            "units": "centimetres",
            "coordinate_mapping": "Blender (x,y,z) -> GarmentCode (x,z,-y)",
            "selection": {
                "z_min_m": options.z_min,
                "z_max_m": options.z_max,
                "min_allowed_weight": options.min_allowed_weight,
                "max_abs_depth_m": options.max_abs_depth,
                "torso_only": options.torso_only,
                "arms_only": options.arms_only,
                "exclude_arm_faces_below_z": options.exclude_arm_faces_below_z,
                "include_any_vertex_weight": options.include_any_vertex_weight,
                "allowed_groups": sorted(allowed_names),
                "face_count": len(selected_faces),
                "vertex_count": len(vertices_gc),
            },
            "bounds_cm": {"min": mins, "max": maxs},
            "output": str(output),
            "segmentation": str(segmentation_path) if segmentation_path else None,
            "next_stage": "voxel-close this source, then simulate the GarmentCode paper pattern against the closed proxy",
        }
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    finally:
        evaluated.to_mesh_clear()


if __name__ == "__main__":
    raise SystemExit(main())
