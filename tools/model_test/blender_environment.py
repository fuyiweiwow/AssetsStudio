"""Discover Blender without embedding a machine-specific installation path."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def discover_blender(explicit: Path | None = None) -> Path:
    configured = os.environ.get("BLENDER_PATH")
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)
    if configured:
        candidates.append(Path(configured))
    for command in ("blender.exe", "blender"):
        resolved = shutil.which(command)
        if resolved:
            candidates.append(Path(resolved))

    workspace_parent = REPOSITORY_ROOT.parent
    candidates.extend(
        path / "blender.exe"
        for path in sorted(workspace_parent.glob("blender-*"), reverse=True)
    )

    program_files = os.environ.get("ProgramFiles")
    if program_files:
        foundation = Path(program_files) / "Blender Foundation"
        if foundation.is_dir():
            candidates.extend(
                path / "blender.exe"
                for path in sorted(foundation.iterdir(), reverse=True)
                if path.is_dir()
            )

    checked: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        key = str(resolved).casefold()
        if key in seen:
            continue
        seen.add(key)
        checked.append(str(resolved))
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(
        "Blender was not found. Set BLENDER_PATH, add Blender to PATH, install it "
        "under Program Files, or place a blender-* portable directory beside the repository. "
        f"Checked: {checked}"
    )
