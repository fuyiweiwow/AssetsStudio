"""Import, render, validate, and re-export a local Hunyuan multiview GLB.

The script writes both a neutral beauty preview and a material-independent
white-on-black silhouette for measurable multiview fitting.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def make_material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.72
    return material


def make_silhouette_material() -> bpy.types.Material:
    material = bpy.data.materials.new("validation_silhouette_white")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    emission.inputs["Strength"].default_value = 1.0
    material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def add_area(name: str, location: tuple[float, float, float], energy: float, size: float, target: Vector) -> None:
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--asset-id", default="actor_core_0ef398ca_v1")
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--target-height-ratio", type=float, default=0.6005859375)
    parser.add_argument("--resolution", type=int, default=1024)
    parser.add_argument(
        "--keep-source-origin",
        action="store_true",
        help="Do not ground and bake the imported mesh into Blender's Z-up coordinate space.",
    )
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw_args)

    if not 0.1 < args.target_height_ratio < 0.95:
        raise ValueError("--target-height-ratio must be between 0.1 and 0.95")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    beauty_dir = args.output_dir / "beauty"
    silhouette_dir = args.output_dir / "silhouette"
    beauty_dir.mkdir(parents=True, exist_ok=True)
    silhouette_dir.mkdir(parents=True, exist_ok=True)

    registration = {}
    if args.registration:
        payload = json.loads(args.registration.read_text(encoding="utf-8"))
        registration = {view["role"]: view for view in payload.get("views", [])}
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(args.input.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("Blender imported no mesh objects")

    for obj in meshes:
        if not obj.data.materials:
            obj.data.materials.append(make_material("validated_shape_neutral", (0.62, 0.66, 0.72, 1.0)))

    source_points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    source_minimum = Vector(
        (min(point.x for point in source_points), min(point.y for point in source_points), min(point.z for point in source_points))
    )
    source_maximum = Vector(
        (max(point.x for point in source_points), max(point.y for point in source_points), max(point.z for point in source_points))
    )

    if not args.keep_source_origin:
        ground_offset = -source_minimum.z
        for obj in meshes:
            world_matrix = Matrix.Translation((0.0, 0.0, ground_offset)) @ obj.matrix_world
            obj.data.transform(world_matrix)
            obj.matrix_world = Matrix.Identity(4)
        bpy.context.view_layer.update()
    else:
        ground_offset = 0.0

    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    minimum = Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points)))
    maximum = Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points)))
    center = (minimum + maximum) / 2.0
    height = max(maximum.z - minimum.z, 0.001)
    radius = max(maximum.x - minimum.x, maximum.y - minimum.y, height) * 0.65

    ground_material = make_material("validated_ground", (0.12, 0.14, 0.18, 1.0))
    bpy.ops.mesh.primitive_plane_add(size=max(height * 4.0, 4.0), location=(center.x, center.y, minimum.z))
    ground = bpy.context.object
    ground.name = "ValidationGround"
    ground.data.materials.append(ground_material)

    world = bpy.context.scene.world or bpy.data.worlds.new("ValidationWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.035, 0.045, 0.065, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35

    camera_data = bpy.data.cameras.new("ValidationCamera")
    camera = bpy.data.objects.new("ValidationCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = height / args.target_height_ratio
    bpy.context.scene.camera = camera

    add_area("Key", (radius, -radius, center.z + height), 900.0, height * 0.8, center)
    add_area("Fill", (-radius, -radius * 0.4, center.z + height * 0.6), 550.0, height * 0.7, center)
    add_area("Rim", (-radius * 0.6, radius, center.z + height * 0.9), 800.0, height * 0.7, center)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "AgX - Medium High Contrast"

    directions = {
        "front": Vector((0.0, -1.0, 0.0)),
        "right": Vector((1.0, 0.0, 0.0)),
        "back": Vector((0.0, 1.0, 0.0)),
        "left": Vector((-1.0, 0.0, 0.0)),
    }
    view_registration_roles = {"front": "front", "right": "side", "back": "back", "left": "side"}

    def place_camera(name: str, direction: Vector) -> None:
        camera.location = center + direction * (height * 2.8)
        camera.location.z = center.z
        look_at(camera, center)

        registered = registration.get(view_registration_roles[name])
        if not registered:
            return
        registered_width, registered_height = registered["image_size"]
        bbox_center_x, bbox_center_y = registered["bbox_center"]
        desired_x = bbox_center_x * args.resolution / registered_width
        desired_y = bbox_center_y * args.resolution / registered_height
        dx_world = (desired_x - args.resolution / 2.0) * camera_data.ortho_scale / args.resolution
        dy_world = (desired_y - args.resolution / 2.0) * camera_data.ortho_scale / args.resolution
        rotation = camera.matrix_world.to_quaternion()
        screen_right = rotation @ Vector((1.0, 0.0, 0.0))
        screen_up = rotation @ Vector((0.0, 1.0, 0.0))
        optical_offset = -screen_right * dx_world + screen_up * dy_world
        camera.location += optical_offset
        look_at(camera, center + optical_offset)

    silhouette_material = make_silhouette_material()
    ground.hide_render = True
    scene.view_layers[0].material_override = silhouette_material
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "FLAT"
    scene.display.shading.color_type = "SINGLE"
    scene.display.shading.single_color = (1.0, 1.0, 1.0)
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = False
    scene.display.shading.background_type = "WORLD"
    world.color = (0.0, 0.0, 0.0)
    for name, direction in directions.items():
        place_camera(name, direction)
        scene.render.filepath = str((silhouette_dir / f"{name}.png").resolve())
        bpy.ops.render.render(write_still=True)

    scene.view_layers[0].material_override = None
    ground.hide_render = False
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.035, 0.045, 0.065, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    for name, direction in directions.items():
        place_camera(name, direction)
        scene.render.filepath = str((beauty_dir / f"{name}.png").resolve())
        bpy.ops.render.render(write_still=True)

    # The ground is useful for the preview renders but must not become part of
    # the reusable character asset.
    bpy.data.objects.remove(ground, do_unlink=True)
    blend_path = args.output_dir / f"{args.asset_id}_validated.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path.resolve()))
    glb_path = args.output_dir / f"{args.asset_id}_validated.glb"
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path.resolve()),
        export_format="GLB",
        export_materials="EXPORT",
        use_selection=True,
    )

    vertex_count = sum(len(obj.data.vertices) for obj in meshes)
    face_count = sum(len(obj.data.polygons) for obj in meshes)
    report = {
        "schema": "assetsstudio_local_hunyuan_mv_blender_validation_v2",
        "asset_id": args.asset_id,
        "input": str(args.input.resolve()),
        "registration": str(args.registration.resolve()) if args.registration else None,
        "validated_blend": str(blend_path.resolve()),
        "validated_glb": str(glb_path.resolve()),
        "mesh_objects": len(meshes),
        "vertices": vertex_count,
        "faces": face_count,
        "source_bbox_min_blender": list(source_minimum),
        "source_bbox_max_blender": list(source_maximum),
        "ground_offset_z": ground_offset,
        "bbox_min": list(minimum),
        "bbox_max": list(maximum),
        "height": height,
        "target_height_ratio": args.target_height_ratio,
        "resolution": args.resolution,
        "renders": {
            name: {
                "beauty": str((beauty_dir / f"{name}.png").resolve()),
                "silhouette": str((silhouette_dir / f"{name}.png").resolve()),
            }
            for name in directions
        },
    }
    (args.output_dir / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"BLENDER_MV_PASS vertices={vertex_count} faces={face_count} output={glb_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
