"""Replace the failed source hood region with the previously measured hood shell."""

from __future__ import annotations

import argparse
import bmesh
import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


SOURCE_SCALE = 56.6540755631


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", type=Path)
    parser.add_argument("--hood-obj", type=Path)
    parser.add_argument("--output-dir", type=Path)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    options, _ = parser.parse_known_args(argv)
    options.input_blend = options.input_blend or Path(os.environ["QHOOD_INPUT_BLEND"])
    options.hood_obj = options.hood_obj or Path(os.environ["QHOOD_SOURCE_OBJ"])
    options.output_dir = options.output_dir or Path(os.environ["QHOOD_OUTPUT_DIR"])
    return options


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def head_bounds(body: bpy.types.Object) -> tuple[Vector, Vector]:
    group = body.vertex_groups.get("CC_Base_Head")
    points = [body.matrix_world @ vertex.co for vertex in body.data.vertices if any(item.group == group.index and item.weight >= 0.25 for item in vertex.groups)]
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    result = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    result.use_nodes = True
    result.diffuse_color = color
    principled = result.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.84
    return result


def import_hood(path: Path, body: bpy.types.Object) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(path.resolve()))
    created = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    if len(created) != 1:
        raise RuntimeError(f"expected one hood mesh, got {len(created)}")
    hood = created[0]
    hood.name = "QStyleIndependentHood_FitCandidate"
    hood.scale = (0.86 / SOURCE_SCALE, 1.0 / SOURCE_SCALE, 1.0 / SOURCE_SCALE)
    bpy.context.view_layer.update()
    hood_low, hood_high = bounds(hood)
    head_low, head_high = head_bounds(body)
    hood_center = (hood_low + hood_high) * 0.5
    head_center = (head_low + head_high) * 0.5
    hood.location += Vector((head_center.x - hood_center.x, head_center.y - hood_center.y, head_center.z - hood_center.z))
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = hood
    hood.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    hood.data.materials.clear()
    hood.data.materials.append(material("AssetsStudio_IndependentHood", (0.075, 0.018, 0.26, 1.0)))
    return hood


def delete_source_upper_region(garment: bpy.types.Object, head_low: Vector, head_high: Vector) -> int:
    bm = bmesh.new()
    bm.from_mesh(garment.data)
    bm.faces.ensure_lookup_table()
    center = (head_low + head_high) * 0.5
    radii = (head_high - head_low) * 0.5 + Vector((0.035, 0.035, 0.035))

    def inside_head(point: Vector) -> bool:
        normalized = Vector(
            (
                (point.x - center.x) / max(radii.x, 1e-6),
                (point.y - center.y) / max(radii.y, 1e-6),
                (point.z - center.z) / max(radii.z, 1e-6),
            )
        )
        return normalized.length < 1.0

    delete_faces = [
        face
        for face in bm.faces
        if face.calc_center_median().z > head_low.z + 0.03 and inside_head(face.calc_center_median())
    ]
    if delete_faces:
        bmesh.ops.delete(bm, geom=delete_faces, context="FACES")
    bm.to_mesh(garment.data)
    bm.free()
    garment.data.update()
    return len(delete_faces)


def project_hood_clearance(hood: bpy.types.Object, head_low: Vector, head_high: Vector) -> int:
    center = (head_low + head_high) * 0.5
    radii = (head_high - head_low) * 0.5 + Vector((0.045, 0.045, 0.045))
    projected = 0
    for vertex in hood.data.vertices:
        point = hood.matrix_world @ vertex.co
        normalized = Vector(
            (
                (point.x - center.x) / max(radii.x, 1e-6),
                (point.y - center.y) / max(radii.y, 1e-6),
                (point.z - center.z) / max(radii.z, 1e-6),
            )
        )
        if normalized.length < 1.0:
            if normalized.length < 1e-6:
                normalized = Vector((0.0, 1.0, 0.0))
            target = center + normalized.normalized() * radii
            vertex.co = hood.matrix_world.inverted() @ target
            projected += 1
    hood.data.update()
    return projected


