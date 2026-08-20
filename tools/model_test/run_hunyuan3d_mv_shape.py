"""Run a local Hunyuan3D-2mv Turbo shape smoke test with split weights."""

from __future__ import annotations

import argparse
import gc
import importlib
import os
import sys
from pathlib import Path

import torch
import yaml
from PIL import Image


def load_split_pipeline(
    model_dir: Path,
    subfolder: str,
    code_root: Path,
    pipeline_module: str,
    device: str,
):
    sys.path.insert(0, str(code_root))
    pipelines = importlib.import_module(pipeline_module)
    Hunyuan3DDiTFlowMatchingPipeline = pipelines.Hunyuan3DDiTFlowMatchingPipeline
    instantiate_from_config = pipelines.instantiate_from_config

    model_root = model_dir / subfolder
    with (model_root / "config.yaml").open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    split_root = model_root / "split_components"

    def load_component(name: str):
        return torch.load(
            split_root / f"{name}.pt",
            map_location="cpu",
            weights_only=True,
            mmap=True,
        )

    model = instantiate_from_config(config["model"])
    model.load_state_dict(load_component("model"), assign=True)
    gc.collect()

    vae = instantiate_from_config(config["vae"])
    vae.load_state_dict(load_component("vae"), strict=False, assign=True)
    gc.collect()

    conditioner = instantiate_from_config(config["conditioner"])
    conditioner.load_state_dict(load_component("conditioner"), assign=True)
    gc.collect()

    scheduler = instantiate_from_config(config["scheduler"])
    image_processor = instantiate_from_config(config["image_processor"])
    return Hunyuan3DDiTFlowMatchingPipeline(
        vae=vae,
        model=model,
        scheduler=scheduler,
        conditioner=conditioner,
        image_processor=image_processor,
        device=device,
        dtype=torch.float16,
        from_pretrained_kwargs={
            "model_path": str(model_dir),
            "subfolder": subfolder,
        },
    )


def enable_manual_cpu_offload(pipeline) -> None:
    from accelerate import cpu_offload_with_hook

    execution_device = torch.device("cuda")
    previous_hook = None
    for name in ("conditioner", "model", "vae"):
        module = getattr(pipeline, name)
        _, previous_hook = cpu_offload_with_hook(
            module,
            execution_device,
            prev_module_hook=previous_hook,
        )
    pipeline.device = execution_device


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=Path(r"E:\env\models\Hunyuan3D-2mv"))
    parser.add_argument("--code-root", type=Path, default=Path(r"E:\env\Hunyuan3D-2"))
    parser.add_argument("--pipeline-module", default="hy3dgen.shapegen.pipelines")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--cpu-offload", action="store_true")
    parser.add_argument("--subfolder", default="hunyuan3d-dit-v2-mv-turbo")
    parser.add_argument("--front", type=Path, required=True)
    parser.add_argument("--left", type=Path)
    parser.add_argument("--back", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--octree-resolution", type=int, default=256)
    parser.add_argument("--num-chunks", type=int, default=20000)
    args = parser.parse_args()

    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the Hunyuan3D smoke test")
    image_paths = tuple(path for path in (args.front, args.left, args.back) if path is not None)
    for image_path in image_paths:
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print("HUNYUAN_MV_LOAD_SPLIT", flush=True)
    pipeline = load_split_pipeline(
        args.model.resolve(),
        args.subfolder,
        args.code_root.resolve(),
        args.pipeline_module,
        args.device,
    )
    if args.cpu_offload:
        enable_manual_cpu_offload(pipeline)
    if args.left is None or args.back is None:
        images = Image.open(args.front).convert("RGBA")
    else:
        images = {
            "front": Image.open(args.front).convert("RGBA"),
            "left": Image.open(args.left).convert("RGBA"),
            "back": Image.open(args.back).convert("RGBA"),
        }
    print("HUNYUAN_MV_GENERATE", flush=True)
    with torch.inference_mode():
        mesh = pipeline(
            image=images,
            num_inference_steps=args.steps,
            octree_resolution=args.octree_resolution,
            num_chunks=args.num_chunks,
            output_type="trimesh",
        )[0]
    mesh.export(args.output)
    print(
        f"HUNYUAN_MV_PASS output={args.output.resolve()} "
        f"vertices={len(mesh.vertices)} faces={len(mesh.faces)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
