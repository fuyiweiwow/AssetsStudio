#!/usr/bin/env python3
"""Focused validation for the F009 Studio local-generation integration."""

from __future__ import annotations

import argparse
import json
import py_compile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "start-local-generation-studio.bat",
    "docs/features/F009-local-prompt-turnaround-studio.md",
    "docs/workflows/studio_local_turnaround_setup.md",
    "docs/workflows/local_reference_turnaround_validation_2026-08-23.md",
    "studio/src/components/TurnaroundGenerator.tsx",
    "studio/src/lib/local-generation.ts",
    "studio/src/lib/local-generation.test.ts",
    "tools/model_test/run_comfy_flux2_klein.py",
    "tools/model_test/studio_local_generation_api.py",
    "tools/start_studio_local_generation.ps1",
    "tools/build_studio_style_slot_registry.py",
    "tools/validate_accessory_generation_contract.py",
    "studio/src/generated/style-slot-profiles.json",
    "docs/workflows/assets/studio_prompt_turnaround_e2e_20260823.png",
    "docs/workflows/assets/studio_prompt_turnaround_e2e_20260823.metrics.json",
]
MODELS = [
    Path(r"E:\Env\ComfyUI\models\diffusion_models\flux-2-klein-4b-fp8.safetensors"),
    Path(r"E:\Env\ComfyUI\models\text_encoders\qwen_3_4b.safetensors"),
    Path(r"E:\Env\ComfyUI\models\vae\flux2-vae.safetensors"),
]


def require_marker(relative: str, marker: str) -> None:
    content = (ROOT / relative).read_text(encoding="utf-8")
    if marker not in content:
        raise RuntimeError(f"missing marker {marker!r} in {relative}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-models", action="store_true")
    args = parser.parse_args()

    missing = [relative for relative in REQUIRED if not (ROOT / relative).is_file()]
    if missing:
        raise RuntimeError("missing F009 files:\n" + "\n".join(missing))
    if args.check_models:
        missing_models = [str(path) for path in MODELS if not path.is_file()]
        if missing_models:
            raise RuntimeError("missing local FLUX.2 files:\n" + "\n".join(missing_models))

    require_marker("studio/src/App.tsx", "本地三视图")
    require_marker("studio/vite.config.ts", '"/api/local-generation"')
    require_marker("tools/model_test/studio_local_generation_api.py", '"visual_review_required"')
    require_marker("tools/model_test/studio_local_generation_api.py", '"/api/accessories"')
    require_marker("tools/start_studio_local_generation.ps1", "--disable-pinned-memory")
    require_marker("start-local-generation-studio.bat", "Start-Process $url")
    require_marker("docs/features/README.md", "F009")

    py_compile.compile(
        str(ROOT / "tools/model_test/studio_local_generation_api.py"), doraise=True
    )
    py_compile.compile(
        str(ROOT / "tools/validate_accessory_generation_contract.py"), doraise=True
    )
    metrics = json.loads(
        (
            ROOT
            / "docs/workflows/assets/studio_prompt_turnaround_e2e_20260823.metrics.json"
        ).read_text(encoding="utf-8")
    )
    if not metrics.get("automatic_pass"):
        raise RuntimeError("tracked Studio E2E turnaround metrics do not pass")
    print(
        "ASSETSSTUDIO_LOCAL_GENERATION_VALIDATE_PASS "
        f"files={len(REQUIRED)} models_checked={args.check_models}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
