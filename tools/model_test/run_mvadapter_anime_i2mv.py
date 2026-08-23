"""Run a guarded SDXL MV-Adapter image-to-four-view character test.

This path uses model CPU offload so the official SDXL I2MV adapter can be
evaluated on the project's RTX 3060 12 GB without loading the whole pipeline
into VRAM at once.
"""

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from PIL import Image


REPO_ROOT = Path(r"E:\env\repos\MV-Adapter-main")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mvadapter.pipelines.pipeline_mvadapter_i2mv_sdxl import (  # noqa: E402
    MVAdapterI2MVSDXLPipeline,
)
from mvadapter.models.attention_processor import (  # noqa: E402
    DecoupledMVRowSelfAttnProcessor2_0,
)
from mvadapter.schedulers.scheduling_shift_snr import ShiftSNRScheduler  # noqa: E402


MISSING_REFERENCE_LAYERS: set[str] = set()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--base-model", default=r"E:\env\models\animagine-xl-3.1"
    )
    parser.add_argument(
        "--adapter-path", default=r"E:\env\models\mv-adapter"
    )
    parser.add_argument(
        "--output",
        default=r"E:\env\outputs\mvadapter_i2mv_actor_v2\actor_v2_i2mv.png",
    )
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument("--steps", type=int, default=35)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--guidance-scale", type=float, default=3.5)
    parser.add_argument("--reference-scale", type=float, default=1.0)
    parser.add_argument(
        "--diagnose-partial-reference-cache",
        action="store_true",
        help=(
            "Continue while recording any MV-Adapter reference-cache keys missing "
            "from the installed upstream stack. Diagnostic only."
        ),
    )
    parser.add_argument(
        "--azimuth-deg", type=int, nargs="+", default=[0, 90, 180, 270]
    )
    parser.add_argument(
        "--prompt",
        default=(
            "same character, chibi anime western fantasy female adventurer, full body, "
            "neutral standing pose, exact same face, hairstyle, body proportions, outfit, "
            "colors and accessories in every view, clean production character reference, "
            "soft 3D anime render, simple neutral gray background, high quality"
        ),
    )
    parser.add_argument(
        "--negative-prompt",
        default=(
            "text, watermark, labels, collage, extra character, different character, "
            "different costume, different hairstyle, changed colors, weapon, action pose, "
            "cropped body, duplicate limbs, extra limbs, deformed hands, busy background"
        ),
    )
    return parser.parse_args()


