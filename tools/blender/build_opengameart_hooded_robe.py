"""Adapt the OpenGameArt hooded-cloth mesh plus a CC0 long skirt to the Actor."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", type=Path)
    parser.add_argument("--hood-blend", type=Path)
    parser.add_argument("--skirt-blend", type=Path)
    parser.add_argument("--output-dir", type=Path)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    options, _ = parser.parse_known_args(argv)
    options.input_blend = options.input_blend or Path(os.environ["OGA_ROBE_INPUT_BLEND"])
    options.hood_blend = options.hood_blend or Path(os.environ["OGA_HOOD_BLEND"])
    options.skirt_blend = options.skirt_blend or Path(os.environ["OGA_SKIRT_BLEND"])
    options.output_dir = options.output_dir or Path(os.environ["OGA_ROBE_OUTPUT_DIR"])
    return options


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))), Vector(
        (max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))
    )


def material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = color
    node = mat.node_tree.nodes.get("Principled BSDF")
    if node:
        node.inputs["Base Color"].default_value = color
        node.inputs["Roughness"].default_value = 0.84
    return mat


def replace_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.material_index = 0


def load_object(path: Path, name: str, collection_name: str) -> bpy.types.Object:
    with bpy.data.libraries.load(str(path.resolve()), link=False) as (data_from, data_to):
        if name not in data_from.objects:
            raise RuntimeError(f"missing object {name!r} in {path}")
        data_to.objects = [name]
    obj = data_to.objects[0]
    collection = bpy.data.collections.get(collection_name) or bpy.data.collections.new(collection_name)
    if collection.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(collection)
    collection.objects.link(obj)
    return obj


def apply_mirror_and_remove_external_rig(obj: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    for modifier in list(obj.modifiers):
        if modifier.type == "MIRROR":
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        elif modifier.type == "ARMATURE":
            obj.modifiers.remove(modifier)
    obj.select_set(False)


def apply_scale_and_z(obj: bpy.types.Object, scale: tuple[float, float, float], z_offset: float) -> None:
    obj.scale = scale
    obj.location = (0.0, 0.0, z_offset)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.select_set(False)


def group(obj: bpy.types.Object, name: str) -> bpy.types.VertexGroup:
    return obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)


def semantic_weights(obj: bpy.types.Object, armature: bpy.types.Object, kind: str) -> dict[str, int]:
    names = [
        "CC_Base_Waist", "CC_Base_Spine01", "CC_Base_Spine02", "CC_Base_NeckTwist01", "CC_Base_Head",
        "CC_Base_L_Clavicle", "CC_Base_L_Upperarm", "CC_Base_L_Forearm",
        "CC_Base_R_Clavicle", "CC_Base_R_Upperarm", "CC_Base_R_Forearm",
        "CC_Base_L_Thigh", "CC_Base_R_Thigh",
    ]
    groups = {name: group(obj, name) for name in names if armature.data.bones.get(name)}
    for vertex_group in groups.values():
        vertex_group.remove(range(len(obj.data.vertices)))
    low, high = bounds(obj)
    span = max(high.z - low.z, 1e-6)
    counts = {"hood": 0, "torso": 0, "left_sleeve": 0, "right_sleeve": 0, "lower": 0}
    for index, vertex in enumerate(obj.data.vertices):
        point = obj.matrix_world @ vertex.co
        ratio = max(0.0, min(1.0, (point.z - low.z) / span))
        if kind == "hooded_cloth":
            if point.z > 2.35:
                groups["CC_Base_NeckTwist01"].add([index], 0.38, "REPLACE")
                groups["CC_Base_Head"].add([index], 0.62, "ADD")
                counts["hood"] += 1
            elif point.x < -0.40:
                groups["CC_Base_R_Clavicle"].add([index], 0.20, "REPLACE")
                groups["CC_Base_R_Upperarm"].add([index], 0.55, "ADD")
                groups["CC_Base_R_Forearm"].add([index], 0.25, "ADD")
                counts["left_sleeve"] += 1
            elif point.x > 0.40:
                groups["CC_Base_L_Clavicle"].add([index], 0.20, "REPLACE")
                groups["CC_Base_L_Upperarm"].add([index], 0.55, "ADD")
                groups["CC_Base_L_Forearm"].add([index], 0.25, "ADD")
                counts["right_sleeve"] += 1
            elif ratio > 0.58:
                groups["CC_Base_Spine01"].add([index], 0.35, "REPLACE")
                groups["CC_Base_Spine02"].add([index], 0.65, "ADD")
                counts["torso"] += 1
            else:
                groups["CC_Base_Waist"].add([index], 0.58, "REPLACE")
                groups["CC_Base_Spine01"].add([index], 0.42, "ADD")
                counts["torso"] += 1
        elif ratio < 0.35 and point.x < -0.08 and "CC_Base_R_Thigh" in groups:
            groups["CC_Base_R_Thigh"].add([index], 0.50, "REPLACE")
            groups["CC_Base_Waist"].add([index], 0.50, "ADD")
            counts["lower"] += 1
        elif ratio < 0.35 and point.x > 0.08 and "CC_Base_L_Thigh" in groups:
            groups["CC_Base_L_Thigh"].add([index], 0.50, "REPLACE")
            groups["CC_Base_Waist"].add([index], 0.50, "ADD")
            counts["lower"] += 1
        elif ratio < 0.56:
            groups["CC_Base_Waist"].add([index], 0.72, "REPLACE")
            groups["CC_Base_Spine01"].add([index], 0.28, "ADD")
            counts["lower"] += 1
        else:
            groups["CC_Base_Spine01"].add([index], 0.38, "REPLACE")
            groups["CC_Base_Spine02"].add([index], 0.62, "ADD")
            counts["torso"] += 1
    modifier = obj.modifiers.new("OpenGameArt_ActorArmature", "ARMATURE")
    modifier.object = armature
    modifier.use_deform_preserve_volume = True
    return counts


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def render(scene: bpy.types.Scene, body: bpy.types.Object, garments: list[bpy.types.Object], output: Path, label: str, frame: int) -> None:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    low, high = bounds(body)
    target = (low + high) * 0.5
    span = max((high - low).x, (high - low).y, (high - low).z)
    camera_data = bpy.data.cameras.new(f"OpenGameArtRobeCamera_{label}")
    camera = bpy.data.objects.new(f"OpenGameArtRobeCamera_{label}", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (span * 3.8, -span * 3.8, target.z) if label == "three_quarter" else (
        (0.0, -span * 4.2, target.z) if label == "front" else (span * 4.2, 0.0, target.z)
    )
    camera.data.lens = 55
    look_at(camera, target)
    scene.camera = camera
    scene.render.filepath = str(output / f"opengameart_robe_{label}.png")
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(camera, do_unlink=True)


def main() -> int:
    options = parse_args()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    scene = bpy.context.scene
    body = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if body is None or armature is None:
        raise RuntimeError("Input must contain Actor body and Armature")
    for name in ("QStylePartitionedRobe_FitCandidate", "QStyleIndependentHood_FitCandidate"):
        old = bpy.data.objects.get(name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)

    cloth = load_object(options.hood_blend, "lone_cloth", "AssetsStudio_OpenGameArt_Hooded")
    skirt = load_object(options.skirt_blend, "Long Skirt", "AssetsStudio_OpenGameArt_Hooded")
    apply_mirror_and_remove_external_rig(cloth)
    apply_mirror_and_remove_external_rig(skirt)

    cloth_low, cloth_high = bounds(cloth)
    cloth_scale_z = (3.00 - 1.20) / max(cloth_high.z - cloth_low.z, 1e-6)
    cloth_scale_x = 1.22 * body.dimensions.x / max(cloth_high.x - cloth_low.x, 1e-6)
    apply_scale_and_z(cloth, (cloth_scale_x, 1.05, cloth_scale_z), 1.20 - cloth_low.z * cloth_scale_z)

    skirt_low, skirt_high = bounds(skirt)
    skirt_scale_z = (1.70 - 0.05) / max(skirt_high.z - skirt_low.z, 1e-6)
    apply_scale_and_z(skirt, (0.96, 1.15, skirt_scale_z), 0.05 - skirt_low.z * skirt_scale_z)
    skirt_low, skirt_high = bounds(skirt)
    skirt_span = max(skirt_high.z - skirt_low.z, 1e-6)
    for vertex in skirt.data.vertices:
        point = skirt.matrix_world @ vertex.co
        ratio = max(0.0, min(1.0, (point.z - skirt_low.z) / skirt_span))
        flare = 1.0 + 0.22 * max(0.0, min(1.0, (0.68 - ratio) / 0.68))
        point.x *= flare
        point.y *= flare
        vertex.co = skirt.matrix_world.inverted() @ point

    cloth.name = "OpenGameArt_HoodedCloth_FitCandidate"
    skirt.name = "OpenGameArt_LongSkirt_FitCandidate"
    robe_material = material("AssetsStudio_OpenGameArt_MageRobe", (0.085, 0.025, 0.28, 1.0))
    replace_material(cloth, robe_material)
    replace_material(skirt, robe_material)
    cloth_weights = semantic_weights(cloth, armature, "hooded_cloth")
    skirt_weights = semantic_weights(skirt, armature, "skirt")
    for obj in (cloth, skirt):
        obj["workflow_route"] = "opengameart_hooded_cloth_actor_adapter"
        obj["status"] = "review_required"
        obj["source_license"] = "CC-BY-SA-4.0"
        obj["source_author"] = "kednar"
        obj["source_url"] = "https://opengameart.org/content/low-poly-hooded-character-rigged-blender"

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.035, 0.035, 0.05)
    original_hide = {obj.name: obj.hide_render for obj in scene.objects}
    garments = [cloth, skirt]
    for obj in scene.objects:
        if obj.type == "MESH" and obj not in {body, *garments}:
            obj.hide_render = True
    render(scene, body, garments, options.output_dir, "front", 1)
    render(scene, body, garments, options.output_dir, "side", 1)
    render(scene, body, garments, options.output_dir, "three_quarter", 1)
    armature.data.pose_position = "POSE"
    action = armature.animation_data.action if armature.animation_data else None
    motion_frames = [1, 18, 36, 54, 71]
    if action:
        start, end = int(action.frame_range[0]), int(action.frame_range[1])
        motion_frames = [round(start + (end - start) * index / 4.0) for index in range(5)]
    for frame in motion_frames:
        render(scene, body, garments, options.output_dir, f"motion_{frame:03d}", frame)
    for name, hidden in original_hide.items():
        if name in scene.objects:
            scene.objects[name].hide_render = hidden

    output_blend = options.output_dir / "opengameart_hooded_robe_actor.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    report = {
        "schema": "assetsstudio_opengameart_hooded_robe_v1",
        "status": "technical_candidate_review_required",
        "source_cloth": str(options.hood_blend.resolve()),
        "source_skirt": str(options.skirt_blend.resolve()),
        "license": "CC-BY-SA-4.0",
        "attribution": "kednar / OpenGameArt.org",
        "output_blend": str(output_blend.resolve()),
        "objects": {
            "hooded_cloth": {"name": cloth.name, "dimensions": [round(float(v), 6) for v in cloth.dimensions], "weights": cloth_weights},
            "skirt": {"name": skirt.name, "dimensions": [round(float(v), 6) for v in skirt.dimensions], "weights": skirt_weights},
        },
        "motion_frames": motion_frames,
        "notes": [
            "The OpenGameArt garment is used as the upper hooded-cloth source; the lower robe is a separate CC0 skirt module.",
            "The original external armature was removed before applying Actor semantic weights.",
            "This is a fit candidate and requires strict penetration, clearance, and visual hood-opening review.",
        ],
    }
    (options.output_dir / "opengameart_hooded_robe_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
