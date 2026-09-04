"""Attach a fitted accessory to a generated rig and validate one stress pose."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fit_tpose_accessory_blender import export_glb, render_views


POSE_AXIS_ANGLE = {
    "CC_Base_Waist": ((1.0, 0.0, 0.0), -12.0),
    "CC_Base_L_Upperarm": ((0.0, 1.0, 0.0), 22.0),
    "CC_Base_L_Thigh": ((1.0, 0.0, 0.0), -35.0),
    "CC_Base_L_Calf": ((1.0, 0.0, 0.0), 48.0),
    "CC_Base_R_Thigh": ((1.0, 0.0, 0.0), 12.0),
}


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--accessory", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--fit-report", required=True, type=Path)
    parser.add_argument("--slot-id", default="waist_accessory")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--resolution", type=int, default=768)
    return parser.parse_args(raw)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluated_bvh(objects: list[bpy.types.Object]) -> BVHTree:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    vertices = []
    polygons = []
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        offset = len(vertices)
        vertices.extend(evaluated.matrix_world @ vertex.co for vertex in evaluated.data.vertices)
        polygons.extend(
            tuple(offset + index for index in polygon.vertices)
            for polygon in evaluated.data.polygons
        )
    return BVHTree.FromPolygons(vertices, polygons, all_triangles=False, epsilon=1e-6)


def main() -> int:
    args = parse_args()
    for path in (args.actor, args.accessory, args.profile, args.fit_report):
        if not path.is_file():
            raise FileNotFoundError(path)
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    fit_report = json.loads(args.fit_report.read_text(encoding="utf-8"))
    if profile.get("schema") != "assetsstudio_actor_slot_profile_v1":
        raise ValueError("dynamic generated-actor validation requires ActorSlotProfile v1")
    if fit_report.get("status") != "pass_static_tpose":
        raise RuntimeError("accessory has not passed the static fit gate")
    expected_accessory = Path(fit_report["outputs"]["accessory_glb"]).resolve()
    if expected_accessory != args.accessory.resolve():
        raise RuntimeError("accessory does not match the approved static fit output")
    if fit_report["inputs"]["actor_sha256"].lower() != sha256(args.actor).lower():
        raise RuntimeError("actor does not match the static fit report")
    slot = next((item for item in profile["slots"] if item["slot_id"] == args.slot_id), None)
    if slot is None:
        raise ValueError(f"slot not found: {args.slot_id}")
    parent_bones = slot["attachment"]["parent_bones"]
    if len(parent_bones) != 1:
        raise ValueError("current rigid accessory probe requires exactly one parent bone")
    parent_bone = parent_bones[0]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.actor.resolve()))
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        raise RuntimeError(f"expected one actor armature, received {len(armatures)}")
    armature = armatures[0]
    actor_meshes = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        and (
            obj.parent == armature
            or any(
                modifier.type == "ARMATURE" and modifier.object == armature
                for modifier in obj.modifiers
            )
        )
    ]
    if len(actor_meshes) != 1:
        raise RuntimeError(f"expected one skinned actor mesh, received {len(actor_meshes)}")
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.accessory.resolve()))
    accessory_meshes = [
        obj for obj in bpy.context.scene.objects if obj not in before and obj.type == "MESH"
    ]
    if not accessory_meshes:
        raise RuntimeError("fitted accessory contains no mesh")
    if armature.data.bones.get(parent_bone) is None:
        raise RuntimeError(f"rig is missing slot parent bone: {parent_bone}")

    for accessory in accessory_meshes:
        world = accessory.matrix_world.copy()
        accessory.parent = armature
        accessory.parent_type = "BONE"
        accessory.parent_bone = parent_bone
        accessory.matrix_world = world

    for name, (axis, degrees) in POSE_AXIS_ANGLE.items():
        bone = armature.pose.bones.get(name)
        if bone is None:
            raise RuntimeError(f"required semantic bone missing: {name}")
        axis_local = bone.bone.matrix_local.to_3x3().inverted() @ Vector(axis)
        axis_local.normalize()
        bone.rotation_mode = "QUATERNION"
        bone.rotation_quaternion = Quaternion(axis_local, math.radians(degrees))
    bpy.context.view_layer.update()

    actor_bvh = evaluated_bvh(actor_meshes)
    accessory_bvh = evaluated_bvh(accessory_meshes)
    overlap_pairs = actor_bvh.overlap(accessory_bvh)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    previews = render_views(
        actor_meshes,
        accessory_meshes,
        output_dir / "preview",
        args.resolution,
    )
    output_glb = output_dir / f"{args.asset_id}.glb"
    export_glb([*actor_meshes, armature, *accessory_meshes], output_glb)
    output_blend = output_dir / f"{args.asset_id}_review.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))

    gates = {
        "static_fit_pass": True,
        "parent_bone_present": True,
        "no_stress_pose_surface_intersection": len(overlap_pairs) == 0,
        "four_view_preview_complete": len(previews) == 4 and all(
            Path(path).is_file() for path in previews.values()
        ),
    }
    passed = all(gates.values())
    report = {
        "schema": "assetsstudio_rigged_accessory_deformation_v1",
        "asset_id": args.asset_id,
        "actor_asset_id": profile["actor_asset_id"],
        "slot_id": args.slot_id,
        "status": "pass_dynamic_probe" if passed else "dynamic_review_failed",
        "approved_asset": False,
        "parent_bone": parent_bone,
        "pose_axis_angle_armature_space": {
            name: {"axis": list(axis), "degrees": degrees}
            for name, (axis, degrees) in POSE_AXIS_ANGLE.items()
        },
        "collision": {"surface_triangle_overlap_pairs": len(overlap_pairs)},
        "automatic_gates": gates,
        "deferred_gates": ["mixamo_walk_cycle", "human_four_view_review"],
        "outputs": {
            "combined_glb": str(output_glb),
            "review_blend": str(output_blend),
            "previews": previews,
        },
    }
    report_path = output_dir / "dynamic_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"ASSETSSTUDIO_RIGGED_ACCESSORY_{'PASS' if passed else 'FAIL'} "
        f"overlaps={len(overlap_pairs)} report={report_path}"
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
