"""Run a guarded MV-Adapter Anime SDXL text-to-four-view smoke test."""

import argparse
import math
import sys
from pathlib import Path

import torch.nn.functional as F
import torch
from PIL import Image


REPO_ROOT = Path(r"E:\env\repos\MV-Adapter-main")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mvadapter.pipelines.pipeline_mvadapter_t2mv_sdxl import (  # noqa: E402
    MVAdapterT2MVSDXLPipeline,
)
from mvadapter.schedulers.scheduling_shift_snr import ShiftSNRScheduler  # noqa: E402


def make_image_grid(images: list[Image.Image]) -> Image.Image:
    grid = Image.new("RGB", (len(images) * images[0].width, images[0].height))
    for index, image in enumerate(images):
        grid.paste(image, (index * image.width, 0))
    return grid


def get_c2w(azimuth_deg: list[int], distance: float, device: str) -> torch.Tensor:
    azimuth = torch.tensor(azimuth_deg, dtype=torch.float32, device=device) * math.pi / 180
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


def get_plucker_embeds_from_cameras_ortho(
    c2w: torch.Tensor, ortho_scale: float, image_size: int
) -> torch.Tensor:
    embeds = []
    for camera in c2w:
        rotation = camera[:3, :3]
        translation = camera[:3, 3]
        # Same Blender-to-OpenCV conversion used by MV-Adapter's geometry helper.
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default=r"E:\env\models\animagine-xl-3.1")
    parser.add_argument("--base-variant", default="none")
    parser.add_argument("--adapter-path", default=r"E:\env\models\mv-adapter")
    parser.add_argument(
        "--output",
        default=r"E:\env\outputs\mvadapter_anime_adventurer_20260821\female_adventurer_4view.png",
    )
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument(
        "--azimuth-deg",
        type=int,
        nargs="+",
        default=[0, 90, 180, 270],
        help="Output view azimuths; use 0 90 180 for front/right/back.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this smoke test")
    if len(args.azimuth_deg) != 4:
        raise ValueError(
            "The current T2MV weight is validated for four joint views; "
            "generate front/right/back/left and select three views afterward."
        )

    base_kwargs = {"torch_dtype": torch.float16, "use_safetensors": True}
    if args.base_variant.lower() != "none":
        base_kwargs["variant"] = args.base_variant
    pipe = MVAdapterT2MVSDXLPipeline.from_pretrained(args.base_model, **base_kwargs)
    pipe.scheduler = ShiftSNRScheduler.from_scheduler(
        pipe.scheduler,
        shift_mode="interpolated",
        shift_scale=8.0,
        scheduler_class=None,
    )
    num_views = len(args.azimuth_deg)
    pipe.init_custom_adapter(num_views=num_views)
    pipe.load_custom_adapter(
        args.adapter_path,
        weight_name="mvadapter_t2mv_sdxl.safetensors",
    )
    # Adapter weights are read on CPU as FP32; cast the complete pipeline before
    # installing Accelerate's CPU-offload hooks.
    pipe.to(dtype=torch.float16)
    pipe.enable_model_cpu_offload()
    pipe.cond_encoder.to(device="cuda", dtype=torch.float16)
    pipe.vae.enable_slicing()

    cameras = get_c2w([x - 90 for x in args.azimuth_deg], 1.8, "cuda")
    plucker_embeds = get_plucker_embeds_from_cameras_ortho(
        cameras, 1.1, args.width
    )
    control_images = ((plucker_embeds + 1.0) / 2.0).clamp(0, 1)
    prompt = (
        "chibi anime female adventurer, western fantasy RPG, full body, same character, "
        "same face and hairstyle, short brown adventurer cape, teal tunic, cream collar, "
        "leather belt, small fantasy boots, clean cel shading, simple white background, "
        "neutral standing pose, consistent costume colors and accessories"
    )
    negative_prompt = (
        "text, watermark, logo, collage, character sheet labels, extra characters, "
        "different costume, different hairstyle, cropped body, duplicate limbs, "
        "deformed hands, inconsistent colors, busy background"
    )
    images = pipe(
        prompt,
        height=args.height,
        width=args.width,
        num_inference_steps=args.steps,
        guidance_scale=5.0,
        num_images_per_prompt=num_views,
        control_image=control_images,
        control_conditioning_scale=1.0,
        negative_prompt=negative_prompt,
        max_sequence_length=214,
        generator=torch.Generator(device="cuda").manual_seed(args.seed),
    ).images

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    make_image_grid(images).save(output)
    for index, image in enumerate(images):
        image.save(output.with_name(f"{output.stem}_{index}.png"))
    print(f"MVADAPTER_ANIME_T2MV_PASS {output}")


if __name__ == "__main__":
    main()
