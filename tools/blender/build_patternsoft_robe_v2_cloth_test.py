"""Build a Blender cloth smoke test from a PatternSoft visual project.

This is a technical bridge: it reads PatternSoft's curved 2D pieces, lays
them around the current Actor, creates sewing springs from the declared seam
segment pairs, and runs a short Blender Cloth simulation. It is deliberately
not a final garment generator; the output is used to judge whether the paper
pattern is worth refining before materials and animation work.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--simulation-end", type=int, default=36)
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    return parser.parse_args(argv)


def make_material() -> bpy.types.Material:
    material = bpy.data.materials.new("PatternSoft_MageRobe_V2")
    material.diffuse_color = (0.12, 0.035, 0.32, 1.0)
    material.metallic = 0.0
    material.roughness = 0.82
    return material


def cubic(a: Vector, c1: Vector, c2: Vector, b: Vector, t: float) -> Vector:
    u = 1.0 - t
    return (u**3) * a + 3.0 * (u**2) * t * c1 + 3.0 * u * (t**2) * c2 + (t**3) * b


def local_point(raw: dict) -> Vector:
    return Vector((float(raw["x"]), float(raw["y"]), 0.0))


def sample_piece(piece: dict, samples_per_segment: int = 8) -> tuple[list[Vector], dict[int, list[int]]]:
    points = piece["points"]
    sampled: list[Vector] = []
    segment_indices: dict[int, list[int]] = {}
    count = len(points)
    for seg_idx in range(count if piece.get("closed", True) else count - 1):
        a_raw = points[seg_idx]
        b_raw = points[(seg_idx + 1) % count]
        a = local_point(a_raw)
        b = local_point(b_raw)
        c1 = local_point(a_raw["curve"]["out"]) if a_raw.get("curve") else a
        c2 = local_point(b_raw["curve"]["in"]) if b_raw.get("curve") else b
        chain: list[int] = []
        for k in range(samples_per_segment):
            t = k / samples_per_segment
            v = cubic(a, c1, c2, b, t) if (a_raw.get("curve") or b_raw.get("curve")) else a.lerp(b, t)
            chain.append(len(sampled))
            sampled.append(v)
        segment_indices[seg_idx] = chain
    return sampled, segment_indices


def piece_layout(piece: dict, sampled: list[Vector], actor: bpy.types.Object) -> tuple[float, float, float, float]:
    xs = [v.x for v in sampled]
    ys = [v.y for v in sampled]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    actor_width = max(float(actor.dimensions.x), 1.0)
    actor_height = max(float(actor.dimensions.z), 1.0)
    name = piece["name"].lower()

    if "front left" in name:
        target_width, x_center, y_plane = actor_width * 0.43, -actor_width * 0.24, -0.56
        z_top, z_bottom = actor_height * 0.47, -actor_height * 0.43
    elif "front right" in name:
        target_width, x_center, y_plane = actor_width * 0.43, actor_width * 0.24, -0.56
        z_top, z_bottom = actor_height * 0.47, -actor_height * 0.43
    elif name == "back":
        target_width, x_center, y_plane = actor_width * 0.92, 0.0, 0.54
        z_top, z_bottom = actor_height * 0.47, -actor_height * 0.43
    elif "sleeve" in name:
        target_width, x_center, y_plane = actor_width * 0.53, (-actor_width * 0.73 if "left" in name else actor_width * 0.73), -0.02
        z_top, z_bottom = actor_height * 0.40, actor_height * 0.03
    else:
        target_width, x_center, y_plane = actor_width * 0.56, (-actor_width * 0.42 if "left" in name else actor_width * 0.42), 0.0
        z_top, z_bottom = actor_height * 0.78, actor_height * 0.49

    x_scale = target_width / width
    z_scale = (z_top - z_bottom) / height
    return x_scale, z_scale, x_center, y_plane


def make_panel_geometry(
    piece: dict,
    actor: bpy.types.Object,
    vertex_offset: int,
    all_vertices: list[tuple[float, float, float]],
    all_faces: list[tuple[int, int, int]],
    boundary_map: dict[str, dict[int, list[int]]],
    pins: list[int],
) -> None:
    sampled, segment_indices = sample_piece(piece)
    x_scale, z_scale, x_center, y_plane = piece_layout(piece, sampled, actor)
    xs = [v.x for v in sampled]
    ys = [v.y for v in sampled]
    min_x, min_y = min(xs), min(ys)
    local_to_mesh: list[int] = []
    for v in sampled:
        x = x_center + (v.x - (min_x + max(xs)) * 0.5) * x_scale
        z = (max(ys) - v.y) * z_scale
        all_vertices.append((x, y_plane, z))
        local_to_mesh.append(vertex_offset + len(local_to_mesh))

    poly = [Vector((v.x, v.y, 0.0)) for v in sampled]
    triangles = tessellate_polygon([poly])
    for tri in triangles:
        face_indices = []
        for v in tri:
            if isinstance(v, int):
                idx = v
            else:
                idx = next(
                    (i for i, candidate in enumerate(poly)
                     if abs(candidate.x - v.x) < 1e-7 and abs(candidate.y - v.y) < 1e-7),
                    None,
                )
                if idx is None:
                    raise RuntimeError(f"tessellation vertex missing for {piece['name']}")
            face_indices.append(local_to_mesh[idx])
        if len(set(face_indices)) == 3:
            all_faces.append(tuple(face_indices))

    boundary_map[piece["id"]] = {
        seg_idx: [local_to_mesh[i] for i in chain]
        for seg_idx, chain in segment_indices.items()
    }
    top_y = min_y + (max(ys) - min_y) * 0.12
    for local_idx, v in enumerate(sampled):
        if v.y <= top_y:
            pins.append(local_to_mesh[local_idx])


def connect_seams(seams: list[dict], boundary_map: dict[str, dict[int, list[int]]], edges: list[tuple[int, int]]) -> None:
    for seam in seams:
        a_ref = seam["a"]
        b_ref = seam["b"]
        a = boundary_map[a_ref["pieceId"]][int(a_ref["segmentIndex"])]
        b = boundary_map[b_ref["pieceId"]][int(b_ref["segmentIndex"])]
        if len(a) != len(b):
            raise RuntimeError(f"seam sample mismatch: {seam.get('name', seam['id'])}")
        if seam.get("reversed"):
            b = list(reversed(b))
        edges.extend((a[i], b[i]) for i in range(len(a)))


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


def add_camera_and_light(actor: bpy.types.Object) -> None:
    bpy.ops.object.camera_add(location=(4.8, -7.2, actor.dimensions.z * 0.36))
    camera = bpy.context.object
    camera.name = "PatternSoft_RobeV2_Camera"
    bpy.context.scene.camera = camera
    target = bpy.data.objects.new("PatternSoft_RobeV2_CameraTarget", None)
    target.location = (0.0, 0.0, actor.dimensions.z * 0.28)
    bpy.context.collection.objects.link(target)
    track = camera.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    bpy.ops.object.light_add(type="AREA", location=(3.0, -4.0, actor.dimensions.z * 1.8))
    key = bpy.context.object
    key.name = "PatternSoft_RobeV2_Key"
    key.data.energy = 1000.0
    key.data.shape = "DISK"
    key.data.size = 5.0
    key.rotation_euler = (0.35, 0.0, 0.55)


def build_garment(pattern: dict, actor: bpy.types.Object) -> bpy.types.Object:
    pieces = pattern["record"]["visual"]["pieces"]
    seams = pattern["record"]["visual"].get("seams", [])
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    sewing_edges: list[tuple[int, int]] = []
    boundary_map: dict[str, dict[int, list[int]]] = {}
    pins: list[int] = []
    for piece in pieces:
        make_panel_geometry(piece, actor, len(vertices), vertices, faces, boundary_map, pins)
    connect_seams(seams, boundary_map, sewing_edges)

    mesh = bpy.data.meshes.new("PatternSoft_MageRobe_V2_Mesh")
    mesh.from_pydata(vertices, sewing_edges, faces)
    mesh.update()
    garment = bpy.data.objects.new("PatternSoft_MageRobe_V2", mesh)
    bpy.context.collection.objects.link(garment)
    garment.data.materials.append(make_material())
    garment["workflow_route"] = "PatternSoft_JSON_to_Blender_Cloth"
    garment["source_pattern"] = pattern["record"]["name"]
    garment["paper_piece_count"] = len(pieces)
    garment["sewing_spring_count"] = len(sewing_edges)

    pin_group = garment.vertex_groups.new(name="PatternSoftShoulderPins")
    pin_group.add(pins, 1.0, "REPLACE")

    bpy.context.view_layer.objects.active = garment
    garment.select_set(True)
    bpy.ops.object.modifier_add(type="CLOTH")
    cloth = garment.modifiers[-1]
    cloth.name = "PatternSoft_RobeV2_Cloth"
    settings = cloth.settings
    settings.use_sewing_springs = True
    settings.sewing_force_max = 30.0
    settings.vertex_group_mass = "PatternSoftShoulderPins"
    settings.quality = 8
    settings.tension_stiffness = 18.0
    settings.compression_stiffness = 18.0
    settings.shear_stiffness = 10.0
    settings.bending_stiffness = 0.4
    settings.tension_damping = 8.0
    settings.compression_damping = 8.0
    settings.shear_damping = 5.0
    settings.bending_damping = 0.6
    settings.mass = 0.35
    settings.air_damping = 5.0
    collision = cloth.collision_settings
    collision.use_collision = True
    collision.distance_min = 0.025
    collision.use_self_collision = False
    cloth.point_cache.frame_start = 1
    cloth.point_cache.frame_end = 36
    refine = garment.modifiers.new("PatternSoft_RobeV2_RenderSubdivision", "SUBSURF")
    refine.subdivision_type = "SIMPLE"
    refine.levels = 1
    refine.render_levels = 1
    garment.select_set(False)
    return garment


def main() -> int:
    options = parse_args()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    pattern = json.loads(options.pattern_json.read_text(encoding="utf-8"))
    actor = add_body_collision()
    garment = build_garment(pattern, actor)
    add_camera_and_light(actor)

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = options.simulation_end
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "MATERIAL"

    scene.frame_set(options.simulation_end)
    bpy.context.view_layer.update()
    scene.render.filepath = str(options.output_dir / "patternsoft_robe_v2_cloth.png")
    bpy.ops.render.render(write_still=True)

    bpy.ops.object.select_all(action="DESELECT")
    actor.select_set(True)
    garment.select_set(True)
    bpy.context.view_layer.objects.active = garment
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output_dir / "patternsoft_robe_v2_cloth.blend"))
    bpy.ops.export_scene.gltf(
        filepath=str(options.output_dir / "patternsoft_robe_v2_cloth.glb"),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )
    print(
        "PATTERNSOFT_ROBE_V2_CLOTH_PASS "
        f"pieces={garment['paper_piece_count']} sewing_edges={garment['sewing_spring_count']} "
        f"frame={options.simulation_end} output={options.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
