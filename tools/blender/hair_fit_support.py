"""Shared Actor hair fitting and review helpers.

This module is the retained, minimal part of AssetsLab's old
``extract_hair_style_candidate.py``.  The OBJ-grid extraction CLI is obsolete;
the current AssetsStudio workflow fits named objects from registered Blend
sources and only needs these geometry, material and four-view helpers.
"""

from __future__ import annotations

from pathlib import Path

import bpy
from mathutils import Vector


HEAD_BONE = "CC_Base_Head"


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector((min(point[index] for point in points) for index in range(3))),
        Vector((max(point[index] for point in points) for index in range(3))),
    )


def head_target(
    armature: bpy.types.Object,
    body: bpy.types.Object,
) -> tuple[Vector, float, float]:
    head_bone = armature.data.bones[HEAD_BONE]
    head_world = armature.matrix_world @ head_bone.head_local
    head_vertices = [
        body.matrix_world @ vertex.co
        for vertex in body.data.vertices
        if (body.matrix_world @ vertex.co).z > head_world.z - 0.22
    ]
    if not head_vertices:
        raise RuntimeError("could not estimate actor head bounds")
    low = Vector((min(point[index] for point in head_vertices) for index in range(3)))
    high = Vector((max(point[index] for point in head_vertices) for index in range(3)))
    center = Vector(((low.x + high.x) * 0.5, (low.y + high.y) * 0.5, high.z))
    return center, high.x - low.x, high.z


def make_material(color: tuple[float, float, float, float]) -> bpy.types.Material:
    material = bpy.data.materials.new("HairCandidatePreviewMaterial")
    material.diffuse_color = color
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.78
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.18
    return material


def configure_render(scene: bpy.types.Scene) -> None:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    world = scene.world or bpy.data.worlds.new("HairCandidateWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background:
        background.inputs["Color"].default_value = (0.018, 0.018, 0.024, 1.0)
        background.inputs["Strength"].default_value = 0.25
    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)
    for name, location, energy, size in (
        ("HairKey", (-4.0, -5.0, 5.0), 700.0, 4.0),
        ("HairFill", (4.0, -2.0, 3.0), 350.0, 3.0),
    ):
        data = bpy.data.lights.new(name + "Data", "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (Vector((0.0, 0.0, 1.6)) - light.location).to_track_quat("-Z", "Y").to_euler()


def render_views(
    scene: bpy.types.Scene,
    output_dir: Path,
    body: bpy.types.Object,
    hair: bpy.types.Object,
) -> dict[str, str]:
    low, high = bounds(body)
    hair_low, hair_high = bounds(hair)
    low.z = min(low.z, hair_low.z)
    high.z = max(high.z, hair_high.z)
    target = Vector(((low.x + high.x) * 0.5, (low.y + high.y) * 0.5, (low.z + high.z) * 0.5))
    scale = max(3.8, (high.z - low.z) * 1.22)
    views = {
        "front": Vector((target.x, target.y - 12.0, target.z)),
        "right": Vector((target.x + 12.0, target.y, target.z)),
        "back": Vector((target.x, target.y + 12.0, target.z)),
        "left": Vector((target.x - 12.0, target.y, target.z)),
    }
    renders: dict[str, str] = {}
    for direction, location in views.items():
        camera_data = bpy.data.cameras.new("HairCandidateCameraData_" + direction)
        camera_data.type = "ORTHO"
        camera_data.ortho_scale = scale
        camera = bpy.data.objects.new("HairCandidateCamera_" + direction, camera_data)
        scene.collection.objects.link(camera)
        camera.location = location
        camera.rotation_euler = (target - location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = camera
        path = output_dir / f"{direction}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        renders[direction] = str(path)
    return renders
