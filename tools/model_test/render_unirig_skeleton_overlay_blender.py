"""Render a UniRig skeleton over its normalized preprocessing mesh."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def material(name: str, color: tuple[float, float, float, float], emission: bool = False):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    nodes = result.node_tree.nodes
    if emission:
        nodes.clear()
        output = nodes.new("ShaderNodeOutputMaterial")
        shader = nodes.new("ShaderNodeEmission")
        shader.inputs["Color"].default_value = color
        shader.inputs["Strength"].default_value = 2.5
        result.node_tree.links.new(shader.outputs["Emission"], output.inputs["Surface"])
    else:
        nodes.clear()
        output = nodes.new("ShaderNodeOutputMaterial")
        transparent = nodes.new("ShaderNodeBsdfTransparent")
        shader = nodes.new("ShaderNodeBsdfPrincipled")
        mix = nodes.new("ShaderNodeMixShader")
        shader.inputs["Base Color"].default_value = color
        shader.inputs["Roughness"].default_value = 0.82
        mix.inputs[0].default_value = color[3]
        result.node_tree.links.new(transparent.outputs["BSDF"], mix.inputs[1])
        result.node_tree.links.new(shader.outputs["BSDF"], mix.inputs[2])
        result.node_tree.links.new(mix.outputs["Shader"], output.inputs["Surface"])
        result.surface_render_method = "BLENDED"
        result.use_transparency_overlap = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-npz", required=True, type=Path)
    parser.add_argument("--skeleton-fbx", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--resolution", type=int, default=768)
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    with np.load(args.mesh_npz.resolve(), allow_pickle=True) as payload:
        vertices = np.asarray(payload["vertices"], dtype=np.float64)
        faces = np.asarray(payload["faces"], dtype=np.int64)

    mesh_data = bpy.data.meshes.new("UniRigDiagnosticMesh")
    mesh_data.from_pydata(vertices.tolist(), [], faces.tolist())
    mesh_data.update()
    mesh = bpy.data.objects.new("UniRigDiagnosticMesh", mesh_data)
    bpy.context.collection.objects.link(mesh)
    mesh.data.materials.append(material("TeacherTransparent", (0.55, 0.63, 0.74, 0.28)))

    bpy.ops.import_scene.fbx(filepath=str(args.skeleton_fbx.resolve()), use_image_search=False)
    armature = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
    bones = list(armature.data.bones)
    minimum = Vector(vertices.min(axis=0))
    maximum = Vector(vertices.max(axis=0))
    center = (minimum + maximum) / 2.0
    height = maximum.z - minimum.z

    curve_data = bpy.data.curves.new("UniRigBoneOverlay", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.bevel_depth = height * 0.006
    curve_data.bevel_resolution = 2
    curve = bpy.data.objects.new("UniRigBoneOverlay", curve_data)
    bpy.context.collection.objects.link(curve)
    curve.data.materials.append(material("BoneOrange", (1.0, 0.18, 0.025, 1.0), emission=True))
    for bone in bones:
        spline = curve_data.splines.new("POLY")
        spline.points.add(1)
        head = armature.matrix_world @ bone.head_local
        tail = armature.matrix_world @ bone.tail_local
        spline.points[0].co = (*head, 1.0)
        spline.points[1].co = (*tail, 1.0)

    camera_data = bpy.data.cameras.new("OverlayCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = height / 0.74
    camera = bpy.data.objects.new("OverlayCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    bpy.context.scene.camera = camera

    world = bpy.context.scene.world or bpy.data.worlds.new("OverlayWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.025, 0.033, 0.05, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
    light_data = bpy.data.lights.new("OverlayKey", type="AREA")
    light_data.energy = 900
    light_data.size = height
    light = bpy.data.objects.new("OverlayKey", light_data)
    bpy.context.collection.objects.link(light)
    light.location = (height, -height, maximum.z)
    look_at(light, center)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.look = "AgX - Medium High Contrast"
    directions = {
        "front": Vector((0.0, -1.0, 0.0)),
        "right": Vector((1.0, 0.0, 0.0)),
        "back": Vector((0.0, 1.0, 0.0)),
        "left": Vector((-1.0, 0.0, 0.0)),
    }
    for name, direction in directions.items():
        camera.location = center + direction * height * 3.0
        camera.location.z = center.z
        look_at(camera, center)
        # Orthographic projection is unchanged by translation along the view
        # axis. Move the diagnostic curve toward the camera so internal bones
        # remain visible without altering their projected joint positions.
        curve.location = direction * height * 0.65
        scene.render.filepath = str((args.output_dir / f"{name}.png").resolve())
        bpy.ops.render.render(write_still=True)

    report = {
        "schema": "assetsstudio_unirig_skeleton_overlay_v1",
        "status": "diagnostic_only",
        "approved_asset": False,
        "vertices": int(len(vertices)),
        "faces": int(len(faces)),
        "bones": len(bones),
        "roots": sum(bone.parent is None for bone in bones),
        "leaf_bones": sum(not bone.children for bone in bones),
        "display_depth_offset_height_ratio": 0.65,
        "bone_lengths": {
            "minimum": min(float(bone.length) for bone in bones),
            "maximum": max(float(bone.length) for bone in bones),
        },
        "renders": {name: str((args.output_dir / f"{name}.png").resolve()) for name in directions},
    }
    (args.output_dir / "skeleton_audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
