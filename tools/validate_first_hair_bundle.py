"""Validate the deterministic first Actor hair bundle cache."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--coverage", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    options = cli_args()
    recipe = json.loads(options.recipe.resolve().read_text(encoding="utf-8"))
    manifest = json.loads(options.manifest.resolve().read_text(encoding="utf-8"))
    coverage = json.loads(options.coverage.resolve().read_text(encoding="utf-8"))
    if recipe.get("schema") != "assetsstudio_hair_bundle_recipe_v1":
        raise RuntimeError("unexpected first hair recipe schema")
    if manifest.get("schema") != "assetslab_chibi_blend_hair_candidate_v1":
        raise RuntimeError("unexpected generated hair candidate schema")
    if manifest.get("source_objects") != recipe.get("components"):
        raise RuntimeError("generated hair components differ from the fixed recipe")
    if manifest.get("source_anchor_object") != recipe.get("source_anchor_object"):
        raise RuntimeError("generated hair source anchor changed")
    if manifest.get("object") != "HairCandidate_Blend":
        raise RuntimeError("generated hair object name changed")
    fit = manifest.get("fit", {})
    expected_fit = recipe.get("fit", {})
    for key in ("q_height_ratio", "width_ratio"):
        if abs(float(fit.get(key, -1)) - float(expected_fit[key])) > 1e-6:
            raise RuntimeError(f"generated hair fit changed: {key}")
    if fit.get("parent_bone") != recipe.get("binding", {}).get("bone"):
        raise RuntimeError("generated hair head binding changed")
    expected_repair = recipe.get("repair")
    actual_repair = manifest.get("front_center_overlap")
    if expected_repair:
        if not actual_repair:
            raise RuntimeError("generated hair omitted the recipe's front-center overlap repair")
        repair_keys = {
            "half_width": "half_width",
            "half_height": "half_height",
            "front_offset": "front_offset",
        }
        for recipe_key, manifest_key in repair_keys.items():
            if abs(float(expected_repair[recipe_key]) - float(actual_repair[manifest_key])) > 1e-6:
                raise RuntimeError(f"generated hair repair changed: {recipe_key}")
        if int(actual_repair.get("moved_vertices", 0)) <= 0:
            raise RuntimeError("front-center overlap repair moved no vertices")
    elif actual_repair is not None:
        raise RuntimeError("generated hair has an undeclared front-center overlap repair")
    for unsupported in ("actor_cap", "source_scalp_cap", "smooth_scalp_cap", "right_hairline_patch"):
        if manifest.get(unsupported) is not None:
            raise RuntimeError(f"first bundle unexpectedly uses repair geometry: {unsupported}")
    for direction in ("front", "right", "back", "left"):
        render_path = Path(str(manifest.get("renders", {}).get(direction, "")))
        if not render_path.is_file():
            raise RuntimeError(f"missing first hair bundle render: {direction}")
    if coverage.get("schema") != "assetsstudio_front_surface_coverage_v1":
        raise RuntimeError("unexpected front surface coverage schema")
    if int(coverage.get("gap_samples", -1)) != 0 or float(coverage.get("coverage_ratio", 0.0)) != 1.0:
        raise RuntimeError("front-center scalp exposure remains after the declared repair")
    print(
        "ASSETSSTUDIO_HAIR_BUNDLE_VALIDATION_PASS "
        f"components={len(recipe['components'])} vertices={manifest.get('vertices')} bone={fit['parent_bone']} coverage=1.0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
