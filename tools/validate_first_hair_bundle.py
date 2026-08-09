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
    return parser.parse_args()


def main() -> int:
    options = cli_args()
    recipe = json.loads(options.recipe.resolve().read_text(encoding="utf-8"))
    manifest = json.loads(options.manifest.resolve().read_text(encoding="utf-8"))
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
    for unsupported in ("actor_cap", "source_scalp_cap", "smooth_scalp_cap", "right_hairline_patch"):
        if manifest.get(unsupported) is not None:
            raise RuntimeError(f"first bundle unexpectedly uses repair geometry: {unsupported}")
    for direction in ("front", "right", "back", "left"):
        render_path = Path(str(manifest.get("renders", {}).get(direction, "")))
        if not render_path.is_file():
            raise RuntimeError(f"missing first hair bundle render: {direction}")
    print(
        "ASSETSSTUDIO_HAIR_BUNDLE_VALIDATION_PASS "
        f"components={len(recipe['components'])} vertices={manifest.get('vertices')} bone={fit['parent_bone']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
