#!/usr/bin/env python3
"""Run a local FLUX.2 Klein Base Actor Core edit as a training diagnostic.

This is deliberately not the RTX 3060 production path. It loads only files
already present in the discovered ModelScope/ComfyUI environments and uses the
official disk-mapped low-memory strategy so a development GPU can compare
Base-LoRA behavior with the distilled production workflow.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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


def discover_file(environment_name: str, candidates: list[Path]) -> Path:
    configured = os.environ.get(environment_name)
    search = ([Path(configured)] if configured else []) + candidates
    for candidate in search:
        resolved = candidate.expanduser().resolve()
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(f"Unable to discover {environment_name}")


def reexec_in_comfy_python(comfy_root: Path) -> int | None:
    if importlib.util.find_spec("torch") is not None:
        return None
    candidates = [
        comfy_root / ".venv" / "Scripts" / "python.exe",
        comfy_root / "venv" / "Scripts" / "python.exe",
        comfy_root / "python_embeded" / "python.exe",
    ]
    python = next((path for path in candidates if path.is_file()), None)
    if python is None:
        raise FileNotFoundError(
            "PyTorch is unavailable and no ComfyUI Python environment was found"
        )
    return subprocess.run(
        [str(python), str(Path(__file__).resolve()), *sys.argv[1:]],
        cwd=ROOT,
        env={**os.environ, "DIFFSYNTH_SKIP_DOWNLOAD": "True"},
        check=False,
    ).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--lora", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--prompt")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260831)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--cfg-scale", type=float, default=4.0)
    parser.add_argument("--height", type=int, default=384)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument(
        "--vram-limit-gib",
        type=float,
        help="maximum allocated VRAM before offload; defaults to total VRAM minus 0.5 GiB",
    )
    args = parser.parse_args()

    comfy_root = discover_directory(
        "ASSETSSTUDIO_COMFY_ROOT",
        [ROOT.parent / "ComfyUI", Path.home() / "ComfyUI"],
        Path("main.py"),
    )
    reexec_result = reexec_in_comfy_python(comfy_root)
    if reexec_result is not None:
        return reexec_result

    diffsynth_root = discover_directory(
        "ASSETSSTUDIO_DIFFSYNTH_ROOT",
        [ROOT / "workspace" / "runtime" / "DiffSynth-Studio"],
        Path("diffsynth/pipelines/flux2_image.py"),
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
    text_encoder = discover_file(
        "ASSETSSTUDIO_FLUX2_TEXT_ENCODER",
        [comfy_root / "models" / "text_encoders" / "qwen_3_4b.safetensors"],
    )
    vae = discover_file(
        "ASSETSSTUDIO_FLUX2_VAE",
        [comfy_root / "models" / "vae" / "flux2-vae.safetensors"],
    )
    source = args.source.expanduser().resolve()
    lora = args.lora.expanduser().resolve()
    for required in (source, lora):
        if not required.is_file():
            raise FileNotFoundError(required)
    if args.prompt and args.prompt_file:
        parser.error("use either --prompt or --prompt-file")
    if args.prompt_file:
        prompt = args.prompt_file.read_text(encoding="utf-8").strip()
    elif args.prompt:
        prompt = args.prompt.strip()
    else:
        raise ValueError("--prompt or --prompt-file is required")

    os.environ["DIFFSYNTH_SKIP_DOWNLOAD"] = "True"
    sys.path.insert(0, str(diffsynth_root))
    import torch
    from PIL import Image
    from diffsynth.pipelines.flux2_image import Flux2ImagePipeline, ModelConfig

    vram_config = {
        "offload_dtype": "disk",
        "offload_device": "disk",
        "onload_dtype": torch.float8_e4m3fn,
        "onload_device": "cpu",
        "preparing_dtype": torch.float8_e4m3fn,
        "preparing_device": "cuda",
        "computation_dtype": torch.bfloat16,
        "computation_device": "cuda",
    }
    vram_limit_gib = args.vram_limit_gib
    if vram_limit_gib is None:
        vram_limit_gib = torch.cuda.mem_get_info("cuda")[1] / (1024**3) - 0.5
    transformer = model_root / "transformer" / "diffusion_pytorch_model.safetensors"
    tokenizer = model_root / "tokenizer"
    print(f"ComfyRoot={comfy_root}", flush=True)
    print(f"DiffSynthRoot={diffsynth_root}", flush=True)
    print(f"ModelRoot={model_root}", flush=True)
    print(f"TextEncoder={text_encoder}", flush=True)
    print(f"VAE={vae}", flush=True)
    print(f"LoRA={lora}", flush=True)
    print("DownloadPolicy=local-only", flush=True)

    started = time.perf_counter()
    pipe = Flux2ImagePipeline.from_pretrained(
        torch_dtype=torch.bfloat16,
        device="cuda",
        model_configs=[
            ModelConfig(path=str(text_encoder), **vram_config),
            ModelConfig(path=str(transformer), **vram_config),
            ModelConfig(path=str(vae)),
        ],
        tokenizer_config=ModelConfig(path=str(tokenizer), skip_download=True),
        vram_limit=vram_limit_gib,
    )
    pipe.load_lora(pipe.dit, str(lora))
    with Image.open(source) as opened:
        edit_image = opened.convert("RGB")
    image = pipe(
        prompt=prompt,
        edit_image=[edit_image],
        seed=args.seed,
        rand_device="cuda",
        num_inference_steps=args.steps,
        cfg_scale=args.cfg_scale,
        height=args.height,
        width=args.width,
    )
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    elapsed = round(time.perf_counter() - started, 2)
    manifest = {
        "schema": "assetsstudio_flux2_base_actor_core_diagnostic_v1",
        "production_path": False,
        "download_policy": "local-only",
        "source": str(source),
        "lora": str(lora),
        "output": str(output),
        "seed": args.seed,
        "steps": args.steps,
        "cfg_scale": args.cfg_scale,
        "size": [args.width, args.height],
        "vram_limit_gib": round(vram_limit_gib, 3),
        "elapsed_seconds": elapsed,
    }
    output.with_suffix(".json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
