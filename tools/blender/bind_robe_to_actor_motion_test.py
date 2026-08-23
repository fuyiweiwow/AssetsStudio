"""Bind a generated robe OBJ to the existing Actor armature for a cheap motion gate.

Weights are copied from the nearest Actor vertex.  This is intentionally a
motion-following smoke test, not cloth simulation or production skinning.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--garment", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--garment-scale", type=float, default=56.6540755631)
    parser.add_argument("--frames", default="1,11,21,31,41,51,61")
    parser.add_argument("--binding-mode", choices=("nearest", "semantic"), default="nearest")
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    return parser.parse_args(argv)


def import_garment(path: Path, scale: float) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(path))
    created = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    if len(created) != 1:
        raise RuntimeError(f"expected one garment mesh, got {len(created)}")
    garment = created[0]
    garment.name = "ActorConformedRobeMotionTest"
    garment.scale = (1.0 / scale, 1.0 / scale, 1.0 / scale)
    bpy.context.view_layer.update()
    return garment


def copy_nearest_weights(source: bpy.types.Object, garment: bpy.types.Object) -> dict[str, int]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = source.evaluated_get(depsgraph)
    source_points = [evaluated.matrix_world @ vertex.co for vertex in evaluated.data.vertices]
    tree = KDTree(len(source_points))
    for index, point in enumerate(source_points):
        tree.insert(point, index)
    tree.balance()

    group_map = {group.index: garment.vertex_groups.new(name=group.name) for group in source.vertex_groups}
    assignments = 0
    for vertex in garment.data.vertices:
        world_point = garment.matrix_world @ vertex.co
        _co, source_index, _distance = tree.find(world_point)
        source_vertex = source.data.vertices[source_index]
        total = sum(max(0.0, assignment.weight) for assignment in source_vertex.groups)
        if total <= 0.0:
            continue
        for assignment in source_vertex.groups:
            target_group = group_map.get(assignment.group)
            if target_group is not None and assignment.weight > 0.0:
                target_group.add([vertex.index], assignment.weight / total, "REPLACE")
                assignments += 1
    return {"source_groups": len(group_map), "vertex_group_assignments": assignments}


def copy_semantic_weights(source: bpy.types.Object, garment: bpy.types.Object) -> dict[str, int]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = source.evaluated_get(depsgraph)
    source_points = [evaluated.matrix_world @ vertex.co for vertex in evaluated.data.vertices]
    head_group = source.vertex_groups.get("CC_Base_Head")
    head_indices = []
    if head_group is not None:
        for vertex in source.data.vertices:
            for assignment in vertex.groups:
                if assignment.group == head_group.index and assignment.weight >= 0.25:
                    head_indices.append(vertex.index)
                    break
    head_bottom = min((source_points[index].z for index in head_indices), default=1.50)
    source_x = [point.x for point in source_points]
    bone_names = {
        "waist": "CC_Base_Waist",
        "spine01": "CC_Base_Spine01",
        "spine02": "CC_Base_Spine02",
        "neck": "CC_Base_NeckTwist01",
        "head": "CC_Base_Head",
        "l_clavicle": "CC_Base_L_Clavicle",
        "l_upperarm": "CC_Base_L_Upperarm",
        "l_forearm": "CC_Base_L_Forearm",
        "r_clavicle": "CC_Base_R_Clavicle",
        "r_upperarm": "CC_Base_R_Upperarm",
        "r_forearm": "CC_Base_R_Forearm",
    }
    groups = {key: garment.vertex_groups.new(name=name) for key, name in bone_names.items()}
    counts = {key: 0 for key in bone_names}
    min_z = min(point.z for point in source_points)
    body_span = max(head_bottom - min_z, 0.5)

    adjacency = [set() for _ in garment.data.vertices]
    for polygon in garment.data.polygons:
        indices = list(polygon.vertices)
        for index in indices:
            adjacency[index].update(other for other in indices if other != index)
    component_ids = [-1] * len(adjacency)
    components: list[list[int]] = []
    for start_index in range(len(adjacency)):
        if component_ids[start_index] != -1:
            continue
        component_index = len(components)
        stack = [start_index]
        component_ids[start_index] = component_index
        members = []
        while stack:
            current = stack.pop()
            members.append(current)
            for neighbor in adjacency[current]:
                if component_ids[neighbor] == -1:
                    component_ids[neighbor] = component_index
                    stack.append(neighbor)
        components.append(members)
    component_kind: dict[int, str] = {}
    for component_index, members in enumerate(components):
        points = [garment.matrix_world @ garment.data.vertices[index].co for index in members]
        cx = sum(point.x for point in points) / len(points)
        max_component_z = max(point.z for point in points)
        if max_component_z >= head_bottom - 0.06:
            component_kind[component_index] = "hood"
        elif cx < -0.8:
            component_kind[component_index] = "left_sleeve"
        elif cx > 0.8:
            component_kind[component_index] = "right_sleeve"
        else:
            component_kind[component_index] = "torso"

    def assign(vertex_index: int, weights: dict[str, float]) -> None:
        total = sum(weights.values())
        for key, weight in weights.items():
            if weight > 0.0:
                groups[key].add([vertex_index], weight / total, "REPLACE")
                counts[key] += 1

    for vertex in garment.data.vertices:
        point = garment.matrix_world @ vertex.co
        kind = component_kind[component_ids[vertex.index]]
        if kind == "hood":
            assign(vertex.index, {"head": 0.78, "neck": 0.22})
        elif kind == "left_sleeve":
            assign(vertex.index, {"l_clavicle": 0.20, "l_upperarm": 0.55, "l_forearm": 0.25})
        elif kind == "right_sleeve":
            assign(vertex.index, {"r_clavicle": 0.20, "r_upperarm": 0.55, "r_forearm": 0.25})
        else:
            ratio = max(0.0, min(1.0, (point.z - min_z) / body_span))
            if ratio > 0.62:
                assign(vertex.index, {"spine01": 0.30, "spine02": 0.70})
            else:
                assign(vertex.index, {"waist": 0.60, "spine01": 0.40})
    return {"mode": "semantic", "head_bottom_world": head_bottom, "components": len(components), "component_kinds": component_kind, "group_assignments": counts}


def add_material(garment: bpy.types.Object) -> None:
    material = bpy.data.materials.new("ActorConformedRobeMotionTest_Material")
    material.diffuse_color = (0.16, 0.025, 0.42, 1.0)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = (0.16, 0.025, 0.42, 1.0)
        principled.inputs["Roughness"].default_value = 0.82
    garment.data.materials.clear()
    garment.data.materials.append(material)


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def configure_preview(scene: bpy.types.Scene, actor: bpy.types.Object) -> None:
    bpy.ops.object.camera_add(location=(4.2, -6.8, 2.1))
    camera = bpy.context.object
    camera.name = "ActorConformedRobeMotionCamera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 3.9
    look_at(camera, Vector((0.0, 0.0, 1.55)))
    scene.camera = camera
    bpy.ops.object.light_add(type="AREA", location=(3.0, -4.0, 4.0))
    key = bpy.context.object
    key.name = "ActorConformedRobeMotionKey"
    key.data.energy = 850.0
    key.data.shape = "DISK"
    key.data.size = 4.0
    look_at(key, Vector((0.0, 0.0, 1.4)))
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True


def main() -> int:
    options = parse_args()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    scene = bpy.context.scene
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if actor is None or armature is None:
        raise RuntimeError("Actor blend must contain ChibiBaseMesh_AccuRIG_InputMesh and Armature")
    frames = [int(value.strip()) for value in options.frames.split(",") if value.strip()]
    scene.frame_set(frames[0])
    original_pose_position = armature.data.pose_position
    armature.data.pose_position = "REST"
    garment = import_garment(options.garment, options.garment_scale)
    weight_report = copy_semantic_weights(actor, garment) if options.binding_mode == "semantic" else copy_nearest_weights(actor, garment)
    armature.data.pose_position = original_pose_position
    modifier = garment.modifiers.new("ActorConformedRobe_Armature", "ARMATURE")
    modifier.object = armature
    modifier.use_deform_preserve_volume = True
    add_material(garment)
    garment["workflow_route"] = "actor_conformed_parameterized_robe"
    garment["motion_test"] = options.binding_mode + "_actor_weights"
    garment["status"] = "motion_smoke_review_required"
    actor.hide_render = False
    actor.hide_viewport = False
    configure_preview(scene, actor)

    renders = []
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        output = options.output_dir / f"motion_frame_{frame:03d}.png"
        scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)
        renders.append(str(output))

    blend_output = options.output_dir / "actor_conformed_robe_motion_test.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_output))
    report = {
        "schema": "assetsstudio_actor_conformed_robe_motion_test_v1",
        "actor_blend": str(options.actor_blend.resolve()),
        "garment": str(options.garment.resolve()),
        "output_blend": str(blend_output),
        "garment_object": garment.name,
        "armature": armature.name,
        "frames": frames,
        "garment_scale": options.garment_scale,
        "weight_transfer": weight_report,
        "renders": renders,
        "status": "motion_smoke_review_required",
        "limitations": [
            f"{options.binding_mode} Actor weights are only a binding smoke test",
            "no cloth simulation, corrective shapes, or collision response",
        ],
    }
    (options.output_dir / "motion_test_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
