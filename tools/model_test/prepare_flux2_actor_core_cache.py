#!/usr/bin/env python3
"""Build the split-training cache for approved FLUX.2 Actor Core pairs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from train_flux2_actor_core_lora import LORA_TARGET_MODULES, discover_directory


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--max-pixels", type=int, default=589824)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    comfy_root = discover_directory(
        "ASSETSSTUDIO_COMFY_ROOT",
        [ROOT.parent / "ComfyUI", Path.home() / "ComfyUI"],
        Path("main.py"),
    )
    if importlib.util.find_spec("torch") is None:
        python_candidates = [
            comfy_root / ".venv" / "Scripts" / "python.exe",
            comfy_root / "venv" / "Scripts" / "python.exe",
        ]
        training_python = next(
            (candidate for candidate in python_candidates if candidate.is_file()), None
        )
        if training_python is None:
            raise FileNotFoundError(
                "PyTorch is unavailable and no ComfyUI Python environment was found"
            )
        return subprocess.run(
            [str(training_python), str(Path(__file__).resolve()), *sys.argv[1:]],
            cwd=ROOT,
            check=False,
        ).returncode

    diffsynth_root = discover_directory(
        "ASSETSSTUDIO_DIFFSYNTH_ROOT",
        [ROOT / "workspace" / "runtime" / "DiffSynth-Studio"],
        Path("examples/flux2/model_training/train.py"),
    )
    model_root = discover_directory(
        "ASSETSSTUDIO_FLUX2_BASE_ROOT",
        [
            ROOT
            / "workspace"
            / "models"
            / "modelscope"
            / "black-forest-labs"
            / "FLUX.2-klein-base-4B"
        ],
        Path("tokenizer/tokenizer.json"),
    )
    dataset_dir = args.dataset_dir.expanduser().resolve()
    metadata_path = dataset_dir / "metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(metadata_path)
    cache_dir = args.cache_dir.expanduser().resolve()
    if cache_dir.exists() and any(cache_dir.iterdir()):
        raise RuntimeError(f"Cache directory is not empty: {cache_dir}")

    text_encoder = comfy_root / "models" / "text_encoders" / "qwen_3_4b.safetensors"
    vae = comfy_root / "models" / "vae" / "flux2-vae.safetensors"
    for model_path in (text_encoder, vae):
        if not model_path.is_file():
            raise FileNotFoundError(model_path)
    tokenizer_path = model_root / "tokenizer"
    train_script = diffsynth_root / "examples" / "flux2" / "model_training" / "train.py"
    command = [
        sys.executable,
        str(train_script),
        "--dataset_base_path",
        str(dataset_dir),
        "--dataset_metadata_path",
        str(metadata_path),
        "--data_file_keys",
        "image,edit_image",
        "--extra_inputs",
        "edit_image",
        "--dataset_repeat",
        "1",
        "--dataset_num_workers",
        "0",
        "--model_paths",
        json.dumps([str(text_encoder), str(vae)]),
        "--tokenizer_path",
        str(tokenizer_path),
        "--output_path",
        str(cache_dir),
        "--lora_base_model",
        "dit",
        "--lora_target_modules",
        LORA_TARGET_MODULES,
        "--lora_rank",
        str(args.lora_rank),
        "--max_pixels",
        str(args.max_pixels),
        "--use_gradient_checkpointing",
        "--task",
        "sft:data_process",
    ]
    print(f"ComfyRoot={comfy_root}", flush=True)
    print(f"DiffSynthRoot={diffsynth_root}", flush=True)
    print(f"DatasetDir={dataset_dir}", flush=True)
    print(f"CacheDir={cache_dir}", flush=True)
    if args.dry_run:
        return 0
    environment = os.environ.copy()
    environment["DIFFSYNTH_SKIP_DOWNLOAD"] = "True"
    return subprocess.run(
        command,
        cwd=diffsynth_root,
        env=environment,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
