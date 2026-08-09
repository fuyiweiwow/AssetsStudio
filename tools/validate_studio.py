"""Validate the curated AssetsStudio milestone contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED = [
    "milestones/body/chibi_actor_mixamo_walk_v1.blend",
    "milestones/body/actor_accurig_input.fbx",
    "milestones/body/release_manifest.json",
    "milestones/body/animation_sources/mixamo_standard_walk.fbx",
    "milestones/body/animation_sources/mixamo_run.fbx",
    "milestones/body/ear_source/miku_chibi_ear_source.fbx",
    "milestones/body/eye_textures/eye_left.png",
    "milestones/body/eye_textures/eye_right.png",
    "milestones/hair/Blender-Chloe_Hair.blend",
    "milestones/hair/male_source/Blend_Hair.blend",
    "milestones/hair/hair_component_catalog_v1.json",
    "milestones/hair/hair_random_pool_v1.json",
    "milestones/face/runtime_chibi_eyes_ears_walk_v1/runtime_manifest.json",
    "milestones/face/eye_assembly_v1/crops_half/imagegen_eye_assembly_L.png",
    "milestones/face/eye_assembly_v1/crops_closed/imagegen_eye_assembly_L.png",
    "milestones/tops/actor_native_tshirt_v5/actor_native_tshirt_body_component_v5_upperarm_coverage.blend",
    "milestones/tops/actor_native_tshirt_v5/manifest.json",
    "milestones/pants/native_control_v0/native_control_shorts_v0.blend",
    "milestones/pants/native_control_v0/manifest.json",
    "milestones/shoes/cartoon_sneaker_v10/actor_cartoon_sneaker_fbx_v10_length_expanded.blend",
    "milestones/shoes/cartoon_sneaker_v10/manifest.json",
    "references/shoes/cartoon_sneaker/source/Shoessneakers.fbx",
    "references/shoes/cartoon_sneaker/reference_manifest.json",
]


def main() -> int:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError("missing required milestone files:\n" + "\n".join(missing))

    status = json.loads((ROOT / "docs" / "ASSET_STATUS.json").read_text(encoding="utf-8"))
    records = status.get("milestones", [])
    ids = [record.get("id") for record in records]
    if len(ids) != len(set(ids)) or len(ids) != 6:
        raise RuntimeError("asset status must contain six unique milestone ids")
    for record in records:
        path = ROOT / str(record["path"])
        if not path.is_file():
            raise FileNotFoundError(path)

    for manifest in ROOT.rglob("*.json"):
        json.loads(manifest.read_text(encoding="utf-8"))

    stale_roots = ("E:\\\\WorkProject\\\\AssetsLab", "D:\\\\Apps\\\\CodeXApp\\\\Tests\\\\AssetsLab")
    stale = []
    for manifest in ROOT.rglob("*.json"):
        content = manifest.read_text(encoding="utf-8")
        if any(root in content for root in stale_roots):
            stale.append(str(manifest.relative_to(ROOT)))
    if stale:
        raise RuntimeError("stale AssetsLab absolute paths:\n" + "\n".join(stale))

    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts)
    total = sum(path.stat().st_size for path in files)
    largest = max(files, key=lambda path: path.stat().st_size)
    if largest.stat().st_size >= 100 * 1024 * 1024:
        raise RuntimeError(f"GitHub 100 MB file limit exceeded: {largest}")
    digest = hashlib.sha256((ROOT / "docs" / "ASSET_STATUS.json").read_bytes()).hexdigest()[:12]
    print(
        f"ASSETSSTUDIO_VALIDATE_PASS milestones={len(records)} files={len(files)} "
        f"bytes={total} largest={largest.relative_to(ROOT)} status_sha256={digest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
