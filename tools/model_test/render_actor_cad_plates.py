"""Render the canonical Actor V1 as clean CAD-style orthographic base plates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args(argv)


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def cad_material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.92
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def main() -> int:
    options = args()
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    body = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    if body is None:
        raise RuntimeError("Actor V1 body mesh is missing")
    armature = bpy.data.objects.get("Armature")
    if armature:
        armature.hide_render = True
    for obj in bpy.context.scene.objects:
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)

    body_material = cad_material("CAD_ActorBody", (0.58, 0.62, 0.68, 1.0))
    ear_material = cad_material("CAD_ActorEars", (0.42, 0.46, 0.52, 1.0))
    body.data.materials.clear()
    body.data.materials.append(body_material)
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.name.startswith("MikuEar_"):
            obj.data.materials.clear()
            obj.data.materials.append(ear_material)

    bpy.context.scene.frame_set(1)
    bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
    bpy.context.scene.render.resolution_x = 640
    bpy.context.scene.render.resolution_y = 800
    bpy.context.scene.render.resolution_percentage = 100
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.context.scene.render.film_transparent = False
    bpy.context.scene.world.color = (0.92, 0.92, 0.92)

    low, high = bounds(body)
    center = (low + high) / 2
    height = high.z - low.z
    out_dir = options.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cameras = {
        "base_front": (Vector((0.0, -12.0, center.z)), height * 1.16),
        "base_right": (Vector((12.0, 0.0, center.z)), height * 1.16),
        "base_back": (Vector((0.0, 12.0, center.z)), height * 1.16),
        "base_top": (Vector((0.0, 0.0, 12.0)), max(high.x - low.x, high.y - low.y) * 1.35),
    }
    for name, (location, scale) in cameras.items():
        camera_data = bpy.data.cameras.new(name + "_CameraData")
        camera_data.type = "ORTHO"
        camera_data.ortho_scale = scale
        camera = bpy.data.objects.new(name + "_Camera", camera_data)
        bpy.context.scene.collection.objects.link(camera)
        camera.location = location
        look_at(camera, center)
        bpy.context.scene.camera = camera
        bpy.context.scene.render.filepath = str(out_dir / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(camera, do_unlink=True)
    print(f"ACTOR_CAD_PLATES_PASS output={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
