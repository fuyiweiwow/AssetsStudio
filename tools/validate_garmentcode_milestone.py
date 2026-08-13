"""Validate every checked-in file in a GarmentCode milestone manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "assetsstudio_garmentcode_short_sleeve_milestone_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    options = parser.parse_args()
    manifest_path = options.manifest.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA:
        raise RuntimeError(f"unexpected milestone schema: {payload.get('schema')}")
    root = manifest_path.parent
    listed: set[str] = set()
    total = 0
    for record in payload.get("files", []):
        relative = str(record["path"])
        if relative in listed or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise RuntimeError(f"unsafe or duplicate milestone path: {relative}")
        listed.add(relative)
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        size = path.stat().st_size
        if size != int(record["bytes"]):
            raise RuntimeError(f"size mismatch for {relative}: {size} != {record['bytes']}")
        digest = sha256(path)
        if digest != str(record["sha256"]).upper():
            raise RuntimeError(f"sha256 mismatch for {relative}: {digest}")
        total += size
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "HUMAN_REVIEW.md"}
    }
    if actual != listed:
        raise RuntimeError(
            f"milestone manifest coverage mismatch: missing={sorted(actual-listed)} "
            f"stale={sorted(listed-actual)}"
        )
    repository = root.parents[2]
    actor = repository / str(payload["actor"]["path"])
    if not actor.is_file() or sha256(actor) != str(payload["actor"]["sha256"]).upper():
        raise RuntimeError("Actor dependency is missing or has the wrong hash")

    provenance_targets = {
        "simulation/panel_membership.json": {
            "pattern_spec": root / "pattern/garment_specification.json",
            "sim_obj": root / "simulation/garment_sim.obj",
        },
        "simulation/panel_membership_initial.json": {
            "pattern_spec": root / "pattern/garment_specification.json",
            "sim_obj": root / "simulation/garment_boxmesh.obj",
        },
    }
    for relative, expected_targets in provenance_targets.items():
        provenance = json.loads((root / relative).read_text(encoding="utf-8"))
        for key, expected_target in expected_targets.items():
            reference = provenance.get(key, {})
            declared = Path(str(reference.get("path", "")))
            if declared.is_absolute() or ".." in declared.parts:
                raise RuntimeError(f"unsafe {key} provenance path in {relative}: {declared}")
            target = (repository / declared).resolve()
            if target != expected_target.resolve():
                raise RuntimeError(
                    f"wrong {key} provenance target in {relative}: {target}"
                )
            if not target.is_file() or sha256(target) != str(reference.get("sha256", "")).upper():
                raise RuntimeError(f"stale {key} provenance hash in {relative}")
    print(
        f"GARMENTCODE_MILESTONE_PASS files={len(listed)} bytes={total} "
        f"manifest={manifest_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
