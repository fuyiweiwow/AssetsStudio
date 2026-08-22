"""Render and measure an already-retargeted Actor V2 action.

Unlike the older procedural walk preview, this script never clears or replaces
the action.  It samples the actual animation stored on the AccuRIG armature.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


LANDMARK_BONES = (
    "CC_Base_Hip",
    "CC_Base_Head",
    "CC_Base_L_Hand",
    "CC_Base_R_Hand",
    "CC_Base_L_Foot",
    "CC_Base_R_Foot",
)


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def evaluated_bounds(obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph) -> tuple[Vector, Vector, bool]:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        matrix = evaluated.matrix_world
        minimum = Vector((math.inf, math.inf, math.inf))
        maximum = Vector((-math.inf, -math.inf, -math.inf))
        finite = True
        for vertex in mesh.vertices:
            point = matrix @ vertex.co
            finite = finite and all(math.isfinite(value) for value in point)
            minimum.x = min(minimum.x, point.x)
            minimum.y = min(minimum.y, point.y)
            minimum.z = min(minimum.z, point.z)
            maximum.x = max(maximum.x, point.x)
            maximum.y = max(maximum.y, point.y)
            maximum.z = max(maximum.z, point.z)
        return minimum, maximum, finite
    finally:
        evaluated.to_mesh_clear()


def bone_head_world(armature: bpy.types.Object, name: str) -> list[float] | None:
    bone = armature.pose.bones.get(name)
    if bone is None:
        return None
    return list(armature.matrix_world @ bone.head)


def evenly_spaced_frames(start: int, end: int, count: int) -> list[int]:
    if count <= 1 or start == end:
        return [start]
    return sorted({round(start + index * (end - start) / (count - 1)) for index in range(count)})


def configure_scene(scene: bpy.types.Scene, resolution: int, height: float, center: Vector) -> bpy.types.Object:
    for obj in list(scene.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)

    world = scene.world or bpy.data.worlds.new("ActorV2_ActionReviewWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background:
        background.inputs["Color"].default_value = (0.035, 0.045, 0.065, 1.0)
        background.inputs["Strength"].default_value = 0.45

    for name, location, energy, size in (
        ("ActionReviewKey", (height, -height * 1.4, height * 1.7), 500.0, height * 1.4),
        ("ActionReviewFill", (-height, -height * 0.6, height), 280.0, height * 1.8),
        ("ActionReviewRim", (0.0, height, height * 1.5), 360.0, height * 1.3),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        look_at(light, center)

    camera_data = bpy.data.cameras.new("ActionReviewCameraData")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = height / 0.70
    camera = bpy.data.objects.new("ActionReviewCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            scene.view_settings.look = look
            break
        except TypeError:
            continue
    return camera


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-count", type=int, default=8)
    parser.add_argument("--resolution", type=int, default=384)
    parser.add_argument("--actor-object", default="ChibiBaseMesh_AccuRIG_InputMesh")
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw_args)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))
    scene = bpy.context.scene
    armatures = [obj for obj in scene.objects if obj.type == "ARMATURE"]
    rigged_meshes = [
        obj
        for obj in scene.objects
        if obj.type == "MESH" and any(mod.type == "ARMATURE" and mod.object for mod in obj.modifiers)
    ]
    if len(armatures) != 1 or not rigged_meshes:
        raise RuntimeError(f"Expected one armature and at least one rigged mesh; got {len(armatures)} and {len(rigged_meshes)}")
    armature = armatures[0]
    actor = next((obj for obj in rigged_meshes if obj.name == args.actor_object), None)
    if actor is None:
        raise RuntimeError(
            f"Actor mesh {args.actor_object!r} not found among rigged meshes: "
            f"{[obj.name for obj in rigged_meshes]}"
        )
    attachment_meshes = [obj for obj in rigged_meshes if obj != actor]
    # Hair, ears, eyes and other rigid head accessories are intentionally
    # bone-parented instead of carrying an Armature modifier.  They must be
    # included in action QA as well; otherwise a drifting or non-finite hair
    # object can be absent from an otherwise green report.
    attachment_meshes.extend(
        obj
        for obj in scene.objects
        if obj.type == "MESH"
        and obj != actor
        and obj.parent == armature
        and obj.parent_type == "BONE"
        and obj not in attachment_meshes
    )
    action = armature.animation_data.action if armature.animation_data else None
    if action is None:
        raise RuntimeError("The target armature has no active action")

    start = int(round(action.frame_range[0]))
    end = int(round(action.frame_range[1]))
    frames = evenly_spaced_frames(start, end, args.sample_count)
    scene.frame_start = start
    scene.frame_end = end
    depsgraph = bpy.context.evaluated_depsgraph_get()

    samples = []
    for frame in frames:
        scene.frame_set(frame)
        depsgraph.update()
        minimum, maximum, finite = evaluated_bounds(actor, depsgraph)
        attachment_finite = {}
        for attachment in attachment_meshes:
            _, _, is_finite = evaluated_bounds(attachment, depsgraph)
            attachment_finite[attachment.name] = is_finite
        dimensions = maximum - minimum
        samples.append(
            {
                "frame": frame,
                "bounds_min": list(minimum),
                "bounds_max": list(maximum),
                "dimensions": list(dimensions),
                "finite_geometry": finite,
                "attachment_finite_geometry": attachment_finite,
                "landmarks": {name: bone_head_world(armature, name) for name in LANDMARK_BONES},
            }
        )

    heights = [sample["dimensions"][2] for sample in samples]
    overall_min = Vector(tuple(min(sample["bounds_min"][axis] for sample in samples) for axis in range(3)))
    overall_max = Vector(tuple(max(sample["bounds_max"][axis] for sample in samples) for axis in range(3)))
    overall_dimensions = overall_max - overall_min
    nominal_height = sum(heights) / len(heights)
    center = (overall_min + overall_max) / 2.0
    hip_positions = [Vector(sample["landmarks"]["CC_Base_Hip"]) for sample in samples]
    head_positions = [Vector(sample["landmarks"]["CC_Base_Head"]) for sample in samples]
    hip_xy_drift = max((Vector((hip.x, hip.y)) - Vector((hip_positions[0].x, hip_positions[0].y))).length for hip in hip_positions)
    head_hip_distances = [(head - hip).length for head, hip in zip(head_positions, hip_positions)]
    head_hip_variation = max(head_hip_distances) - min(head_hip_distances)

    gates = {
        "active_action": action is not None,
        "all_landmark_bones_present": all(name in armature.pose.bones for name in LANDMARK_BONES),
        "finite_deformed_geometry": all(sample["finite_geometry"] for sample in samples),
        "finite_rigged_attachments": all(
            all(sample["attachment_finite_geometry"].values()) for sample in samples
        ),
        "no_severe_ground_penetration": min(sample["bounds_min"][2] for sample in samples) >= -nominal_height * 0.03,
        "bounded_height_change": max(heights) - min(heights) <= nominal_height * 0.15,
        "in_place_root": hip_xy_drift <= nominal_height * 0.05,
        "stable_head_to_hip_distance": head_hip_variation <= nominal_height * 0.12,
    }

    camera = configure_scene(scene, args.resolution, nominal_height, center)
    directions = {
        "front": Vector((0.0, -1.0, 0.0)),
        "right": Vector((1.0, 0.0, 0.0)),
        "back": Vector((0.0, 1.0, 0.0)),
        "left": Vector((-1.0, 0.0, 0.0)),
    }
    render_paths: dict[str, list[str]] = {}
    for view, direction in directions.items():
        view_dir = args.output_dir / "frames" / view
        view_dir.mkdir(parents=True, exist_ok=True)
        camera.location = center + direction * nominal_height * 3.2
        camera.location.z = center.z
        look_at(camera, center)
        render_paths[view] = []
        for frame in frames:
            scene.frame_set(frame)
            path = view_dir / f"frame_{frame:03d}.png"
            scene.render.filepath = str(path.resolve())
            bpy.ops.render.render(write_still=True)
            render_paths[view].append(str(path.resolve()))

    report = {
        "schema": "assetsstudio_actor_v2_action_review_v1",
        "status": "pass" if all(gates.values()) else "review",
        "input": str(args.input.resolve()),
        "action": action.name,
        "frame_range": [start, end],
        "sample_frames": frames,
        "actor_object": actor.name,
        "rigged_attachment_objects": [obj.name for obj in attachment_meshes],
        "armature_object": armature.name,
        "overall_bounds_min": list(overall_min),
        "overall_bounds_max": list(overall_max),
        "overall_dimensions": list(overall_dimensions),
        "nominal_height": nominal_height,
        "minimum_ground_z": min(sample["bounds_min"][2] for sample in samples),
        "height_range": [min(heights), max(heights)],
        "hip_xy_drift": hip_xy_drift,
        "head_hip_distance_range": [min(head_hip_distances), max(head_hip_distances)],
        "gates": gates,
        "samples": samples,
        "renders": render_paths,
    }
    report_path = args.output_dir / "action_review.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"ACTOR_V2_ACTION_REVIEW_{report['status'].upper()} action={action.name} "
        f"frames={start}-{end} samples={len(frames)} report={report_path.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
