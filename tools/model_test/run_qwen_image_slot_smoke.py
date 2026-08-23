"""Run low-memory Qwen-Image text-to-image or Edit-2511 smoke tests."""

from __future__ import annotations

import argparse
import gc
from pathlib import Path

import torch
from PIL import Image


def build_quant_config():
    from diffusers.quantizers import PipelineQuantizationConfig

    return PipelineQuantizationConfig(
        quant_backend="bitsandbytes_4bit",
        quant_kwargs={
            "load_in_4bit": True,
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_compute_dtype": torch.bfloat16,
        },
        components_to_quantize=["transformer", "text_encoder"],
    )


def load_pipeline(args):
    from diffusers import QwenImageEditPlusPipeline, QwenImagePipeline

    pipeline_type = QwenImagePipeline if args.mode == "text" else QwenImageEditPlusPipeline
    print(f"QWEN_LOAD mode={args.mode} model={args.model}", flush=True)
    pipe = pipeline_type.from_pretrained(
        str(args.model.resolve()),
        torch_dtype=torch.bfloat16,
        quantization_config=build_quant_config(),
        device_map="cuda",
    )
    pipe.enable_model_cpu_offload()
    pipe.set_progress_bar_config(disable=False)
    return pipe


def main() -> int:
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
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the Qwen smoke test")
    if not args.model.is_dir():
        raise FileNotFoundError(args.model)
    if args.mode == "edit" and not args.input:
        raise ValueError("--input is required in edit mode")
    input_images = []
    for image_path in args.input:
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        input_images.append(Image.open(image_path).convert("RGB"))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pipe = load_pipeline(args)
    generator = torch.Generator(device="cuda").manual_seed(args.seed)
    torch.cuda.reset_peak_memory_stats()
    print("QWEN_GENERATE", flush=True)
    with torch.inference_mode():
        if args.mode == "text":
            result = pipe(
                prompt=args.prompt,
                negative_prompt="低分辨率，畸形，拼图，多物件，人物，背景杂物",
                width=args.width,
                height=args.height,
                num_inference_steps=args.steps,
                true_cfg_scale=4.0,
                generator=generator,
            )
        else:
            result = pipe(
                image=input_images,
                prompt=args.prompt,
                negative_prompt="拼图，多视图面板，额外物件，人物残片，背景杂物",
                width=args.width,
                height=args.height,
                num_inference_steps=args.steps,
                true_cfg_scale=4.0,
                guidance_scale=1.0,
                generator=generator,
                num_images_per_prompt=1,
            )
    result.images[0].save(args.output)
    peak = torch.cuda.max_memory_allocated() / (1024**3)
    print(f"QWEN_PASS output={args.output.resolve()} peak_cuda_gib={peak:.2f}", flush=True)
    del result, pipe, input_images
    gc.collect()
    torch.cuda.empty_cache()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
