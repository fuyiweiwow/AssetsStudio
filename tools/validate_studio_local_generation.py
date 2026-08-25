#!/usr/bin/env python3
"""Validate the current modular local-generation workflow only."""

from __future__ import annotations

import argparse
import json
import os
import py_compile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_TEST = ROOT / "tools" / "model_test"
REQUIRED = [
    "README.md",
    "docs/CURRENT_WORKFLOW.md",
    "docs/ENVIRONMENT.md",
    "docs/ACCURIG_HANDOFF.md",
    "start-local-generation-studio.bat",
    "studio/src/App.tsx",
    "studio/src/components/TurnaroundGenerator.tsx",
    "studio/src/components/GeneratedModelPreview.tsx",
    "studio/src/lib/local-generation.ts",
    "studio/src/lib/style-slot-profiles.ts",
    "studio/src/generated/style-slot-profiles.json",
    "references/style_profiles/qstyle_anime_western_fantasy_no_face_v1.json",
    "references/actor_core/actor_core_0ef398ca/actor_slot_profile_v1.json",
    "references/actor_core/rig_landmark_profiles/chibi_featureless_v1.json",
    "tools/model_test/run_comfy_flux2_klein.py",
    "tools/model_test/run_hunyuan3d_mv_shape.py",
    "tools/model_test/studio_local_generation_api.py",
    "tools/model_test/process_actor_core_accurig_rig.py",
    "tools/start_studio_local_generation.ps1",
    "tools/cleanup_current_workflow.ps1",
]
PYTHON_SOURCES = [
    "tools/build_studio_style_slot_registry.py",
    "tools/validate_accessory_generation_contract.py",
    "tools/validate_style_slot_profiles.py",
    "tools/model_test/analyze_turnaround_sheet.py",
    "tools/model_test/blender_environment.py",
    "tools/model_test/hunyuan_environment.py",
    "tools/model_test/run_comfy_flux2_klein.py",
    "tools/model_test/run_hunyuan3d_mv_shape.py",
    "tools/model_test/studio_local_generation_api.py",
    "tools/model_test/process_actor_core_accurig_rig.py",
]
COMFY_MODELS = [
    Path("models/diffusion_models/flux-2-klein-4b-fp8.safetensors"),
    Path("models/text_encoders/qwen_3_4b.safetensors"),
    Path("models/vae/flux2-vae.safetensors"),
]


def discover_comfy_root(requested: str | None) -> Path:
    candidates = [
        requested,
        os.environ.get("ASSETSSTUDIO_COMFY_ROOT"),
        ROOT.parent / "ComfyUI",
        Path.home() / "ComfyUI",
    ]
    for value in candidates:
        if not value:
            continue
        candidate = Path(value).expanduser().resolve()
        if (candidate / "main.py").is_file():
            return candidate
    raise RuntimeError(
        "ComfyUI was not found. Pass --comfy-root, set ASSETSSTUDIO_COMFY_ROOT, "
        "or place it beside AssetsStudio/in the user profile."
    )


def require_marker(relative: str, marker: str) -> None:
    if marker not in (ROOT / relative).read_text(encoding="utf-8"):
        raise RuntimeError(f"missing marker {marker!r} in {relative}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-models", action="store_true")
    parser.add_argument("--comfy-root")
    args = parser.parse_args()

    missing = [relative for relative in REQUIRED if not (ROOT / relative).is_file()]
    if missing:
        raise RuntimeError("missing current-workflow files:\n" + "\n".join(missing))

    for relative in PYTHON_SOURCES:
        py_compile.compile(str(ROOT / relative), doraise=True)

    registry = json.loads(
        (ROOT / "studio/src/generated/style-slot-profiles.json").read_text(encoding="utf-8")
    )
    if [item["id"] for item in registry["styles"]] != [
        "qstyle_anime_western_fantasy_no_face_v1"
    ]:
        raise RuntimeError("Studio registry contains a non-current StyleProfile")
    if [item["id"] for item in registry["actors"]] != [
        "actor_core_0ef398ca_slots_v1"
    ]:
        raise RuntimeError("Studio registry contains a non-current ActorSlotProfile")

    require_marker("studio/src/App.tsx", "CURRENT MODULAR WORKFLOW")
    require_marker("studio/src/components/TurnaroundGenerator.tsx", "选择骨骼 FBX")
    require_marker("tools/model_test/studio_local_generation_api.py", '"rig-intakes"')
    require_marker("tools/start_studio_local_generation.ps1", "$env:VIRTUAL_ENV")
    require_marker(
        "tools/cleanup_current_workflow.ps1",
        "76CDFB3B70A357625DC5CFEEA95F033D49A06871DCF1BE4477255DE0DF4FE065",
    )

    if args.check_models:
        comfy_root = discover_comfy_root(args.comfy_root)
        missing_models = [str(comfy_root / path) for path in COMFY_MODELS if not (comfy_root / path).is_file()]
        if missing_models:
            raise RuntimeError("missing local FLUX.2 files:\n" + "\n".join(missing_models))
        sys.path.insert(0, str(MODEL_TEST))
        from hunyuan_environment import discover_code_root, discover_model_root, discover_subfolder

        code_root = discover_code_root()
        model_root = discover_model_root()
        discover_subfolder(model_root)
        if not (code_root / "hy3dgen" / "rembg.py").is_file():
            raise RuntimeError("Hunyuan source tree is missing the official rembg wrapper")

    print(
        "ASSETSSTUDIO_CURRENT_WORKFLOW_PASS "
        f"files={len(REQUIRED)} models_checked={args.check_models}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
