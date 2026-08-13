"""Load and validate the shared AssetsStudio garment material contract."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "assetsstudio_garment_material_library_v1"
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
PATTERNS = {"none", "weave", "stripes"}


def load_material_library(path: Path) -> dict[str, Any]:
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA:
        raise RuntimeError(f"unexpected material library schema: {payload.get('schema')}")
    if not payload.get("geometry_immutable"):
        raise RuntimeError("material library must declare geometry_immutable=true")
    targets = payload.get("target_objects")
    if not isinstance(targets, list) or not targets or not all(isinstance(item, str) for item in targets):
        raise RuntimeError("material library requires target_objects")
    limits = payload.get("parameter_limits", {})
    required_limits = ("roughness", "metalness", "sheen", "pattern_scale", "pattern_strength")
    for name in required_limits:
        bounds = limits.get(name)
        if not isinstance(bounds, list) or len(bounds) != 2 or float(bounds[0]) > float(bounds[1]):
            raise RuntimeError(f"invalid parameter limit: {name}")
    recipes = payload.get("recipes")
    if not isinstance(recipes, list) or not recipes:
        raise RuntimeError("material library requires recipes")
    ids: set[str] = set()
    for recipe in recipes:
        recipe_id = recipe.get("id")
        if not isinstance(recipe_id, str) or not recipe_id or recipe_id in ids:
            raise RuntimeError(f"invalid or duplicate recipe id: {recipe_id}")
        ids.add(recipe_id)
        for color_name in ("base_color", "accent_color"):
            if not HEX_COLOR.match(str(recipe.get(color_name, ""))):
                raise RuntimeError(f"{recipe_id} has invalid {color_name}")
        if recipe.get("pattern") not in PATTERNS:
            raise RuntimeError(f"{recipe_id} has unsupported pattern")
        for parameter in required_limits:
            value = float(recipe.get(parameter, 0.0))
            low, high = (float(item) for item in limits[parameter])
            if value < low or value > high:
                raise RuntimeError(f"{recipe_id}.{parameter}={value} outside {low}..{high}")
    if payload.get("default_recipe_id") not in ids:
        raise RuntimeError("default_recipe_id does not identify a recipe")
    return payload


def resolve_recipe(library: dict[str, Any], recipe_id: str) -> dict[str, Any]:
    for recipe in library["recipes"]:
        if recipe["id"] == recipe_id:
            return recipe
    raise RuntimeError(f"unknown material recipe: {recipe_id}")


def hex_to_linear_rgba(value: str) -> tuple[float, float, float, float]:
    channels = [int(value[index : index + 2], 16) / 255.0 for index in (1, 3, 5)]
    linear = tuple(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels)
    return linear[0], linear[1], linear[2], 1.0
