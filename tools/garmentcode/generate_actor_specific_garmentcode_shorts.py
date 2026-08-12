"""Generate canonical GarmentCode Pants from Actor-specific lower-body data."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


EXPECTED_PANELS = {"pant_f_l", "pant_b_l", "pant_f_r", "pant_b_r"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--garmentcode-root", required=True, type=Path)
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--measurements", required=True, type=Path)
    parser.add_argument("--body", required=True, type=Path)
    parser.add_argument("--design-template", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--name", default="actor_specific_garmentcode_shorts_v1")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--pants-length", type=float, default=0.30)
    parser.add_argument("--pants-width", type=float, default=1.05)
    parser.add_argument("--pants-flare", type=float, default=1.0)
    parser.add_argument("--pants-rise", type=float, default=1.0)
    return parser.parse_args()


def guard(options: argparse.Namespace, pattern: Path, manifest: Path | None = None) -> None:
    command = [
        sys.executable,
        str(Path(__file__).with_name("validate_actor_native_garmentcode_inputs.py")),
        "--experiment-kind", "garmentcode_actor_specific",
        "--actor", str(options.actor.resolve()),
        "--measurements", str(options.measurements.resolve()),
        "--pattern", str(pattern.resolve()),
    ]
    if manifest is not None:
        command.extend(["--manifest", str(manifest.resolve())])
    subprocess.run(command, check=True)


def main() -> int:
    options = parse_args()
    measurements = json.loads(options.measurements.read_text(encoding="utf-8"))
    if measurements.get("schema") != "assetsstudio_actor_complete_pants_measurements_v1":
        raise RuntimeError("expected Actor pants measurement report")
    if Path(measurements["source_actor"]).resolve() != options.actor.resolve():
        raise RuntimeError("Actor does not match pants measurement source")
    body_payload = yaml.safe_load(options.body.read_text(encoding="utf-8"))
    provenance = body_payload.get("assetsstudio_actor_pants_body_provenance", {})
    if Path(provenance.get("actor", "")).resolve() != options.actor.resolve():
        raise RuntimeError("pants body YAML is not derived from this Actor")

    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    authoring_spec = output / "actor_specific_pants_pattern_spec.json"
    spec = {
        "schema": "assetsstudio_actor_specific_garmentcode_pants_spec_v1",
        "experiment_kind": "garmentcode_actor_specific",
        "authoring_source": "actor_measurements_and_actor_pattern",
        "actor": str(options.actor.resolve()),
        "measurements": str(options.measurements.resolve()),
        "body_parameters": str(options.body.resolve()),
        "style": {"upper": None, "bottom": "Pants", "waistband": None},
        "garment_style_parameters": {
            "pants_length": options.pants_length,
            "pants_width": options.pants_width,
            "pants_flare": options.pants_flare,
            "pants_rise": options.pants_rise,
        },
        "actor_parameters": {
            key: body_payload["body"][key]
            for key in ("waist", "hips", "leg_circ", "waist_line", "hips_line", "crotch_hip_diff")
        },
        "design_template": str(options.design_template.resolve()),
    }
    authoring_spec.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    guard(options, authoring_spec)

    source_root = options.garmentcode_root.resolve()
    sys.path.insert(0, str(source_root))
    from assets.bodies.body_params import BodyParameters
    from assets.garment_programs.meta_garment import MetaGarment

    design = yaml.safe_load(options.design_template.read_text(encoding="utf-8"))["design"]
    design["meta"]["upper"]["v"] = None
    design["meta"]["bottom"]["v"] = "Pants"
    design["meta"]["wb"]["v"] = None
    design["pants"]["length"]["v"] = options.pants_length
    design["pants"]["width"]["v"] = options.pants_width
    design["pants"]["flare"]["v"] = options.pants_flare
    design["pants"]["rise"]["v"] = options.pants_rise
    design["pants"]["cuff"]["type"]["v"] = None
    random.seed(options.seed)
    body = BodyParameters(str(options.body.resolve()))
    garment = MetaGarment(options.name, body, design)
    garment.assert_non_empty()
    garment.assert_total_length()
    pattern = garment.assembly()
    panels = set(pattern.pattern["panels"])
    if panels != EXPECTED_PANELS:
        raise RuntimeError(f"unexpected canonical Pants panels: {sorted(panels)}")
    if garment.is_self_intersecting():
        raise RuntimeError("GarmentCode generated a self-intersecting initial Pants pattern")
    destination = Path(pattern.serialize(
        str(output), tag=f"seed_{options.seed}", with_3d=False,
        with_text=False, view_ids=False, with_printable=False,
    ))
    body.save(destination)
    shutil.copy2(options.design_template.resolve(), destination / "design_template_source.yaml")
    (destination / "design_params.yaml").write_text(
        yaml.safe_dump({"design": design}, sort_keys=False), encoding="utf-8"
    )
    manifest = {
        "schema": "assetsstudio_garmentcode_pants_candidate_v1",
        "experiment_kind": "garmentcode_actor_specific",
        "authoring_source": "actor_measurements_and_actor_pattern",
        "generator": "GarmentCode/PyGarment",
        "name": options.name,
        "seed": options.seed,
        "actor_source": str(options.actor.resolve()),
        "measurements_source": str(options.measurements.resolve()),
        "body_source": str(options.body.resolve()),
        "pattern_spec": str(authoring_spec.resolve()),
        "design_template_source": str(options.design_template.resolve()),
        "actor_parameters": spec["actor_parameters"],
        "garment_style_parameters": spec["garment_style_parameters"],
        "output": str(destination.resolve()),
        "panels": sorted(panels),
        "stitches": len(pattern.pattern["stitches"]),
        "next_stage": "Actor collision simulation, exact panel membership, native weight transfer, physical and animation review",
    }
    manifest_path = destination / "assetsstudio_candidate_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    guard(options, authoring_spec, manifest_path)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
