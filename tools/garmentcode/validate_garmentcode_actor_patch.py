"""Verify the pinned GarmentCode checkout exposes Actor-specific sleeve fields."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


PINNED_COMMIT = "d449629979028123a5c4dc9e732a2ec19b7fce31"
WARP_PINNED_COMMIT = "63baf6855efdd89b2834b74640f84b3bb0d86b50"
REQUIRED_MARKERS = {
    "assets/garment_programs/bodice.py": ("actor_sleeve_connecting_width",),
    "assets/garment_programs/sleeves.py": (
        "actor_sleeve_cuff_circumference",
        "actor_sleeve_length",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--garmentcode-root", required=True, type=Path)
    options = parser.parse_args()
    root = options.garmentcode_root.resolve()
    if not (root / ".git").exists():
        raise RuntimeError(f"not a GarmentCode checkout: {root}")
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    if commit != PINNED_COMMIT:
        raise RuntimeError(f"GarmentCode commit mismatch: {commit} != {PINNED_COMMIT}")
    for relative, markers in REQUIRED_MARKERS.items():
        source = (root / relative).read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in source]
        if missing:
            raise RuntimeError(f"missing Actor field support in {relative}: {missing}")
    warp_root = root.parent / "NvidiaWarp-GarmentCode"
    if not (warp_root / ".git").exists():
        raise RuntimeError(f"missing sibling Warp checkout: {warp_root}")
    warp_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=warp_root, text=True
    ).strip()
    if warp_commit != WARP_PINNED_COMMIT:
        raise RuntimeError(
            f"Warp commit mismatch: {warp_commit} != {WARP_PINNED_COMMIT}"
        )
    print("GARMENTCODE_ACTOR_PATCH_PASS")
    print(f"root={root}")
    print(f"commit={commit}")
    print(f"warp_root={warp_root}")
    print(f"warp_commit={warp_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
