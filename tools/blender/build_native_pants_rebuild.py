"""Build a controllable full-length pants shell from the Actor body.

This is the first pants-rebuild baseline.  It deliberately keeps the Actor's
bone weights and topology relationship, but applies garment clearance in
world-space because the source mesh is authored at a 0.01 object scale.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


PANTS_BONE_TOKENS = ("pelvis", "thigh", "calf", "twist")
FOOT_BONE_TOKENS = ("foot", "toe")


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--lower-z", type=float, default=0.06)
    parser.add_argument("--upper-z", type=float, default=0.80)
    parser.add_argument("--max-abs-x", type=float, default=0.48)
    parser.add_argument("--surface-offset", type=float, default=0.012)
    parser.add_argument("--radial-looseness", type=float, default=0.008)
    parser.add_argument("--solidify-thickness", type=float, default=0.006)
    parser.add_argument("--name", default="NativePantsRebuild")
    return parser.parse_args(argv)


def make_material() -> bpy.types.Material:
    material = bpy.data.materials.new("NativePantsRebuild_Material")
    material.diffuse_color = (0.08, 0.30, 0.85, 1.0)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = (0.08, 0.30, 0.85, 1.0)
        principled.inputs["Roughness"].default_value = 0.78
    return material


def group_names(source: bpy.types.Object) -> dict[int, str]:
    return {group.index: group.name.lower() for group in source.vertex_groups}


def vertex_is_leg_weighted(source: bpy.types.Object, vertex: bpy.types.MeshVertex, names: dict[int, str]) -> bool:
    leg_weight = 0.0
    for assignment in vertex.groups:
        name = names.get(assignment.group, "")
        if any(token in name for token in PANTS_BONE_TOKENS):
            leg_weight += assignment.weight
    # Ankle vertices often carry both calf and foot weights.  The lower-z
    # selection bound is the safer foot exclusion; rejecting shared weights
    # here would remove the calf shell and collapse the result into shorts.
    return leg_weight >= 0.20


def copy_vertex_groups(source: bpy.types.Object, target: bpy.types.Object, source_indices: list[int]) -> None:
    group_map = {
        source_group.index: target.vertex_groups.new(name=source_group.name)
        for source_group in source.vertex_groups
    }
    reverse = {source_index: target_index for target_index, source_index in enumerate(source_indices)}
    for source_index in source_indices:
        target_index = reverse[source_index]
        for assignment in source.data.vertices[source_index].groups:
            target_group = group_map.get(assignment.group)
            if target_group is not None and assignment.weight > 0.0:
                target_group.add([target_index], assignment.weight, "REPLACE")


def world_clearance(source: bpy.types.Object, vertex: bpy.types.MeshVertex, options: argparse.Namespace) -> Vector:
    point_world = source.matrix_world @ vertex.co
    normal_world = (source.matrix_world.to_3x3() @ vertex.normal).normalized()
    # Add the looseness along the evaluated body normal as well.  A radial
    # vector points inward on some inner-thigh vertices and can cancel the
    # intended shell clearance during animation.
    target_world = point_world + normal_world * (options.surface_offset + options.radial_looseness)
    return source.matrix_world.inverted() @ target_world


def add_crotch_bridge(
    source: bpy.types.Object,
    points: list[Vector],
    faces: list[tuple[int, ...]],
    options: argparse.Namespace,
) -> list[int]:
    """Close the inner-thigh opening with a tapered, thin gusset."""
    rings = (
        (0.47, 0.045, 0.105),
        (0.55, 0.075, 0.135),
        (0.64, 0.100, 0.155),
    )
    world_points = []
    for z, half_width, depth in rings:
        world_points.extend(
            [
                Vector((-half_width, -depth, z)),
                Vector((half_width, -depth, z)),
                Vector((-half_width, depth, z)),
                Vector((half_width, depth, z)),
            ]
        )
    local_points = [source.matrix_world.inverted() @ point for point in world_points]
    start = len(points)
    points.extend(local_points)
    faces.extend(
        [
            (start + 0, start + 1, start + 5, start + 4),
            (start + 4, start + 5, start + 9, start + 8),
            (start + 3, start + 2, start + 6, start + 7),
            (start + 7, start + 6, start + 10, start + 11),
            (start + 0, start + 4, start + 6, start + 2),
            (start + 4, start + 8, start + 10, start + 6),
            (start + 1, start + 3, start + 7, start + 5),
            (start + 5, start + 7, start + 11, start + 9),
            (start + 0, start + 2, start + 3, start + 1),
            (start + 8, start + 9, start + 11, start + 10),
        ]
    )
    return list(range(start, start + len(local_points)))


def add_waistband(
    source: bpy.types.Object,
    points: list[Vector],
    faces: list[tuple[int, ...]],
) -> list[int]:
    """Keep the waist integrated into the source-derived pants shell."""
    return []

    # Retained as the recipe for a future sewn waistband, but not used in the
    # integrated pants candidate because a separate ring reads as a belt.
    segments = 32
    lower_z, upper_z = 0.735, 0.785
    # Push the front/back of the ring just outside the actor surface so the
    # front waist does not disappear behind the body and read as a notch.
    radius_x, radius_y = 0.355, 0.275
    world_points = []
    for z in (lower_z, upper_z):
        for segment in range(segments):
            angle = 2.0 * math.pi * segment / segments
            world_points.append(Vector((radius_x * math.cos(angle), radius_y * math.sin(angle), z)))
    local_points = [source.matrix_world.inverted() @ point for point in world_points]
    start = len(points)
    points.extend(local_points)
    for segment in range(segments):
        next_segment = (segment + 1) % segments
        faces.append((start + segment, start + next_segment, start + segments + next_segment, start + segments + segment))
    return list(range(start, start + len(local_points)))


def flatten_waist_boundary(
    source: bpy.types.Object,
    source_indices: list[int],
    points: list[Vector],
) -> None:
    """Make the selected source top edge meet the continuous waist ring."""
    waist_z = 0.735
    inverse = source.matrix_world.inverted()
    for target_index, source_index in enumerate(source_indices):
        source_world = source.matrix_world @ source.data.vertices[source_index].co
        if source_world.z < waist_z:
            continue
        target_world = source.matrix_world @ points[target_index]
        target_world.z = waist_z
        points[target_index] = inverse @ target_world


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.actor.resolve()))
    scene = bpy.context.scene
    scene.frame_set(1)

    source = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if source is None or source.type != "MESH":
        raise RuntimeError("Actor mesh ChibiBaseMesh_AccuRIG_InputMesh is required")
    if armature is None or armature.type != "ARMATURE":
        raise RuntimeError("Actor Armature is required")

    source.data.update()
    names = group_names(source)
    selected_faces: list[tuple[int, ...]] = []
    used_source_indices: set[int] = set()
    for polygon in source.data.polygons:
        center_world = source.matrix_world @ polygon.center
        if not (options.lower_z <= center_world.z <= options.upper_z):
            continue
        if abs(center_world.x) > options.max_abs_x:
            continue
        selected_faces.append(tuple(polygon.vertices))
        used_source_indices.update(polygon.vertices)

    if not selected_faces:
        raise RuntimeError("No pants faces matched the configured Actor bounds")

    source_indices = sorted(used_source_indices)
    source_to_target = {source_index: target_index for target_index, source_index in enumerate(source_indices)}
    points = [world_clearance(source, source.data.vertices[source_index], options) for source_index in source_indices]
    flatten_waist_boundary(source, source_indices, points)
    faces = [tuple(source_to_target[index] for index in face) for face in selected_faces]
    bridge_indices = add_crotch_bridge(source, points, faces, options)
    waistband_indices = add_waistband(source, points, faces)

    mesh = bpy.data.meshes.new(f"{options.name}_Mesh")
    mesh.from_pydata(points, [], faces)
    mesh.update()
    mesh.validate(verbose=False)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    source_index_attribute = mesh.attributes.new("assetslab_source_index", "INT", "POINT")
    for target_index, source_index in enumerate(source_indices):
        source_index_attribute.data[target_index].value = source_index
    for target_index in bridge_indices + waistband_indices:
        source_index_attribute.data[target_index].value = -1
    mesh.materials.append(make_material())

    garment = bpy.data.objects.new(options.name, mesh)
    scene.collection.objects.link(garment)
    garment.matrix_world = source.matrix_world.copy()
    garment["assetslab_garment_route"] = "native_blender_pants_rebuild"
    garment["assetslab_source_actor"] = source.name
    garment["assetslab_world_surface_offset"] = options.surface_offset
    garment["assetslab_radial_looseness"] = options.radial_looseness
    garment["assetslab_acceptance_status"] = "candidate_pending"

    copy_vertex_groups(source, garment, source_indices)
    hip_group = garment.vertex_groups.get("CC_Base_Hip") or garment.vertex_groups.new(name="CC_Base_Hip")
    left_thigh_group = garment.vertex_groups.get("CC_Base_L_Thigh") or garment.vertex_groups.new(name="CC_Base_L_Thigh")
    right_thigh_group = garment.vertex_groups.get("CC_Base_R_Thigh") or garment.vertex_groups.new(name="CC_Base_R_Thigh")
    # Anchor the upper gusset on the pelvis and blend the lower rows into the
    # corresponding thighs.  This keeps the seam connected without making a
    # rigid connector read as an independent moving color block.
    for local_index, target_index in enumerate(bridge_indices):
        is_left = local_index % 4 in (0, 2)
        is_upper = local_index // 4 == 2
        thigh_group = left_thigh_group if is_left else right_thigh_group
        hip_weight = 0.70 if is_upper else 0.25
        thigh_weight = 0.30 if is_upper else 0.75
        hip_group.add([target_index], hip_weight, "REPLACE")
        thigh_group.add([target_index], thigh_weight, "REPLACE")
    hip_group.add(waistband_indices, 1.0, "REPLACE")
    armature_modifier = garment.modifiers.new(f"{options.name}_Armature", "ARMATURE")
    armature_modifier.object = armature
    solidify = garment.modifiers.new(f"{options.name}_Thickness", "SOLIDIFY")
    solidify.thickness = options.solidify_thickness
    solidify.offset = 1.0
    solidify.use_rim = True

    source.hide_set(True)
    scene["assetslab_pants_rebuild_schema"] = "assetslab_native_pants_rebuild_v1"
    scene["assetslab_pants_rebuild_status"] = "candidate_pending"

    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "assetslab_native_pants_rebuild_v1",
        "source_actor": str(options.actor.resolve()),
        "source_mesh": source.name,
        "garment_object": garment.name,
        "selected_source_vertices": len(source_indices),
        "selected_faces": len(selected_faces),
        "crotch_bridge_vertices": len(bridge_indices),
        "waistband_vertices": len(waistband_indices),
        "selection_world": {
            "lower_z": options.lower_z,
            "upper_z": options.upper_z,
            "max_abs_x": options.max_abs_x,
            "surface_offset": options.surface_offset,
            "radial_looseness": options.radial_looseness,
            "solidify_thickness": options.solidify_thickness,
        },
        "animation_binding": {
            "armature": armature.name,
            "modifier": armature_modifier.name,
            "copied_vertex_groups": len(garment.vertex_groups),
        },
        "status": "candidate_pending",
        "next_gate": "render four views and validate eight walk samples",
    }
    (output / "pants_rebuild_geometry_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(output / f"{options.name}.blend"))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
