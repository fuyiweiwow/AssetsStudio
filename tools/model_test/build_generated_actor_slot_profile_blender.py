"""Measure a generated, rigged Actor Core and emit a bone-aware waist slot.

The first version intentionally emits only the waist slot used by the isolated
accessory experiment. Other slots must be measured from their own semantic
bones before Studio exposes them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--generation-reference", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--actor-asset-id", required=True)
    parser.add_argument("--style-profile-id", required=True)
    parser.add_argument("--label", required=True)
    return parser.parse_args(raw)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rounded(vector) -> list[float]:
    return [round(float(value), 6) for value in vector]


def vector_bounds(points: list[Vector]) -> tuple[Vector, Vector]:
    return (
        Vector(tuple(min(point[index] for point in points) for index in range(3))),
        Vector(tuple(max(point[index] for point in points) for index in range(3))),
    )


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    actor_path = args.actor.resolve()
    authority_path = args.generation_reference.resolve()
    output_path = args.output.resolve()
    for path in (actor_path, authority_path):
        if not path.is_file() or root not in path.parents:
            raise FileNotFoundError(path)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(actor_path))
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        raise RuntimeError(
            f"Expected one actor armature, received {len(armatures)} armatures"
        )
    armature = armatures[0]
    meshes = [
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
    if len(meshes) != 1:
        raise RuntimeError(f"Expected one skinned actor mesh, received {len(meshes)}")
    mesh = meshes[0]
    required_bones = {"CC_Base_Hip", "CC_Base_Pelvis", "CC_Base_Waist", "CC_Base_Head"}
    missing = sorted(required_bones - set(armature.data.bones.keys()))
    if missing:
        raise RuntimeError("Generated rig is missing semantic bones: " + ", ".join(missing))

    points = [mesh.matrix_world @ vertex.co for vertex in mesh.data.vertices]
    minimum, maximum = vector_bounds(points)
    height = maximum.z - minimum.z
    center_x = (minimum.x + maximum.x) * 0.5
    center_y = (minimum.y + maximum.y) * 0.5
    if height <= 0.0:
        raise RuntimeError("Actor height is zero")

    hip_bone = armature.data.bones["CC_Base_Hip"]
    hip_head = armature.matrix_world @ hip_bone.head_local
    hip_tail = armature.matrix_world @ hip_bone.tail_local
    # UniRig's Waist segment starts above this actor's navel. A belt belongs at
    # the upper-pelvis transition, represented by the midpoint of its root Hip
    # segment. This also keeps the prop below the round abdomen.
    waist_z = (hip_head.z + hip_tail.z) * 0.5
    half_band = height * 0.028
    waist_points = [
        point
        for point in points
        if abs(point.z - waist_z) <= half_band and abs(point.x - center_x) <= height * 0.16
    ]
    if len(waist_points) < 50:
        raise RuntimeError(f"Waist measurement band is too sparse: {len(waist_points)} vertices")
    waist_minimum, waist_maximum = vector_bounds(waist_points)

    clearance = height * 0.008
    envelope_minimum = Vector((
        waist_minimum.x - height * 0.050,
        waist_minimum.y - height * 0.040,
        waist_z - height * 0.060,
    ))
    envelope_maximum = Vector((
        waist_maximum.x + height * 0.050,
        waist_maximum.y + height * 0.075,
        waist_z + height * 0.060,
    ))
    head_floor = (armature.matrix_world @ armature.data.bones["CC_Base_Head"].head_local).z
    head_points = [point for point in points if point.z >= head_floor]
    head_minimum, head_maximum = vector_bounds(head_points)
    head_height = head_maximum.z - head_minimum.z

    actor_relative = actor_path.relative_to(root).as_posix()
    authority_relative = authority_path.relative_to(root).as_posix()
    actor_hash = sha256(actor_path)
    authority_hash = sha256(authority_path)
    evidence = [
        {
            "path": actor_relative,
            "kind": "measurement",
            "tracked": False,
            "sha256": actor_hash,
        },
        {
            "path": authority_relative,
            "kind": "review",
            "tracked": True,
            "sha256": authority_hash,
        },
    ]
    profile = {
        "schema": "assetsstudio_actor_slot_profile_v1",
        "id": args.profile_id,
        "label": args.label,
        "revision": 1,
        "status": "measured_provisional",
        "actor_asset_id": args.actor_asset_id,
        "style_profile_id": args.style_profile_id,
        "coordinate_contract": {
            "unit": "meter",
            "up": "+Z",
            "front": "-Y",
            "actor_left": "+X",
            "ground_z": round(float(minimum.z), 6),
        },
        "measurements": {
            "actor_bounds_m": {"min": rounded(minimum), "max": rounded(maximum)},
            "head_bounds_m": {"min": rounded(head_minimum), "max": rounded(head_maximum)},
            "actor_height_m": round(float(height), 6),
            "total_heads": round(float(height / head_height), 6),
            "source": actor_relative,
        },
        "slots": [
            {
                "slot_id": "waist_accessory",
                "label": "Belt and waist pouch",
                "category": "prop",
                "side": "center",
                "status": "measured_provisional",
                "attachment": {
                    "mode": "bone",
                    "parent_bones": ["CC_Base_Pelvis"],
                    "anchors": [
                        {
                            "id": "WaistCenter",
                            "parent_bone": "CC_Base_Pelvis",
                            "position_m": rounded((center_x, center_y, waist_z)),
                        }
                    ],
                },
                "fit_envelope": {
                    "frame": "actor_world_rest",
                    "kind": "surface",
                    "bounds_m": {
                        "min": rounded(envelope_minimum),
                        "max": rounded(envelope_maximum),
                    },
                    "clearance_m": round(float(clearance), 6),
                },
                "generation_reference": {
                    "path": authority_relative,
                    "sha256": authority_hash,
                    "role": "isolated_slot_authority",
                },
                "generation_policy": {
                    "preferred_mode": "standalone",
                    "allowed_asset_kinds": ["belt", "waist_pouch", "buckle", "small_holster"],
                    "include_actor_context": True,
                },
                "validation": {
                    "required_views": 4,
                    "required_frames": 8,
                    "collision_policy": "no persistent hand or thigh penetration during locomotion",
                    "human_review_required": True,
                },
                "evidence": evidence,
            }
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "ASSETSSTUDIO_GENERATED_ACTOR_SLOT_PROFILE_PASS "
        f"actor={args.actor_asset_id} waist_z={waist_z:.6f} "
        f"waist_points={len(waist_points)} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
