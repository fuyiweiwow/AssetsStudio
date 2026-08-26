#!/usr/bin/env python3
"""Validate the current modular local-generation workflow only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_TEST = ROOT / "tools" / "model_test"
PUBLISHED_SEED_ROOT = ROOT / "references" / "style_profiles" / "published_seeds"
REQUIRED = [
    "README.md",
    "docs/CURRENT_WORKFLOW.md",
    "docs/ENVIRONMENT.md",
    "docs/ACTOR_CORE_TRAINING.md",
    "docs/ACCURIG_HANDOFF.md",
    "docs/ANIMATION_RETARGET.md",
    "start-local-generation-studio.bat",
    "studio/src/App.tsx",
    "studio/src/components/TurnaroundGenerator.tsx",
    "studio/src/components/GeneratedModelPreview.tsx",
    "studio/src/lib/local-generation.ts",
    "studio/src/lib/style-slot-profiles.ts",
    "studio/src/generated/style-slot-profiles.json",
    "references/style_profiles/qstyle_anime_western_fantasy_no_face_v1.json",
    "references/style_profiles/published_seeds/README.md",
    "references/actor_core/actor_core_0ef398ca/actor_slot_profile_v1.json",
    "references/actor_core/rig_landmark_profiles/chibi_featureless_v1.json",
    "schemas/strip_to_actor_core_pair.schema.json",
    "tools/model_test/run_comfy_flux2_klein.py",
    "tools/model_test/build_actor_core_repair_mask.py",
    "tools/model_test/build_actor_core_silhouette_guide.py",
    "tools/model_test/normalize_turnaround_panel_centers.py",
    "tools/model_test/register_strip_to_actor_core_pair.py",
    "tools/model_test/export_strip_to_actor_core_dataset.py",
    "tools/model_test/export_strip_to_actor_core_diffsynth_dataset.py",
    "tools/model_test/run_hunyuan3d_mv_shape.py",
    "tools/model_test/studio_local_generation_api.py",
    "tools/model_test/process_actor_core_accurig_rig.py",
    "tools/model_test/retarget_mixamo_to_actor_core.py",
    "tools/model_test/build_animation_preview_gifs.py",
    "tools/start_studio_local_generation.ps1",
    "tools/setup_flux2_actor_core_training.ps1",
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
    "tools/model_test/build_actor_core_repair_mask.py",
    "tools/model_test/build_actor_core_silhouette_guide.py",
    "tools/model_test/normalize_turnaround_panel_centers.py",
    "tools/model_test/register_strip_to_actor_core_pair.py",
    "tools/model_test/export_strip_to_actor_core_dataset.py",
    "tools/model_test/export_strip_to_actor_core_diffsynth_dataset.py",
    "tools/model_test/run_hunyuan3d_mv_shape.py",
    "tools/model_test/studio_local_generation_api.py",
    "tools/model_test/process_actor_core_accurig_rig.py",
    "tools/model_test/retarget_mixamo_to_actor_core.py",
    "tools/model_test/build_animation_preview_gifs.py",
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


def validate_published_style_seeds() -> int:
    expected_ids = {
        "74e7accb7e54400aada8f8807f111001",
        "d70bce2777f44dfcadb07e030c69b30b",
    }
    found_ids: set[str] = set()
    for seed_path in PUBLISHED_SEED_ROOT.glob("*/seed.json"):
        raw = seed_path.read_text(encoding="utf-8")
        if ":\\" in raw or "workspace/" in raw or "workspace\\" in raw:
            raise RuntimeError(f"published seed contains a machine-local path: {seed_path}")
        payload = json.loads(raw)
        asset_id = payload.get("asset_id")
        if payload.get("schema") != "assetsstudio_published_style_seed_v1":
            raise RuntimeError(f"unsupported published seed schema: {seed_path}")
        if asset_id != seed_path.parent.name or asset_id in found_ids:
            raise RuntimeError(f"invalid or duplicate published seed id: {seed_path}")
        if payload.get("style_profile_id") != "qstyle_anime_western_fantasy_no_face_v1":
            raise RuntimeError(f"published seed uses a non-current StyleProfile: {asset_id}")
        if payload.get("review_status") != "approved" or not payload.get("portable"):
            raise RuntimeError(f"published seed is not approved and portable: {asset_id}")
        for key in ("artifact", "metrics"):
            contract = payload[key]
            source = seed_path.parent / contract["path"]
            if not source.is_file():
                raise RuntimeError(f"published seed {key} is missing: {asset_id}")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if digest != contract["sha256"]:
                raise RuntimeError(f"published seed {key} hash mismatch: {asset_id}")
        metrics = json.loads(
            (seed_path.parent / payload["metrics"]["path"]).read_text(encoding="utf-8")
        )
        if metrics.get("image") != "style_seed.png" or not metrics.get("automatic_pass"):
            raise RuntimeError(f"published seed metrics are not portable/passing: {asset_id}")
        found_ids.add(asset_id)
    if found_ids != expected_ids:
        raise RuntimeError(
            "published style seed set mismatch: "
            f"expected={sorted(expected_ids)} actual={sorted(found_ids)}"
        )
    return len(found_ids)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-models", action="store_true")
    parser.add_argument("--check-local-assets", action="store_true")
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
    require_marker("studio/src/components/TurnaroundGenerator.tsx", "自动适配并生成预览")
    require_marker("tools/model_test/studio_local_generation_api.py", '"rig-intakes"')
    require_marker("tools/model_test/studio_local_generation_api.py", '"animation-previews"')
    require_marker("tools/model_test/studio_local_generation_api.py", '"training-pairs"')
    require_marker("tools/model_test/studio_local_generation_api.py", '"training-previews"')
    require_marker("tools/model_test/run_comfy_flux2_klein.py", '"LoraLoaderModelOnly"')
    require_marker("tools/setup_flux2_actor_core_training.ps1", "modelscope.cli.cli download")
    require_marker(
        "tools/model_test/studio_local_generation_api.py",
        '"teacher_backend_required": False',
    )
    require_marker("tools/model_test/retarget_mixamo_to_actor_core.py", "hands_not_together_behind_back")
    require_marker("tools/start_studio_local_generation.ps1", "$env:VIRTUAL_ENV")
    require_marker(
        "tools/cleanup_current_workflow.ps1",
        "76CDFB3B70A357625DC5CFEEA95F033D49A06871DCF1BE4477255DE0DF4FE065",
    )
    require_marker("tools/model_test/studio_local_generation_api.py", "sync_published_style_seeds")
    require_marker(
        "tools/model_test/studio_local_generation_api.py",
        "approved_style_seed_contract_and_proportion_gate",
    )
    require_marker(
        "schemas/strip_to_actor_core_pair.schema.json",
        "assetsstudio_strip_to_actor_core_pair_v1",
    )
    require_marker(
        "tools/model_test/export_strip_to_actor_core_dataset.py",
        'control_directory =',
    )
    require_marker(
        "tools/model_test/export_strip_to_actor_core_diffsynth_dataset.py",
        '"edit_image": [source_name]',
    )

    published_seeds = validate_published_style_seeds()

    animation_assets = 0
    if args.check_local_assets:
        animation_root = ROOT / "workspace" / "local_animation_library"
        manifests = sorted(animation_root.glob("*/asset_manifest.json"))
        if not manifests:
            raise RuntimeError("local animation library is empty")
        for manifest_path in manifests:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if payload.get("schema") != "assetsstudio_local_animation_asset_v1":
                raise RuntimeError(f"unsupported local animation manifest: {manifest_path}")
            source = manifest_path.parent / payload["source_filename"]
            if not source.is_file():
                raise RuntimeError(f"local animation source is missing: {source}")
            if hashlib.sha256(source.read_bytes()).hexdigest() != payload["sha256"]:
                raise RuntimeError(f"local animation source hash mismatch: {source}")
            animation_assets += 1

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
        f"files={len(REQUIRED)} published_seeds={published_seeds} "
        f"animation_assets={animation_assets} models_checked={args.check_models}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
