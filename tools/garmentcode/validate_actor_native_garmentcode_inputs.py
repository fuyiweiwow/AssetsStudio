"""Fail-fast guard for Actor-specific GarmentCode authoring experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


FORBIDDEN_SOURCE_MARKERS = ("official", "neutral", "demo", "sim.obj")
MEASUREMENT_SCHEMAS = {
    "assetsstudio_actor_complete_shirt_measurements_v1",
    "assetsstudio_actor_complete_pants_measurements_v1",
}


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-kind", required=True, choices=("garmentcode_actor_specific",))
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--measurements", required=True, type=Path)
    parser.add_argument("--pattern", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    return parser.parse_args()


def source_text(path: Path) -> str:
    return str(path.resolve()).lower()


def fail(message: str) -> None:
    raise RuntimeError("ACTOR_NATIVE_GARMENTCODE_INPUTS_FAIL: " + message)


def main() -> int:
    options = args()
    if options.experiment_kind != "garmentcode_actor_specific":
        fail("this guard only accepts an explicitly declared GarmentCode Actor-specific experiment")
    for label, path in (("actor", options.actor), ("measurements", options.measurements), ("pattern", options.pattern)):
        if not path.exists():
            fail(f"missing {label}: {path}")

    actor_name = options.actor.name.lower()
    if actor_name != "chibi_actor_mixamo_walk_v1.blend":
        fail(f"unexpected Actor source name: {options.actor.name}")

    try:
        measurements = json.loads(options.measurements.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read measurements: {exc}")
    if measurements.get("schema") not in MEASUREMENT_SCHEMAS:
        fail(f"measurements schema must be one of {sorted(MEASUREMENT_SCHEMAS)}")
    if measurements.get("pose") != "REST":
        fail("measurements must come from Actor REST pose")
    if measurements.get("units") != "centimetres":
        fail("measurements units must be centimetres")
    if "body" not in measurements:
        fail("measurements must contain Actor body sections")
    if measurements.get("schema") == "assetsstudio_actor_complete_shirt_measurements_v1" and "arms" not in measurements:
        fail("shirt measurements must contain Actor arms")

    pattern_text = source_text(options.pattern)
    if any(marker in pattern_text for marker in FORBIDDEN_SOURCE_MARKERS):
        fail(f"pattern path looks like an official/demo transfer source: {options.pattern}")
    if options.pattern.suffix.lower() not in {".json", ".yaml", ".yml", ".py", ".npz", ".obj"}:
        fail("pattern must be a pattern specification or Actor-specific generated asset")

    if options.manifest:
        if not options.manifest.exists():
            fail(f"missing manifest: {options.manifest}")
        try:
            manifest = json.loads(options.manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"cannot read manifest: {exc}")
        if manifest.get("authoring_source") != "actor_measurements_and_actor_pattern":
            fail("manifest authoring_source must be actor_measurements_and_actor_pattern")
        for key in ("fitted_source", "official_source", "demo_source"):
            value = str(manifest.get(key, "")).lower()
            if any(marker in value for marker in FORBIDDEN_SOURCE_MARKERS):
                fail(f"manifest contains forbidden {key}: {value}")

    print("ACTOR_NATIVE_GARMENTCODE_INPUTS_PASS")
    print(f"actor={options.actor.resolve()}")
    print(f"measurements={options.measurements.resolve()}")
    print(f"pattern={options.pattern.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
