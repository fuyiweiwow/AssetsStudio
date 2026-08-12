"""Export the Actor REST pelvis and upper legs for pants collision."""

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
    parser.add_argument("--segmentation", required=True, type=Path)
    parser.add_argument("--object", default="ChibiBaseMesh_AccuRIG_InputMesh")
    parser.add_argument("--z-min", type=float, default=0.30)
    parser.add_argument("--z-max", type=float, default=0.82)
    parser.add_argument("--min-lower-weight", type=float, default=0.30)
    return parser.parse_args(argv)


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.actor.resolve()))
    for armature in (obj for obj in bpy.data.objects if obj.type == "ARMATURE"):
        if armature.animation_data is not None:
            armature.animation_data.action = None
        armature.data.pose_position = "REST"
    bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()
    actor = bpy.data.objects.get(options.object)
    if actor is None or actor.type != "MESH":
        raise RuntimeError(f"Actor mesh not found: {options.object}")

    evaluated = actor.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        if len(mesh.vertices) != len(actor.data.vertices):
            raise RuntimeError("evaluated mesh changed Actor vertex indexing")
        group_names = {group.index: group.name for group in actor.vertex_groups}
        lower_names = {
            name for name in group_names.values()
            if any(token in name for token in ("Hip", "Waist", "Spine01", "Thigh"))
        }
        selected_faces = []
        selected_vertices = set()
        for polygon in mesh.polygons:
            center = sum(
                (evaluated.matrix_world @ mesh.vertices[index].co for index in polygon.vertices),
                Vector(),
            ) / len(polygon.vertices)
            if not options.z_min <= center.z <= options.z_max:
                continue
            weights = []
            for index in polygon.vertices:
                weights.append(sum(
                    assignment.weight
                    for assignment in actor.data.vertices[index].groups
                    if group_names.get(assignment.group) in lower_names
                ))
            if sum(weights) / len(weights) < options.min_lower_weight:
                continue
            selected_faces.append(tuple(polygon.vertices))
            selected_vertices.update(polygon.vertices)
        if len(selected_faces) < 20:
            raise RuntimeError(f"too few lower-body faces selected: {len(selected_faces)}")

        ordered = sorted(selected_vertices)
        local_index = {source: index for index, source in enumerate(ordered)}
        vertices_gc = []
        for source_index in ordered:
            point = evaluated.matrix_world @ mesh.vertices[source_index].co
            vertices_gc.append((point.x * 100.0, point.z * 100.0, -point.y * 100.0))
        lines = ["# AssetsStudio Actor lower-body GarmentCode source\n"]
        lines.extend(f"v {x:.8f} {y:.8f} {z:.8f}\n" for x, y, z in vertices_gc)
        for face in selected_faces:
            # Blender -> GarmentCode is a proper rotation (determinant +1),
            # so preserve the Actor's outward winding.
            lines.append(
                "f " + " ".join(str(local_index[index] + 1) for index in face) + "\n"
            )

        labels = {
            "body": [], "left_arm": [], "right_arm": [],
            "left_leg": [], "right_leg": [], "face_internal": [],
        }
        for source_index in ordered:
            source = actor.data.vertices[source_index]
            scores = {
                "left_leg": sum(
                    assignment.weight for assignment in source.groups
                    if "L_Thigh" in group_names.get(assignment.group, "")
                ),
                "right_leg": sum(
                    assignment.weight for assignment in source.groups
                    if "R_Thigh" in group_names.get(assignment.group, "")
                ),
            }
            label, score = max(scores.items(), key=lambda item: item[1])
            labels[label if score >= 0.20 else "body"].append(local_index[source_index])

        output = options.output.resolve()
        report_path = options.report.resolve()
        segmentation_path = options.segmentation.resolve()
        for path in (output, report_path, segmentation_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(lines), encoding="utf-8")
        segmentation_path.write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
        report = {
            "schema": "assetsstudio_actor_lower_body_proxy_source_v1",
            "source_actor": str(options.actor.resolve()),
            "pose": "REST",
            "units": "centimetres",
            "coordinate_mapping": "Blender (x,y,z) -> GarmentCode (x,z,-y)",
            "selection": {
                "z_min_m": options.z_min,
                "z_max_m": options.z_max,
                "min_lower_weight": options.min_lower_weight,
                "allowed_groups": sorted(lower_names),
                "vertices": len(vertices_gc),
                "faces": len(selected_faces),
            },
            "bounds_cm": [
                [min(vertex[index] for vertex in vertices_gc) for index in range(3)],
                [max(vertex[index] for vertex in vertices_gc) for index in range(3)],
            ],
            "segmentation": str(segmentation_path),
            "output": str(output),
            "next_stage": "fill boundary loops, validate closed collision envelope, then simulate pants",
        }
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    finally:
        evaluated.to_mesh_clear()


if __name__ == "__main__":
    raise SystemExit(main())
