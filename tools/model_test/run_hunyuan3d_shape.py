"""Generate a Hunyuan3D-2mini Turbo shape for the model_test branch."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import torch
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--octree-resolution", type=int, default=320)
    parser.add_argument("--num-chunks", type=int, default=20000)
    args = parser.parse_args()

    os.environ.setdefault("HY3DGEN_MODELS", r"E:\env\models")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")

    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    if not args.image.is_file():
        raise FileNotFoundError(args.image)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print("Loading Hunyuan3D-2mini Turbo...")
    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        "Hunyuan3D-2mini",
        subfolder="hunyuan3d-dit-v2-mini-turbo",
        use_safetensors=True,
        device="cuda",
        dtype=torch.float16,
    )

    image = Image.open(args.image).convert("RGBA")
    with torch.inference_mode():
        mesh = pipeline(
            image=image,
            num_inference_steps=args.steps,
            octree_resolution=args.octree_resolution,
            num_chunks=args.num_chunks,
        )[0]

    mesh.export(args.output)
    print(f"HUNYUAN3D_PASS output={args.output}")
    print(f"vertices={len(mesh.vertices)} faces={len(mesh.faces)}")


if __name__ == "__main__":
    main()
