"""Generate the first Actor-specific mage robe candidate.

This is intentionally a separate experiment from the accepted/provisional
short-sleeve generator.  The body and arm measurements still come from the
current Actor; only style multipliers are applied to the Actor garment fields.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from generate_actor_specific_garmentcode_pattern import (
    EXPECTED_EDGE_COUNTS,
    EXPECTED_PANELS,
    MEASUREMENT_SCHEMA,
    assert_topology,
    label_sleeve_panels,
    read_body,
    read_measurements,
    run_command,
    set_value,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--garmentcode-root", type=Path, required=True)
    parser.add_argument("--actor", type=Path, required=True)
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--body", type=Path, required=True)
    parser.add_argument("--design-template", type=Path, required=True)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def fail(message: str) -> None:
    raise RuntimeError(f"MAGE_ROBE_GARMENTCODE_FAIL: {message}")


def load_recipe(path: Path) -> dict:
    try:
        recipe = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read recipe: {exc}")
    if recipe.get("schema") != "assetsstudio_garment_recipe_v1":
        fail("recipe schema must be assetsstudio_garment_recipe_v1")
    if recipe.get("asset_type") != "humanoid.garment":
        fail("recipe asset_type must be humanoid.garment")
    if recipe.get("archetype") != "mage_robe_body_v1":
        fail("first experiment requires mage_robe_body_v1")
    parameters = recipe.get("parameters", {})
    required = {
        "length_factor", "skirt_length_factor", "body_width_factor", "hem_flare",
        "sleeve_length_factor", "cuff_width_factor",
    }
    if set(parameters) != required:
        fail(f"recipe parameters must be exactly {sorted(required)}")
    for key, value in parameters.items():
        if float(value) <= 0.0:
            fail(f"recipe parameter must be positive: {key}")
    for key in ("main_color", "trim_color"):
        value = recipe.get("materials", {}).get(key, "")
        if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
            fail(f"recipe material must be a hex color: {key}")
    return recipe


def derive_body(source: dict, recipe: dict, path: Path) -> dict:
    body = copy.deepcopy(source)
    params = recipe["parameters"]
    values = body["body"]
    # The actor measurements remain the source of truth.  These fields are
    # explicit style-eased derivatives used by the GarmentCode program.
    values["actor_sleeve_length"] = float(values["actor_sleeve_length"]) * float(
        params["sleeve_length_factor"]
    )
    values["actor_sleeve_cuff_circumference"] = float(
        values["actor_sleeve_cuff_circumference"]
    ) * float(params["cuff_width_factor"])
    values["assetsstudio_style_derivation"] = {
        "source_body": "current Actor body_measurements.yaml",
        "archetype": recipe["archetype"],
        "sleeve_length_factor": params["sleeve_length_factor"],
        "cuff_width_factor": params["cuff_width_factor"],
    }
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return body


def build_design(template: Path, recipe: dict) -> dict:
    try:
        design = yaml.safe_load(template.read_text(encoding="utf-8"))["design"]
    except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        fail(f"cannot read design template: {exc}")
    params = recipe["parameters"]
    set_value(design, "meta", "upper", value="Shirt")
    set_value(design, "meta", "bottom", value="SkirtCircle")
    set_value(design, "meta", "wb", value=None)
    set_value(design, "shirt", "width", value=float(params["body_width_factor"]))
    set_value(design, "shirt", "length", value=float(params["length_factor"]))
    set_value(design, "shirt", "flare", value=float(params["hem_flare"]))
    # Use GarmentCode's stable upper-plus-skirt composition. The result is one
    # visual robe, while avoiding an overlong single torso panel.
    set_value(design, "flare-skirt", "length", value=float(params["skirt_length_factor"]))
    set_value(design, "flare-skirt", "rise", value=1.0)
    set_value(design, "flare-skirt", "suns", value=0.85)
    set_value(design, "flare-skirt", "cut", "add", value=False)
    # Keep a single, continuous主体服装.  The wide sleeve is part of the
    # robe pattern; trim remains a later material/component concern.
    for side in ((), ("left",)):
        set_value(design, *side, "sleeve", "sleeveless", value=False)
        set_value(design, *side, "sleeve", "armhole_shape", value="ArmholeCurve")
        set_value(design, *side, "sleeve", "smoothing_coeff", value=0.18)
        set_value(design, *side, "sleeve", "cuff", "type", value=None)
        set_value(design, *side, "sleeve", "cuff", "cuff_len", value=0.10)
        set_value(design, *side, "sleeve", "sleeve_angle", value=18)
        set_value(design, *side, "sleeve", "opening_dir_mix", value=0.15)
    set_value(design, "collar", "f_collar", value="CircleNeckHalf")
    set_value(design, "collar", "b_collar", value="CircleNeckHalf")
    set_value(design, "collar", "component", "style", value=None)
    set_value(design, "collar", "width", value=0.0)
    set_value(design, "collar", "fc_depth", value=0.25)
    set_value(design, "collar", "bc_depth", value=0.10)
    return design


def make_spec(options: argparse.Namespace, recipe: dict, measurements: dict, body: dict, derived_body: Path) -> dict:
    left = measurements["arms"]["left"]
    right = measurements["arms"]["right"]
    params = recipe["parameters"]
    return {
        "schema": "assetsstudio_actor_specific_garmentcode_pattern_spec_v1",
        "experiment_kind": "garmentcode_actor_specific",
        "authoring_source": "actor_measurements_and_actor_pattern",
        "archetype": recipe["archetype"],
        "recipe": str(options.recipe.resolve()),
        "actor": str(options.actor.resolve()),
        "measurements": str(options.measurements.resolve()),
        "body_parameters": str(options.body.resolve()),
        "derived_style_body": str(derived_body.resolve()),
        "style": {
            "upper": "MageRobeBody",
            "bottom": "SkirtCircle",
            "collar_front": "CircleNeckHalf",
            "collar_back": "CircleNeckHalf",
            "sleeve": "wide_long_sleeve_open_hem",
        },
        "actor_parameters": {
            "shoulder_width_cm": body["shoulder_w"],
            "neck_width_cm": body["neck_w"],
            "bust_cm": body["bust"],
            "waist_line_cm": body["waist_line"],
            "arm_pose_angle_deg": body["arm_pose_angle"],
            "left_upperarm_section": left["sections"]["upperarm_shoulder"],
            "right_upperarm_section": right["sections"]["upperarm_shoulder"],
        },
        "garment_style_parameters": params,
        "source_policy": "Actor measurements are authoritative; derived body fields only apply explicit recipe style multipliers",
        "design_template": str(options.design_template.resolve()),
    }


def run_guards(options: argparse.Namespace, spec_path: Path) -> None:
    run_command([
        sys.executable, str(Path(__file__).with_name("validate_garmentcode_actor_patch.py")),
        "--garmentcode-root", str(options.garmentcode_root.resolve()),
    ], "GarmentCode dependency guard rejected the checkout")
    run_command([
        sys.executable, str(Path(__file__).with_name("validate_actor_native_garmentcode_inputs.py")),
        "--experiment-kind", "garmentcode_actor_specific",
        "--actor", str(options.actor.resolve()),
        "--measurements", str(options.measurements.resolve()),
        "--pattern", str(spec_path.resolve()),
    ], "Actor-specific input guard rejected the experiment")


def main() -> int:
    options = parse_args()
    for label, path in (
        ("GarmentCode root", options.garmentcode_root),
        ("Actor", options.actor),
        ("measurements", options.measurements),
        ("body", options.body),
        ("design template", options.design_template),
        ("recipe", options.recipe),
    ):
        if not path.exists():
            fail(f"missing {label}: {path}")

    recipe = load_recipe(options.recipe.resolve())
    measurements = read_measurements(options.measurements.resolve())
    if Path(measurements["source_actor"]).resolve() != options.actor.resolve():
        fail("Actor does not match measurement source_actor")
    _body_payload, source_body = read_body(options.body.resolve())

    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    derived_body_path = output / "actor_style_body_measurements.yaml"
    derived_payload = derive_body({"body": source_body}, recipe, derived_body_path)
    spec_path = output / "actor_specific_pattern_spec.json"
    spec = make_spec(options, recipe, measurements, source_body, derived_body_path)
    spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    run_guards(options, spec_path)

    source_root = options.garmentcode_root.resolve()
    sys.path.insert(0, str(source_root))
    from assets.bodies.body_params import BodyParameters
    from assets.garment_programs.meta_garment import MetaGarment

    body = BodyParameters(str(derived_body_path))
    design = build_design(options.design_template.resolve(), recipe)
    random.seed(recipe["seed"])
    garment = MetaGarment("MageRobeBody", body, design)
    garment.assert_non_empty()
    garment.assert_total_length()
    pattern = garment.assembly()
    label_changes = label_sleeve_panels(pattern)
    # The current Actor collision proxy intentionally has no leg vertices.
    # Keep the skirt on the available closed body collider until a dedicated
    # lower-body proxy is accepted; this is a collision-label policy, not a
    # change to the GarmentCode pattern geometry.
    for panel_name, panel in pattern.pattern["panels"].items():
        if not panel_name.startswith("skirt_"):
            continue
        before = panel.get("label", "") if isinstance(panel, dict) else getattr(panel, "label", "")
        if isinstance(panel, dict):
            panel["label"] = "body"
        else:
            panel.label = "body"
        label_changes.append({"panel": panel_name, "before": before, "after": "body"})
    panel_names = set(pattern.pattern["panels"])
    required_prefixes = (
        "left_btorso", "right_btorso", "left_ftorso", "right_ftorso",
        "left_sleeve_", "right_sleeve_", "skirt_",
    )
    if not all(any(name.startswith(prefix) for name in panel_names) for prefix in required_prefixes):
        fail(f"robe component topology is incomplete: {sorted(panel_names)}")
    if len(pattern.pattern["stitches"]) < 14:
        fail("robe component topology has too few stitches")
    if garment.is_self_intersecting():
        fail("GarmentCode generated a self-intersecting initial robe")

    destination = Path(pattern.serialize(
        str(output), tag=f"seed_{recipe['seed']}", with_3d=False, with_text=False,
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
        "archetype": recipe["archetype"],
        "generator": "GarmentCode/PyGarment",
        "license_boundary": "GarmentCode core MIT; no paid garment software dependency",
        "recipe": str(options.recipe.resolve()),
        "seed": recipe["seed"],
        "actor_source": str(options.actor.resolve()),
        "measurements_source": str(options.measurements.resolve()),
        "body_source": str(derived_body_path.resolve()),
        "actor_body_source": str(options.body.resolve()),
        "pattern_spec": str(spec_path.resolve()),
        "generated_specification": str((destination / f"{destination.name}_specification.json").resolve()),
        "design_template_source": str(options.design_template.resolve()),
        "actor_parameters": spec["actor_parameters"],
        "garment_style_parameters": spec["garment_style_parameters"],
        "output": str(destination.resolve()),
        "panels": sorted(pattern.pattern["panels"]),
        "stitches": len(pattern.pattern["stitches"]),
        "explicit_arm_side_label_changes": label_changes,
        "status": "candidate",
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
