"""Discover a usable local Hunyuan3D source tree and shape model.

Explicit CLI values remain authoritative.  Otherwise the active machine is
searched through environment variables, the repository's sibling experiment
directory, and common ModelScope/Hugging Face cache layouts.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPOSITORY_ROOT.parent


def _unique(paths: Iterable[Path | None]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for candidate in paths:
        if candidate is None:
            continue
        resolved = candidate.expanduser().resolve()
        key = str(resolved).casefold()
        if key not in seen:
            seen.add(key)
            result.append(resolved)
    return result


def _environment_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


def discover_code_root(explicit: Path | None = None) -> Path:
    candidates = _unique(
        [
            explicit,
            _environment_path("HUNYUAN3D_SOURCE"),
            TESTS_ROOT / "Hunyuan3D_Experiment" / "Hunyuan3D-2-main",
            TESTS_ROOT / "Hunyuan3D_Experiment" / "Hunyuan3D-2.1-source",
            TESTS_ROOT / "Hunyuan3D-2",
        ]
    )
    for candidate in candidates:
        if (candidate / "hy3dgen" / "shapegen").is_dir():
            return candidate
    checked = "\n  - ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "No usable Hunyuan3D source tree was found. Set HUNYUAN3D_SOURCE "
        f"or pass --code-root. Checked:\n  - {checked}"
    )


def discover_model_root(explicit: Path | None = None) -> Path:
    home = Path.home()
    candidates = _unique(
        [
            explicit,
            _environment_path("HUNYUAN3D_MODEL_ROOT"),
            TESTS_ROOT
            / "Hunyuan3D_Experiment"
            / "local_models"
            / "Hunyuan3D-2mv",
            home
            / ".cache"
            / "modelscope"
            / "hub"
            / "models"
            / "Tencent-Hunyuan"
            / "Hunyuan3D-2mv",
            home
            / ".cache"
            / "huggingface"
            / "hub"
            / "models--tencent--Hunyuan3D-2mv"
            / "snapshots",
        ]
    )
    for candidate in candidates:
        if any(_is_shape_subfolder(path) for path in candidate.glob("hunyuan3d-dit-v2-mv*")):
            return candidate
        if candidate.name == "snapshots" and candidate.is_dir():
            for snapshot in candidate.iterdir():
                if snapshot.is_dir() and any(
                    _is_shape_subfolder(path)
                    for path in snapshot.glob("hunyuan3d-dit-v2-mv*")
                ):
                    return snapshot
    checked = "\n  - ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "No usable Hunyuan3D-2mv model was found. Prefer a ModelScope local "
        "download, set HUNYUAN3D_MODEL_ROOT, or pass --model. "
        f"Checked:\n  - {checked}"
    )


def _is_shape_subfolder(path: Path) -> bool:
    split_root = path / "split_components"
    return (path / "config.yaml").is_file() and (
        (path / "model.fp16.ckpt").is_file()
        or all((split_root / name).is_file() for name in ("model.pt", "vae.pt", "conditioner.pt"))
    )


def discover_subfolder(model_root: Path, requested: str | None = None) -> str:
    names = [
        requested,
        "hunyuan3d-dit-v2-mv-turbo",
        "hunyuan3d-dit-v2-mv-fast",
        "hunyuan3d-dit-v2-mv",
    ]
    for name in dict.fromkeys(name for name in names if name):
        if _is_shape_subfolder(model_root / name):
            return name
    raise FileNotFoundError(
        f"No Hunyuan3D-2mv checkpoint subfolder was found under {model_root}"
    )
