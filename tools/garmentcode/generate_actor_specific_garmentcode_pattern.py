"""Generate the canonical short-sleeve pattern from this Actor's data only."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


MEASUREMENT_SCHEMA = "assetsstudio_actor_complete_shirt_measurements_v1"
EXPECTED_PANELS = {
    "left_btorso", "left_ftorso", "left_sleeve_f", "left_sleeve_b",
    "sl_left_cuff_f", "sl_left_cuff_b", "right_btorso", "right_ftorso",
    "right_sleeve_f", "right_sleeve_b", "sl_right_cuff_f", "sl_right_cuff_b",
}
EXPECTED_EDGE_COUNTS = {
    "left_btorso": 6, "left_ftorso": 6, "left_sleeve_f": 4,
    "left_sleeve_b": 4, "sl_left_cuff_f": 4, "sl_left_cuff_b": 4,
    "right_btorso": 6, "right_ftorso": 6, "right_sleeve_f": 4,
    "right_sleeve_b": 4, "sl_right_cuff_f": 4, "sl_right_cuff_b": 4,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--garmentcode-root", type=Path, required=True)
    parser.add_argument("--actor", type=Path, required=True)
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--body", type=Path, required=True)
    parser.add_argument("--design-template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", default="actor_specific_short_sleeve_v1")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--shirt-width-ease", type=float, default=1.05)
    parser.add_argument("--shirt-length-factor", type=float, default=0.90)
    return parser.parse_args()


def fail(message: str) -> None:
    raise RuntimeError(f"ACTOR_SPECIFIC_GARMENTCODE_FAIL: {message}")


def read_measurements(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read measurements: {exc}")
    if data.get("schema") != MEASUREMENT_SCHEMA:
        fail(f"measurement schema must be {MEASUREMENT_SCHEMA}")
    if data.get("pose") != "REST" or data.get("units") != "centimetres":
        fail("measurements must be Actor REST centimetres")
    if not data.get("body") or set(data.get("arms", {})) != {"left", "right"}:
        fail("measurements must contain body and both arms")
    return data


def read_body(path: Path) -> tuple[dict, dict]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        body = payload["body"]
    except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        fail(f"cannot read Actor body YAML: {exc}")
    required = {
        "height", "arm_length", "arm_pose_angle", "armscye_depth", "shoulder_w",
        "shoulder_incl", "neck_w", "bust", "waist_line",
        "actor_sleeve_cuff_circumference", "actor_sleeve_connecting_width",
        "actor_sleeve_length", "actor_sleeve_cuff_t",
    }
    missing = sorted(required - set(body))
    if missing:
        fail(f"Actor body parameters missing: {missing}")
    non_positive = sorted(key for key in required if float(body[key]) <= 0.0)
    if non_positive:
        fail(f"Actor body parameters must be positive: {non_positive}")
    return payload, body


def set_value(design: dict, *keys: str, value) -> None:
    node = design
    for key in keys[:-1]:
        node = node[key]
    node[keys[-1]]["v"] = value


def build_design(template: Path, width_ease: float, length_factor: float) -> dict:
    try:
        design = yaml.safe_load(template.read_text(encoding="utf-8"))["design"]
    except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        fail(f"cannot read design template: {exc}")
    set_value(design, "meta", "upper", value="Shirt")
    set_value(design, "meta", "bottom", value=None)
    set_value(design, "meta", "wb", value=None)
    set_value(design, "shirt", "width", value=width_ease)
    set_value(design, "shirt", "length", value=length_factor)
    set_value(design, "shirt", "flare", value=1.0)
    for side in ((), ("left",)):
        set_value(design, *side, "sleeve", "sleeveless", value=False)
        set_value(design, *side, "sleeve", "armhole_shape", value="ArmholeCurve")
        set_value(design, *side, "sleeve", "smoothing_coeff", value=0.18)
        set_value(design, *side, "sleeve", "cuff", "type", value="CuffBand")
        set_value(design, *side, "sleeve", "cuff", "cuff_len", value=0.10)
    set_value(design, "collar", "f_collar", value="CircleNeckHalf")
    set_value(design, "collar", "b_collar", value="CircleNeckHalf")
    set_value(design, "collar", "component", "style", value=None)
    set_value(design, "collar", "width", value=0.0)
    set_value(design, "collar", "fc_depth", value=0.25)
    set_value(design, "collar", "bc_depth", value=0.10)
    return design


def run_command(command: list[str], failure: str) -> None:
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        fail(failure)
    print(result.stdout, end="")


def run_guards(options: argparse.Namespace, spec_path: Path) -> None:
    run_command([
        sys.executable,
        str(Path(__file__).with_name("validate_garmentcode_actor_patch.py")),
        "--garmentcode-root", str(options.garmentcode_root.resolve()),
    ], "GarmentCode dependency guard rejected the checkout")
    run_command([
        sys.executable,
        str(Path(__file__).with_name("validate_actor_native_garmentcode_inputs.py")),
        "--experiment-kind", "garmentcode_actor_specific",
        "--actor", str(options.actor.resolve()),
        "--measurements", str(options.measurements.resolve()),
        "--pattern", str(spec_path.resolve()),
    ], "Actor-specific input guard rejected the experiment")


def label_sleeve_panels(pattern) -> list[dict[str, str]]:
    changes = []
    for side in ("left", "right"):
        label = f"{side}_arm"
        for panel_name, panel in pattern.pattern["panels"].items():
            if not (
                panel_name.startswith(f"{side}_sleeve_")
                or panel_name.startswith(f"sl_{side}_cuff_")
            ):
                continue
            if isinstance(panel, dict):
                before = panel.get("label", "")
                panel["label"] = label
            else:
                before = getattr(panel, "label", "")
                panel.label = label
            changes.append({"panel": panel_name, "before": before, "after": label})
    return changes


def assert_topology(pattern) -> None:
    panels = pattern.pattern["panels"]
    if set(panels) != EXPECTED_PANELS:
        fail(f"expected exactly 12 canonical panels, got {sorted(panels)}")
    if len(pattern.pattern["stitches"]) != 22:
        fail(f"expected exactly 22 stitches, got {len(pattern.pattern['stitches'])}")
    edge_counts = {
        name: len(panel["edges"] if isinstance(panel, dict) else panel.edges)
        for name, panel in panels.items()
    }
    if edge_counts != EXPECTED_EDGE_COUNTS:
        fail(f"canonical panel edge counts changed: {edge_counts}")


def pattern_spec(options: argparse.Namespace, data: dict, body: dict) -> dict:
    left = data["arms"]["left"]
    right = data["arms"]["right"]
    return {
        "schema": "assetsstudio_actor_specific_garmentcode_pattern_spec_v1",
        "experiment_kind": "garmentcode_actor_specific",
        "authoring_source": "actor_measurements_and_actor_pattern",
        "actor": str(options.actor.resolve()),
        "measurements": str(options.measurements.resolve()),
        "body_parameters": str(options.body.resolve()),
        "style": {
            "upper": "Shirt",
            "bottom": None,
            "collar_front": "CircleNeckHalf",
            "collar_back": "CircleNeckHalf",
            "sleeve": "short_sleeve_with_closed_cuff",
        },
        "actor_parameters": {
            "shoulder_width_cm": body["shoulder_w"],
            "neck_width_cm": body["neck_w"],
            "bust_cm": body["bust"],
            "waist_line_cm": body["waist_line"],
            "arm_pose_angle_deg": body["arm_pose_angle"],
            "sleeve_length_cm": body["actor_sleeve_length"],
            "sleeve_connecting_width_cm": body["actor_sleeve_connecting_width"],
            "sleeve_cuff_circumference_cm": body["actor_sleeve_cuff_circumference"],
            "sleeve_cuff_t": body["actor_sleeve_cuff_t"],
            "left_upperarm_section": left["sections"]["upperarm_shoulder"],
            "right_upperarm_section": right["sections"]["upperarm_shoulder"],
            "left_cuff_section": left["sections"]["sleeve_cuff"],
            "right_cuff_section": right["sections"]["sleeve_cuff"],
        },
        "actor_parameter_sources": {
            "body_parameters": str(options.body.resolve()),
            "arm_section_details": str(options.measurements.resolve()),
            "rule": "all scalar garment parameters come from the Actor body YAML",
        },
        "garment_style_parameters": {
            "shirt_width_ease": options.shirt_width_ease,
            "shirt_length_factor": options.shirt_length_factor,
            "sleeve_armhole_shape": "ArmholeCurve",
            "sleeve_cuff_type": "CuffBand",
            "sleeve_cuff_length_factor": 0.10,
            "collar_width_fraction": 0.0,
            "front_collar_depth_fraction": 0.25,
            "back_collar_depth_fraction": 0.10,
        },
        "design_template": str(options.design_template.resolve()),
    }


def main() -> int:
    options = parse_args()
    for label, path in (
        ("GarmentCode root", options.garmentcode_root),
        ("Actor", options.actor),
        ("measurements", options.measurements),
        ("body", options.body),
        ("design template", options.design_template),
    ):
        if not path.exists():
            fail(f"missing {label}: {path}")
    if options.shirt_width_ease <= 0.0 or options.shirt_length_factor <= 0.0:
        fail("shirt width ease and length factor must be positive")

    data = read_measurements(options.measurements.resolve())
    if Path(data["source_actor"]).resolve() != options.actor.resolve():
        fail("Actor does not match measurement source_actor")
    _body_payload, body_values = read_body(options.body.resolve())

    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    spec_path = output / "actor_specific_pattern_spec.json"
    spec = pattern_spec(options, data, body_values)
    spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    run_guards(options, spec_path)

    source_root = options.garmentcode_root.resolve()
    sys.path.insert(0, str(source_root))
    from assets.bodies.body_params import BodyParameters
    from assets.garment_programs.meta_garment import MetaGarment

    body = BodyParameters(str(options.body.resolve()))
    design = build_design(
        options.design_template.resolve(), options.shirt_width_ease, options.shirt_length_factor
    )
    random.seed(options.seed)
    garment = MetaGarment(options.name, body, design)
    garment.assert_non_empty()
    garment.assert_total_length()
    pattern = garment.assembly()
    label_changes = label_sleeve_panels(pattern)
    assert_topology(pattern)
    if garment.is_self_intersecting():
        fail("GarmentCode generated a self-intersecting initial garment")

    destination = Path(pattern.serialize(
        str(output), tag=f"seed_{options.seed}", with_3d=False, with_text=False,
        view_ids=False, with_printable=False,
    ))
    body.save(destination)
    shutil.copy2(options.design_template.resolve(), destination / "design_template_source.yaml")
    (destination / "design_params.yaml").write_text(
        yaml.safe_dump({"design": design}, sort_keys=False), encoding="utf-8"
    )
    manifest = {
        "schema": "assetsstudio_garmentcode_candidate_v1",
        "experiment_kind": "garmentcode_actor_specific",
        "authoring_source": "actor_measurements_and_actor_pattern",
        "generator": "GarmentCode/PyGarment",
        "license_boundary": "GarmentCode core MIT; no GPL measurement dependency",
        "name": options.name,
        "seed": options.seed,
        "actor_source": str(options.actor.resolve()),
        "measurements_source": str(options.measurements.resolve()),
        "body_source": str(options.body.resolve()),
        "pattern_spec": str(spec_path.resolve()),
        "design_template_source": str(options.design_template.resolve()),
        "actor_parameters": spec["actor_parameters"],
        "garment_style_parameters": spec["garment_style_parameters"],
        "output": str(destination.resolve()),
        "panels": sorted(pattern.pattern["panels"]),
        "stitches": len(pattern.pattern["stitches"]),
        "explicit_arm_side_label_changes": label_changes,
        "next_stage": "static equilibrium, Actor transfer, physical audit, four-direction review",
    }
    manifest_path = destination / "assetsstudio_candidate_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    run_guards(options, spec_path)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
