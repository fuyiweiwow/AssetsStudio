"""Render GLB previews for the model-test segmentation stages."""

import argparse
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def import_glb(path: Path):
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    # Hunyuan exports may retain a default helper cube. It is not part of the
    # character and otherwise becomes the large wall/ground seen in previews.
    return [
        obj for obj in bpy.context.scene.objects
        if obj not in before and obj.type == "MESH" and obj.name.lower() not in {"cube", "plane"}
    ]


def make_material(name: str, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.72
    return mat


def apply_material(objects, material):
    for obj in objects:
        obj.data.materials.clear()
        obj.data.materials.append(material)


def bbox(objects):
    corners = []
    for obj in objects:
        corners.extend([obj.matrix_world @ Vector(c) for c in obj.bound_box])
    if not corners:
        return Vector((-1, -1, -1)), Vector((1, 1, 1))
    return Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners))), Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))


def add_camera_and_lights(objects, camera_location=(2.8, -4.8, 2.2)):
    lo, hi = bbox(objects)
    center = (lo + hi) / 2
    # The exported GLBs use Z-up. Keep the preview contract in Z-up as well.
    height = max(hi.z - lo.z, 0.5)
    bpy.ops.object.camera_add(location=camera_location)
    camera = bpy.context.object
    camera.data.lens = 55
    camera.data.sensor_width = 36
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = camera

    for name, location, energy, size in (
        ("key", (3.5, -2.5, 4.5), 900, 4.0),
        ("fill", (-3.0, -1.0, 2.5), 500, 3.0),
        ("rim", (0.0, 3.5, 3.5), 850, 3.0),
    ):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.name = name
        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = size
        light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()

    bpy.ops.mesh.primitive_plane_add(size=max(height * 3.5, 5.0), location=(center.x, center.y, lo.z - 0.03))
    ground = bpy.context.object
    ground.data.materials.append(make_material("ground", (0.025, 0.035, 0.055)))


def set_render(path: Path, resolution=640):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(path)
    scene.world.color = (0.008, 0.012, 0.022)
    scene.render.film_transparent = False
    bpy.ops.render.render(write_still=True)


def render_single(path: Path, out: Path, material_color=None):
    clear_scene()
    objects = import_glb(path)
    if material_color:
        apply_material(objects, make_material(path.stem + "_material", material_color))
    add_camera_and_lights(objects)
    set_render(out)


def render_grid(part_paths, out: Path):
    clear_scene()
    materials = {
        "hair_wig": make_material("hair", (0.30, 0.18, 0.10)),
        "adventurer_jacket": make_material("jacket", (0.06, 0.20, 0.48)),
        "trousers": make_material("trousers", (0.18, 0.34, 0.12)),
        "boots": make_material("boots", (0.30, 0.14, 0.06)),
    }
    all_objects = []
    locations = [(-1.25, 1.25, 0), (1.25, 1.25, 0), (-1.25, -1.25, 0), (1.25, -1.25, 0)]
    for (name, path), location in zip(part_paths.items(), locations):
        objects = import_glb(path)
        apply_material(objects, materials[name])
        lo, hi = bbox(objects)
        height = max(hi.y - lo.y, 1e-4)
        scale = 1.35 / height
        for obj in objects:
            obj.scale *= scale
            obj.location += Vector(location)
            obj.location.z += -lo.z * scale + 0.04
        all_objects.extend(objects)
    add_camera_and_lights(all_objects, camera_location=(0.0, -7.5, 3.6))
    set_render(out, resolution=900)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", default=os.environ.get("MODEL_TEST_FULL"))
    parser.add_argument("--segmented", default=os.environ.get("MODEL_TEST_SEGMENTED"))
    parser.add_argument("--parts_dir", default=os.environ.get("MODEL_TEST_PARTS_DIR"))
    parser.add_argument("--out_dir", default=os.environ.get("MODEL_TEST_OUT_DIR"))
    # Blender keeps its own command-line flags in sys.argv when executing a
    # Python script; ignore those and use the MODEL_TEST_* environment values.
    args, _unknown = parser.parse_known_args()

    if not all((args.full, args.segmented, args.parts_dir, args.out_dir)):
        parser.error("provide arguments or MODEL_TEST_* environment variables")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    part_dir = Path(args.parts_dir)
    render_single(Path(args.full), out_dir / "male_adventurer_v1_full.png")
    render_single(Path(args.segmented), out_dir / "male_adventurer_v1_p3sam_128.png")
    part_paths = {name: part_dir / f"{name}_candidate.glb" for name in ("hair_wig", "adventurer_jacket", "trousers", "boots")}
    render_grid(part_paths, out_dir / "male_adventurer_v1_parts_grid.png")
    for name, path in part_paths.items():
        render_single(path, out_dir / f"male_adventurer_v1_{name}.png", (0.22, 0.30, 0.52))
    print(f"PREVIEWS_WRITTEN {out_dir}")


if __name__ == "__main__":
    main()
