"""Validate and prepare one user-exported AccuRIG FBX for one Actor Core.

This starts after the manual AccuRIG operation.  It never places landmarks or
binds a mesh automatically.  The script audits the uploaded FBX against the
selected Actor's handoff manifest, preserves a cleaned raw-weight Blend, makes
a four-influence runtime copy, exports a rigged GLB, and renders four rest-pose
skeleton previews.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


REQUIRED_BONES = (
    "CC_Base_Hip",
    "CC_Base_Pelvis",
    "CC_Base_Waist",
    "CC_Base_Spine01",
    "CC_Base_Spine02",
    "CC_Base_NeckTwist01",
    "CC_Base_Head",
    "CC_Base_L_Clavicle",
    "CC_Base_L_Upperarm",
    "CC_Base_L_Forearm",
    "CC_Base_L_Hand",
    "CC_Base_R_Clavicle",
    "CC_Base_R_Upperarm",
    "CC_Base_R_Forearm",
    "CC_Base_R_Hand",
    "CC_Base_L_Thigh",
    "CC_Base_L_Calf",
    "CC_Base_L_Foot",
    "CC_Base_L_ToeBase",
    "CC_Base_R_Thigh",
    "CC_Base_R_Calf",
    "CC_Base_R_Foot",
    "CC_Base_R_ToeBase",
)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def world_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector(tuple(min(point[index] for point in points) for index in range(3))),
        Vector(tuple(max(point[index] for point in points) for index in range(3))),
    )


def weight_audit(actor: bpy.types.Object) -> dict[str, object]:
    unweighted: list[int] = []
    non_normalized: list[int] = []
    maximum_influences = 0
    vertices_over_four = 0
    minimum_sum = math.inf
    maximum_sum = 0.0
    for vertex in actor.data.vertices:
        weights = [item.weight for item in vertex.groups if item.weight > 1e-8]
        if not weights:
            unweighted.append(vertex.index)
            continue
        total = sum(weights)
        minimum_sum = min(minimum_sum, total)
        maximum_sum = max(maximum_sum, total)
        if abs(total - 1.0) > 0.01:
            non_normalized.append(vertex.index)
        maximum_influences = max(maximum_influences, len(weights))
        if len(weights) > 4:
            vertices_over_four += 1
    return {
        "unweighted_vertices": len(unweighted),
        "unweighted_sample": unweighted[:20],
        "non_normalized_vertices": len(non_normalized),
        "non_normalized_sample": non_normalized[:20],
        "minimum_weight_sum": 0.0 if minimum_sum == math.inf else minimum_sum,
        "maximum_weight_sum": maximum_sum,
        "max_influences_per_vertex": maximum_influences,
        "vertices_over_four_influences": vertices_over_four,
    }


def optimize_weights(actor: bpy.types.Object, maximum: int = 4) -> dict[str, int]:
    changed_vertices = 0
    removed_assignments = 0
    before = weight_audit(actor)
    for vertex in actor.data.vertices:
        assignments = sorted(
            ((item.group, item.weight) for item in vertex.groups if item.weight > 1e-8),
            key=lambda item: item[1],
            reverse=True,
        )
        if len(assignments) <= maximum:
            continue
        changed_vertices += 1
        retained = assignments[:maximum]
        total = sum(weight for _, weight in retained)
        for group_index, _weight in assignments[maximum:]:
            actor.vertex_groups[group_index].remove([vertex.index])
            removed_assignments += 1
        for group_index, weight in retained:
            actor.vertex_groups[group_index].add([vertex.index], weight / total, "REPLACE")
    after = weight_audit(actor)
    if after["max_influences_per_vertex"] > maximum:
        raise RuntimeError("Four-influence optimization did not converge")
    return {
        "before_max_influences": int(before["max_influences_per_vertex"]),
        "before_vertices_over_four": int(before["vertices_over_four_influences"]),
        "after_max_influences": int(after["max_influences_per_vertex"]),
        "after_vertices_over_four": int(after["vertices_over_four_influences"]),
        "changed_vertices": changed_vertices,
        "removed_assignments": removed_assignments,
    }


def relative_dimension_drift(expected: list[float], actual: Vector) -> float:
    return max(
        abs(actual[index] - expected[index]) / max(abs(expected[index]), 1e-8)
        for index in range(3)
    )


def material(name: str, color: tuple[float, float, float, float], emission: bool = False):
    value = bpy.data.materials.new(name)
    value.diffuse_color = color
    value.use_nodes = True
    principled = value.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.76
        principled.inputs["Alpha"].default_value = color[3]
        if emission:
            principled.inputs["Emission Color"].default_value = color
            principled.inputs["Emission Strength"].default_value = 2.0
    if color[3] < 1.0:
        value.surface_render_method = "DITHERED"
    return value


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def guide_segment(name: str, head: Vector, tail: Vector, radius: float, guide_material) -> bpy.types.Object:
    direction = tail - head
    length = max(direction.length, radius * 2.0)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius, depth=length, location=(head + tail) / 2.0)
    obj = bpy.context.object
    obj.name = f"RigPreview_{name}"
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    obj.data.materials.append(guide_material)
    return obj


def guide_joint(name: str, point: Vector, radius: float, guide_material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=radius, location=point)
    obj = bpy.context.object
    obj.name = f"RigPreviewJoint_{name}"
    obj.data.materials.append(guide_material)
    return obj


def bone_group(name: str) -> str:
    if any(token in name for token in ("Clavicle", "Upperarm", "Forearm", "Hand")):
        return "arm"
    if any(token in name for token in ("Thigh", "Calf", "Foot", "ToeBase")):
        return "leg"
    if any(token in name for token in ("Neck", "Head")):
        return "head"
    return "torso"


def render_rig_previews(
    actor: bpy.types.Object,
    armature: bpy.types.Object,
    preview_dir: Path,
    resolution: int,
) -> dict[str, str]:
    minimum, maximum = world_bounds(actor)
    center = (minimum + maximum) / 2.0
    height = maximum.z - minimum.z
    actor.data.materials.clear()
    actor.data.materials.append(material("ActorCore_RiggedPreview", (0.26, 0.38, 0.58, 0.28)))
    guide_materials = {
        "torso": material("RigPreview_Torso", (1.0, 0.68, 0.08, 1.0), True),
        "head": material("RigPreview_Head", (0.30, 1.0, 0.38, 1.0), True),
        "arm": material("RigPreview_Arm", (0.05, 0.86, 1.0, 1.0), True),
        "leg": material("RigPreview_Leg", (1.0, 0.18, 0.62, 1.0), True),
    }
    guides: list[bpy.types.Object] = []
    for name in REQUIRED_BONES:
        bone = armature.data.bones.get(name)
        if bone is None:
            continue
        head = armature.matrix_world @ bone.head_local
        tail = armature.matrix_world @ bone.tail_local
        group = bone_group(name)
        guides.append(guide_segment(name, head, tail, height * 0.0045, guide_materials[group]))
        guides.append(guide_joint(name, head, height * 0.008, guide_materials[group]))

    world = bpy.context.scene.world or bpy.data.worlds.new("ActorCore_RigPreviewWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background:
        background.inputs["Color"].default_value = (0.025, 0.035, 0.055, 1.0)
        background.inputs["Strength"].default_value = 0.38

    light_data = bpy.data.lights.new("RigPreviewKey", type="AREA")
    light_data.energy = 420.0
    light_data.size = height * 1.2
    light = bpy.data.objects.new("RigPreviewKey", light_data)
    bpy.context.collection.objects.link(light)
    light.location = (height, -height, height * 1.5)
    look_at(light, center)

    camera_data = bpy.data.cameras.new("RigPreviewCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = height / 0.78
    camera = bpy.data.objects.new("RigPreviewCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
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
    output = {}
    for name, direction in directions.items():
        camera.location = center + direction * height * 3.0
        camera.location.z = center.z
        look_at(camera, center)
        destination = preview_dir / f"{name}.png"
        scene.render.filepath = str(destination.resolve())
        bpy.ops.render.render(write_still=True)
        output[name] = str(destination.resolve())

    for obj in [*guides, camera, light]:
        bpy.data.objects.remove(obj, do_unlink=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--expected-manifest", type=Path)
    parser.add_argument("--resolution", type=int, default=768)
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw_args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    preview_dir = args.output_dir / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)

    expected = None
    if args.expected_manifest:
        expected = json.loads(args.expected_manifest.read_text(encoding="utf-8"))
        if expected.get("asset_id") != args.asset_id:
            raise ValueError("AccuRIG handoff manifest does not belong to the selected Actor")

    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(args.input.resolve()), use_anim=False)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    rigged_meshes = [
        obj for obj in meshes if any(mod.type == "ARMATURE" and mod.object for mod in obj.modifiers)
    ]
    if len(armatures) != 1 or len(rigged_meshes) != 1:
        raise RuntimeError(
            "Expected exactly one AccuRIG armature and one rigged Actor mesh; "
            f"armatures={len(armatures)} rigged_meshes={len(rigged_meshes)} meshes={len(meshes)}"
        )

    armature = armatures[0]
    actor = rigged_meshes[0]
    removed_extras = []
    for obj in list(bpy.context.scene.objects):
        if obj not in {armature, actor}:
            removed_extras.append({"name": obj.name, "type": obj.type})
            bpy.data.objects.remove(obj, do_unlink=True)

    armature.name = "Armature"
    actor.name = "ChibiBaseMesh_AccuRIG_InputMesh"
    actor.data.name = f"{args.asset_id}_RiggedMeshData"
    armature.animation_data_clear()
    armature.data.pose_position = "REST"
    for bone in armature.pose.bones:
        bone.rotation_mode = "QUATERNION"

    minimum, maximum = world_bounds(actor)
    dimensions = maximum - minimum
    height = dimensions.z
    x_center = (minimum.x + maximum.x) / 2.0
    missing_bones = [name for name in REQUIRED_BONES if name not in armature.data.bones]
    armature_modifiers = [mod for mod in actor.modifiers if mod.type == "ARMATURE"]
    weights = weight_audit(actor)
    expected_vertices = expected.get("mesh", {}).get("vertices") if expected else None
    expected_faces = expected.get("mesh", {}).get("faces") if expected else None
    expected_dimensions = (
        expected.get("canonical_bounds", {}).get("dimensions") if expected else None
    )
    dimension_drift = (
        relative_dimension_drift(expected_dimensions, dimensions)
        if expected_dimensions and len(expected_dimensions) == 3
        else None
    )
    gates = {
        "one_mesh": len(meshes) == 1,
        "one_armature": len(armatures) == 1,
        "required_bones_present": not missing_bones,
        "armature_modifier_bound": len(armature_modifiers) == 1 and armature_modifiers[0].object == armature,
        "no_unweighted_vertices": weights["unweighted_vertices"] == 0,
        "weights_normalized_1pct": weights["non_normalized_vertices"] == 0,
        "max_eight_influences": weights["max_influences_per_vertex"] <= 8,
        "grounded_z": abs(minimum.z) <= height * 0.005,
        "centered_x": abs(x_center) <= height * 0.005,
        "z_is_long_axis": dimensions.z > dimensions.x * 1.5,
        "vertex_count_matches_handoff": expected_vertices is None or len(actor.data.vertices) == expected_vertices,
        "face_count_matches_handoff": expected_faces is None or len(actor.data.polygons) == expected_faces,
        "dimensions_match_handoff_1pct": dimension_drift is None or dimension_drift <= 0.01,
    }
    report_path = args.output_dir / "validation.json"
    base_report = {
        "schema": "assetsstudio_actor_core_accurig_validation_v1",
        "asset_id": args.asset_id,
        "status": "pass" if all(gates.values()) else "fail",
        "input": str(args.input.resolve()),
        "expected_manifest": str(args.expected_manifest.resolve()) if args.expected_manifest else None,
        "removed_export_extras": removed_extras,
        "mesh": {
            "vertices": len(actor.data.vertices),
            "faces": len(actor.data.polygons),
            "bounds_min": list(minimum),
            "bounds_max": list(maximum),
            "dimensions": list(dimensions),
            "expected_vertices": expected_vertices,
            "expected_faces": expected_faces,
            "expected_dimensions": expected_dimensions,
            "max_relative_dimension_drift": dimension_drift,
        },
        "armature": {
            "bones": len(armature.data.bones),
            "missing_required_bones": missing_bones,
        },
        "weights": weights,
        "gates": gates,
    }
    if not all(gates.values()):
        report_path.write_text(json.dumps(base_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise RuntimeError(f"Uploaded AccuRIG FBX failed Actor one-to-one gates: {gates}")

    raw_blend = args.output_dir / f"{args.asset_id}_accurig_raw.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(raw_blend.resolve()))
    optimization = optimize_weights(actor, 4)
    runtime_blend = args.output_dir / f"{args.asset_id}_runtime_4weights.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(runtime_blend.resolve()))

    runtime_glb = args.output_dir / f"{args.asset_id}_rigged_preview.glb"
    bpy.ops.object.select_all(action="DESELECT")
    actor.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.gltf(
        filepath=str(runtime_glb.resolve()),
        export_format="GLB",
        use_selection=True,
        export_skins=True,
        export_animations=False,
        export_materials="EXPORT",
    )
    previews = render_rig_previews(actor, armature, preview_dir, args.resolution)
    report = {
        **base_report,
        "outputs": {
            "raw_blend": str(raw_blend.resolve()),
            "runtime_blend": str(runtime_blend.resolve()),
            "runtime_glb": str(runtime_glb.resolve()),
            "previews": previews,
        },
        "runtime_weight_optimization": optimization,
        "next_required_gate": "manual rest-pose preview review, then action retarget and deformation QA",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "ACTOR_CORE_ACCURIG_PROCESS_PASS "
        f"asset={args.asset_id} bones={len(armature.data.bones)} "
        f"vertices={len(actor.data.vertices)} output={runtime_glb.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
