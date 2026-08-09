"""Validate the exported Studio GLB model/rig/animation/Face contract."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


EXPECTED_BLINK_STATES = ("open", "half", "closed")
EXPECTED_BLINK_SCHEDULE = ("open", "half", "closed", "half", "open", "open", "open", "open")


def cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args()


def glb_json(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < 20:
        raise RuntimeError("GLB is too small")
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total_length != len(data):
        raise RuntimeError("invalid GLB header")
    offset = 12
    while offset < total_length:
        length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        payload = data[offset : offset + length]
        offset += length
        if chunk_type == 0x4E4F534A:
            return json.loads(payload.decode("utf-8").rstrip("\x00 "))
    raise RuntimeError("GLB has no JSON chunk")


def main() -> int:
    options = cli_args()
    document = glb_json(options.glb.resolve())
    manifest = json.loads(options.manifest.resolve().read_text(encoding="utf-8"))

    names = [str(material.get("name", "")) for material in document.get("materials", [])]
    expected_materials = {
        f"EyeAssemblyV1_{state.title()}_{side}"
        for state in EXPECTED_BLINK_STATES
        for side in ("L", "R")
    }
    missing_materials = expected_materials.difference(names)
    if missing_materials:
        raise RuntimeError(f"GLB is missing eye-state materials: {sorted(missing_materials)}")

    eye_states: list[str] = []
    unskinned_eye_nodes: list[str] = []
    hair_nodes: list[str] = []
    unskinned_hair_nodes: list[str] = []
    legacy_nodes: list[str] = []
    for node in document.get("nodes", []):
        name = str(node.get("name", ""))
        if name.startswith(("EyePackageV1_", "EyePackageV2_", "EyeBlinkV1_")):
            legacy_nodes.append(name)
        extras = node.get("extras", {})
        if isinstance(extras, dict) and extras.get("assetsstudio_blink_state"):
            eye_states.append(str(extras["assetsstudio_blink_state"]))
            if node.get("skin") is None:
                unskinned_eye_nodes.append(name)
        if isinstance(extras, dict) and extras.get("assetsstudio_component") == "hair":
            hair_nodes.append(name)
            if node.get("skin") is None:
                unskinned_hair_nodes.append(name)
    if legacy_nodes:
        raise RuntimeError(f"legacy eye nodes remain in GLB: {legacy_nodes}")
    if sorted(eye_states) != ["closed", "closed", "half", "half", "open", "open"]:
        raise RuntimeError(f"unexpected mutually exclusive eye states: {eye_states}")
    if unskinned_eye_nodes:
        raise RuntimeError(f"eye-state nodes must be skinned to the Actor rig: {unskinned_eye_nodes}")
    if hair_nodes != ["HairBundle_Female_Seed04"]:
        raise RuntimeError(f"unexpected first hair bundle nodes: {hair_nodes}")
    if unskinned_hair_nodes:
        raise RuntimeError(f"hair nodes must be skinned to the Actor rig: {unskinned_hair_nodes}")
    if not document.get("animations"):
        raise RuntimeError("GLB has no animation")

    if manifest.get("schema") != "assetsstudio_actor_preview_export_v1":
        raise RuntimeError("unexpected preview manifest schema")
    if manifest.get("rig", {}).get("head_bone") != "CC_Base_Head":
        raise RuntimeError("preview manifest has no authoritative head bone")
    face = manifest.get("face", {})
    if tuple(face.get("blink_states", [])) != EXPECTED_BLINK_STATES:
        raise RuntimeError("preview manifest blink states changed")
    if tuple(face.get("blink_schedule", [])) != EXPECTED_BLINK_SCHEDULE:
        raise RuntimeError("preview manifest blink schedule changed")
    hair = manifest.get("hair", {})
    if hair.get("bundle_id") != "female_chloe_seed_04_bangs04":
        raise RuntimeError("preview manifest has no first hair bundle")
    if hair.get("head_bone") != "CC_Base_Head":
        raise RuntimeError("preview manifest hair binding changed")
    if manifest.get("components", {}).get("hair") != ["HairBundle_Female_Seed04"]:
        raise RuntimeError("preview manifest hair component list changed")

    print(
        "ASSETSSTUDIO_ACTOR_PREVIEW_VALIDATION_PASS "
        f"eye_states={len(eye_states)} hair_nodes={len(hair_nodes)} materials={len(expected_materials)} animations={len(document['animations'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
