"""Build a minimal Blender-native shorts control garment from Actor topology.

This is a Gate 1 control experiment. It intentionally does not use GarmentCode,
Shrinkwrap, Cloth, or a zero-penetration repair. A lower-body face subset is
copied from the Actor's rest mesh, offset slightly along rest normals, and
rebound to the original Actor armature using the copied vertex groups.
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
    parser.add_argument("--lower-z", type=float, default=0.40)
    parser.add_argument("--upper-z", type=float, default=0.738)
    parser.add_argument("--max-abs-x", type=float, default=0.40)
    parser.add_argument("--surface-offset", type=float, default=0.012)
    parser.add_argument("--solidify-thickness", type=float, default=0.006)
    return parser.parse_args(argv)


def world_point(obj: bpy.types.Object, co: Vector) -> Vector:
    return obj.matrix_world @ co


def make_material() -> bpy.types.Material:
    material = bpy.data.materials.new("NativeControlShorts_Material")
    material.diffuse_color = (0.08, 0.30, 0.85, 1.0)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = (0.08, 0.30, 0.85, 1.0)
        principled.inputs["Roughness"].default_value = 0.72
    return material


def copy_vertex_groups(
    source: bpy.types.Object,
    target: bpy.types.Object,
    source_indices: list[int],
) -> None:
    group_map = {}
    for source_group in source.vertex_groups:
        group_map[source_group.index] = target.vertex_groups.new(name=source_group.name)

    reverse = {source_index: target_index for target_index, source_index in enumerate(source_indices)}
    for source_index in source_indices:
        target_index = reverse[source_index]
        # Read assignments from the vertex itself. Calling VertexGroup.weight()
        # for every group emits a noisy Blender error for groups the vertex does
        # not belong to, even when the exception is caught.
        for assignment in source.data.vertices[source_index].groups:
            target_group = group_map.get(assignment.group)
            if target_group is not None and assignment.weight > 0.0:
                target_group.add([target_index], assignment.weight, "REPLACE")


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
    selected_faces = []
    used_source_indices: set[int] = set()
    for polygon in source.data.polygons:
        center_world = world_point(source, polygon.center)
        if not (options.lower_z <= center_world.z <= options.upper_z):
            continue
        if abs(center_world.x) > options.max_abs_x:
            continue
        selected_faces.append(tuple(polygon.vertices))
        used_source_indices.update(polygon.vertices)

    if not selected_faces:
        raise RuntimeError("No lower-body faces matched the native control bounds")

    source_indices = sorted(used_source_indices)
    source_to_target = {source_index: target_index for target_index, source_index in enumerate(source_indices)}
    points = []
    for source_index in source_indices:
        vertex = source.data.vertices[source_index]
        points.append(tuple(vertex.co + vertex.normal * options.surface_offset))
    faces = [tuple(source_to_target[index] for index in face) for face in selected_faces]

    mesh = bpy.data.meshes.new("NativeControlShorts_Mesh")
    mesh.from_pydata(points, [], faces)
    mesh.update()
    mesh.validate(verbose=False)
    mesh.materials.append(make_material())

    garment = bpy.data.objects.new("NativeControlShorts", mesh)
    scene.collection.objects.link(garment)
    garment.matrix_world = source.matrix_world.copy()
    garment["assetslab_garment_route"] = "native_blender_control"
    garment["assetslab_gate"] = "gate1_static_and_animation_control"
    garment["assetslab_source_actor"] = source.name
    garment["assetslab_surface_offset"] = options.surface_offset
    garment["assetslab_acceptance_status"] = "gate1_pending"

    copy_vertex_groups(source, garment, source_indices)
    armature_modifier = garment.modifiers.new("NativeControlShorts_Armature", "ARMATURE")
    armature_modifier.object = armature
    solidify = garment.modifiers.new("NativeControlShorts_Thickness", "SOLIDIFY")
    solidify.thickness = options.solidify_thickness
    solidify.offset = 1.0
    solidify.use_rim = True

    source.hide_viewport = True
    source.hide_set(True)
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj != garment and obj.name != source.name:
            if obj.name.startswith("NativeControl"):
                obj.hide_render = True
                obj.hide_set(True)

    scene["assetslab_native_control_schema"] = "assetslab_native_shorts_control_v1"
    scene["assetslab_native_control_status"] = "gate1_pending"
    scene["assetslab_native_control_source"] = str(options.actor.resolve())
    scene["assetslab_native_control_policy"] = (
        "No GarmentCode, Cloth, Shrinkwrap, or zero-penetration repair; "
        "use as a control experiment only."
    )

    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bounds = {
        "min": [min(v[axis] for v in points) for axis in range(3)],
        "max": [max(v[axis] for v in points) for axis in range(3)],
    }
    report = {
        "schema": "assetslab_native_shorts_control_v1",
        "source_actor": str(options.actor.resolve()),
        "source_mesh": source.name,
        "garment_object": garment.name,
        "selected_source_vertices": len(source_indices),
        "selected_faces": len(selected_faces),
        "bounds_local": bounds,
        "selection": {
            "lower_z": options.lower_z,
            "upper_z": options.upper_z,
            "max_abs_x": options.max_abs_x,
            "surface_offset": options.surface_offset,
            "solidify_thickness": options.solidify_thickness,
        },
        "animation_binding": {
            "armature": armature.name,
            "modifier": armature_modifier.name,
            "copied_vertex_groups": len(garment.vertex_groups),
        },
        "status": "gate1_pending",
        "next_gate": "render static four views and 8-frame front/right GIF before any GarmentCode branch",
    }
    (output / "native_control_geometry_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "native_control_shorts_v0.blend"))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
