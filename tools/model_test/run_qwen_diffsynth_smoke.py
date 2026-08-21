"""Run local Qwen-Image / Edit-2511 smoke tests through DiffSynth-Studio.

DiffSynth's disk offload path is used because the target machine has an RTX
3060 12 GB. The model files are expected to have already been downloaded to
the local ModelScope cache directory supplied with --model.
"""

from __future__ import annotations

import argparse
import gc
import platform
from pathlib import Path

import torch
from PIL import Image


def install_local_qwen_loader() -> None:
    """Avoid DiffSynth's whole-checkpoint safetensors hash pass on Windows.

    DiffSynth hashes every tensor key across all shards before loading. With a
    1 GiB Windows page file this metadata-only pass can fail with Win32 error
    1455 even when disk-offload inference itself would fit. The local Qwen
    directory layout is explicit, so select the known Qwen model definitions
    by subdirectory instead of hashing the 40+ GiB shard sets.
    """
    from diffsynth.configs import MODEL_CONFIGS
    from diffsynth.models.model_loader import ModelPool

    selected = {
        "transformer": next(
            config
            for config in MODEL_CONFIGS
            if config["model_name"] == "qwen_image_dit"
            and "extra_kwargs" not in config
        ),
        "text_encoder": next(
            config
            for config in MODEL_CONFIGS
            if config["model_name"] == "qwen_image_text_encoder"
        ),
        "vae": next(
            config
            for config in MODEL_CONFIGS
            if config["model_name"] == "qwen_image_vae"
            and "extra_kwargs" not in config
        ),
    }

    def auto_load_local_qwen(
        self, path, vram_config=None, vram_limit=None, clear_parameters=False,
        state_dict=None, quantize=None,
    ):
        first = str(path[0] if isinstance(path, list) else path).replace("\\", "/").lower()
        if "/transformer/" in first:
            config = selected["transformer"]
        elif "/text_encoder/" in first:
            config = selected["text_encoder"]
        elif "/vae/" in first:
            config = selected["vae"]
        else:
            raise ValueError(f"Unexpected local Qwen model path: {path}")

        print(f"Loading local Qwen model without shard hash: {config['model_name']}", flush=True)
        model = self.load_model_file(
            config, path, vram_config, vram_limit=vram_limit,
            state_dict=state_dict, quantize=quantize,
        )
        if clear_parameters:
            self.clear_parameters(model)
        self.model.append(model)
        self.model_name.append(config["model_name"])
        self.model_path.append(path)

    ModelPool.auto_load_model = auto_load_local_qwen


def local_model_config(ModelConfig, root: Path, relative: str, vram_config: dict):
    paths = sorted(str(path) for path in (root / relative).glob("*.safetensors"))
    if not paths:
        raise FileNotFoundError(f"No safetensors found under {root / relative}")
    return ModelConfig(path=paths, **vram_config)


def build_pipeline(args):
    install_local_qwen_loader()
    from diffsynth.pipelines.qwen_image import ModelConfig, QwenImagePipeline

    root = args.model.resolve()
    # RTX 30-series cards are more reliable with fp16 layer staging than with
    # an fp8 staging conversion. Disk offload still keeps the peak footprint
    # below the card's 12 GB limit.
    vram_config = {
        "offload_dtype": "disk",
        "offload_device": "disk",
        "onload_dtype": torch.float16,
        # CPU-backed DiskMap is safe now that the host has a 64 GiB page file;
        # mapping the full shard set onto CUDA exceeds the 12 GiB RTX 3060.
        "onload_device": "cpu",
        "preparing_dtype": torch.float16,
        "preparing_device": "cuda",
        "computation_dtype": torch.float16,
        "computation_device": "cuda",
    }

    model_configs = [
        local_model_config(ModelConfig, root, "transformer", vram_config),
        local_model_config(ModelConfig, root, "text_encoder", vram_config),
        local_model_config(ModelConfig, root, "vae", vram_config),
    ]
    tokenizer_config = ModelConfig(path=str(root / ("processor" if args.mode == "edit" else "tokenizer")))
    processor_config = (
        ModelConfig(path=str(root / "processor")) if args.mode == "edit" else None
    )

    print(f"QWEN_DIFFSYNTH_LOAD mode={args.mode} model={root}", flush=True)
    return QwenImagePipeline.from_pretrained(
        torch_dtype=torch.bfloat16,
        device="cuda",
        model_configs=model_configs,
        tokenizer_config=tokenizer_config,
        processor_config=processor_config,
        vram_limit=args.vram_limit,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("text", "edit"), required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--input", type=Path, nargs="*", default=[])
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=640)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--vram-limit", type=float, default=8.0)
    parser.add_argument(
        "--unsafe-windows-run",
        action="store_true",
        help="override the Windows memory-map safety stop (not recommended)",
    )
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the local Qwen smoke test")
    if not args.model.is_dir():
        raise FileNotFoundError(args.model)
    if args.mode == "edit" and not args.input:
        raise ValueError("--input requires at least one image in edit mode")
    if args.vram_limit < 4.0 or args.vram_limit > 10.0:
        raise ValueError("--vram-limit must stay between 4 and 10 GiB for this machine")

    if platform.system() == "Windows" and not args.unsafe_windows_run:
        raise RuntimeError(
            "Windows full-shard Qwen inference is disabled after repeated "
            "0x1A memory-management BSODs during safetensors mapping. Use a "
            "quantized/isolated Linux path, or pass --unsafe-windows-run only "
            "after explicitly accepting the system-crash risk."
        )

    if platform.system() == "Windows":
        try:
            import psutil

            pagefile_gib = psutil.swap_memory().total / (1024**3)
            print(f"QWEN_PREFLIGHT pagefile_gib={pagefile_gib:.2f}", flush=True)
            if pagefile_gib < 8.0:
                raise RuntimeError(
                    "Windows page file is below 8 GiB. The Qwen safetensor shard "
                    "mapping will fail with Win32 error 1455; increase the page "
                    "file before starting full local inference."
                )
        except ImportError:
            print("QWEN_PREFLIGHT pagefile=unknown (psutil unavailable)", flush=True)

    free, total = torch.cuda.mem_get_info("cuda")
    print(
        f"QWEN_PREFLIGHT gpu_free_gib={free / (1024**3):.2f} "
        f"gpu_total_gib={total / (1024**3):.2f} "
        f"configured_limit_gib={args.vram_limit:.2f}",
        flush=True,
    )

    images = []
    for path in args.input:
        if not path.is_file():
            raise FileNotFoundError(path)
        images.append(Image.open(path).convert("RGB"))

    pipe = build_pipeline(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        if args.mode == "text":
            image = pipe(
                prompt=args.prompt,
                negative_prompt="text, watermark, logo, contact sheet, collage, extra object, person",
                cfg_scale=4.0,
                width=args.width,
                height=args.height,
                seed=args.seed,
                num_inference_steps=args.steps,
            )
        else:
            image = pipe(
                prompt=args.prompt,
                negative_prompt="text, watermark, logo, contact sheet, collage, extra object",
                cfg_scale=4.0,
                edit_image=images,
                edit_image_auto_resize=True,
                width=args.width,
                height=args.height,
                seed=args.seed,
                num_inference_steps=args.steps,
                zero_cond_t=True,
            )
        image.save(args.output)
        print(f"QWEN_OUTPUT {args.output.resolve()}", flush=True)
    finally:
        del pipe
        gc.collect()
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
