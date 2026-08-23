"""Build a parameterized cloak-body Cloth sewing smoke test in Blender.

This is a route-B benchmark, not the mage robe milestone.  It deliberately
tests only the body shell: three rectangular panels, sewn at the side and
center seams, pinned at the shoulder line, and simulated against the current
Actor body.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--robe-length-factor", type=float, default=1.0)
    parser.add_argument("--hem-width-factor", type=float, default=1.0)
    parser.add_argument("--hood-depth-factor", type=float, default=1.0)
    parser.add_argument("--simulation-end", type=int, default=36)
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    return parser.parse_args(argv)


def make_material() -> bpy.types.Material:
    material = bpy.data.materials.new("WorkflowSmoke_MageCloth")
    material.diffuse_color = (0.075, 0.12, 0.32, 1.0)
    material.metallic = 0.0
    material.roughness = 0.78
    return material


def add_grid(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int, int]],
    pins: list[int],
    x0: float,
    x1: float,
    y: float,
    z_top: float,
    z_bottom: float,
    nx: int,
    nz: int,
) -> list[list[int]]:
    grid: list[list[int]] = []
    for iz in range(nz):
        row: list[int] = []
        z = z_top + (z_bottom - z_top) * iz / (nz - 1)
        for ix in range(nx):
            x = x0 + (x1 - x0) * ix / (nx - 1)
            row.append(len(vertices))
            vertices.append((x, y, z))
        grid.append(row)

    for iz in range(nz - 1):
        for ix in range(nx - 1):
            a, b = grid[iz][ix], grid[iz][ix + 1]
            c, d = grid[iz + 1][ix + 1], grid[iz + 1][ix]
            faces.append((a, b, c, d))

    pins.extend(grid[0])
    return grid


def add_variable_grid(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int, int]],
    pins: list[int],
    x0_top: float,
    x1_top: float,
    y_top: float,
    x0_bottom: float,
    x1_bottom: float,
    y_bottom: float,
    z_top: float,
    z_bottom: float,
    nx: int,
    nz: int,
) -> list[list[int]]:
    grid: list[list[int]] = []
    for iz in range(nz):
        row: list[int] = []
        t = iz / (nz - 1)
        z = z_top + (z_bottom - z_top) * t
        x0 = x0_top + (x0_bottom - x0_top) * t
        x1 = x1_top + (x1_bottom - x1_top) * t
        y = y_top + (y_bottom - y_top) * t
        for ix in range(nx):
            x = x0 + (x1 - x0) * ix / (nx - 1)
            row.append(len(vertices))
            vertices.append((x, y, z))
        grid.append(row)

    for iz in range(nz - 1):
        for ix in range(nx - 1):
            a, b = grid[iz][ix], grid[iz][ix + 1]
            c, d = grid[iz + 1][ix + 1], grid[iz + 1][ix]
            faces.append((a, b, c, d))

    pins.extend(grid[0])
    return grid


def add_hood_panel(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int, int]],
    pins: list[int],
    theta_start: float,
    theta_end: float,
    hood_depth_factor: float,
    z_top: float,
    z_bottom: float,
    nx: int,
    nz: int,
) -> list[list[int]]:
    grid: list[list[int]] = []
    for iz in range(nz):
        row: list[int] = []
        t = iz / (nz - 1)
        z = z_top + (z_bottom - z_top) * t
        radius = (0.48 + 0.11 * (1.0 - t)) * hood_depth_factor
        for ix in range(nx):
            theta = theta_start + (theta_end - theta_start) * ix / (nx - 1)
            row.append(len(vertices))
            vertices.append((radius * math.sin(theta), radius * math.cos(theta), z))
        grid.append(row)

    for iz in range(nz - 1):
        for ix in range(nx - 1):
            a, b = grid[iz][ix], grid[iz][ix + 1]
            c, d = grid[iz + 1][ix + 1], grid[iz + 1][ix]
            faces.append((a, b, c, d))

    pins.extend(grid[-1])
    return grid


def add_sleeve_panel(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int, int]],
    pins: list[int],
    shoulder_x: float,
    wrist_x: float,
    shoulder_z: float,
    wrist_z: float,
    y: float,
    width_shoulder: float,
    width_wrist: float,
    nx: int,
    nz: int,
) -> list[list[int]]:
    grid: list[list[int]] = []
    for iz in range(nz):
        row: list[int] = []
        t = iz / (nz - 1)
        cx = shoulder_x + (wrist_x - shoulder_x) * t
        cz = shoulder_z + (wrist_z - shoulder_z) * t
        half_width = (width_shoulder + (width_wrist - width_shoulder) * t) * 0.5
        for ix in range(nx):
            x = cx - half_width + (2.0 * half_width) * ix / (nx - 1)
            row.append(len(vertices))
            vertices.append((x, y, cz))
        grid.append(row)

    for iz in range(nz - 1):
        for ix in range(nx - 1):
            a, b = grid[iz][ix], grid[iz][ix + 1]
            c, d = grid[iz + 1][ix + 1], grid[iz + 1][ix]
            faces.append((a, b, c, d))

    pins.extend(grid[0])
    return grid


def connect_seam(edges: list[tuple[int, int]], edge_a: list[int], edge_b: list[int]) -> None:
    if len(edge_a) != len(edge_b):
        raise ValueError("sewing edges must have the same vertex count")
    edges.extend(zip(edge_a, edge_b))


def build_garment(options: argparse.Namespace) -> bpy.types.Object:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    sewing_edges: list[tuple[int, int]] = []
    pins: list[int] = []

    nx, nz = 15, 20
    half_shoulder = 0.78
    half_hem = 1.16 * options.hem_width_factor
    top = 1.43
    length = 2.85 * options.robe_length_factor
    bottom = top - length
    front_y_top, front_y_bottom = -0.78, -0.58
    back_y_top, back_y_bottom = 0.78, 0.58

    front_left = add_variable_grid(
        vertices, faces, pins, -half_shoulder, 0.0, front_y_top, -half_hem, 0.0, front_y_bottom, top, bottom, nx, nz
    )
    front_right = add_variable_grid(
        vertices, faces, pins, 0.0, half_shoulder, front_y_top, 0.0, half_hem, front_y_bottom, top, bottom, nx, nz
    )
    back = add_variable_grid(
        vertices,
        faces,
        pins,
        -half_shoulder,
        half_shoulder,
        back_y_top,
        -half_hem,
        half_hem,
        back_y_bottom,
        top,
        bottom,
        nx * 2 - 1,
        nz,
    )

    hood_left = add_hood_panel(vertices, faces, pins, 0.0, 2.25, options.hood_depth_factor, 2.28, 1.38, 13, 12)
    hood_right = add_hood_panel(vertices, faces, pins, 0.0, -2.25, options.hood_depth_factor, 2.28, 1.38, 13, 12)

    sleeve_left_front = add_sleeve_panel(vertices, faces, pins, 0.28, 0.51, 1.36, 0.82, -0.24, 0.34, 0.25, 9, 11)
    sleeve_left_back = add_sleeve_panel(vertices, faces, pins, 0.28, 0.51, 1.36, 0.82, 0.24, 0.34, 0.25, 9, 11)
    sleeve_right_front = add_sleeve_panel(vertices, faces, pins, -0.30, -0.53, 1.36, 0.82, -0.24, 0.34, 0.25, 9, 11)
    sleeve_right_back = add_sleeve_panel(vertices, faces, pins, -0.30, -0.53, 1.36, 0.82, 0.24, 0.34, 0.25, 9, 11)

    # Center front seam and both long side seams.  The extra edges have no
    # faces and are therefore interpreted by Blender as sewing springs.
    connect_seam(sewing_edges, [row[-1] for row in front_left], [row[0] for row in front_right])
    connect_seam(sewing_edges, [row[0] for row in front_left], [row[0] for row in back])
    connect_seam(sewing_edges, [row[-1] for row in front_right], [row[-1] for row in back])
    connect_seam(sewing_edges, [row[0] for row in hood_left], [row[0] for row in hood_right])
    for front, back_panel in (
        (sleeve_left_front, sleeve_left_back),
        (sleeve_right_front, sleeve_right_back),
    ):
        connect_seam(sewing_edges, [row[0] for row in front], [row[0] for row in back_panel])
        connect_seam(sewing_edges, [row[-1] for row in front], [row[-1] for row in back_panel])

    mesh = bpy.data.meshes.new("WorkflowSmoke_CloakBodyMesh")
    mesh.from_pydata(vertices, sewing_edges, faces)
    mesh.update()
    garment = bpy.data.objects.new("WorkflowSmoke_CloakBody", mesh)
    bpy.context.collection.objects.link(garment)
    garment.data.materials.append(make_material())
    garment["workflow_route"] = "B_blender_cloth_sewing"
    garment["robe_length_factor"] = options.robe_length_factor
    garment["hem_width_factor"] = options.hem_width_factor
    garment["hood_depth_factor"] = options.hood_depth_factor
    garment["panel_count"] = 9
    garment["sewing_spring_count"] = len(sewing_edges)

    pin_group = garment.vertex_groups.new(name="ShoulderPin")
    pin_group.add(pins, 1.0, "REPLACE")

    bpy.context.view_layer.objects.active = garment
    garment.select_set(True)
    bpy.ops.object.modifier_add(type="CLOTH")
    cloth = garment.modifiers[-1]
    cloth.name = "WorkflowSmoke_ClothSewing"
    settings = cloth.settings
    settings.use_sewing_springs = True
    settings.sewing_force_max = 20.0
    settings.vertex_group_mass = "ShoulderPin"
    settings.quality = 8
    settings.tension_stiffness = 18.0
    settings.compression_stiffness = 18.0
    settings.shear_stiffness = 10.0
    settings.bending_stiffness = 0.35
    settings.tension_damping = 8.0
    settings.compression_damping = 8.0
    settings.shear_damping = 5.0
    settings.bending_damping = 0.5
    settings.mass = 0.35
    settings.air_damping = 5.0
    collision = cloth.collision_settings
    collision.use_collision = True
    collision.distance_min = 0.025
    collision.use_self_collision = False
    cloth.point_cache.frame_start = 1
    cloth.point_cache.frame_end = options.simulation_end
    garment.select_set(False)
    return garment


def add_body_collision() -> bpy.types.Object:
    body = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    if body is None or body.type != "MESH":
        raise RuntimeError("current Actor body mesh was not found")
    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    if not any(mod.type == "COLLISION" for mod in body.modifiers):
        bpy.ops.object.modifier_add(type="COLLISION")
    body.select_set(False)
    return body


def add_camera_and_light() -> None:
    bpy.ops.object.camera_add(location=(5.7, -7.8, 1.2))
    camera = bpy.context.object
    camera.name = "WorkflowSmoke_Camera"
    bpy.context.scene.camera = camera
    target = bpy.data.objects.new("WorkflowSmoke_CameraTarget", None)
    target.location = (0.0, 0.0, 0.15)
    bpy.context.collection.objects.link(target)
    track = camera.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    bpy.ops.object.light_add(type="AREA", location=(3.0, -4.0, 6.0))
    key = bpy.context.object
    key.name = "WorkflowSmoke_Key"
    key.data.energy = 900.0
    key.data.shape = "DISK"
    key.data.size = 5.0
    key.rotation_euler = (0.45, 0.0, 0.55)


def main() -> int:
    options = parse_args()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    body = add_body_collision()
    garment = build_garment(options)
    add_camera_and_light()

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = options.simulation_end
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "MATERIAL"

    scene.frame_set(options.simulation_end)
    bpy.context.view_layer.update()
    scene.render.filepath = str(options.output_dir / "route_b_cloth_sewing_body.png")
    bpy.ops.render.render(write_still=True)

    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    garment.select_set(True)
    bpy.context.view_layer.objects.active = garment
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output_dir / "route_b_cloth_sewing_body.blend"))
    bpy.ops.export_scene.gltf(
        filepath=str(options.output_dir / "route_b_cloth_sewing_body.glb"),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )
    print(
        "ROUTE_B_SMOKE_PASS "
        f"panels={garment['panel_count']} sewing_edges={garment['sewing_spring_count']} "
        f"frame={options.simulation_end} output={options.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
