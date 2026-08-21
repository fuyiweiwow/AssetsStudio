"""Run a conservative local SDXL text-to-image or image-to-image smoke test."""

from __future__ import annotations

import argparse
import gc
from pathlib import Path

import torch
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("text", "img2img"), required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--strength", type=float, default=0.55)
    parser.add_argument(
        "--variant",
        default="fp16",
        help="Diffusers weight variant; use 'none' for checkpoints without a variant.",
    )
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the SDXL smoke test")
    if not args.model.is_dir():
        raise FileNotFoundError(args.model)
    if args.mode == "img2img" and not args.input:
        raise ValueError("--input is required for img2img")

    from diffusers import StableDiffusionXLImg2ImgPipeline, StableDiffusionXLPipeline

    pipeline_type = StableDiffusionXLPipeline if args.mode == "text" else StableDiffusionXLImg2ImgPipeline
    print(f"SDXL_LOAD mode={args.mode} model={args.model.resolve()}", flush=True)
    load_kwargs = {
        "torch_dtype": torch.float16,
        "use_safetensors": True,
    }
    if args.variant.lower() != "none":
        load_kwargs["variant"] = args.variant
    pipe = pipeline_type.from_pretrained(str(args.model.resolve()), **load_kwargs)
    pipe.enable_model_cpu_offload()
    pipe.vae.enable_slicing()
    pipe.set_progress_bar_config(disable=False)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    generator = torch.Generator(device="cpu").manual_seed(args.seed)
    try:
        kwargs = dict(
            prompt=args.prompt,
            negative_prompt="text, watermark, logo, contact sheet, collage, person, mannequin, extra limbs",
            width=args.width,
            height=args.height,
            num_inference_steps=args.steps,
            guidance_scale=5.0,
            generator=generator,
        )
        if args.mode == "img2img":
            kwargs["image"] = Image.open(args.input).convert("RGB")
            kwargs["strength"] = args.strength
        image = pipe(**kwargs).images[0]
        image.save(args.output)
        print(f"SDXL_OUTPUT {args.output.resolve()}", flush=True)
    finally:
        del pipe
        gc.collect()
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
