"""Build a GarmentCode body YAML from the Actor-centered measurement audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--measurement-report", required=True, type=Path)
    parser.add_argument("--actor-measurements", required=True, type=Path)
    parser.add_argument("--actor-native-body", required=True, type=Path)
    parser.add_argument("--units-audit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--neck-w-override",
        type=float,
        help="Diagnostic-only GarmentCode neck_w override in cm; preserves the accepted body YAML.",
    )
    args = parser.parse_args()

    report = json.loads(args.measurement_report.read_text(encoding="utf-8"))
    actor = json.loads(args.actor_measurements.read_text(encoding="utf-8"))
    native_body = yaml.safe_load(args.actor_native_body.read_text(encoding="utf-8"))["body"]
    units = json.loads(args.units_audit.read_text(encoding="utf-8"))
    selected = report["selected_measurements_cm"]
    old = native_body
    armature_height_cm = units["armature_transform"]["dimensions_m_reported"][2] * 100.0
    neck_z_cm = actor["landmarks_m"]["neck"] * 100.0
    waist_z_cm = actor["landmarks_m"]["waist"] * 100.0
    bust_z_cm = actor["landmarks_m"]["bust"] * 100.0
    hips_z_cm = actor["landmarks_m"]["hips"] * 100.0

    # Keep arm/sleeve measurements directly from the Actor REST pass.  Replace
    # only torso circumferences and vertical landmarks with the centered,
    # topology-aware report.  Height is anchored to the skeleton, not the
    # oversized head mesh, while height-head_l remains the actual neck level.
    neck_w = old["neck_w"] if args.neck_w_override is None else float(args.neck_w_override)
    if neck_w <= 0:
        raise ValueError("--neck-w-override must be positive")
    body = {
        "height": armature_height_cm,
        "head_l": armature_height_cm - neck_z_cm,
        "arm_length": old["arm_length"],
        "arm_pose_angle": old["arm_pose_angle"],
        "armscye_depth": old["armscye_depth"],
        "shoulder_w": old["shoulder_w"],
        "shoulder_incl": old["shoulder_incl"],
        "neck_w": neck_w,
        "bust": selected["bust"],
        "back_width": selected["bust"] / 2.0,
        "underbust": selected["bust"],
        "bust_line": neck_z_cm - bust_z_cm,
        "vert_bust_line": neck_z_cm - bust_z_cm,
        "bust_points": (report["results"]["bust"]["selected"]["bounds_cm"]["axis0"][1] - report["results"]["bust"]["selected"]["bounds_cm"]["axis0"][0]) / 2.0,
        "waist": selected["waist"],
        "waist_back_width": selected["waist"] / 2.0,
        "waist_line": neck_z_cm - waist_z_cm,
        "waist_over_bust_line": neck_z_cm - waist_z_cm,
        "hips": selected["hips"],
        "hip_back_width": selected["hips"] / 2.0,
        "hips_line": waist_z_cm - hips_z_cm,
        "hip_inclination": 0.0,
        "wrist": old["wrist"],
        "actor_upperarm_cuff_circumference": old["actor_upperarm_cuff_circumference"],
        "actor_sleeve_cuff_circumference": old["actor_sleeve_cuff_circumference"],
        "actor_sleeve_connecting_width": old["actor_sleeve_connecting_width"],
        "actor_sleeve_length": old["actor_sleeve_length"],
        "actor_sleeve_cuff_t": old["actor_sleeve_cuff_t"],
    }
    provenance = {
        "schema": "assetsstudio_actor_garmentcodedata_body_provenance_v1",
        "actor": actor["source_actor"],
        "pose": "REST",
        "units": "centimetres",
        "body_height_source": "Actor armature world height; oversized head mesh excluded",
        "torso_measurement_source": str(args.measurement_report.resolve()),
        "torso_measurement_policy": "centered closed body loop, +/-2cm at 5mm, bust/hips MAX and waist MIN, 10% continuity gate",
        "arm_measurement_source": str(args.actor_measurements.resolve()),
        "neck_measurement_source": (
            "accepted native body value"
            if args.neck_w_override is None
            else "diagnostic override supplied by actor neck face-section scan; not yet accepted"
        ),
        "unsupported_or_style_assumptions": [
            "underbust equals centered bust because Actor has no separate underbust landmark",
            "back widths are half of corresponding circumferences for GarmentCode front/back allocation",
            "hip inclination is zero because this is an upper-garment test",
        ],
    }
    if args.neck_w_override is not None:
        provenance["neck_w_override_cm"] = float(args.neck_w_override)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump({"body": body, "assetsstudio_actor_body_provenance": provenance}, sort_keys=False), encoding="utf-8")
    print(yaml.safe_dump({"body": body}, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
