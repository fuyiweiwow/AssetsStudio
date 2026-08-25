#!/usr/bin/env python3
"""Compile validated StyleProfile and ActorSlotProfile assets for Studio."""

from __future__ import annotations

import json
from pathlib import Path

from validate_style_slot_profiles import (
    ACTOR_SCHEMA,
    STYLE_SCHEMA,
    load_json,
    validate_schema,
    validate_semantics,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "studio/src/generated/style-slot-profiles.json"
STYLE_PATHS = [
    ROOT / "references/style_profiles/qstyle_anime_western_fantasy_no_face_v1.json",
]
ACTOR_PATHS = [
    ROOT / "references/actor_core/actor_core_0ef398ca/actor_slot_profile_v1.json",
]


def main() -> int:
    styles = [load_json(path) for path in STYLE_PATHS]
    actors = [load_json(path) for path in ACTOR_PATHS]
    for style in styles:
        validate_schema(style, STYLE_SCHEMA)
    styles_by_id = {style["id"]: style for style in styles}
    if len(styles_by_id) != len(styles):
        raise RuntimeError("duplicate StyleProfile id")
    for actor in actors:
        validate_schema(actor, ACTOR_SCHEMA)
        style = styles_by_id.get(actor["style_profile_id"])
        if style is None:
            raise RuntimeError(
                f"ActorSlotProfile references unknown style: {actor['style_profile_id']}"
            )
        validate_semantics(style, actor)

    payload = {
        "schema": "assetsstudio_style_slot_registry_v1",
        "updated": "2026-08-25",
        "styles": styles,
        "actors": actors,
        "sources": {
            "styles": [path.relative_to(ROOT).as_posix() for path in STYLE_PATHS],
            "actors": [path.relative_to(ROOT).as_posix() for path in ACTOR_PATHS],
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "ASSETSSTUDIO_STYLE_SLOT_REGISTRY_PASS "
        f"styles={len(styles)} actors={len(actors)} output={OUTPUT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