def add_hood_weights(hood: bpy.types.Object, armature: bpy.types.Object) -> None:
    head = hood.vertex_groups.get("CC_Base_Head") or hood.vertex_groups.new(name="CC_Base_Head")
    neck = hood.vertex_groups.get("CC_Base_NeckTwist01") or hood.vertex_groups.new(name="CC_Base_NeckTwist01")
    for vertex in hood.data.vertices:
        head.add([vertex.index], 0.78, "REPLACE")
        neck.add([vertex.index], 0.22, "REPLACE")
    modifier = hood.modifiers.new("QStyleIndependentHood_Armature", "ARMATURE")
    modifier.object = armature
    modifier.use_deform_preserve_volume = True


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def render_group(scene: bpy.types.Scene, body: bpy.types.Object, garments: list[bpy.types.Object], output: Path) -> list[int]:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.035, 0.035, 0.05)
    low, high = bounds(body)
    target = (low + high) * 0.5
    span = max((high - low).x, (high - low).y, (high - low).z)
    original_hide = {obj.name: obj.hide_render for obj in scene.objects}
    for obj in scene.objects:
        if obj.type == "MESH" and obj not in {body, *garments}:
            obj.hide_render = True
    frames = [1]
    action = bpy.data.objects.get("Armature").animation_data.action if bpy.data.objects.get("Armature").animation_data else None
    if action:
        start, end = int(action.frame_range[0]), int(action.frame_range[1])
        frames = [round(start + (end - start) * index / 4.0) for index in range(5)]
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        for label, location in {
            "front": (0.0, -span * 4.2, target.z),
            "side": (span * 4.2, 0.0, target.z),
            "three_quarter": (span * 3.2, -span * 3.2, target.z),
        }.items():
            camera_data = bpy.data.cameras.new(f"QHoodCamera_{frame}_{label}")
            camera = bpy.data.objects.new(f"QHoodCamera_{frame}_{label}", camera_data)
            scene.collection.objects.link(camera)
            camera.location = location
            camera.data.lens = 55
            look_at(camera, target)
            scene.camera = camera
            scene.render.filepath = str(output / f"qhood_{label}_{frame:03d}.png")
            bpy.ops.render.render(write_still=True)
            bpy.data.objects.remove(camera, do_unlink=True)
    for name, hidden in original_hide.items():
        if name in scene.objects:
            scene.objects[name].hide_render = hidden
    return frames


def main() -> int:
    options = parse_args()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    scene = bpy.context.scene
    body = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    garment = bpy.data.objects.get("QStylePartitionedRobe_FitCandidate")
    armature = bpy.data.objects.get("Armature")
    if body is None or garment is None or armature is None:
        raise RuntimeError("input must contain Actor body, robe candidate, and Armature")
    scene.frame_set(1)
    armature.data.pose_position = "REST"
    head_low, head_high = head_bounds(body)
    deleted_faces = delete_source_upper_region(garment, head_low, head_high)
    garment.name = "QStyleRobeBody_FitCandidate"
    hood = import_hood(options.hood_obj, body)
    projected_hood_vertices = project_hood_clearance(hood, head_low, head_high)
    add_hood_weights(hood, armature)
    garment["hood_replacement"] = "actor_conformed_hood_shell_v11_cowl5"
    garment["status"] = "review_required"
    hood["workflow_route"] = "qstyle_partitioned_external_template"
    hood["status"] = "review_required"
    frames = render_group(scene, body, [garment, hood], options.output_dir)
    output_blend = options.output_dir / "qstyle_robe_independent_hood.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    hood_low, hood_high = bounds(hood)
    report = {
        "schema": "assetsstudio_qstyle_robe_independent_hood_v1",
        "input_blend": str(options.input_blend.resolve()),
        "hood_source_obj": str(options.hood_obj.resolve()),
        "output_blend": str(output_blend.resolve()),
        "body_object": garment.name,
        "hood_object": hood.name,
        "source_upper_faces_deleted": deleted_faces,
        "hood_clearance_vertices_projected": projected_hood_vertices,
        "hood_bbox_min": [round(float(value), 6) for value in hood_low],
        "hood_bbox_max": [round(float(value), 6) for value in hood_high],
        "frames": frames,
        "status": "review_required",
        "limitations": [
            "The hood shell is reused from an earlier Actor-conformed prototype.",
            "The robe body still needs a robe-specific loose-fit collision envelope.",
        ],
    }
    (options.output_dir / "independent_hood_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
