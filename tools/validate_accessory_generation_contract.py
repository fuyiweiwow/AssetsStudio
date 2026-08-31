#!/usr/bin/env python3
"""Focused validation for profile-locked accessory generation contracts."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "model_test"))

from studio_local_generation_api import (  # noqa: E402
    ACTOR_PROFILES,
    STYLE_PROFILES,
    compile_accessory_prompt,
    find_slot,
)
from analyze_turnaround_sheet import analyze_turnaround  # noqa: E402


def main() -> int:
    style = STYLE_PROFILES["qstyle_anime_western_fantasy_no_face_v1"]
    actor = ACTOR_PROFILES["actor_core_0ef398ca_slots_v1"]
    waist = find_slot(actor, "waist_accessory")
    prompt = compile_accessory_prompt(
        "rounded leather adventurer waist pouch", style, actor, waist
    )
    required_markers = [
        "waist_accessory",
        "0.64m wide",
        "reference image only as visual style",
        "exact right profile",
        "no wearer",
        "warm_natural #765133",
    ]
    missing = [marker for marker in required_markers if marker not in prompt]
    if missing:
        raise RuntimeError("compiled accessory prompt is missing: " + ", ".join(missing))

    hair = find_slot(actor, "head_hair")
    try:
        compile_accessory_prompt("short hair shell", style, actor, hair)
    except ValueError as exc:
        if "no isolated generation reference" not in str(exc):
            raise
    else:
        raise RuntimeError("a slot without an isolated authority was incorrectly accepted")

    authority = ROOT / waist["generation_reference"]["path"]
    report = analyze_turnaround(authority, 4)
    if not report["automatic_pass"]:
        raise RuntimeError("current isolated accessory authority failed automatic QA")

    chibi3_style = STYLE_PROFILES["qstyle_anime_western_fantasy_chibi3_no_face_v1"]
    chibi3_actor = ACTOR_PROFILES["actor_core_chibi3_v9b_tpose_slots_v1"]
    chibi3_waist = find_slot(chibi3_actor, "waist_accessory")
    chibi3_prompt = compile_accessory_prompt(
        "rounded leather adventurer waist pouch",
        chibi3_style,
        chibi3_actor,
        chibi3_waist,
    )
    chibi3_markers = [
        "unbound static T-Pose fitting proxy",
        "0.606m wide",
        "do not invent bones",
        "actor_core_chibi3_source_v9b_seed20260830",
    ]
    chibi3_missing = [marker for marker in chibi3_markers if marker not in chibi3_prompt]
    if chibi3_missing:
        raise RuntimeError(
            "compiled Chibi3 T-Pose prompt is missing: " + ", ".join(chibi3_missing)
        )

    print(
        "ASSETSSTUDIO_ACCESSORY_GENERATION_CONTRACT_PASS "
        f"style={style['id']} actor={actor['id']} slot={waist['slot_id']} "
        f"authority_gate={report['automatic_pass']} tpose_actor={chibi3_actor['id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
