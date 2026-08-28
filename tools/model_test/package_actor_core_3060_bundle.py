#!/usr/bin/env python3
"""Package the small, project-specific part of the RTX 3060 Actor Core line.

Large upstream FLUX.2 files are intentionally excluded.  The production setup
script fetches only missing files from ModelScope; the bundle carries the
trained LoRA, a fixed gate source, expected output, and reproducibility data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_with_record(source: Path, destination: Path, bundle_root: Path) -> dict:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {
        "path": destination.relative_to(bundle_root).as_posix(),
        "bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
    }


def copy_sanitized_report(source: Path, destination: Path, bundle_root: Path) -> dict:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["environment"]["comfy_root_discovery"] = "<discovered at runtime>"
    payload["turnaround_qa"]["image"] = "actor_core_seed20260865.png"
    payload["actor_core_shape_qa"]["image"] = "actor_core_seed20260865.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "path": destination.relative_to(bundle_root).as_posix(),
        "bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
    }


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lora", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-image", type=Path, required=True)
    parser.add_argument("--expected-report", type=Path, required=True)
    parser.add_argument("--zip", action="store_true")
    args = parser.parse_args()

    output = args.output.expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Bundle directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    lora_name = (
        "strip_to_actor_core_teacher_v6_distilled_native_canonical_5pair_e75_rank16.safetensors"
    )
    files = []
    files.append(
        copy_with_record(args.lora, output / "models" / lora_name, output)
    )
    files.append(
        copy_with_record(
            args.source,
            output / "sources" / "clean_holdout_short_male_boots.png",
            output,
        )
    )
    files.append(
        copy_with_record(
            args.expected_image,
            output / "expected" / "actor_core_seed20260865.png",
            output,
        )
    )
    files.append(
        copy_sanitized_report(
            args.expected_report,
            output / "expected" / "actor_core_seed20260865.report.json",
            output,
        )
    )
    lora_record = files[0]
    manifest = {
        "schema": "assetsstudio_actor_core_rtx3060_bundle_v1",
        "repository": {
            "remote": "https://github.com/fuyiweiwow/AssetsStudio.git",
            "ref": "main",
            "packaged_from_commit": git_commit(),
        },
        "boundary": {
            "teacher_gpu": "RTX 5070 Ti may train and curate weights/assets only",
            "production_gpu": "RTX 3060 12GB must run generation, automatic Gate, persistence and local-library intake",
            "base_models_included": False,
            "base_model_policy": "discover existing files first; download only missing files from ModelScope",
        },
        "lora": {
            "filename": lora_name,
            "bytes": lora_record["bytes"],
            "sha256": lora_record["sha256"],
            "training": "v6 distilled-native canonical 5-pair, rank 16, epoch 75",
        },
        "gate": {
            "source": "sources/clean_holdout_short_male_boots.png",
            "expected_image": "expected/actor_core_seed20260865.png",
            "expected_report": "expected/actor_core_seed20260865.report.json",
            "seed": 20260865,
            "lora_strength": 3.0,
            "width": 1536,
            "height": 768,
            "steps": 4,
            "cfg": 1.0,
            "manual_review_required": True,
        },
        "modelscope_sources": [
            {
                "model_id": "black-forest-labs/FLUX.2-klein-4b-fp8",
                "file": "flux-2-klein-4b-fp8.safetensors",
                "comfy_relative_path": "models/diffusion_models/flux-2-klein-4b-fp8.safetensors",
            },
            {
                "model_id": "Comfy-Org/flux2-klein-4B",
                "file": "split_files/text_encoders/qwen_3_4b.safetensors",
                "comfy_relative_path": "models/text_encoders/qwen_3_4b.safetensors",
                "role": "FLUX.2 text encoder; not Qwen-Image-Edit",
            },
            {
                "model_id": "Comfy-Org/flux2-klein-4B",
                "file": "split_files/vae/flux2-vae.safetensors",
                "comfy_relative_path": "models/vae/flux2-vae.safetensors",
            },
        ],
        "files": files,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    readme = """AssetsStudio Actor Core RTX 3060 validation bundle

This bundle intentionally excludes the large upstream FLUX.2 files. Pull the
repository main branch, extract this directory, and run from the repository:

  powershell -ExecutionPolicy Bypass -File tools/setup_actor_core_production.ps1 -BundleRoot <this-directory>

For the complete cold-start hardware Gate, stop ComfyUI on port 8190 first:

  powershell -ExecutionPolicy Bypass -File tools/run_actor_core_3060_validation.ps1 -BundleRoot <this-directory> -ColdStart

The setup command searches the environment first and silently downloads only
missing upstream files from ModelScope. The validation command does not accept
or publish an asset. It writes a local qualification record only after an RTX
3060 12GB cold start, 1536x768/4-step inference, automatic Gate, and saved-file
hash reload all pass. Visual review remains mandatory.
"""
    (output / "README.txt").write_text(readme, encoding="utf-8")
    if args.zip:
        archive = shutil.make_archive(str(output), "zip", root_dir=output.parent, base_dir=output.name)
        print(f"archive={archive}")
    print(f"bundle={output}")
    print(f"lora_sha256={lora_record['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
