"""Generate the new independent male_adventurer_v2 base with local Hunyuan."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import torch
import yaml
from PIL import Image

sys.path.insert(0, r"E:\env\Hunyuan3D-2")
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
from hy3dgen.shapegen.pipelines import instantiate_from_config


def install_memory_mapped_torch_load() -> None:
    """Avoid duplicating the 3.8 GB local checkpoint during deserialization."""
    original_load = torch.load

    def load_with_mmap(*args, **kwargs):
        source = args[0] if args else kwargs.get("f")
        if isinstance(source, (str, os.PathLike)) and str(source).lower().endswith(".ckpt"):
            kwargs.setdefault("mmap", True)
        return original_load(*args, **kwargs)

    torch.load = load_with_mmap


def load_pipeline_low_memory(model_root: Path) -> Hunyuan3DDiTFlowMatchingPipeline:
    """Load the three checkpoint sections one at a time instead of keeping 3.8 GB live."""
    model_dir = model_root / "hunyuan3d-dit-v2-mini-turbo"
    config = yaml.safe_load((model_dir / "config.yaml").read_text(encoding="utf-8"))
    split_dir = model_dir / "split_components"
    if not split_dir.exists():
        raise FileNotFoundError(
            f"Missing split checkpoint cache: {split_dir}. "
            "Run split_hunyuan_checkpoint.py first."
        )

    def load_component(module, prefix: str, strict: bool = True) -> None:
        component_path = split_dir / f"{prefix}.pt"
        state = torch.load(
            str(component_path),
            map_location="cpu",
            weights_only=True,
            mmap=True,
        )
        module.load_state_dict(state, strict=strict, assign=True)
        del state

    print("LOAD_COMPONENT conditioner_init", flush=True)
    conditioner = instantiate_from_config(config["conditioner"])
    print("LOAD_COMPONENT conditioner_weights", flush=True)
    load_component(conditioner, "conditioner")
    print("LOAD_COMPONENT model_init", flush=True)
    model = instantiate_from_config(config["model"])
    print("LOAD_COMPONENT model_weights", flush=True)
    load_component(model, "model")
    print("LOAD_COMPONENT vae_init", flush=True)
    vae = instantiate_from_config(config["vae"])
    print("LOAD_COMPONENT vae_weights", flush=True)
    load_component(vae, "vae", strict=False)
    print("LOAD_COMPONENT scheduler", flush=True)
    scheduler = instantiate_from_config(config["scheduler"])
    image_processor = instantiate_from_config(config["image_processor"])
    return Hunyuan3DDiTFlowMatchingPipeline(
        vae=vae,
        model=model,
        scheduler=scheduler,
        conditioner=conditioner,
        image_processor=image_processor,
        device="cpu",
        dtype=torch.float16,
        from_pretrained_kwargs={
            "model_path": str(model_root),
            "subfolder": "hunyuan3d-dit-v2-mini-turbo",
            "use_safetensors": True,
        },
    )


def enable_manual_cpu_offload(pipeline: Hunyuan3DDiTFlowMatchingPipeline) -> None:
    """Apply the repo's intended hook chain without relying on its missing components property."""
    from accelerate import cpu_offload_with_hook

    execution_device = torch.device("cuda")
    previous_hook = None
    for name in ("conditioner", "model", "vae"):
        module = getattr(pipeline, name)
        print(f"OFFLOAD_HOOK_START {name}", flush=True)
        _, previous_hook = cpu_offload_with_hook(
            module, execution_device, prev_module_hook=previous_hook
        )
        print(f"OFFLOAD_HOOK_PASS {name}", flush=True)
    pipeline.device = execution_device
    print("OFFLOAD_READY", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", default=r"E:\env\models\Hunyuan3D-2mini")
    parser.add_argument("--seed", type=int, default=20260817)
    parser.add_argument("--octree-resolution", type=int, default=192)
    parser.add_argument("--num-chunks", type=int, default=8000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ.setdefault("HY3DGEN_MODELS", r"E:\env\models")
    os.environ.setdefault("PYTHONPATH", r"E:\env\Hunyuan3D-2")
    image = Image.open(args.image.resolve()).convert("RGBA")
    previous_default_dtype = torch.get_default_dtype()
    torch.set_default_dtype(torch.float16)
    pipeline = load_pipeline_low_memory(Path(args.model).resolve())
    torch.set_default_dtype(previous_default_dtype)
    enable_manual_cpu_offload(pipeline)
    mesh = pipeline(
        image=image,
        num_inference_steps=5,
        octree_resolution=args.octree_resolution,
        num_chunks=args.num_chunks,
        generator=torch.manual_seed(args.seed),
        output_type="trimesh",
    )[0]
    print("HUNYUAN_SHAPE_PASS", flush=True)
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(args.output.resolve()))
    print(f"HUNYUAN_V2_BASE_PASS output={args.output.resolve()} seed={args.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
