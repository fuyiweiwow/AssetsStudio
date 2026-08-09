"""Shared render helpers for current Actor-derived assets.

This module contains only generic camera, lighting, material, bounds and
four-direction review behavior.  It replaces imports from retired eye and
shirt experiments so current top and shoe rebuild scripts remain independent
of historical test pipelines.
"""

from __future__ import annotations

from pathlib import Path

import bpy
from mathutils import Vector


DIRECTIONS = {
    "front": (0.0, -12.0),
    "right": (12.0, 0.0),
    "back": (0.0, 12.0),
    "left": (-12.0, 0.0),
}


def visible_bounds() -> tuple[Vector, Vector]:
    points = [
        obj.matrix_world @ Vector(corner)
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and not obj.hide_render
        for corner in obj.bound_box
    ]
    if not points:
        raise RuntimeError("no visible meshes in Actor asset scene")
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def _look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    if direction.length > 1e-6:
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def configure_lighting(scene: bpy.types.Scene, target: Vector, profile: str = "soft_flat") -> None:
    if profile == "current":
        scene["assetsstudio_lighting_profile"] = "current_source_scene"
        return
    if profile != "soft_flat":
        raise ValueError(f"unknown lighting profile: {profile}")

    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)

    world = scene.world or bpy.data.worlds.new("AssetsStudioSoftFlatWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.14, 0.16, 0.20, 1.0)
        background.inputs["Strength"].default_value = 0.42
    world.color = (0.14, 0.16, 0.20)

    def add_area(
        name: str,
        location: tuple[float, float, float],
        energy: float,
        size: float,
        use_shadow: bool,
    ) -> None:
        data = bpy.data.lights.new(name, type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        if hasattr(data, "use_shadow"):
            data.use_shadow = use_shadow
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        _look_at(light, target)

    add_area("AssetsStudioSoftFlatKey", (target.x - 4.5, target.y - 6.0, target.z + 7.5), 430.0, 6.5, True)
    add_area("AssetsStudioSoftFlatFill", (target.x + 5.0, target.y - 3.5, target.z + 4.5), 300.0, 8.0, False)

    try:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
    except (AttributeError, TypeError, ValueError):
        pass
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene["assetsstudio_lighting_profile"] = "soft_flat_v1"


def make_camera(
    scene: bpy.types.Scene,
    target: Vector,
    name: str,
    location: tuple[float, float, float],
    scale: float,
) -> bpy.types.Object:
    data = bpy.data.cameras.new(name + "Data")
    data.type = "ORTHO"
    data.ortho_scale = scale
    data.clip_start = 0.01
    data.clip_end = 1000.0
    camera = bpy.data.objects.new(name, data)
    scene.collection.objects.link(camera)
    camera.location = location
    _look_at(camera, target)
    return camera


def make_material() -> bpy.types.Material:
    material = bpy.data.materials.new("ActorNativeTshirt_Material")
    material.diffuse_color = (0.12, 0.38, 0.82, 1.0)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    if shader:
        shader.inputs["Base Color"].default_value = (0.12, 0.38, 0.82, 1.0)
        shader.inputs["Roughness"].default_value = 0.86
    return material


def render_review(
    scene: bpy.types.Scene,
    output: Path,
    actor: bpy.types.Object,
    asset: bpy.types.Object,
    resolution: int,
) -> list[dict[str, object]]:
    del actor, asset
    low, high = visible_bounds()
    center = (low + high) * 0.5
    configure_lighting(scene, center, "soft_flat")
    scene.view_settings.exposure = 0.35
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    armature = bpy.data.objects.get("Armature")
    action = armature.animation_data.action if armature and armature.animation_data else None
    if action is None:
        raise RuntimeError("Actor armature has no active action")
    start, end = int(action.frame_range[0]), int(action.frame_range[1])
    sample_frames = [round(start + (end - start) * index / 7.0) for index in range(8)]
    ortho_scale = max(high.z - low.z, high.x - low.x, high.y - low.y) * 1.16
    frames: list[dict[str, object]] = []
    for direction, (x, y) in DIRECTIONS.items():
        camera = make_camera(scene, center, f"ActorAsset_{direction}", (x, y, center.z), ortho_scale)
        scene.camera = camera
        for index, source_frame in enumerate(sample_frames):
            scene.frame_set(source_frame)
            bpy.context.view_layer.update()
            path = output / f"{direction}_{index:02d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            frames.append(
                {
                    "direction": direction,
                    "sample_index": index,
                    "source_frame": source_frame,
                    "path": path.name,
                }
            )
        bpy.data.objects.remove(camera, do_unlink=True)
    return frames
