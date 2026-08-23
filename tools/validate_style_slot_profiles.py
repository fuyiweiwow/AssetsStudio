#!/usr/bin/env python3
"""Validate reusable StyleProfile and ActorSlotProfile contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STYLE = ROOT / "references/style_profiles/western_fantasy_qstyle_soft3d_v1.json"
DEFAULT_ACTOR = ROOT / "references/actor_v2/default_adventurer_v2/actor_slot_profile_v1.json"
STYLE_SCHEMA = ROOT / "schemas/style-profile.v1.schema.json"
ACTOR_SCHEMA = ROOT / "schemas/actor-slot-profile.v1.schema.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(instance: dict, schema_path: Path) -> None:
    validator = Draft202012Validator(load_json(schema_path))
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        lines = [
            f"{'.'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        ]
        raise RuntimeError(
            f"{schema_path.name} validation failed:\n" + "\n".join(lines)
        )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_semantics(style: dict, actor: dict) -> None:
    if actor["style_profile_id"] != style["id"]:
        raise RuntimeError(
            "ActorSlotProfile style_profile_id does not match StyleProfile id"
        )

    lower, upper = style["proportions"]["target_total_heads_range"]
    measured = actor["measurements"]["total_heads"]
    if lower > upper or not lower <= measured <= upper:
        raise RuntimeError(
            f"actor total_heads={measured} is outside style target range [{lower}, {upper}]"
        )

    authority_ids: set[str] = set()
    for authority in style["authorities"]:
        if authority["id"] in authority_ids:
            raise RuntimeError(f"duplicate style authority id: {authority['id']}")
        authority_ids.add(authority["id"])
        path = ROOT / authority["path"]
        if authority["required"] and not path.is_file():
            raise FileNotFoundError(path)
        if path.is_file() and sha256(path).lower() != authority["sha256"].lower():
            raise RuntimeError(f"style authority hash changed: {authority['path']}")

    slot_ids: set[str] = set()
    validated_slots = 0
    for slot in actor["slots"]:
        slot_id = slot["slot_id"]
        if slot_id in slot_ids:
            raise RuntimeError(f"duplicate actor slot id: {slot_id}")
        slot_ids.add(slot_id)
        if slot["status"] == "validated":
            validated_slots += 1
        parent_bones = set(slot["attachment"]["parent_bones"])
        for anchor in slot["attachment"]["anchors"]:
            if anchor["parent_bone"] not in parent_bones:
                raise RuntimeError(
                    f"slot {slot_id} anchor {anchor['id']} uses undeclared parent bone"
                )
        for evidence in slot["evidence"]:
            if evidence["tracked"] and not (ROOT / evidence["path"]).is_file():
                raise FileNotFoundError(ROOT / evidence["path"])
        generation_reference = slot.get("generation_reference")
        if generation_reference:
            reference_path = ROOT / generation_reference["path"]
            if not reference_path.is_file():
                raise FileNotFoundError(reference_path)
            if sha256(reference_path).lower() != generation_reference["sha256"].lower():
                raise RuntimeError(
                    f"slot generation reference hash changed: {generation_reference['path']}"
                )

    required_slots = {
        "EarPair",
        "head_hair",
        "waist_accessory",
        "hand_prop_l",
        "hand_prop_r",
    }
    missing = sorted(required_slots - slot_ids)
    if missing:
        raise RuntimeError(
            "ActorSlotProfile is missing required generation slots: "
            + ", ".join(missing)
        )
    if validated_slots < 4:
        raise RuntimeError(
            "ActorSlotProfile must preserve at least four previously validated slots"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", type=Path, default=DEFAULT_STYLE)
    parser.add_argument("--actor", type=Path, default=DEFAULT_ACTOR)
    args = parser.parse_args()

    style = load_json(args.style)
    actor = load_json(args.actor)
    validate_schema(style, STYLE_SCHEMA)
    validate_schema(actor, ACTOR_SCHEMA)
    validate_semantics(style, actor)
    print(
        "ASSETSSTUDIO_STYLE_SLOT_PROFILE_PASS "
        f"style={style['id']} actor={actor['id']} slots={len(actor['slots'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
