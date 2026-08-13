"""Validate an Actor-derived hair under-cap candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    options = parser.parse_args()
    manifest = json.loads(options.manifest.resolve().read_text(encoding="utf-8"))
    if manifest.get("schema") != "assetsstudio_hair_under_cap_v1":
        raise RuntimeError("unexpected hair under-cap schema")
    if manifest.get("status") != "candidate":
        raise RuntimeError("under-cap candidates must remain candidate until human review")
    if manifest.get("object") != "HairUnderCapCandidate":
        raise RuntimeError("unexpected under-cap object name")
    if manifest.get("profile") == "seed04_scalp_base" and manifest.get("variant") not in {"conservative", "coverage"}:
        raise RuntimeError("seed04 scalp base must declare conservative or coverage variant")
    if manifest.get("binding") != {"bone": "CC_Base_Head", "web_contract": "single_bone_skin"}:
        raise RuntimeError("under-cap binding contract changed")
    geometry = manifest.get("geometry", {})
    for key in ("vertices", "polygons", "selected_faces"):
        if int(geometry.get(key, 0)) <= 0:
            raise RuntimeError(f"under-cap geometry is empty: {key}")
    if float(geometry.get("surface_offset", 0.0)) <= 0:
        raise RuntimeError("under-cap surface offset must be positive")
    renders = manifest.get("renders", {})
    for direction in ("front", "right", "back", "left"):
        path = Path(str(renders.get(direction, "")))
        if not path.is_file():
            raise RuntimeError(f"missing under-cap render: {direction}")
    print(
        "ASSETSSTUDIO_HAIR_UNDER_CAP_VALIDATION_PASS "
        f"vertices={geometry['vertices']} polygons={geometry['polygons']} profile={manifest['profile']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
