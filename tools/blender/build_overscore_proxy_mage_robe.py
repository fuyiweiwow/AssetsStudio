"""Adapt the CC0 OverScore Proxy hoodie/skirt modules to the shared Actor.

This is a source-locked adapter pass, not a claim that a generic clothing
asset is already production-ready.  The Proxy file is used because it offers
clean, modular, Q-style clothing parts with UVs; the adapter keeps the hoodie
and lower robe as separate objects so their fit can be repaired independently.
"""

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
    parser.add_argument("--proxy-blend", type=Path)
    parser.add_argument("--output-dir", type=Path)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    options, _ = parser.parse_known_args(argv)
    options.input_blend = options.input_blend or Path(os.environ["OVERSCORE_INPUT_BLEND"])
    options.proxy_blend = options.proxy_blend or Path(os.environ["OVERSCORE_PROXY_BLEND"])
    options.output_dir = options.output_dir or Path(os.environ["OVERSCORE_OUTPUT_DIR"])
    return options


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def world_point(armature: bpy.types.Object, bone_name: str, which: str = "head") -> Vector:
    bone = armature.data.bones.get(bone_name)
    if bone is None:
        raise RuntimeError(f"missing Actor bone: {bone_name}")
    return armature.matrix_world @ getattr(bone, f"{which}_local")


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.82) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = color
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = roughness
    return mat


def replace_materials(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.material_index = 0


def load_proxy_objects(proxy_path: Path, names: list[str]) -> dict[str, bpy.types.Object]:
    loaded: dict[str, bpy.types.Object] = {}
    with bpy.data.libraries.load(str(proxy_path.resolve()), link=False) as (data_from, data_to):
        available = set(data_from.objects)
        missing = [name for name in names if name not in available]
        if missing:
            raise RuntimeError(f"Proxy object(s) missing: {missing}")
        data_to.objects = names

    collection = bpy.data.collections.get("AssetsStudio_OverScoreProxy")
    if collection is None:
        collection = bpy.data.collections.new("AssetsStudio_OverScoreProxy")
        bpy.context.scene.collection.children.link(collection)
    for obj in data_to.objects:
        if obj is None:
            continue
        collection.objects.link(obj)
        loaded[obj.name] = obj
    return loaded


def apply_transform(
    obj: bpy.types.Object,
    scale: tuple[float, float, float],
    z_offset: float,
    xy_offset: tuple[float, float] = (0.0, 0.0),
) -> None:
    obj.scale = scale
    obj.location = (xy_offset[0], xy_offset[1], z_offset)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.select_set(False)


def enlarge_hood_for_actor(obj: bpy.types.Object, body: bpy.types.Object) -> None:
    """Expand only the hood crown/opening around the larger shared Actor head."""
    head_points = [
        body.matrix_world @ vertex.co
        for vertex in body.data.vertices
        if (body.matrix_world @ vertex.co).z > 2.02
    ]
    if not head_points:
        return
    head_center = sum(head_points, Vector()) / len(head_points)
    for vertex in obj.data.vertices:
        point = obj.matrix_world @ vertex.co
        if point.z <= 2.22:
            continue
        factor = 1.0 + 0.42 * max(0.0, min(1.0, (point.z - 2.22) / 0.70))
        point.x = head_center.x + (point.x - head_center.x) * factor
        point.y = head_center.y + (point.y - head_center.y) * (1.0 + (factor - 1.0) * 0.82)
        if point.z > 2.78:
            point.z += 0.04 * max(0.0, min(1.0, (point.z - 2.78) / 0.30))
        vertex.co = obj.matrix_world.inverted() @ point


def ensure_group(obj: bpy.types.Object, name: str) -> bpy.types.VertexGroup:
    return obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)


