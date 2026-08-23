"""Repair the upper face opening and head clearance of a Q-style robe candidate."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", type=Path)
    parser.add_argument("--output-dir", type=Path)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    options, _ = parser.parse_known_args(argv)
    options.input_blend = options.input_blend or Path(os.environ["COLLAR_INPUT_BLEND"])
    options.output_dir = options.output_dir or Path(os.environ["COLLAR_OUTPUT_DIR"])
    return options


def head_bounds(body: bpy.types.Object) -> tuple[Vector, Vector]:
    group = body.vertex_groups.get("CC_Base_Head")
    if group is None:
        raise RuntimeError("Actor head vertex group is missing")
    points = [
        body.matrix_world @ vertex.co
        for vertex in body.data.vertices
        if any(item.group == group.index and item.weight >= 0.25 for item in vertex.groups)
    ]
    if len(points) < 10:
        raise RuntimeError("Actor head group contains too few vertices")
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def render_candidate(scene: bpy.types.Scene, body: bpy.types.Object, garment: bpy.types.Object, output: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_qstyle_partitioned_robe import render_frame

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.035, 0.035, 0.05)
    original_hide_render = {obj.name: obj.hide_render for obj in scene.objects}
    for obj in scene.objects:
        if obj.type == "MESH" and obj not in {body, garment}:
            obj.hide_render = True
    for label in ("front", "side", "three_quarter"):
        render_frame(scene, body, garment, output, 1, label)
    armature = bpy.data.objects.get("Armature")
    action = armature.animation_data.action if armature and armature.animation_data else None
    if armature and action:
        armature.data.pose_position = "POSE"
        start, end = int(action.frame_range[0]), int(action.frame_range[1])
        for index in range(5):
            frame = round(start + (end - start) * index / 4.0)
            render_frame(scene, body, garment, output, frame, f"motion_{frame:03d}")
    for name, hidden in original_hide_render.items():
        if name in scene.objects:
            scene.objects[name].hide_render = hidden


def main() -> int:
    options = parse_args()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    scene = bpy.context.scene
    body = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    garment = bpy.data.objects.get("QStylePartitionedRobe_FitCandidate")
    if body is None or garment is None:
        raise RuntimeError("collar repair input must contain Actor body and QStylePartitionedRobe_FitCandidate")
    scene.frame_set(1)
    bpy.context.view_layer.update()
    garment.matrix_world = garment.matrix_world.copy()
    head_low, head_high = head_bounds(body)
    head_center = (head_low + head_high) * 0.5
    head_radii = (head_high - head_low) * 0.5
    opening_faces = 0
    projected_vertices = 0

    mesh = garment.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    for face in bm.faces:
        center = face.calc_center_median()
        # Open a centered face/neck opening on the front (negative Y) while
        # retaining the side and back hood/cowl volume.
        if (
            center.y < head_center.y - head_radii.y * 0.54
            and abs(center.x - head_center.x) < head_radii.x * 0.62
            and head_low.z + 0.04 < center.z < head_high.z - 0.10
        ):
            face.tag = True
        else:
            face.tag = False
    delete_faces = [face for face in bm.faces if face.tag]
    opening_faces = len(delete_faces)
    if delete_faces:
        bmesh.ops.delete(bm, geom=delete_faces, context="FACES")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    # Push only upper central vertices that are inside the expanded head
    # ellipsoid. This retains a loose hood/cowl instead of collapsing it onto
    # the head, while leaving the lower robe body untouched.
    margin = 0.045
    expanded = head_radii + Vector((margin, margin, margin))
    for vertex in mesh.vertices:
        point = garment.matrix_world @ vertex.co
        if point.z < head_low.z + 0.02 or abs(point.x - head_center.x) > expanded.x * 1.05:
            continue
        normalized = Vector(
            (
                (point.x - head_center.x) / max(expanded.x, 1e-6),
                (point.y - head_center.y) / max(expanded.y, 1e-6),
                (point.z - head_center.z) / max(expanded.z, 1e-6),
            )
        )
        magnitude = normalized.length
        if magnitude < 1.0:
            projected = head_center + normalized.normalized() * expanded if magnitude > 1e-6 else head_center + Vector((0.0, expanded.y, 0.0))
            vertex.co = garment.matrix_world.inverted() @ projected
            projected_vertices += 1

    garment.data.update()
    garment.name = "QStyleCollarHoodRepair_FitCandidate"
    garment["workflow_route"] = "qstyle_partitioned_external_template"
    garment["collar_hood_repair"] = "front_opening_and_head_ellipsoid_clearance"
    garment["status"] = "review_required"
    render_candidate(scene, body, garment, options.output_dir)
    output_blend = options.output_dir / "qstyle_collar_hood_repaired.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    report = {
        "schema": "assetsstudio_qstyle_collar_hood_repair_v1",
        "input_blend": str(options.input_blend.resolve()),
        "output_blend": str(output_blend.resolve()),
        "garment_object": garment.name,
        "head_bbox_min": [round(float(value), 6) for value in head_low],
        "head_bbox_max": [round(float(value), 6) for value in head_high],
        "opening_faces_deleted": opening_faces,
        "head_clearance_vertices_projected": projected_vertices,
        "status": "review_required",
        "limitations": [
            "The repair is geometric and deterministic; it is not cloth simulation.",
            "The source topology still does not encode a production hood seam contract.",
        ],
    }
    (options.output_dir / "collar_hood_repair_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
