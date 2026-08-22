"""Fit one validated Hunyuan ear mesh into the detachable Actor V2 EarPair Slot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


HEAD_BONE = "CC_Base_Head"
EAR_OBJECTS = ("EarPair_HunyuanV2_L", "EarPair_HunyuanV2_R")


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", type=Path, required=True)
    parser.add_argument("--ear-glb", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-dir", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=512)
    parser.add_argument("--center-x", type=float, default=0.430)
    parser.add_argument("--center-y", type=float, default=0.018)
    parser.add_argument("--center-z", type=float, default=1.325)
    parser.add_argument("--width-x", type=float, default=0.100)
    parser.add_argument("--depth-y", type=float, default=0.075)
    parser.add_argument("--height-z", type=float, default=0.190)
    parser.add_argument("--target-faces", type=int, default=24000)
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    return parser.parse_args(raw)


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector(tuple(min(point[axis] for point in points) for axis in range(3))),
        Vector(tuple(max(point[axis] for point in points) for axis in range(3))),
    )


def parent_to_head(obj: bpy.types.Object, armature: bpy.types.Object) -> None:
    # Newly linked duplicates can still expose a stale identity matrix until
    # the dependency graph updates. Preserve the evaluated world placement,
    # otherwise bone parenting silently snaps the Slot object to world origin.
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = HEAD_BONE
    obj.matrix_world = world


def head_world_matrix(armature: bpy.types.Object) -> Matrix:
    return armature.matrix_world @ armature.pose.bones[HEAD_BONE].matrix


def relative_translation(armature: bpy.types.Object, obj: bpy.types.Object) -> Vector:
    return (head_world_matrix(armature).inverted() @ obj.matrix_world).translation


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def make_material() -> bpy.types.Material:
    material = bpy.data.materials.new("EarPair_HunyuanV2_Skin")
    material.use_nodes = True
    material.diffuse_color = (0.96, 0.54, 0.39, 1.0)
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = material.diffuse_color
        principled.inputs["Roughness"].default_value = 0.76
    return material


def import_and_prepare_source(path: Path, dimensions: Vector, target_faces: int) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    imported = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    if len(imported) != 1:
        raise RuntimeError(f"expected one Hunyuan ear mesh, found {[obj.name for obj in imported]}")
    source = imported[0]
    source.data.transform(source.matrix_world)
    source.matrix_world = Matrix.Identity(4)
    low, high = bounds(source)
    source.data.transform(Matrix.Translation(-(low + high) * 0.5))
    source.scale = (
        dimensions.x / max(high.x - low.x, 1e-6),
        dimensions.y / max(high.y - low.y, 1e-6),
        dimensions.z / max(high.z - low.z, 1e-6),
    )
    bpy.context.view_layer.objects.active = source
    source.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if target_faces > 0 and len(source.data.polygons) > target_faces:
        modifier = source.modifiers.new("EarPair_HunyuanV2_Decimate", "DECIMATE")
        modifier.ratio = target_faces / len(source.data.polygons)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    for polygon in source.data.polygons:
        polygon.use_smooth = True
    source.name = "EarPair_HunyuanV2_Template"
    return source


def create_review_camera(scene: bpy.types.Scene, name: str, ortho_scale: float) -> bpy.types.Object:
    data = bpy.data.cameras.new(name + "Data")
    data.type = "ORTHO"
    data.ortho_scale = ortho_scale
    camera = bpy.data.objects.new(name, data)
    scene.collection.objects.link(camera)
    return camera


def main() -> int:
    options = args()
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.review_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(options.actor.resolve()))
    scene = bpy.context.scene
    armature = bpy.data.objects.get("Armature")
    actor = next(
        (
            obj for obj in scene.objects
            if obj.type == "MESH" and any(mod.type == "ARMATURE" and mod.object for mod in obj.modifiers)
        ),
        None,
    )
    if armature is None or actor is None or HEAD_BONE not in armature.pose.bones:
        raise RuntimeError("Actor V2 armature, rigged mesh or CC_Base_Head is missing")

    for obj in list(bpy.data.objects):
        if obj.name.startswith(("EarPair_DefaultHuman_", "EarPair_HunyuanV2_", "EarRoot_")):
            bpy.data.objects.remove(obj, do_unlink=True)
    collection = bpy.data.collections.get("EarPair_HunyuanV2") or bpy.data.collections.new("EarPair_HunyuanV2")
    if collection.name not in scene.collection.children:
        scene.collection.children.link(collection)

    template = import_and_prepare_source(
        options.ear_glb,
        Vector((options.width_x, options.depth_y, options.height_z)),
        options.target_faces,
    )
    material = make_material()
    template.data.materials.clear()
    template.data.materials.append(material)
    ears = []
    anchors = []
    centers = {
        "L": Vector((options.center_x, options.center_y, options.center_z)),
        "R": Vector((-options.center_x, options.center_y, options.center_z)),
    }
    for side, center in centers.items():
        ear = template.copy()
        ear.data = template.data.copy()
        scene.collection.objects.link(ear)
        ear.name = f"EarPair_HunyuanV2_{side}"
        if side == "R":
            ear.scale.x = -1.0
            bpy.context.view_layer.objects.active = ear
            ear.select_set(True)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        ear.location = center
        ear["assetsstudio_slot_id"] = "EarPair"
        ear["assetsstudio_bundle_id"] = "earpair_default_human_v2_hunyuan"
        ear["assetsstudio_side"] = side
        ear["assetsstudio_parent_bone"] = HEAD_BONE
        ear["assetsstudio_source_kind"] = "hunyuan3d_2mv"
        ear["assetsstudio_source_glb"] = str(options.ear_glb.resolve())
        ear["assetsstudio_root_overlap_m"] = max(0.0, options.center_x + options.width_x * 0.5 - 0.467)
        parent_to_head(ear, armature)
        for linked in list(ear.users_collection):
            if linked != collection:
                linked.objects.unlink(ear)
        collection.objects.link(ear)
        ears.append(ear)

        anchor = bpy.data.objects.new(f"EarRoot_{side}", None)
        scene.collection.objects.link(anchor)
        anchor.empty_display_type = "SPHERE"
        anchor.empty_display_size = 0.020
        anchor.location = center
        anchor["assetsstudio_slot_anchor"] = "EarPair"
        parent_to_head(anchor, armature)
        anchors.append(anchor)
    bpy.data.objects.remove(template, do_unlink=True)

    scene["assetsstudio_earpair_slot_id"] = "EarPair"
    scene["assetsstudio_earpair_bundle_id"] = "earpair_default_human_v2_hunyuan"
    scene["assetsstudio_earpair_objects"] = list(EAR_OBJECTS)
    scene["assetsstudio_earpair_source_kind"] = "hunyuan3d_2mv"

    start, end = int(scene.frame_start), int(scene.frame_end)
    sample_frames = sorted({start, round(start + (end - start) * 0.43), end})
    base_relative = {}
    max_relative_drift = 0.0
    for frame in sample_frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        for ear in ears:
            current = relative_translation(armature, ear)
            if ear.name not in base_relative:
                base_relative[ear.name] = current.copy()
            max_relative_drift = max(max_relative_drift, (current - base_relative[ear.name]).length)

    scene.frame_set(start)
    bpy.context.view_layer.update()
    for obj in list(scene.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    world = scene.world or bpy.data.worlds.new("EarPairHunyuanReviewWorld")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.035, 0.045, 0.065, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.42
    for name, location, energy, size in (
        ("EarPairKey", (2.0, -2.0, 3.0), 320.0, 2.0),
        ("EarPairFill", (-2.0, -1.0, 2.0), 190.0, 2.0),
        ("EarPairRim", (0.0, 2.0, 2.5), 230.0, 2.0),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.size = size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        look_at(light, Vector((0.0, 0.0, 1.35)))

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = scene.render.resolution_y = options.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            scene.view_settings.look = look
            break
        except TypeError:
            continue
    directions = {
        "front": Vector((0.0, -1.0, 0.0)),
        "right": Vector((1.0, 0.0, 0.0)),
        "back": Vector((0.0, 1.0, 0.0)),
        "left": Vector((-1.0, 0.0, 0.0)),
    }
    previews = {"full": {}, "head": {}}
    for scope, target, ortho_scale in (
        ("full", Vector((0.0, 0.0, 0.995)), 2.76),
        ("head", Vector((0.0, 0.0, 1.48)), 1.10),
    ):
        camera = create_review_camera(scene, f"EarPair{scope.title()}Camera", ortho_scale)
        scene.camera = camera
        scope_dir = options.review_dir / scope
        scope_dir.mkdir(parents=True, exist_ok=True)
        for name, direction in directions.items():
            camera.location = target + direction * 5.0
            look_at(camera, target)
            path = scope_dir / f"{name}.png"
            scene.render.filepath = str(path.resolve())
            bpy.ops.render.render(write_still=True)
            previews[scope][name] = str(path.resolve())
        bpy.data.objects.remove(camera, do_unlink=True)

    actual_faces = {ear.name: len(ear.data.polygons) for ear in ears}
    gates = {
        "two_separate_hunyuan_mesh_objects": sorted(ear.name for ear in ears) == sorted(EAR_OBJECTS),
        "source_is_hunyuan": all(ear.get("assetsstudio_source_kind") == "hunyuan3d_2mv" for ear in ears),
        "same_bundle": all(ear.get("assetsstudio_bundle_id") == "earpair_default_human_v2_hunyuan" for ear in ears),
        "head_bone_parent": all(
            ear.parent == armature and ear.parent_type == "BONE" and ear.parent_bone == HEAD_BONE for ear in ears
        ),
        "two_ear_root_anchors": sorted(anchor.name for anchor in anchors) == ["EarRoot_L", "EarRoot_R"],
        "head_motion_relative_drift": max_relative_drift <= 0.0001,
        "face_budget": all(faces <= options.target_faces * 1.05 for faces in actual_faces.values()),
    }
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output.resolve()))
    report = {
        "schema": "assetsstudio_actor_v2_hunyuan_earpair_build_v1",
        "status": "pass" if all(gates.values()) else "fail",
        "actor": str(options.actor.resolve()),
        "source_glb": str(options.ear_glb.resolve()),
        "output": str(options.output.resolve()),
        "slot_id": "EarPair",
        "bundle_id": "earpair_default_human_v2_hunyuan",
        "objects": [ear.name for ear in ears],
        "anchors": {side: list(center) for side, center in centers.items()},
        "target_dimensions_m": list((options.width_x, options.depth_y, options.height_z)),
        "faces": actual_faces,
        "sample_frames": sample_frames,
        "max_head_relative_translation_drift_m": max_relative_drift,
        "gates": gates,
        "previews": previews,
    }
    report_path = options.output.with_suffix(".earpair.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["status"] != "pass":
        raise RuntimeError(f"Hunyuan EarPair validation failed: {gates}")
    print(
        f"ACTOR_V2_HUNYUAN_EARPAIR_PASS output={options.output.resolve()} "
        f"faces={actual_faces} drift={max_relative_drift:.8f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