def clear_and_weight(obj: bpy.types.Object, armature: bpy.types.Object, kind: str) -> dict[str, int]:
    names = [
        "CC_Base_Waist",
        "CC_Base_Spine01",
        "CC_Base_Spine02",
        "CC_Base_NeckTwist01",
        "CC_Base_Head",
        "CC_Base_L_Clavicle",
        "CC_Base_L_Upperarm",
        "CC_Base_L_Forearm",
        "CC_Base_R_Clavicle",
        "CC_Base_R_Upperarm",
        "CC_Base_R_Forearm",
        "CC_Base_L_Thigh",
        "CC_Base_R_Thigh",
    ]
    groups = {name: ensure_group(obj, name) for name in names if armature.data.bones.get(name)}
    for group in groups.values():
        group.remove(range(len(obj.data.vertices)))
    counts = {"torso": 0, "hood": 0, "left_sleeve": 0, "right_sleeve": 0, "lower": 0}
    low, high = bounds(obj)
    span_z = max(high.z - low.z, 1e-6)
    for index, vertex in enumerate(obj.data.vertices):
        point = obj.matrix_world @ vertex.co
        ratio = max(0.0, min(1.0, (point.z - low.z) / span_z))
        if kind == "hood":
            groups["CC_Base_NeckTwist01"].add([index], 0.35, "REPLACE")
            groups["CC_Base_Head"].add([index], 0.65, "ADD")
            counts["hood"] += 1
        elif kind == "upper":
            if point.z > 2.48:
                groups["CC_Base_NeckTwist01"].add([index], 0.48, "REPLACE")
                groups["CC_Base_Head"].add([index], 0.52, "ADD")
                counts["hood"] += 1
            elif point.x < -0.42:
                groups["CC_Base_R_Clavicle"].add([index], 0.20, "REPLACE")
                groups["CC_Base_R_Upperarm"].add([index], 0.55, "ADD")
                groups["CC_Base_R_Forearm"].add([index], 0.25, "ADD")
                counts["left_sleeve"] += 1
            elif point.x > 0.42:
                groups["CC_Base_L_Clavicle"].add([index], 0.20, "REPLACE")
                groups["CC_Base_L_Upperarm"].add([index], 0.55, "ADD")
                groups["CC_Base_L_Forearm"].add([index], 0.25, "ADD")
                counts["right_sleeve"] += 1
            elif ratio > 0.55:
                groups["CC_Base_Spine01"].add([index], 0.35, "REPLACE")
                groups["CC_Base_Spine02"].add([index], 0.65, "ADD")
                counts["torso"] += 1
            else:
                groups["CC_Base_Waist"].add([index], 0.55, "REPLACE")
                groups["CC_Base_Spine01"].add([index], 0.45, "ADD")
                counts["torso"] += 1
        else:
            if ratio < 0.36 and point.x < -0.08 and "CC_Base_R_Thigh" in groups:
                groups["CC_Base_R_Thigh"].add([index], 0.50, "REPLACE")
                groups["CC_Base_Waist"].add([index], 0.50, "ADD")
                counts["lower"] += 1
            elif ratio < 0.36 and point.x > 0.08 and "CC_Base_L_Thigh" in groups:
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
    for modifier in list(obj.modifiers):
        if modifier.type == "ARMATURE":
            obj.modifiers.remove(modifier)
    modifier = obj.modifiers.new("OverScoreProxy_ActorArmature", "ARMATURE")
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
    camera_data = bpy.data.cameras.new(f"OverScoreProxyCamera_{label}")
    camera = bpy.data.objects.new(f"OverScoreProxyCamera_{label}", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (span * 3.8, -span * 3.8, target.z) if label == "three_quarter" else (
        (0.0, -span * 4.2, target.z) if label == "front" else (span * 4.2, 0.0, target.z)
    )
    camera.data.lens = 55
    look_at(camera, target)
    scene.camera = camera
    scene.render.filepath = str(output / f"overscore_proxy_{label}.png")
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
        raise RuntimeError("Input must contain the shared Actor body and Armature")

    for name in ("QStylePartitionedRobe_FitCandidate", "QStyleIndependentHood_FitCandidate"):
        obj = bpy.data.objects.get(name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)

    loaded = load_proxy_objects(options.proxy_blend, ["Winter Jacket without Hood", "Long Skirt", "Assassin Hood"])
    hoodie = loaded["Winter Jacket without Hood"]
    skirt = loaded["Long Skirt"]
    hood = loaded["Assassin Hood"]
    # Proxy clothing is authored as a half-mesh with a live Mirror modifier.
    # Apply Mirror before assigning Actor weights; otherwise the generated
    # mirrored sleeve inherits one side's weights and breaks asymmetric poses.
    for obj in (hoodie, skirt, hood):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        for modifier in list(obj.modifiers):
            if modifier.type == "MIRROR":
                bpy.ops.object.modifier_apply(modifier=modifier.name)
        obj.select_set(False)
    # Source coordinates are the Proxy avatar's 5-unit body.  The two pieces
    # are fitted independently to the Actor's shoulder/head and foot/hem
    # landmarks; this avoids a global scale that destroys the robe silhouette.
    apply_transform(hoodie, (0.55, 1.15, 0.85), -1.15)
    apply_transform(skirt, (0.96, 1.15, 1.05), -0.415)
    apply_transform(hood, (1.90, 1.70, 1.20), -3.00, (0.0, -0.12))
    # Turn the straight Proxy skirt into a controlled robe flare.  The upper
    # seam remains unchanged; only the lower 65% expands toward the hem.
    skirt_low, skirt_high = bounds(skirt)
    skirt_span = max(skirt_high.z - skirt_low.z, 1e-6)
    for vertex in skirt.data.vertices:
        point = skirt.matrix_world @ vertex.co
        ratio = max(0.0, min(1.0, (point.z - skirt_low.z) / skirt_span))
        flare = 1.0 + 0.20 * max(0.0, min(1.0, (0.65 - ratio) / 0.65))
        point.x *= flare
        point.y *= flare
        vertex.co = skirt.matrix_world.inverted() @ point
    hoodie.name = "OverScoreProxy_WinterJacket_FitCandidate"
    skirt.name = "OverScoreProxy_LongSkirt_FitCandidate"
    hood.name = "OverScoreProxy_AssassinHood_FitCandidate"
    robe_mat = material("AssetsStudio_OverScoreProxy_MageRobe", (0.085, 0.025, 0.28, 1.0))
    replace_materials(hoodie, robe_mat)
    replace_materials(skirt, robe_mat)
    replace_materials(hood, material("AssetsStudio_OverScoreProxy_MageHood", (0.045, 0.012, 0.16, 1.0)))
    hoodie_counts = clear_and_weight(hoodie, armature, "upper")
    skirt_counts = clear_and_weight(skirt, armature, "skirt")
    hood_counts = clear_and_weight(hood, armature, "hood")
    for obj in (hoodie, skirt, hood):
        obj["workflow_route"] = "overscore_proxy_qstyle_adapter"
        obj["status"] = "review_required"
        obj["source_license"] = "CC0"
        obj["source_asset"] = str(options.proxy_blend.resolve())

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.035, 0.035, 0.05)
    original_hide = {obj.name: obj.hide_render for obj in scene.objects}
    for obj in scene.objects:
        if obj.type == "MESH" and obj not in {body, hoodie, skirt, hood}:
            obj.hide_render = True
    garments = [hoodie, skirt, hood]
    render(scene, body, garments, options.output_dir, "front", 1)
    render(scene, body, garments, options.output_dir, "side", 1)
    render(scene, body, garments, options.output_dir, "three_quarter", 1)
    armature.data.pose_position = "POSE"
    action = armature.animation_data.action if armature.animation_data else None
    motion_frames = [1, 16, 31, 46, 61]
    if action:
        start, end = int(action.frame_range[0]), int(action.frame_range[1])
        motion_frames = [round(start + (end - start) * index / 4.0) for index in range(5)]
    for frame in motion_frames:
        render(scene, body, garments, options.output_dir, f"motion_{frame:03d}", frame)
    for name, hidden in original_hide.items():
        if name in scene.objects:
            scene.objects[name].hide_render = hidden

    output_blend = options.output_dir / "overscore_proxy_mage_robe_actor.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    report = {
        "schema": "assetsstudio_overscore_proxy_mage_robe_v1",
        "status": "technical_candidate_review_required",
        "source": str(options.proxy_blend.resolve()),
        "license": "CC0",
        "input_blend": str(options.input_blend.resolve()),
        "output_blend": str(output_blend.resolve()),
        "objects": {
            "upper": {"name": hoodie.name, "dimensions": [round(float(v), 6) for v in hoodie.dimensions], "weights": hoodie_counts},
            "hood": {"name": hood.name, "dimensions": [round(float(v), 6) for v in hood.dimensions], "weights": hood_counts},
            "skirt": {"name": skirt.name, "dimensions": [round(float(v), 6) for v in skirt.dimensions], "weights": skirt_counts},
        },
        "transforms": {
            "upper": {"source": "Winter Jacket without Hood", "scale": [0.55, 1.15, 0.85], "z_offset": -1.15},
            "hood": {"source": "Assassin Hood", "scale": [1.90, 1.70, 1.20], "xy_offset": [0.0, -0.12], "z_offset": -3.00},
            "skirt": {"scale": [0.96, 1.15, 1.05], "z_offset": -0.415},
        },
        "motion_frames": motion_frames,
        "notes": [
            "The hoodie and skirt remain separate repair regions.",
            "This pass validates source compatibility and rig binding before material/detail work.",
            "A strict penetration/hem checker must decide promotion; the render is not a production approval.",
        ],
    }
    (options.output_dir / "overscore_proxy_mage_robe_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
