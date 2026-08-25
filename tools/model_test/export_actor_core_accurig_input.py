"""Export and round-trip validate a clean Actor Core FBX for AccuRIG."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def load_source(path: Path) -> None:
    if path.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
        return
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(path.resolve()))


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    return (
        Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))),
        Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))),
    )


def payload_bounds(minimum: Vector, maximum: Vector) -> dict[str, list[float]]:
    return {
        "min": list(minimum),
        "max": list(maximum),
        "dimensions": list(maximum - minimum),
        "center": list((minimum + maximum) / 2.0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rig-calibration-report", type=Path)
    parser.add_argument("--asset-id", default="actor_core_0ef398ca_v1")
    parser.add_argument("--object-name", default="ChibiBaseMesh_AccuRIG_InputMesh")
    parser.add_argument("--mesh-data-name")
    parser.add_argument("--manifest-schema", default="assetsstudio_actor_core_accurig_input_v1")
    parser.add_argument("--finger-count", type=int, default=0)
    parser.add_argument(
        "--finger-policy-reason",
        default="The Actor has rounded mitten hands with no modeled finger separation.",
    )
    parser.add_argument(
        "--face-rig-policy",
        default="not supplied by AccuRIG; keep EyeAssembly and blink workflow separate",
    )
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw_args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)

    load_source(args.input)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(meshes) != 1:
        raise RuntimeError(f"AccuRIG input requires one Actor mesh; found {len(meshes)}")
    if armatures:
        raise RuntimeError("AccuRIG input must be unrigged")

    actor = meshes[0]
    source_minimum, source_maximum = world_bounds(meshes)
    source_center = (source_minimum + source_maximum) / 2.0
    canonical_offset = Vector((-source_center.x, -source_center.y, -source_minimum.z))
    actor.data.transform(Matrix.Translation(canonical_offset) @ actor.matrix_world)
    actor.matrix_world = Matrix.Identity(4)
    actor.name = args.object_name
    actor.data.name = args.mesh_data_name or f"{args.asset_id}_RigMeshData"
    actor.data.validate(clean_customdata=False)
    actor.data.update()
    bpy.context.view_layer.update()

    canonical_minimum, canonical_maximum = world_bounds([actor])
    height = canonical_maximum.z - canonical_minimum.z
    if abs(canonical_minimum.z) > height * 0.001:
        raise RuntimeError("Canonical Actor is not grounded")
    if abs((canonical_minimum.x + canonical_maximum.x) / 2.0) > height * 0.001:
        raise RuntimeError("Canonical Actor is not centered on AccuRIG's YZ plane")

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0
    bpy.ops.object.select_all(action="DESELECT")
    actor.select_set(True)
    bpy.context.view_layer.objects.active = actor
    expected_vertices = len(actor.data.vertices)
    expected_faces = len(actor.data.polygons)
    bpy.ops.export_scene.fbx(
        filepath=str(args.output.resolve()),
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z",
        axis_up="Y",
        bake_space_transform=False,
        use_mesh_modifiers=True,
        mesh_smooth_type="OFF",
        use_triangles=False,
        add_leaf_bones=False,
        path_mode="AUTO",
        embed_textures=False,
    )

    # Validate the interchange file rather than trusting only the export call.
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(args.output.resolve()))
    imported_meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    imported_armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(imported_meshes) != 1:
        raise RuntimeError(f"Round-trip FBX contains {len(imported_meshes)} meshes")
    imported = imported_meshes[0]
    imported_minimum, imported_maximum = world_bounds(imported_meshes)
    imported_height = imported_maximum.z - imported_minimum.z
    imported_width = imported_maximum.x - imported_minimum.x
    imported_x_center = (imported_minimum.x + imported_maximum.x) / 2.0

    gates = {
        "one_mesh": len(imported_meshes) == 1,
        "no_armature": not imported_armatures,
        "object_name_preserved": imported.name == args.object_name,
        "vertex_count_preserved": len(imported.data.vertices) == expected_vertices,
        "face_count_preserved": len(imported.data.polygons) == expected_faces,
        "grounded_z": abs(imported_minimum.z) <= imported_height * 0.001,
        "centered_on_yz_plane": abs(imported_x_center) <= imported_height * 0.001,
        "z_is_long_axis": imported_height > imported_width * 1.5,
        "unit_scale": all(abs(value - 1.0) < 1e-5 for value in imported.scale),
    }

    calibration = None
    if args.rig_calibration_report:
        calibration = json.loads(args.rig_calibration_report.read_text(encoding="utf-8"))

    manifest = {
        "schema": args.manifest_schema,
        "asset_id": args.asset_id,
        "status": "pass" if all(gates.values()) else "fail",
        "input": str(args.input.resolve()),
        "fbx": str(args.output.resolve()),
        "object_name": args.object_name,
        "pose": "relaxed_A",
        "coordinate_contract_blender": {
            "up": "+Z",
            "front": "-Y",
            "actor_left": "+X",
            "center_plane": "YZ / X=0",
            "ground_z": 0.0,
            "unit": "meter",
        },
        "source_bounds": payload_bounds(source_minimum, source_maximum),
        "canonical_bounds": payload_bounds(canonical_minimum, canonical_maximum),
        "round_trip_bounds": payload_bounds(imported_minimum, imported_maximum),
        "mesh": {
            "vertices": len(imported.data.vertices),
            "faces": len(imported.data.polygons),
            "mesh_objects": len(imported_meshes),
            "armatures": len(imported_armatures),
        },
        "gates": gates,
        "accurig_setup": {
            "body_type": "biped",
            "finger_count_per_hand": args.finger_count,
            "force_symmetry": False,
            "finger_policy_reason": args.finger_policy_reason,
            "manual_review_required": [
                "center line through pelvis",
                "head and neck guides",
                "shoulders, elbows and wrists",
                "hips, knees and ankles",
                "toe direction toward character front",
            ],
            "face_rig": args.face_rig_policy,
        },
        "provisional_landmarks": calibration.get("bones") if calibration else None,
        "ear_roots": calibration.get("ear_roots") if calibration else None,
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if manifest["status"] != "pass":
        raise RuntimeError(f"AccuRIG FBX round-trip failed: {gates}")
    print(
        f"ACTOR_V2_ACCURIG_INPUT_PASS output={args.output.resolve()} "
        f"vertices={len(imported.data.vertices)} faces={len(imported.data.polygons)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
