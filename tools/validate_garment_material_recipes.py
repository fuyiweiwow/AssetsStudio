"""Validate a garment material library without requiring Blender."""

from __future__ import annotations

import argparse
from pathlib import Path

from garment_material_recipe import load_material_library


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", required=True, type=Path)
    options = parser.parse_args()
    payload = load_material_library(options.library)
    print(
        "GARMENT_MATERIAL_LIBRARY_PASS "
        f"recipes={len(payload['recipes'])} target={','.join(payload['target_objects'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