def fit_reference(image: Image.Image, width: int, height: int) -> Image.Image:
    image = image.convert("RGB")
    scale = min(width * 0.90 / image.width, height * 0.90 / image.height)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGB", (width, height), (224, 224, 224))
    canvas.paste(
        resized,
        ((width - resized.width) // 2, (height - resized.height) // 2),
    )
    return canvas


def make_grid(images: list[Image.Image]) -> Image.Image:
    grid = Image.new("RGB", (len(images) * images[0].width, images[0].height))
    for index, image in enumerate(images):
        grid.paste(image.convert("RGB"), (index * images[0].width, 0))
    return grid


def get_c2w(azimuth_deg: list[int], distance: float, device: str) -> torch.Tensor:
    azimuth = torch.tensor(azimuth_deg, dtype=torch.float32, device=device)
    azimuth = azimuth * math.pi / 180
    elevation = torch.zeros_like(azimuth)
    camera_positions = torch.stack(
        [
            distance * torch.cos(elevation) * torch.cos(azimuth),
            distance * torch.cos(elevation) * torch.sin(azimuth),
            distance * torch.sin(elevation),
        ],
        dim=-1,
    )
    center = torch.zeros_like(camera_positions)
    up = torch.tensor([0, 0, 1], dtype=torch.float32, device=device)[None, :].repeat(
        len(azimuth_deg), 1
    )
    lookat = F.normalize(center - camera_positions, dim=-1)
    right = F.normalize(torch.cross(lookat, up, dim=-1), dim=-1)
    up = F.normalize(torch.cross(right, lookat, dim=-1), dim=-1)
    c2w3x4 = torch.cat(
        [torch.stack([right, up, -lookat], dim=-1), camera_positions[:, :, None]],
        dim=-1,
    )
    c2w = torch.cat([c2w3x4, torch.zeros_like(c2w3x4[:, :1])], dim=1)
    c2w[:, 3, 3] = 1.0
    return c2w


def make_plucker(c2w: torch.Tensor, image_size: int) -> torch.Tensor:
    embeds = []
    for camera in c2w:
        world_to_cam = torch.linalg.inv(camera)
        world_to_cam[1, :] *= -1
        world_to_cam[2, :] *= -1
        rotation_cv = world_to_cam[:3, :3]
        translation_cv = world_to_cam[:3, 3]
        cam_pos = F.normalize(-rotation_cv.T @ translation_cv, dim=0)
        view_dir = rotation_cv.T @ torch.tensor(
            [0.0, 0.0, 1.0], dtype=torch.float32, device=camera.device
        )
        plucker = torch.cat([view_dir, cam_pos]).reshape(6, 1, 1)
        embeds.append(plucker.repeat(1, image_size, image_size))
    return torch.stack(embeds)


def install_reference_cache_diagnostic() -> None:
    original_call = DecoupledMVRowSelfAttnProcessor2_0.__call__

    def guarded_call(
        self,
        attn,
        hidden_states,
        encoder_hidden_states=None,
        attention_mask=None,
        temb=None,
        mv_scale=1.0,
        ref_hidden_states=None,
        ref_scale=1.0,
        cache_hidden_states=None,
        use_mv=True,
        use_ref=True,
        num_views=None,
        *args,
        **kwargs,
    ):
        if (
            use_ref
            and self.use_ref
            and ref_hidden_states is not None
            and self.name not in ref_hidden_states
        ):
            MISSING_REFERENCE_LAYERS.add(self.name)
            use_ref = False
        return original_call(
            self,
            attn,
            hidden_states,
            encoder_hidden_states=encoder_hidden_states,
            attention_mask=attention_mask,
            temb=temb,
            mv_scale=mv_scale,
            ref_hidden_states=ref_hidden_states,
            ref_scale=ref_scale,
            cache_hidden_states=cache_hidden_states,
            use_mv=use_mv,
            use_ref=use_ref,
            num_views=num_views,
            *args,
            **kwargs,
        )

    DecoupledMVRowSelfAttnProcessor2_0.__call__ = guarded_call


def main() -> None:
    args = parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this test")
    if len(args.azimuth_deg) != 4:
        raise ValueError("This guarded test requires front/right/back/left together")
    if args.width != args.height or args.width % 8:
        raise ValueError("MV-Adapter test dimensions must be equal and divisible by 8")
    if args.diagnose_partial_reference_cache:
        install_reference_cache_diagnostic()

    adapter_file = Path(args.adapter_path) / "mvadapter_i2mv_sdxl.safetensors"
    if not adapter_file.is_file():
        raise FileNotFoundError(
            f"Missing {adapter_file}; download the official I2MV weight first"
        )

    started = time.time()
    pipe = MVAdapterI2MVSDXLPipeline.from_pretrained(
        args.base_model,
        torch_dtype=torch.float16,
        use_safetensors=True,
    )
    pipe.scheduler = ShiftSNRScheduler.from_scheduler(
        pipe.scheduler,
        shift_mode="interpolated",
        shift_scale=8.0,
        scheduler_class=None,
    )
    pipe.init_custom_adapter(num_views=4)
    pipe.load_custom_adapter(
        args.adapter_path, weight_name="mvadapter_i2mv_sdxl.safetensors"
    )
    pipe.to(dtype=torch.float16)
    pipe.enable_model_cpu_offload()
    pipe.cond_encoder.to(device="cuda", dtype=torch.float16)
    pipe.vae.enable_slicing()
    pipe.vae.enable_tiling()

    cameras = get_c2w(
        [value - 90 for value in args.azimuth_deg], 1.8, "cuda"
    )
    plucker = make_plucker(cameras, args.width)
    control_images = ((plucker + 1.0) / 2.0).clamp(0, 1)
    reference = fit_reference(Image.open(args.input), args.width, args.height)

    images = pipe(
        args.prompt,
        height=args.height,
        width=args.width,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance_scale,
        num_images_per_prompt=4,
        control_image=control_images,
        control_conditioning_scale=1.0,
        reference_image=reference,
        reference_conditioning_scale=args.reference_scale,
        negative_prompt=args.negative_prompt,
        generator=torch.Generator(device="cuda").manual_seed(args.seed),
    ).images

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    make_grid(images).save(output)
    reference.save(output.with_name(f"{output.stem}_reference.png"))
    for index, image in enumerate(images):
        image.save(output.with_name(f"{output.stem}_{index}.png"))
    report = {
        "schema": "assetsstudio_local_i2mv_experiment_v1",
        "input": str(Path(args.input).resolve()),
        "base_model": args.base_model,
        "adapter": str(adapter_file),
        "views": ["front", "right", "back", "left"],
        "azimuth_degrees": args.azimuth_deg,
        "resolution": [args.width, args.height],
        "steps": args.steps,
        "seed": args.seed,
        "guidance_scale": args.guidance_scale,
        "reference_scale": args.reference_scale,
        "diagnostic_partial_reference_cache": args.diagnose_partial_reference_cache,
        "missing_reference_layer_count": len(MISSING_REFERENCE_LAYERS),
        "missing_reference_layers": sorted(MISSING_REFERENCE_LAYERS),
        "prompt": args.prompt,
        "negative_prompt": args.negative_prompt,
        "elapsed_seconds": round(time.time() - started, 3),
        "gpu": torch.cuda.get_device_name(0),
    }
    output.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"MVADAPTER_ANIME_I2MV_PASS {output}")
    print(f"MVADAPTER_MISSING_REFERENCE_LAYERS {len(MISSING_REFERENCE_LAYERS)}")


if __name__ == "__main__":
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    main()
