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
    style = STYLE_PROFILES["western_fantasy_qstyle_soft3d_v1"]
    actor = ACTOR_PROFILES["default_adventurer_v2_slots_v1"]
    waist = find_slot(actor, "waist_accessory")
    prompt = compile_accessory_prompt(
        "rounded leather adventurer waist pouch", style, actor, waist
    )
    required_markers = [
        "waist_accessory",
        "0.59m wide",
        "reference image only as visual style",
        "exact right profile",
        "no wearer",
        "leather_brown #765133",
    ]
    missing = [marker for marker in required_markers if marker not in prompt]
    if missing:
        raise RuntimeError("compiled accessory prompt is missing: " + ", ".join(missing))

    ear = find_slot(actor, "EarPair")
    try:
        compile_accessory_prompt("new ears", style, actor, ear)
    except ValueError as exc:
        if "reuse_only" not in str(exc):
            raise
    else:
        raise RuntimeError("reuse_only EarPair was incorrectly accepted for image generation")

    tracked_candidate = (
        ROOT
        / "docs/workflows/assets/accessory_isolated_multiview_candidate_20260823.png"
    )
    report = analyze_turnaround(tracked_candidate, 3)
    if report["automatic_pass"]:
        raise RuntimeError("known inconsistent accessory candidate unexpectedly passed QA")

    print(
        "ASSETSSTUDIO_ACCESSORY_GENERATION_CONTRACT_PASS "
        f"style={style['id']} actor={actor['id']} slot={waist['slot_id']} "
        f"known_failure_gate={not report['automatic_pass']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
