"""Build and validate the default rounded-human EarPair on Actor V2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


HEAD_BONE = "CC_Base_Head"
EAR_OBJECTS = ("EarPair_DefaultHuman_L", "EarPair_DefaultHuman_R")


def material(name: str, color: tuple[float, float, float, float], roughness: float) -> bpy.types.Material:
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    principled = result.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = roughness
    return result


def parent_to_head(obj: bpy.types.Object, armature: bpy.types.Object) -> None:
    world = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = HEAD_BONE
    obj.matrix_world = world


def create_ear(
    side: str,
    center: Vector,
    armature: bpy.types.Object,
    outer_material: bpy.types.Material,
    inner_material: bpy.types.Material,
) -> bpy.types.Object:
    sign = 1.0 if side == "L" else -1.0
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=24, location=center)
    outer = bpy.context.object
    outer.name = f"EarPair_DefaultHuman_{side}"
    outer.scale = (0.048, 0.072, 0.102)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    outer.data.materials.append(outer_material)

    inner_center = center + Vector((sign * 0.043, -0.010, 0.0))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, location=inner_center)
    inner = bpy.context.object
    inner.name = f"EarPair_DefaultHuman_{side}_InnerBowl"
    inner.scale = (0.008, 0.028, 0.045)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    inner.data.materials.append(inner_material)

    bpy.ops.object.select_all(action="DESELECT")
    outer.select_set(True)
    inner.select_set(True)
    bpy.context.view_layer.objects.active = outer
    bpy.ops.object.join()
    for polygon in outer.data.polygons:
        polygon.use_smooth = True
    outer["assetsstudio_slot_id"] = "EarPair"
    outer["assetsstudio_bundle_id"] = "earpair_default_human_v1"
    outer["assetsstudio_side"] = side
    outer["assetsstudio_parent_bone"] = HEAD_BONE
    outer["assetsstudio_root_overlap_m"] = 0.030
    parent_to_head(outer, armature)
    return outer


def head_world_matrix(armature: bpy.types.Object) -> Matrix:
    return armature.matrix_world @ armature.pose.bones[HEAD_BONE].matrix


def relative_translation(armature: bpy.types.Object, obj: bpy.types.Object) -> Vector:
    return (head_world_matrix(armature).inverted() @ obj.matrix_world).translation


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-dir", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=512)
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw_args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.review_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))
    scene = bpy.context.scene
    armature = bpy.data.objects.get("Armature")
    actor = next(
        (
            obj
            for obj in scene.objects
            if obj.type == "MESH" and any(mod.type == "ARMATURE" and mod.object for mod in obj.modifiers)
        ),
        None,
    )
    if armature is None or actor is None or HEAD_BONE not in armature.pose.bones:
        raise RuntimeError("Actor V2 armature, rigged mesh or CC_Base_Head is missing")
    scene.frame_set(int(scene.frame_start))
    bpy.context.view_layer.update()

    for obj in list(bpy.data.objects):
        if obj.name.startswith("EarPair_DefaultHuman_") or obj.name.startswith("EarRoot_"):
            bpy.data.objects.remove(obj, do_unlink=True)
    collection = bpy.data.collections.get("EarPair_DefaultHuman_V1") or bpy.data.collections.new(
        "EarPair_DefaultHuman_V1"
    )
    if collection.name not in scene.collection.children:
        scene.collection.children.link(collection)

    outer_material = material("EarPair_DefaultHuman_Skin", (0.96, 0.54, 0.39, 1.0), 0.76)
    inner_material = material("EarPair_DefaultHuman_Inner", (0.82, 0.40, 0.30, 1.0), 0.82)
    centers = {
        "L": Vector((0.430, 0.018, 1.325)),
        "R": Vector((-0.430, 0.018, 1.325)),
    }
    ears = []
    anchors = []
    for side, center in centers.items():
        ear = create_ear(side, center, armature, outer_material, inner_material)
        for linked in list(ear.users_collection):
            if linked != collection:
                linked.objects.unlink(ear)
        collection.objects.link(ear)
        ears.append(ear)

        anchor = bpy.data.objects.new(f"EarRoot_{side}", None)
        scene.collection.objects.link(anchor)
        anchor.empty_display_type = "SPHERE"
        anchor.empty_display_size = 0.025
        anchor.location = center
        anchor["assetsstudio_slot_anchor"] = "EarPair"
        parent_to_head(anchor, armature)
        anchors.append(anchor)

    scene["assetsstudio_earpair_slot_id"] = "EarPair"
    scene["assetsstudio_earpair_bundle_id"] = "earpair_default_human_v1"
    scene["assetsstudio_earpair_objects"] = list(EAR_OBJECTS)

    start = int(scene.frame_start)
    end = int(scene.frame_end)
    sample_frames = sorted({start, round(start + (end - start) * 0.43), end})
    base_relative = {}
    max_relative_drift = 0.0
    for frame in sample_frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        for ear in ears:
            translation = relative_translation(armature, ear)
            if ear.name not in base_relative:
                base_relative[ear.name] = translation.copy()
            max_relative_drift = max(max_relative_drift, (translation - base_relative[ear.name]).length)

    scene.frame_set(start)
    bpy.context.view_layer.update()
    points = [actor.matrix_world @ Vector(corner) for corner in actor.bound_box]
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    center = (low + high) / 2.0
    height = high.z - low.z

    for obj in list(scene.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    world = scene.world or bpy.data.worlds.new("EarPairReviewWorld")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.035, 0.045, 0.065, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.42
    for name, location, energy in (
        ("EarPairKey", (height, -height, height * 1.7), 300.0),
        ("EarPairFill", (-height, -height * 0.5, height), 180.0),
        ("EarPairRim", (0.0, height, height * 1.5), 220.0),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.size = height * 1.4
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        look_at(light, center)
    camera_data = bpy.data.cameras.new("EarPairReviewCameraData")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = height / 0.72
    camera = bpy.data.objects.new("EarPairReviewCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
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
    previews = {}
    for name, direction in directions.items():
        camera.location = center + direction * height * 3.2
        camera.location.z = center.z
        look_at(camera, center)
        path = args.review_dir / f"{name}.png"
        scene.render.filepath = str(path.resolve())
        bpy.ops.render.render(write_still=True)
        previews[name] = str(path.resolve())

    gates = {
        "two_separate_mesh_objects": sorted(ear.name for ear in ears) == sorted(EAR_OBJECTS),
        "same_bundle": all(ear.get("assetsstudio_bundle_id") == "earpair_default_human_v1" for ear in ears),
        "head_bone_parent": all(
            ear.parent == armature and ear.parent_type == "BONE" and ear.parent_bone == HEAD_BONE for ear in ears
        ),
        "two_ear_root_anchors": sorted(anchor.name for anchor in anchors) == ["EarRoot_L", "EarRoot_R"],
        "designed_root_overlap": all(ear.get("assetsstudio_root_overlap_m", 0.0) >= 0.020 for ear in ears),
        "head_motion_relative_drift": max_relative_drift <= 0.0001,
    }
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    report = {
        "schema": "assetsstudio_actor_v2_earpair_build_v1",
        "status": "pass" if all(gates.values()) else "fail",
        "input": str(args.input.resolve()),
        "output": str(args.output.resolve()),
        "slot_id": "EarPair",
        "bundle_id": "earpair_default_human_v1",
        "objects": [ear.name for ear in ears],
        "anchors": {side: list(center) for side, center in centers.items()},
        "dimensions_m": {"thickness_x": 0.096, "depth_y": 0.144, "height_z": 0.204},
        "sample_frames": sample_frames,
        "max_head_relative_translation_drift_m": max_relative_drift,
        "gates": gates,
        "previews": previews,
    }
    args.output.with_suffix(".earpair.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if report["status"] != "pass":
        raise RuntimeError(f"EarPair validation failed: {gates}")
    print(f"ACTOR_V2_EARPAIR_PASS output={args.output.resolve()} drift={max_relative_drift:.8f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
