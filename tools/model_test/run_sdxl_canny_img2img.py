"""Run a guarded SDXL + Canny ControlNet garment replacement smoke test."""

import argparse
import os
from pathlib import Path

import cv2
import numpy as np
import torch
from diffusers import ControlNetModel, StableDiffusionXLControlNetImg2ImgPipeline
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default=r"E:\env\models\sdxl-base-1.0-fp16",
    )
    parser.add_argument(
        "--controlnet",
        default=r"E:\env\models\controlnet-canny-sdxl-1.0-small",
    )
    parser.add_argument(
        "--input",
        default=r"E:\env\Hunyuan3D-2\assets\example_mv_images\1\front.png",
    )
    parser.add_argument(
        "--output",
        default=r"E:\env\outputs\qwen_standard_slot_test_20260820\sdxl_canny_img2img_front.png",
    )
    parser.add_argument(
        "--prompt",
        default=(
            "replace only the torso garment with a teal short tunic and cream collar, "
            "preserve subject silhouette, camera angle, pose and plain background, no text"
        ),
    )
    parser.add_argument(
        "--negative-prompt",
        default=(
            "text, watermark, logo, collage, extra object, changed camera, duplicate, "
            "extra limbs, distorted anatomy"
        ),
    )
    parser.add_argument(
        "--variant",
        default="fp16",
        help="Diffusers weight variant; use 'none' for models without an fp16 variant.",
    )
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--strength", type=float, default=0.65)
    parser.add_argument("--control-scale", type=float, default=0.7)
    return parser.parse_args()


def make_canny(image: Image.Image) -> Image.Image:
    rgb = np.asarray(image.convert("RGB"))
    edges = cv2.Canny(rgb, 100, 200)
    edges = np.repeat(edges[:, :, None], 3, axis=2)
    return Image.fromarray(edges)


def main() -> None:
    args = parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this smoke test")

    input_image = Image.open(args.input).convert("RGB").resize(
        (args.width, args.height), Image.Resampling.LANCZOS
    )
    control_image = make_canny(input_image)

    controlnet = ControlNetModel.from_pretrained(
        args.controlnet,
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True,
    )
    pipeline_kwargs = {
        "controlnet": controlnet,
        "torch_dtype": torch.float16,
        "use_safetensors": True,
    }
    if args.variant.lower() != "none":
        pipeline_kwargs["variant"] = args.variant
    pipe = StableDiffusionXLControlNetImg2ImgPipeline.from_pretrained(
        args.model,
        **pipeline_kwargs,
    )
    pipe.enable_model_cpu_offload()
    pipe.vae.enable_slicing()
    pipe.enable_attention_slicing()

    generator = torch.Generator(device="cpu").manual_seed(args.seed)
    result = pipe(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        image=input_image,
        control_image=control_image,
        strength=args.strength,
        controlnet_conditioning_scale=args.control_scale,
        num_inference_steps=args.steps,
        guidance_scale=5.0,
        width=args.width,
        height=args.height,
        generator=generator,
    ).images[0]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)
    print(f"SDXL_CANNY_SMOKE_PASS {output_path}")


if __name__ == "__main__":
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    main()
