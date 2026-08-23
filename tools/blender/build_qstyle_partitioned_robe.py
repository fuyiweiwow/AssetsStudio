"""Build a Q-style partitioned robe candidate from an already fitted robe.

The source fit is preserved.  This pass only repairs the coupled failure that
an adult-proportion robe places both sleeves above the Q-style Actor shoulder.
Sleeves are reposed around Actor upper-arm landmarks, while the torso and
central collar remain separate repair regions.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", type=Path)
    parser.add_argument("--output-dir", type=Path)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    options, _ = parser.parse_known_args(argv)
    options.input_blend = options.input_blend or Path(os.environ["QSTYLE_INPUT_BLEND"])
    options.output_dir = options.output_dir or Path(os.environ["QSTYLE_OUTPUT_DIR"])
    return options


def world_point(armature: bpy.types.Object, bone_name: str, which: str = "head") -> Vector:
    bone = armature.data.bones.get(bone_name)
    if bone is None:
        raise RuntimeError(f"missing Actor bone: {bone_name}")
    return armature.matrix_world @ getattr(bone, f"{which}_local")


def smoothstep(value: float, low: float, high: float) -> float:
    if high <= low:
        return 1.0 if value >= high else 0.0
    t = max(0.0, min(1.0, (value - low) / (high - low)))
    return t * t * (3.0 - 2.0 * t)


def add_weight(groups: dict[str, bpy.types.VertexGroup], index: int, values: dict[str, float]) -> None:
    total = sum(max(0.0, value) for value in values.values())
    if total <= 0.0:
        return
    for name, value in values.items():
        if value > 0.0:
            groups[name].add([index], value / total, "REPLACE")


def make_material(garment: bpy.types.Object) -> None:
    material = bpy.data.materials.get("AssetsStudio_QStyleRobeDiagnostic") or bpy.data.materials.new(
        "AssetsStudio_QStyleRobeDiagnostic"
    )
    material.use_nodes = True
    material.diffuse_color = (0.10, 0.035, 0.34, 1.0)
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = (0.10, 0.035, 0.34, 1.0)
        principled.inputs["Roughness"].default_value = 0.84
    garment.data.materials.clear()
    garment.data.materials.append(material)


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def render_frame(scene: bpy.types.Scene, body: bpy.types.Object, garment: bpy.types.Object, output: Path, frame: int, label: str) -> None:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    low, high = bounds(body)
    target = (low + high) * 0.5
    span = max((high - low).x, (high - low).y, (high - low).z)
    camera_data = bpy.data.cameras.new(f"QStyleRobeCamera_{label}")
    camera = bpy.data.objects.new(f"QStyleRobeCamera_{label}", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (span * 3.8, -span * 3.8, target.z) if label == "three_quarter" else (
        (0.0, -span * 4.2, target.z) if label == "front" else (span * 4.2, 0.0, target.z)
    )
    camera.data.lens = 55
    look_at(camera, target)
    scene.camera = camera
    scene.render.filepath = str(output / f"qstyle_robe_{label}.png")
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(camera, do_unlink=True)


def main() -> int:
    options = parse_args()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    scene = bpy.context.scene
    body = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    garment = bpy.data.objects.get("ExternalLongRobe_FitCandidate")
    armature = bpy.data.objects.get("Armature")
    if body is None or garment is None or armature is None:
        raise RuntimeError("Q-style input must contain Actor body, Armature, and ExternalLongRobe_FitCandidate")

    scene.frame_set(1)
    armature.data.pose_position = "REST"
    bpy.context.view_layer.update()
    vertex_points = [garment.matrix_world @ vertex.co for vertex in garment.data.vertices]
    original_points = list(vertex_points)

    # In this Actor rig, the negative-X screen-left sleeve corresponds to the
    # R-named bones, while the positive-X sleeve corresponds to L-named bones.
    target_pivots = {
        "left": world_point(armature, "CC_Base_R_Upperarm"),
        "right": world_point(armature, "CC_Base_L_Upperarm"),
    }
    hand_targets = {
        "left": (world_point(armature, "CC_Base_R_Hand") + world_point(armature, "CC_Base_R_Hand", "tail")) * 0.5,
        "right": (world_point(armature, "CC_Base_L_Hand") + world_point(armature, "CC_Base_L_Hand", "tail")) * 0.5,
    }

    # The downloaded robe's sleeve/armhole band is around z=2.08, while the
    # shared Q-style Actor's upper-arm heads are around z=1.35.
    source_pivots: dict[str, Vector] = {}
    transform_records: dict[str, dict[str, object]] = {}
    for side, sign in (("left", -1.0), ("right", 1.0)):
        candidates = [
            point
            for point in original_points
            if 0.34 <= sign * point.x <= 0.52 and 1.70 <= point.z <= 2.40
        ]
        source_pivot = (
            Vector((sum(point.x for point in candidates) / len(candidates), sum(point.y for point in candidates) / len(candidates), sum(point.z for point in candidates) / len(candidates)))
            if candidates
            else Vector((sign * 0.42, 0.0, 2.08))
        )
        source_pivots[side] = source_pivot
        target_pivot = target_pivots[side]
        target_hand = hand_targets[side]
        angle = math.radians(48.0 * sign)
        rotation = Matrix.Rotation(angle, 4, "Y")
        transform_records[side] = {
            "source_pivot": [round(value, 6) for value in source_pivot],
            "target_pivot": [round(value, 6) for value in target_pivot],
            "target_hand": [round(value, 6) for value in target_hand],
            "rotation_degrees_y": 48.0 * sign,
            "transition_band_x": [0.34, 0.52],
        }
        for index, point in enumerate(vertex_points):
            side_x = sign * point.x
            if side_x <= 0.34:
                continue
            influence = smoothstep(side_x, 0.34, 0.52)
            transformed = target_pivot + rotation @ ((point - source_pivot) * 0.82)
            vertex_points[index] = point.lerp(transformed, influence)

    for vertex, point in zip(garment.data.vertices, vertex_points):
        vertex.co = garment.matrix_world.inverted() @ point

    # Create explicit region groups for later ECF EVGF and manual tuning.
    groups = {}
    for name in (
        "QStyle_Torso",
        "QStyle_LeftSleeve",
        "QStyle_RightSleeve",
        "QStyle_Collar",
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
    ):
        groups[name] = garment.vertex_groups.get(name) or garment.vertex_groups.new(name=name)

    low, high = bounds(body)
    min_z, max_z = low.z, high.z
    sleeve_counts = {"left": 0, "right": 0, "torso": 0, "collar": 0}
    for index, vertex in enumerate(garment.data.vertices):
        point = garment.matrix_world @ vertex.co
        left_weight = smoothstep(-point.x, 0.34, 0.52)
        right_weight = smoothstep(point.x, 0.34, 0.52)
        if left_weight > 0.5:
            groups["QStyle_LeftSleeve"].add([index], left_weight, "REPLACE")
            add_weight(groups, index, {"CC_Base_R_Clavicle": 0.20, "CC_Base_R_Upperarm": 0.55, "CC_Base_R_Forearm": 0.25})
            sleeve_counts["left"] += 1
            continue
        if right_weight > 0.5:
            groups["QStyle_RightSleeve"].add([index], right_weight, "REPLACE")
            add_weight(groups, index, {"CC_Base_L_Clavicle": 0.20, "CC_Base_L_Upperarm": 0.55, "CC_Base_L_Forearm": 0.25})
            sleeve_counts["right"] += 1
            continue

        groups["QStyle_Torso"].add([index], 1.0, "REPLACE")
        ratio = max(0.0, min(1.0, (point.z - min_z) / max(max_z - min_z, 1e-6)))
        if ratio > 0.82:
            groups["QStyle_Collar"].add([index], 1.0, "REPLACE")
            add_weight(index=index, groups=groups, values={"CC_Base_NeckTwist01": 0.45, "CC_Base_Head": 0.55})
            sleeve_counts["collar"] += 1
        elif ratio > 0.58:
            add_weight(index=index, groups=groups, values={"CC_Base_Spine01": 0.30, "CC_Base_Spine02": 0.70})
        else:
            add_weight(index=index, groups=groups, values={"CC_Base_Waist": 0.60, "CC_Base_Spine01": 0.40})
        sleeve_counts["torso"] += 1

    for modifier in list(garment.modifiers):
        if modifier.type == "ARMATURE":
            garment.modifiers.remove(modifier)
    armature_modifier = garment.modifiers.new("QStyleRobe_Armature", "ARMATURE")
    armature_modifier.object = armature
    armature_modifier.use_deform_preserve_volume = True
    make_material(garment)
    garment.name = "QStylePartitionedRobe_FitCandidate"
    garment["workflow_route"] = "qstyle_partitioned_external_template"
    garment["status"] = "review_required"
    garment["fit_regions"] = ["torso", "left_sleeve", "right_sleeve", "collar"]

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.035, 0.035, 0.05)
    original_hide_render = {obj.name: obj.hide_render for obj in scene.objects}
    for obj in scene.objects:
        if obj.type == "MESH" and obj not in {body, garment}:
            obj.hide_render = True
    render_frame(scene, body, garment, options.output_dir, 1, "front")
    render_frame(scene, body, garment, options.output_dir, 1, "side")
    render_frame(scene, body, garment, options.output_dir, 1, "three_quarter")
    armature.data.pose_position = "POSE"
    action = armature.animation_data.action if armature.animation_data else None
    motion_frames = [1, 16, 31, 46, 61]
    if action:
        start, end = int(action.frame_range[0]), int(action.frame_range[1])
        motion_frames = [round(start + (end - start) * index / 4.0) for index in range(5)]
        for frame in motion_frames:
            render_frame(scene, body, garment, options.output_dir, frame, f"motion_{frame:03d}")
    for name, hidden in original_hide_render.items():
        if name in scene.objects:
            scene.objects[name].hide_render = hidden

    output_blend = options.output_dir / "qstyle_partitioned_robe_actor.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    report = {
        "schema": "assetsstudio_qstyle_partitioned_robe_v1",
        "input_blend": str(options.input_blend.resolve()),
        "output_blend": str(output_blend.resolve()),
        "garment_object": garment.name,
        "regions": ["torso", "left_sleeve", "right_sleeve", "collar"],
        "region_vertex_counts": sleeve_counts,
        "sleeve_transforms": transform_records,
        "motion_frames": motion_frames,
        "status": "review_required",
        "limitations": [
            "Sleeve remap is a deterministic rest-pose repair, not cloth simulation.",
            "Collar/hood design remains provisional because the downloaded base has no dedicated hood topology.",
        ],
    }
    (options.output_dir / "qstyle_partition_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
