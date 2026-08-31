"""Fit a generated accessory to an unbound T-Pose profile and render review views."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", type=Path, required=True)
    parser.add_argument("--accessory", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--slot-id", required=True)
    parser.add_argument("--source-preparation", type=Path, required=True)
    parser.add_argument("--shape-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--resolution", type=int, default=768)
    parser.add_argument("--max-axis-scale-ratio", type=float, default=4.5)
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def imported_meshes(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj not in before and obj.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"no mesh imported from {path}")
    return meshes


def world_vertices(objects: list[bpy.types.Object]) -> list[Vector]:
    return [obj.matrix_world @ vertex.co for obj in objects for vertex in obj.data.vertices]


def bounds(points: list[Vector]) -> tuple[Vector, Vector]:
    return (
        Vector((min(v.x for v in points), min(v.y for v in points), min(v.z for v in points))),
        Vector((max(v.x for v in points), max(v.y for v in points), max(v.z for v in points))),
    )


def bake_world(objects: list[bpy.types.Object]) -> None:
    for obj in objects:
        obj.data.transform(obj.matrix_world)
        obj.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()


def build_bvh(objects: list[bpy.types.Object]) -> BVHTree:
    vertices: list[Vector] = []
    polygons: list[tuple[int, ...]] = []
    for obj in objects:
        offset = len(vertices)
        vertices.extend(obj.matrix_world @ vertex.co for vertex in obj.data.vertices)
        polygons.extend(tuple(offset + index for index in polygon.vertices) for polygon in obj.data.polygons)
    return BVHTree.FromPolygons(vertices, polygons, all_triangles=False, epsilon=1e-6)


def material(name: str, color: tuple[float, float, float, float], metallic=0.0) -> bpy.types.Material:
    result = bpy.data.materials.new(name)
    result.diffuse_color = color
    result.use_nodes = True
    shader = result.node_tree.nodes.get("Principled BSDF")
    if shader:
        shader.inputs["Base Color"].default_value = color
        shader.inputs["Roughness"].default_value = 0.68
        shader.inputs["Metallic"].default_value = metallic
    return result


def assign_material(objects: list[bpy.types.Object], value: bpy.types.Material) -> None:
    for obj in objects:
        obj.data.materials.clear()
        obj.data.materials.append(value)


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_views(
    actor: list[bpy.types.Object],
    accessory: list[bpy.types.Object],
    output_dir: Path,
    resolution: int,
) -> dict[str, str]:
    assign_material(actor, material("actor_proxy_neutral", (0.56, 0.62, 0.69, 1.0)))
    assign_material(accessory, material("accessory_candidate_brown", (0.38, 0.19, 0.075, 1.0)))
    points = world_vertices(actor + accessory)
    minimum, maximum = bounds(points)
    center = (minimum + maximum) * 0.5
    width = maximum.x - minimum.x
    depth = maximum.y - minimum.y
    height = maximum.z - minimum.z

    ground = material("review_ground", (0.075, 0.085, 0.105, 1.0))
    bpy.ops.mesh.primitive_plane_add(size=max(width, depth, height) * 4.0, location=(center.x, center.y, minimum.z))
    bpy.context.object.data.materials.append(ground)

    world = bpy.context.scene.world or bpy.data.worlds.new("review_world")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.035, 0.045, 0.06, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.55

    for name, location, energy, size in (
        ("key", (center.x - height, center.y - height, center.z + height), 1100.0, height),
        ("fill", (center.x + height, center.y - height * 0.5, center.z + height * 0.4), 650.0, height),
        ("rear_fill", (center.x, center.y + height, center.z + height * 0.55), 850.0, height),
    ):
        data = bpy.data.lights.new(name, type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        obj.location = location
        look_at(obj, center)

    camera_data = bpy.data.cameras.new("review_camera")
    camera_data.type = "ORTHO"
    camera = bpy.data.objects.new("review_camera", camera_data)
    bpy.context.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    camera_data.ortho_scale = max(height * 1.15, width * 1.15)
    distance = max(width, depth, height) * 2.5
    target = Vector((center.x, center.y, minimum.z + height * 0.5))
    view_locations = {
        "front": Vector((center.x, center.y - distance, target.z)),
        "right": Vector((center.x + distance, center.y, target.z)),
        "back": Vector((center.x, center.y + distance, target.z)),
        "left": Vector((center.x - distance, center.y, target.z)),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    previews: dict[str, str] = {}
    for name, location in view_locations.items():
        camera.location = location
        look_at(camera, target)
        path = output_dir / f"{name}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        previews[name] = str(path.resolve())
    return previews


def export_glb(objects: list[bpy.types.Object], path: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
    )


def main() -> int:
    args = parse_args()
    for path in (args.actor, args.accessory, args.profile, args.source_preparation, args.shape_manifest):
        if not path.is_file():
            raise FileNotFoundError(path)
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    if profile.get("schema") != "assetsstudio_actor_slot_profile_v2":
        raise ValueError("static fitting requires ActorSlotProfile v2")
    if profile["coordinate_contract"]["rig_state"] != "unbound_tpose":
        raise ValueError("profile is not an unbound T-Pose contract")
    if sha256(args.actor).lower() != profile["actor_model"]["sha256"].lower():
        raise RuntimeError("actor model hash does not match the slot profile")
    slot = next((item for item in profile["slots"] if item["slot_id"] == args.slot_id), None)
    if slot is None or slot.get("fit_envelope") is None:
        raise ValueError("slot has no static fit envelope")
    preparation = json.loads(args.source_preparation.read_text(encoding="utf-8"))
    shape_manifest = json.loads(args.shape_manifest.read_text(encoding="utf-8"))

    clear_scene()
    actor = imported_meshes(args.actor)
    accessory = imported_meshes(args.accessory)
    bake_world(actor)
    bake_world(accessory)
    actor_points = world_vertices(actor)
    accessory_points = world_vertices(accessory)
    actor_minimum, actor_maximum = bounds(actor_points)
    source_minimum, source_maximum = bounds(accessory_points)
    height = actor_maximum.z - actor_minimum.z
    center_x = (actor_minimum.x + actor_maximum.x) * 0.5
    center_y = (actor_minimum.y + actor_maximum.y) * 0.5
    envelope = slot["fit_envelope"]
    low_h = Vector(envelope["bounds_h"]["min"])
    high_h = Vector(envelope["bounds_h"]["max"])
    envelope_minimum = Vector((center_x + low_h.x * height, center_y + low_h.y * height, actor_minimum.z + low_h.z * height))
    envelope_maximum = Vector((center_x + high_h.x * height, center_y + high_h.y * height, actor_minimum.z + high_h.z * height))
    envelope_size = envelope_maximum - envelope_minimum

    waist_center_h = slot["attachment"]["anchors"][0]["position_h"]
    waist_z = actor_minimum.z + float(waist_center_h[2]) * height
    waist_band = [
        value for value in actor_points
        if abs(value.z - waist_z) <= 0.025 * height and abs(value.x - center_x) <= 0.2 * height
    ]
    if not waist_band:
        raise RuntimeError("actor waist band contains no vertices")
    waist_minimum, waist_maximum = bounds(waist_band)
    clearance = float(envelope["clearance_h"]) * height

    source_size = source_maximum - source_minimum
    front_aspect = float(preparation["outputs"]["front"]["foreground_aspect_width_over_height"])
    target_width = envelope_size.x
    target_height = min(envelope_size.z, target_width / front_aspect)
    target_depth = max(
        source_size.y / source_size.x * target_width,
        (waist_maximum.y - waist_minimum.y) + clearance * 2.0,
    )
    target_depth = min(target_depth, envelope_size.y)
    target_size = Vector((target_width, target_depth, target_height))
    scale = Vector((target_size.x / source_size.x, target_size.y / source_size.y, target_size.z / source_size.z))
    axis_scale_ratio = max(scale) / min(scale)
    envelope_center = (envelope_minimum + envelope_maximum) * 0.5
    target_center = Vector((envelope_center.x, envelope_center.y, waist_z))
    source_center = (source_minimum + source_maximum) * 0.5
    transform = Matrix.Translation(target_center) @ Matrix.Diagonal((scale.x, scale.y, scale.z, 1.0)) @ Matrix.Translation(-source_center)
    for obj in accessory:
        obj.data.transform(transform)
    bpy.context.view_layer.update()

    fitted_minimum, fitted_maximum = bounds(world_vertices(accessory))
    tolerance = 1e-5
    envelope_contained = all(
        fitted_minimum[index] >= envelope_minimum[index] - tolerance
        and fitted_maximum[index] <= envelope_maximum[index] + tolerance
        for index in range(3)
    )
    actor_bvh = build_bvh(actor)
    accessory_bvh = build_bvh(accessory)
    overlap_pairs = actor_bvh.overlap(accessory_bvh)

    output_dir = args.output_dir.resolve()
    preview_dir = output_dir / "preview"
    previews = render_views(actor, accessory, preview_dir, args.resolution)
    accessory_glb = output_dir / f"{args.asset_id}.glb"
    combined_glb = output_dir / f"{args.asset_id}_on_{profile['actor_asset_id']}.glb"
    export_glb(accessory, accessory_glb)
    export_glb(actor + accessory, combined_glb)
    blend_path = output_dir / f"{args.asset_id}_review.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    gates = {
        "shape_topology_pass": shape_manifest.get("status") == "pass" and shape_manifest.get("asset_kind") == "accessory",
        "fit_envelope_contained": envelope_contained,
        "axis_registration_within_limit": axis_scale_ratio <= args.max_axis_scale_ratio,
        "no_surface_triangle_intersection": len(overlap_pairs) == 0,
        "four_view_preview_complete": len(previews) == 4 and all(Path(path).is_file() for path in previews.values()),
    }
    automatic_pass = all(gates.values())
    report = {
        "schema": "assetsstudio_tpose_accessory_fit_v1",
        "asset_id": args.asset_id,
        "actor_profile_id": profile["id"],
        "actor_asset_id": profile["actor_asset_id"],
        "slot_id": args.slot_id,
        "rig_state": "unbound_tpose",
        "status": "pass_static_tpose" if automatic_pass else "automatic_review_failed",
        "inputs": {
            "actor": str(args.actor.resolve()),
            "actor_sha256": sha256(args.actor),
            "accessory": str(args.accessory.resolve()),
            "accessory_sha256": sha256(args.accessory),
            "profile": str(args.profile.resolve()),
            "shape_manifest": str(args.shape_manifest.resolve()),
        },
        "registration": {
            "source_size_m": [round(value, 6) for value in source_size],
            "target_size_m": [round(value, 6) for value in target_size],
            "scale_xyz": [round(value, 6) for value in scale],
            "axis_scale_ratio": round(axis_scale_ratio, 6),
            "max_axis_scale_ratio": args.max_axis_scale_ratio,
            "source_front_aspect": front_aspect,
        },
        "collision": {
            "surface_triangle_overlap_pairs": len(overlap_pairs),
            "scope": "static_tpose_only",
        },
        "automatic_gates": gates,
        "deferred_gates": [
            "bone_mapping",
            "skin_weights",
            "joint_deformation",
            "hand_and_thigh_clearance_during_locomotion",
            "mixamo_animation_review",
        ],
        "outputs": {
            "accessory_glb": str(accessory_glb),
            "combined_glb": str(combined_glb),
            "review_blend": str(blend_path),
            "previews": previews,
        },
    }
    report_path = output_dir / "fit_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"ASSETSSTUDIO_TPOSE_ACCESSORY_FIT_{'PASS' if automatic_pass else 'FAIL'} "
        f"asset={args.asset_id} overlaps={len(overlap_pairs)} "
        f"axis_scale_ratio={axis_scale_ratio:.4f} report={report_path}"
    )
    return 0 if automatic_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
