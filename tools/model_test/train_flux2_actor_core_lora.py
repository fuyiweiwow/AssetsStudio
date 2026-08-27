#!/usr/bin/env python3
"""Launch the local FLUX.2 Actor Core LoRA trainer with discovered paths."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LORA_TARGET_MODULES = ",".join(
    [
        "to_q",
        "to_k",
        "to_v",
        "to_out.0",
        "add_q_proj",
        "add_k_proj",
        "add_v_proj",
        "to_add_out",
        "linear_in",
        "linear_out",
        "to_qkv_mlp_proj",
        *[
            f"single_transformer_blocks.{index}.attn.to_out"
            for index in range(20)
        ],
    ]
)


def discover_directory(
    environment_name: str, candidates: list[Path], marker: Path
) -> Path:
    configured = os.environ.get(environment_name)
    search = ([Path(configured)] if configured else []) + candidates
    for candidate in search:
        resolved = candidate.expanduser().resolve()
        if resolved.is_dir() and (resolved / marker).is_file():
            return resolved
    raise FileNotFoundError(
        f"Unable to discover {environment_name}; expected marker {marker}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-repeat", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-pixels", type=int, default=393216)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    comfy_root = discover_directory(
        "ASSETSSTUDIO_COMFY_ROOT",
        [ROOT.parent / "ComfyUI", Path.home() / "ComfyUI"],
        Path("main.py"),
    )
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
        Path("transformer/diffusion_pytorch_model.safetensors"),
    )
    cache_dir = args.cache_dir.expanduser().resolve()
    if not cache_dir.is_dir() or not list(cache_dir.rglob("*.pth")):
        raise FileNotFoundError(f"No cached training samples found in {cache_dir}")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    train_script = diffsynth_root / "examples/flux2/model_training/train.py"
    model_path = model_root / "transformer/diffusion_pytorch_model.safetensors"
    tokenizer_path = model_root / "tokenizer"
    if not tokenizer_path.is_dir():
        raise FileNotFoundError(tokenizer_path)

    command = [
        sys.executable,
        str(train_script),
        "--dataset_base_path",
        str(cache_dir),
        "--dataset_repeat",
        str(args.dataset_repeat),
        "--dataset_num_workers",
        "0",
        "--model_paths",
        json.dumps([str(model_path)]),
        "--tokenizer_path",
        str(tokenizer_path),
        "--learning_rate",
        "0.0001",
        "--num_epochs",
        str(args.epochs),
        "--output_path",
        str(output_dir),
        "--remove_prefix_in_ckpt",
        "pipe.dit.",
        "--lora_base_model",
        "dit",
        "--lora_target_modules",
        LORA_TARGET_MODULES,
        "--lora_rank",
        str(args.lora_rank),
        "--use_gradient_checkpointing",
        "--max_pixels",
        str(args.max_pixels),
        "--task",
        "sft:train",
    ]
    print(f"ComfyRoot={comfy_root}", flush=True)
    print(f"DiffSynthRoot={diffsynth_root}", flush=True)
    print(f"ModelRoot={model_root}", flush=True)
    print(f"CacheDir={cache_dir}", flush=True)
    print(f"OutputDir={output_dir}", flush=True)
    if args.dry_run:
        return 0
    return subprocess.run(command, cwd=diffsynth_root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
