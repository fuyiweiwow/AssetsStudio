"""Create a GarmentCode body YAML whose pants-driving values come from Actor REST."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--measurements", required=True, type=Path)
    parser.add_argument("--base-body", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = json.loads(args.measurements.read_text(encoding="utf-8"))
    if report.get("schema") != "assetsstudio_actor_complete_pants_measurements_v1":
        raise RuntimeError("expected Actor pants measurement report")
    body = dict(yaml.safe_load(args.base_body.read_text(encoding="utf-8"))["body"])
    measured = report["body"]
    points = report["landmarks_gc_m"]
    waist = float(measured["waist"]["perimeter_cm"])
    hips = float(measured["hips"]["perimeter_cm"])
    leg = float(measured["leg_circ"])
    if waist >= hips:
        # Pants assumes positive hip-to-waist shaping.  Preserve measured hips
        # and cap the pattern waist just below it; record this explicit pattern
        # compatibility adjustment in provenance.
        waist = hips * 0.98
    neck_y = float(points["neck"][1]) * 100.0
    waist_y = float(measured["waist"]["y_m"]) * 100.0
    hips_y = float(measured["hips"]["y_m"]) * 100.0
    thigh_y = 0.5 * (
        float(measured["left_thigh"]["y_m"]) + float(measured["right_thigh"]["y_m"])
    ) * 100.0
    body.update({
        "waist": waist,
        "waist_back_width": waist / 2.0,
        "hips": hips,
        "hip_back_width": hips / 2.0,
        "leg_circ": leg,
        "waist_line": neck_y - waist_y,
        "waist_over_bust_line": neck_y - waist_y,
        "hips_line": waist_y - hips_y,
        "crotch_hip_diff": max(hips_y - thigh_y, 2.0),
        "hip_inclination": 0.0,
        "bust_points": max(hips / 8.0, 2.0),
        "bum_points": max(hips / 8.0, 2.0),
    })
    provenance = {
        "schema": "assetsstudio_actor_pants_body_provenance_v1",
        "actor": report["source_actor"],
        "measurements": str(args.measurements.resolve()),
        "pose": "REST",
        "units": "centimetres",
        "pants_driving_fields": [
            "waist", "waist_back_width", "hips", "hip_back_width", "leg_circ",
            "waist_line", "hips_line", "crotch_hip_diff", "hip_inclination",
            "bust_points", "bum_points",
        ],
        "unrelated_field_source": str(args.base_body.resolve()),
        "waist_pattern_compatibility_adjusted": measured["waist"]["perimeter_cm"] >= measured["hips"]["perimeter_cm"],
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump({"body": body, "assetsstudio_actor_pants_body_provenance": provenance}, sort_keys=False),
        encoding="utf-8",
    )
    print(yaml.safe_dump({"body": body}, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
