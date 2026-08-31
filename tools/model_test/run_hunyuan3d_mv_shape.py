"""Run a local Hunyuan3D-2mv Turbo shape smoke test with split weights."""

from __future__ import annotations

import argparse
import gc
import importlib
import json
import os
import sys
from pathlib import Path

import torch
import trimesh
import yaml
from PIL import Image

from hunyuan_environment import (
    discover_code_root,
    discover_model_root,
    discover_subfolder,
)


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
    parser.add_argument("--model", type=Path)
    parser.add_argument("--code-root", type=Path)
    parser.add_argument("--pipeline-module", default="hy3dgen.shapegen.pipelines")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--cpu-offload", action="store_true")
    parser.add_argument("--subfolder")
    parser.add_argument("--front", type=Path, required=True)
    parser.add_argument("--left", type=Path)
    parser.add_argument("--back", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--guidance-scale", type=float)
    parser.add_argument("--octree-resolution", type=int, default=256)
    parser.add_argument("--num-chunks", type=int, default=20000)
    parser.add_argument("--asset-kind", choices=("base_actor", "accessory"), default="base_actor")
    parser.add_argument("--max-components", type=int, default=16)
    parser.add_argument("--min-component-face-fraction", type=float, default=0.00025)
    args = parser.parse_args()

    args.model = discover_model_root(args.model)
    args.code_root = discover_code_root(args.code_root)
    args.subfolder = discover_subfolder(args.model, args.subfolder)
    print(
        "HUNYUAN_ENV "
        f"model={args.model} code_root={args.code_root} subfolder={args.subfolder}",
        flush=True,
    )

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
    torch.cuda.reset_peak_memory_stats()
    generator = torch.Generator(device="cuda").manual_seed(args.seed)
    with torch.inference_mode():
        generation_args = {
            "image": images,
            "num_inference_steps": args.steps,
            "octree_resolution": args.octree_resolution,
            "num_chunks": args.num_chunks,
            "generator": generator,
            "output_type": "trimesh",
        }
        if args.guidance_scale is not None:
            generation_args["guidance_scale"] = args.guidance_scale
        mesh = pipeline(**generation_args)[0]
    peak_memory_bytes = int(torch.cuda.max_memory_allocated())
    raw_components = list(mesh.split(only_watertight=False))
    raw_face_count = len(mesh.faces)
    discarded_components: list[dict[str, float | int]] = []
    if args.asset_kind == "accessory":
        kept_components = []
        for component in raw_components:
            fraction = len(component.faces) / max(raw_face_count, 1)
            if fraction < args.min_component_face_fraction:
                discarded_components.append(
                    {"faces": len(component.faces), "face_fraction": fraction}
                )
            else:
                kept_components.append(component)
        if not kept_components:
            raise RuntimeError("accessory cleanup removed every component")
        if discarded_components:
            mesh = trimesh.util.concatenate(kept_components)
    mesh.export(args.output)
    components = list(mesh.split(only_watertight=False))
    connected_components = len(components)
    topology = {
        "geometry_count": 1,
        "connected_components": connected_components,
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "euler_number": int(mesh.euler_number),
        "all_components_watertight": all(bool(component.is_watertight) for component in components),
    }
    if args.asset_kind == "base_actor":
        automatic_gates = {
            "single_geometry": topology["geometry_count"] == 1,
            "single_connected_component": connected_components == 1,
            "watertight": topology["watertight"],
            "winding_consistent": topology["winding_consistent"],
            "genus_zero_euler_two": topology["euler_number"] == 2,
        }
    else:
        automatic_gates = {
            "single_geometry": topology["geometry_count"] == 1,
            "component_count_within_slot_limit": 1 <= connected_components <= args.max_components,
            "all_components_watertight": topology["all_components_watertight"],
            "winding_consistent": topology["winding_consistent"],
            "tiny_fragment_cleanup_bounded": sum(item["faces"] for item in discarded_components) / max(raw_face_count, 1) <= 0.001,
        }
    automatic_pass = all(automatic_gates.values())
    report = {
        "schema": "assetsstudio_hunyuan3d_2mv_shape_v1",
        "model": str(args.model.resolve()),
        "subfolder": args.subfolder,
        "inputs": {
            "front": str(args.front.resolve()),
            "left": str(args.left.resolve()) if args.left else None,
            "back": str(args.back.resolve()) if args.back else None,
        },
        "output": str(args.output.resolve()),
        "seed": args.seed,
        "steps": args.steps,
        "guidance_scale": args.guidance_scale,
        "octree_resolution": args.octree_resolution,
        "num_chunks": args.num_chunks,
        "cpu_offload": args.cpu_offload,
        "asset_kind": args.asset_kind,
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "peak_cuda_memory_bytes": peak_memory_bytes,
        "mesh_audit": topology,
        "component_policy": {
            "max_components": args.max_components,
            "min_component_face_fraction": args.min_component_face_fraction,
            "raw_components": len(raw_components),
            "kept_components": connected_components,
            "discarded_components": discarded_components,
        },
        "automatic_gates": automatic_gates,
        "status": "pass" if automatic_pass else "fail",
    }
    if args.manifest is not None:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(
        f"HUNYUAN_MV_{'PASS' if automatic_pass else 'FAIL'} output={args.output.resolve()} "
        f"vertices={len(mesh.vertices)} faces={len(mesh.faces)} "
        f"connected_components={connected_components} "
        f"watertight={topology['watertight']} euler_number={topology['euler_number']} "
        f"peak_cuda_memory_bytes={peak_memory_bytes}",
        flush=True,
    )
    return 0 if automatic_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
