"""Generate a parameterized Actor-conformed robe body and sleeves.

This is a geometry bridge, not a cloth simulator.  It deliberately creates
an open-neck, flared robe shell from the measured Actor envelope, then adds
two independent tapered sleeves.  The result is used to test whether the
Actor-first 3D base is a better starting point than flat GarmentCode panels.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--head-measurements", type=Path)
    parser.add_argument("--neck-under-head-cm", type=float, default=5.0)
    parser.add_argument("--actor-scale", type=float, default=56.6540755631)
    parser.add_argument("--hem-width-cm", type=float, default=104.0)
    parser.add_argument("--hem-depth-cm", type=float, default=58.0)
    parser.add_argument("--body-length-cm", type=float, default=82.0)
    parser.add_argument("--neck-width-cm", type=float, default=28.0)
    parser.add_argument("--sleeve-length-cm", type=float, default=55.0)
    parser.add_argument("--sleeve-radius-cm", type=float, default=12.0)
    parser.add_argument("--segments", type=int, default=24)
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    return parser.parse_args(argv)


def import_actor(path: Path, scale: float) -> tuple[bpy.types.Object, Vector, Vector]:
    bpy.ops.wm.obj_import(filepath=str(path))
    meshes = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"Actor OBJ produced no mesh: {path}")
    actor = meshes[0]
    actor.scale = (scale, scale, scale)
    bpy.context.view_layer.update()
    world_points = [actor.matrix_world @ v.co for v in actor.data.vertices]
    minimum = Vector((
        min(v.x for v in world_points),
        min(v.y for v in world_points),
        min(v.z for v in world_points),
    ))
    maximum = Vector((
        max(v.x for v in world_points),
        max(v.y for v in world_points),
        max(v.z for v in world_points),
    ))
    actor.hide_render = True
    actor.hide_viewport = True
    return actor, minimum, maximum


def material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.roughness = 0.84
    return mat


def mesh_object(
    name: str,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    mat: bpy.types.Material,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def ring_shell(
    name: str,
    rings: list[tuple[float, float, float]],
    segments: int,
    mat: bpy.types.Material,
    phase: float = 0.0,
) -> bpy.types.Object:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    for z, rx, ry in rings:
        for i in range(segments):
            theta = phase + (2.0 * math.pi * i / segments)
            vertices.append((rx * math.cos(theta), ry * math.sin(theta), z))
    for r in range(len(rings) - 1):
        for i in range(segments):
            a = r * segments + i
            b = r * segments + (i + 1) % segments
            c = (r + 1) * segments + (i + 1) % segments
            d = (r + 1) * segments + i
            faces.append((a, b, c, d))
    obj = mesh_object(name, vertices, faces, mat)
    obj["generator"] = "actor_conformed_robe_shell_v1"
    obj["open_neck"] = True
    return obj


def sleeve_mesh(
    name: str,
    start: Vector,
    end: Vector,
    start_radius: float,
    end_radius: float,
    segments: int,
    mat: bpy.types.Material,
) -> bpy.types.Object:
    axis = (end - start).normalized()
    helper = Vector((0.0, 1.0, 0.0))
    side = axis.cross(helper).normalized()
    up = side.cross(axis).normalized()
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    for center, radius in ((start, start_radius), (end, end_radius)):
        for i in range(segments):
            theta = 2.0 * math.pi * i / segments
            p = center + radius * (math.cos(theta) * side + math.sin(theta) * up)
            vertices.append(tuple(p))
    for i in range(segments):
        a = i
        b = (i + 1) % segments
        c = segments + (i + 1) % segments
        d = segments + i
        faces.append((a, b, c, d))
    obj = mesh_object(name, vertices, faces, mat)
    obj["generator"] = "actor_conformed_robe_shell_v1"
    obj["independent_sleeve"] = True
    return obj


def main() -> int:
    options = parse_args()
    options.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    _, minimum, maximum = import_actor(options.actor, options.actor_scale)
    height = maximum.z - minimum.z
    center_x = (minimum.x + maximum.x) * 0.5
    center_y = (minimum.y + maximum.y) * 0.5
    z_hem = minimum.z + max(18.0, height * 0.17)
    head_bottom_raw = None
    if options.head_measurements:
        head_source = json.loads(options.head_measurements.read_text(encoding="utf-8"))
        head_bbox = head_source["world_bbox"]
        calibration = float(head_source["calibration"]["cm_per_world_unit"])
        # Blender source Z becomes exported Actor-OBJ Y, which is Blender Z
        # after OBJ import.  Use the measured head bottom for the garment neck.
        head_bottom_raw = float(head_bbox["min"][2]) * calibration
        z_neck = head_bottom_raw - options.neck_under_head_cm
    else:
        z_neck = z_hem + options.body_length_cm
    body_length = z_neck - z_hem
    if body_length <= 20.0:
        raise RuntimeError(f"computed robe body length is too short: {body_length:.2f} cm")
    z_shoulder = z_neck - 9.0

    robe_mat = material("ActorConformedRobe_Violet", (0.18, 0.035, 0.42, 1.0))
    trim_mat = material("ActorConformedRobe_Trim", (0.52, 0.22, 0.08, 1.0))
    rings = [
        (z_hem, options.hem_width_cm * 0.50, options.hem_depth_cm * 0.50),
        (z_hem + 5.0, options.hem_width_cm * 0.46, options.hem_depth_cm * 0.46),
        (z_hem + body_length * 0.52, 38.0, 23.0),
        (z_shoulder, 42.0, 25.0),
        (z_neck, options.neck_width_cm * 0.50, options.neck_width_cm * 0.58),
    ]
    body = ring_shell("ActorConformedRobe_Body", rings, options.segments, robe_mat, phase=math.pi / options.segments)
    body.location.x = center_x
    body.location.y = center_y
    body["actor_height_cm"] = height
    body["body_length_cm"] = body_length
    body["hem_width_cm"] = options.hem_width_cm
    body["hem_depth_cm"] = options.hem_depth_cm
    body["neck_width_cm"] = options.neck_width_cm

    shoulder_z = z_shoulder - 2.0
    left_start = Vector((center_x - 33.0, center_y, shoulder_z))
    right_start = Vector((center_x + 33.0, center_y, shoulder_z))
    left_end = Vector((center_x - 33.0 - options.sleeve_length_cm, center_y + 1.5, shoulder_z - 31.0))
    right_end = Vector((center_x + 33.0 + options.sleeve_length_cm, center_y + 1.5, shoulder_z - 31.0))
    left = sleeve_mesh("ActorConformedRobe_Sleeve_L", left_start, left_end, options.sleeve_radius_cm, options.sleeve_radius_cm * 0.78, options.segments, robe_mat)
    right = sleeve_mesh("ActorConformedRobe_Sleeve_R", right_start, right_end, options.sleeve_radius_cm, options.sleeve_radius_cm * 0.78, options.segments, robe_mat)
    for sleeve in (left, right):
        sleeve["sleeve_length_cm"] = options.sleeve_length_cm
        sleeve["sleeve_radius_cm"] = options.sleeve_radius_cm

    for obj in (body, left, right):
        bevel = obj.modifiers.new("SoftTailorEdge", "BEVEL")
        bevel.width = 0.8
        bevel.segments = 2

    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    left.select_set(True)
    right.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.name = "ActorConformedRobeShell"
    bpy.ops.wm.obj_export(filepath=str(options.output), export_materials=False, export_selected_objects=True)
    manifest = {
        "schema": "assetsstudio_actor_conformed_robe_shell_v1",
        "coordinate_space": "Blender Z-up scene exported to Y-up centimeter OBJ",
        "front_semantic": "+Z in exported Actor OBJ",
        "actor": str(options.actor),
        "output": str(options.output),
        "actor_scale": options.actor_scale,
        "actor_bounds_cm": {"min": list(minimum), "max": list(maximum)},
        "parameters": {
            "hem_width_cm": options.hem_width_cm,
            "hem_depth_cm": options.hem_depth_cm,
            "body_length_cm": options.body_length_cm,
            "computed_body_length_cm": body_length,
            "neck_width_cm": options.neck_width_cm,
            "sleeve_length_cm": options.sleeve_length_cm,
            "sleeve_radius_cm": options.sleeve_radius_cm,
            "segments": options.segments,
        },
        "status": "geometry_candidate_review_required",
        "head_measurements": str(options.head_measurements) if options.head_measurements else None,
        "neck_under_head_cm": options.neck_under_head_cm,
        "head_bottom_raw_cm": head_bottom_raw,
    }
    options.output.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"ACTOR_CONFORMED_ROBE_SHELL_PASS output={options.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
