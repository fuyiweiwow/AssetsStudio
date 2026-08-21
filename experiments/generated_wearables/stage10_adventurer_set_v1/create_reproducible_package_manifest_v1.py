from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "REPRODUCIBLE_PACKAGE_V1.json"
EXCLUDED_PARTS = {"__pycache__"}
SOURCE_SLOTS = [
    "head_hair",
    "torso_outer",
    "legs_outer",
    "waist_accessory",
    "feet_outer",
    "wrist_accessory",
    "back_accessory",
]
TEXT_EXTENSIONS = {".json", ".md", ".ps1", ".py"}


def canonical_payload(path: Path) -> tuple[bytes, str]:
    payload = path.read_bytes()
    if path.suffix.lower() in TEXT_EXTENSIONS:
        payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        return payload, "text_utf8_lf"
    return payload, "binary_exact"


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (
        path != OUTPUT
        and not any(part in EXCLUDED_PARTS for part in relative.parts)
        and path.suffix.lower() != ".blend1"
    )


def main() -> None:
    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and included(path))
    entries = []
    for path in files:
        payload, hash_mode = canonical_payload(path)
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "hash_mode": hash_mode,
            }
        )
    payload = {
        "schema": "assetslab_reproducible_generated_wearable_package_v1",
        "actor_class": "ChibiActorV1",
        "wearable_set": "AdventurerSetV1",
        "checkpoint": "V3 diagnostic baseline",
        "status": "reproducible_with_known_visual_blockers",
        "authoritative_blend": "milestone/adventurer_set_workflow_v3.blend",
        "source_slots": SOURCE_SLOTS,
        "external_dependencies": {
            "git_lfs": "required for blend, glb, gif and png payloads",
            "blender": "4.5.10 LTS; set BLENDER_EXE or pass -BlenderExe",
            "hunyuan_runtime": "official Hunyuan3D-2 checkout, Python 3.10",
            "hunyuan_model": "local Hunyuan3D-2mv weights; set HUNYUAN3D_SOURCE and HUNYUAN3D_2MV_MODEL",
            "model_weights_in_git": False,
        },
        "known_blockers": [
            "generated sleeve/torso self-intersection during animation",
            "rigid foot-bone boot binding rotates the sole and loses planted contact",
            "old Actor exposed-limb topology is coarse at close range",
        ],
        "required_files": entries,
        "file_count": len(entries),
        "package_bytes": sum(entry["bytes"] for entry in entries),
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT} with {len(entries)} files")


if __name__ == "__main__":
    main()
