"""Measure an unbound T-Pose body and emit portable height-normalized slots.

Run inside Blender. The resulting profile deliberately has no active bone
dependency; future bone names are mapping hints consumed only after rig intake.
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
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--head-report", type=Path, required=True)
    parser.add_argument("--style-profile-id", required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--generation-reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def rounded(values) -> list[float]:
    return [round(float(value), 6) for value in values]


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    source = args.input.resolve()
    head_report_path = args.head_report.resolve()
    generation_reference = args.generation_reference.resolve()
    output = args.output.resolve()
    for path in (source, head_report_path, generation_reference):
        if not path.is_file() or root not in path.parents:
            raise FileNotFoundError(path)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    vertices: list[Vector] = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        vertices.extend(obj.matrix_world @ vertex.co for vertex in obj.data.vertices)
    if not vertices:
        raise RuntimeError("input contains no mesh vertices")

    minimum = Vector((min(v.x for v in vertices), min(v.y for v in vertices), min(v.z for v in vertices)))
    maximum = Vector((max(v.x for v in vertices), max(v.y for v in vertices), max(v.z for v in vertices)))
    height = maximum.z - minimum.z
    center_x = (minimum.x + maximum.x) * 0.5
    center_y = (minimum.y + maximum.y) * 0.5
    if height <= 0:
        raise RuntimeError("actor height is zero")

    def to_h(point: Vector) -> list[float]:
        return rounded(((point.x - center_x) / height, (point.y - center_y) / height, (point.z - minimum.z) / height))

    def bounds_h(points: list[Vector]) -> dict[str, list[float]]:
        return {
            "min": to_h(Vector((min(v.x for v in points), min(v.y for v in points), min(v.z for v in points)))),
            "max": to_h(Vector((max(v.x for v in points), max(v.y for v in points), max(v.z for v in points)))),
        }

    def band(z_h: float, half_band_h: float, central_x_h: float | None = None) -> list[Vector]:
        low = minimum.z + (z_h - half_band_h) * height
        high = minimum.z + (z_h + half_band_h) * height
        points = [v for v in vertices if low <= v.z <= high]
        if central_x_h is not None:
            points = [v for v in points if abs(v.x - center_x) <= central_x_h * height]
        if not points:
            raise RuntimeError(f"no vertices in band z={z_h}")
        return points

    head_report = json.loads(head_report_path.read_text(encoding="utf-8"))
    head_fraction = float(head_report["metrics"]["head_height_over_full_height"])
    head_floor = maximum.z - head_fraction * height
    head_points = [v for v in vertices if v.z >= head_floor]
    head_bounds = bounds_h(head_points)
    waist_points = band(0.39, 0.025, 0.2)
    chest_points = band(0.54, 0.025, 0.22)
    shoulder_points = band(0.5965, 0.018, 0.22)
    waist_bounds = bounds_h(waist_points)
    chest_bounds = bounds_h(chest_points)
    shoulder_bounds = bounds_h(shoulder_points)

    left_tip = max(vertices, key=lambda value: value.x)
    right_tip = min(vertices, key=lambda value: value.x)
    left_wrist_x = left_tip.x - 0.0486 * height
    right_wrist_x = right_tip.x + 0.0471 * height
    # The reach audit's ~0.287H value is the projected arm-down fingertip
    # landmark, not the physical T-Pose wrist height. Rest anchors stay on the
    # actual horizontal hand chain.
    wrist_z = (left_tip.z + right_tip.z) * 0.5

    foot_points = [v for v in vertices if v.z <= minimum.z + 0.17 * height]
    left_foot = [v for v in foot_points if v.x >= center_x]
    right_foot = [v for v in foot_points if v.x < center_x]

    def average(points: list[Vector]) -> Vector:
        return sum(points, Vector()) / len(points)

    left_foot_center = average(left_foot)
    right_foot_center = average(right_foot)
    waist_center = Vector((center_x, center_y, minimum.z + 0.39 * height))
    chest_center = Vector((center_x, center_y, minimum.z + 0.54 * height))
    head_center = Vector((
        center_x,
        center_y,
        minimum.z + ((head_bounds["min"][2] + head_bounds["max"][2]) * 0.5) * height,
    ))

    evidence = [
        {"path": relative(root, source), "kind": "measurement", "tracked": True, "sha256": sha256(source)},
        {"path": relative(root, head_report_path), "kind": "fit_report", "tracked": True, "sha256": sha256(head_report_path)},
    ]

    def anchor(identifier: str, point: Vector, future_bone: str, normal=None) -> dict:
        result = {"id": identifier, "position_h": to_h(point), "future_parent_bone": future_bone}
        if normal is not None:
            result["normal"] = list(normal)
        return result

    def envelope(low, high, clearance=0.006, kind="aabb") -> dict:
        return {
            "frame": "actor_normalized_rest",
            "kind": kind,
            "bounds_h": {"min": rounded(low), "max": rounded(high)},
            "clearance_h": clearance,
        }

    head_low, head_high = head_bounds["min"], head_bounds["max"]
    waist_low, waist_high = waist_bounds["min"], waist_bounds["max"]
    chest_low, chest_high = chest_bounds["min"], chest_bounds["max"]
    shoulder_low, shoulder_high = shoulder_bounds["min"], shoulder_bounds["max"]
    waist_fit = envelope(
        [waist_low[0] - 0.035, waist_low[1] - 0.055, 0.33],
        [waist_high[0] + 0.035, waist_high[1] + 0.08, 0.46],
        0.008,
        "surface",
    )
    head_fit = envelope(
        [head_low[0] - 0.01, head_low[1] - 0.01, head_low[2] - 0.01],
        [head_high[0] + 0.01, head_high[1] + 0.01, head_high[2] + 0.02],
        0.008,
        "surface",
    )
    torso_fit = envelope(
        [min(waist_low[0], chest_low[0]) - 0.02, min(waist_low[1], chest_low[1]) - 0.025, 0.33],
        [max(chest_high[0], shoulder_high[0]) + 0.02, max(chest_high[1], shoulder_high[1]) + 0.035, 0.62],
        0.008,
        "surface",
    )

    slots = [
        {
            "slot_id": "EarPair", "label": "Replaceable ear pair", "category": "body_feature", "side": "bilateral", "status": "static_tpose_only",
            "attachment": {"mode": "rest_surface_pair", "rig_dependency": "none_until_rig_intake", "anchors": [
                anchor("EarRoot_L", Vector((center_x + (head_high[0] - 0.01) * height, center_y, minimum.z + 0.79 * height)), "Head", (1.0, 0.0, 0.0)),
                anchor("EarRoot_R", Vector((center_x + (head_low[0] + 0.01) * height, center_y, minimum.z + 0.79 * height)), "Head", (-1.0, 0.0, 0.0)),
            ]},
            "fit_envelope": head_fit,
            "generation_policy": {"preferred_mode": "on_actor_then_isolate", "allowed_asset_kinds": ["human_ear_pair", "elf_ear_pair", "fantasy_ear_pair"], "include_actor_context": True},
            "validation": {"required_views": 4, "required_frames": 1, "collision_policy": "project roots to the T-Pose head surface; animation clearance is deferred", "human_review_required": True},
            "evidence": evidence,
        },
        {
            "slot_id": "head_hair", "label": "Independent hair shell", "category": "hair", "side": "center", "status": "static_tpose_only",
            "attachment": {"mode": "rest_envelope", "rig_dependency": "none_until_rig_intake", "anchors": [anchor("HeadSurfaceCenter", head_center, "Head")]},
            "fit_envelope": head_fit,
            "generation_policy": {"preferred_mode": "on_actor_then_isolate", "allowed_asset_kinds": ["hair_cap", "bangs", "side_locks", "back_hair"], "include_actor_context": True},
            "validation": {"required_views": 4, "required_frames": 1, "collision_policy": "closed crown and static head clearance; neck deformation is deferred", "human_review_required": True},
            "evidence": evidence,
        },
        {
            "slot_id": "headwear", "label": "Headwear", "category": "headwear", "side": "center", "status": "static_tpose_only",
            "attachment": {"mode": "rest_anchor", "rig_dependency": "none_until_rig_intake", "anchors": [anchor("HeadTop", Vector((center_x, center_y, maximum.z)), "Head", (0.0, 0.0, 1.0))]},
            "fit_envelope": head_fit,
            "generation_policy": {"preferred_mode": "on_actor_then_isolate", "allowed_asset_kinds": ["hat", "helmet", "hood"], "include_actor_context": True},
            "validation": {"required_views": 4, "required_frames": 1, "collision_policy": "validate static crown, hair and ear envelopes", "human_review_required": True},
            "evidence": evidence,
        },
        {
            "slot_id": "torso_outer", "label": "Torso outer layer", "category": "wearable", "side": "center", "status": "static_tpose_only",
            "attachment": {"mode": "rest_envelope", "rig_dependency": "none_until_rig_intake", "anchors": [anchor("UpperTorsoCenter", chest_center, "Spine2")]},
            "fit_envelope": torso_fit,
            "generation_policy": {"preferred_mode": "on_actor_then_isolate", "allowed_asset_kinds": ["jacket", "shirt", "robe", "scarf"], "include_actor_context": True},
            "validation": {"required_views": 4, "required_frames": 1, "collision_policy": "preserve static neck, axilla and arm clearance", "human_review_required": True},
            "evidence": evidence,
        },
        {
            "slot_id": "waist_accessory", "label": "Belt and waist pouch", "category": "prop", "side": "center", "status": "source_contract",
            "attachment": {"mode": "rest_envelope", "rig_dependency": "none_until_rig_intake", "anchors": [anchor("WaistCenter", waist_center, "Waist")]},
            "fit_envelope": waist_fit,
            "generation_reference": {"path": relative(root, generation_reference), "sha256": sha256(generation_reference), "role": "isolated_slot_authority"},
            "generation_policy": {"preferred_mode": "standalone", "allowed_asset_kinds": ["belt", "waist_pouch", "buckle", "small_holster"], "include_actor_context": True},
            "validation": {"required_views": 4, "required_frames": 1, "collision_policy": "static T-Pose body clearance only; hand, thigh and locomotion gates are deferred", "human_review_required": True},
            "evidence": evidence + [{"path": relative(root, generation_reference), "kind": "review", "tracked": True, "sha256": sha256(generation_reference)}],
        },
        {
            "slot_id": "legs_outer", "label": "Leg outer layer", "category": "wearable", "side": "bilateral", "status": "static_tpose_only",
            "attachment": {"mode": "rest_envelope", "rig_dependency": "none_until_rig_intake", "anchors": [anchor("PelvisCenter", Vector((center_x, center_y, minimum.z + 0.335 * height)), "Pelvis")]},
            "fit_envelope": envelope([-0.18, -0.13, 0.08], [0.18, 0.15, 0.39], 0.008, "surface"),
            "generation_policy": {"preferred_mode": "on_actor_then_isolate", "allowed_asset_kinds": ["shorts", "pants", "skirt", "leg_armor"], "include_actor_context": True},
            "validation": {"required_views": 4, "required_frames": 1, "collision_policy": "preserve static pelvis and independent leg gaps", "human_review_required": True},
            "evidence": evidence,
        },
        {
            "slot_id": "feet_outer", "label": "Footwear", "category": "wearable", "side": "bilateral", "status": "static_tpose_only",
            "attachment": {"mode": "rest_anchor_pair", "rig_dependency": "none_until_rig_intake", "anchors": [anchor("FootRoot_L", left_foot_center, "LeftFoot"), anchor("FootRoot_R", right_foot_center, "RightFoot")]},
            "fit_envelope": envelope([-0.18, -0.13, 0.0], [0.18, 0.16, 0.18], 0.006, "surface"),
            "generation_policy": {"preferred_mode": "on_actor_then_isolate", "allowed_asset_kinds": ["boots", "shoes", "greaves"], "include_actor_context": True},
            "validation": {"required_views": 4, "required_frames": 1, "collision_policy": "preserve ground contact and static toe direction", "human_review_required": True},
            "evidence": evidence,
        },
        {
            "slot_id": "wrist_accessory", "label": "Wrist accessory", "category": "prop", "side": "bilateral", "status": "static_tpose_only",
            "attachment": {"mode": "rest_anchor_pair", "rig_dependency": "none_until_rig_intake", "anchors": [
                anchor("Wrist_L", Vector((left_wrist_x, center_y, wrist_z)), "LeftForearm"),
                anchor("Wrist_R", Vector((right_wrist_x, center_y, wrist_z)), "RightForearm"),
            ]},
            "fit_envelope": None,
            "generation_policy": {"preferred_mode": "standalone", "allowed_asset_kinds": ["bracer", "bracelet", "wrist_guard"], "include_actor_context": True},
            "validation": {"required_views": 4, "required_frames": 1, "collision_policy": "validate static wrist and mitten clearance", "human_review_required": True},
            "evidence": evidence,
        },
        {
            "slot_id": "hand_prop_l", "label": "Left-hand prop", "category": "prop", "side": "left", "status": "static_tpose_only",
            "attachment": {"mode": "rest_anchor", "rig_dependency": "none_until_rig_intake", "anchors": [anchor("Grip_L", left_tip, "LeftHand")]},
            "fit_envelope": None,
            "generation_policy": {"preferred_mode": "standalone", "allowed_asset_kinds": ["weapon", "tool", "lantern", "shield"], "include_actor_context": True},
            "validation": {"required_views": 4, "required_frames": 1, "collision_policy": "static grip alignment only; hand pose is deferred", "human_review_required": True},
            "evidence": evidence,
        },
        {
            "slot_id": "hand_prop_r", "label": "Right-hand prop", "category": "prop", "side": "right", "status": "static_tpose_only",
            "attachment": {"mode": "rest_anchor", "rig_dependency": "none_until_rig_intake", "anchors": [anchor("Grip_R", right_tip, "RightHand")]},
            "fit_envelope": None,
            "generation_policy": {"preferred_mode": "standalone", "allowed_asset_kinds": ["weapon", "tool", "lantern", "shield"], "include_actor_context": True},
            "validation": {"required_views": 4, "required_frames": 1, "collision_policy": "static grip alignment only; hand pose is deferred", "human_review_required": True},
            "evidence": evidence,
        },
        {
            "slot_id": "back_accessory", "label": "Back accessory", "category": "prop", "side": "center", "status": "static_tpose_only",
            "attachment": {"mode": "rest_anchor", "rig_dependency": "none_until_rig_intake", "anchors": [anchor("BackCenter", Vector((center_x, center_y + chest_high[1] * height, chest_center.z)), "Spine2", (0.0, 1.0, 0.0))]},
            "fit_envelope": envelope([chest_low[0] - 0.04, chest_high[1], 0.35], [chest_high[0] + 0.04, chest_high[1] + 0.16, 0.67], 0.01),
            "generation_policy": {"preferred_mode": "standalone", "allowed_asset_kinds": ["backpack", "cape_mount", "quiver", "back_weapon"], "include_actor_context": True},
            "validation": {"required_views": 4, "required_frames": 1, "collision_policy": "static back clearance only; spine and shoulder motion are deferred", "human_review_required": True},
            "evidence": evidence,
        },
    ]

    profile = {
        "schema": "assetsstudio_actor_slot_profile_v2",
        "id": args.profile_id,
        "label": args.label,
        "revision": 1,
        "status": "experimental_proxy",
        "actor_asset_id": args.asset_id,
        "style_profile_id": args.style_profile_id,
        "actor_model": {"path": relative(root, source), "sha256": sha256(source), "role": "tpose_fitting_proxy"},
        "coordinate_contract": {"unit": "meter", "up": "+Z", "front": "-Y", "actor_left": "+X", "ground_z": round(minimum.z, 6), "normalization": "actor_height", "rig_state": "unbound_tpose"},
        "measurements": {
            "actor_bounds_m": {"min": rounded(minimum), "max": rounded(maximum)},
            "head_bounds_m": {
                "min": rounded((center_x + head_low[0] * height, center_y + head_low[1] * height, minimum.z + head_low[2] * height)),
                "max": rounded((center_x + head_high[0] * height, center_y + head_high[1] * height, minimum.z + head_high[2] * height)),
            },
            "actor_height_m": round(height, 6),
            "total_heads": round(1.0 / head_fraction, 6),
            "source": relative(root, head_report_path),
        },
        "slots": slots,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "ASSETSSTUDIO_TPOSE_SLOT_PROFILE_PASS "
        f"actor={args.asset_id} height={height:.6f} heads={1.0 / head_fraction:.4f} "
        f"slots={len(slots)} output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
