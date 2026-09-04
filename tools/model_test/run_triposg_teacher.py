#!/usr/bin/env python3
"""Run TripoSG as an offline, disposable shape-teacher backend.

The generated mesh is diagnostic evidence. It is never a production Actor Core.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types
from pathlib import Path


def _existing_dir(candidates: list[Path | None], marker: str) -> Path | None:
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = candidate.expanduser().resolve()
        if (resolved / marker).is_file():
            return resolved
    return None


def _existing_triposg_model(candidates: list[Path | None]) -> Path | None:
    required = {
        "model_index.json": 100,
        "transformer/diffusion_pytorch_model.safetensors": 5_000_000_000,
        "vae/diffusion_pytorch_model.safetensors": 800_000_000,
        "image_encoder_dinov2/model.safetensors": 1_000_000_000,
    }
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = candidate.expanduser().resolve()
        if all(
            (resolved / relative).is_file()
            and (resolved / relative).stat().st_size >= minimum
            for relative, minimum in required.items()
        ):
            return resolved
    return None


def _discover_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    project_root = Path(__file__).resolve().parents[2]
    project_parent = project_root.parent
    runtime_root = Path(
        os.environ.get(
            "ASSETSSTUDIO_ACTOR_CORE_V2_RUNTIME",
            project_root / "workspace" / "runtime" / "actor_core_v2",
        )
    )
    source = _existing_dir(
        [
            Path(args.source) if args.source else None,
            Path(os.environ["ASSETSSTUDIO_TRIPOSG_SOURCE"])
            if os.environ.get("ASSETSSTUDIO_TRIPOSG_SOURCE")
            else None,
            runtime_root / "source" / "TripoSG",
            project_parent / "TripoSG",
        ],
        "scripts/inference_triposg.py",
    )
    model = _existing_triposg_model(
        [
            Path(args.model) if args.model else None,
            Path(os.environ["ASSETSSTUDIO_TRIPOSG_MODEL"])
            if os.environ.get("ASSETSSTUDIO_TRIPOSG_MODEL")
            else None,
            project_root
            / "workspace"
            / "models"
            / "modelscope"
            / "VAST-AI-Research"
            / "TripoSG",
            Path.home()
            / ".cache"
            / "modelscope"
            / "hub"
            / "models"
            / "VAST-AI-Research"
            / "TripoSG",
        ]
    )
    if source is None:
        raise FileNotFoundError(
            "TripoSG source not found; run tools/setup_actor_core_v2_research.ps1"
        )
    if model is None:
        raise FileNotFoundError(
            "TripoSG ModelScope weights not found; run tools/setup_actor_core_v2_research.ps1"
        )
    return source, model


def _validate_rgba_input(path: Path) -> None:
    from PIL import Image

    with Image.open(path) as image:
        if image.mode != "RGBA":
            raise ValueError("Teacher input must be RGBA so no RMBG model is downloaded.")
        alpha = image.getchannel("A")
        low, high = alpha.getextrema()
        if low > 0 or high < 255:
            raise ValueError("RGBA input must contain both transparent and opaque pixels.")


def _install_optional_diso_stub() -> None:
    try:
        __import__("diso")
    except ImportError:
        module = types.ModuleType("diso")

        class DiffDMC:  # pragma: no cover - must never run in portable mode
            def __init__(self, *args: object, **kwargs: object) -> None:
                raise RuntimeError("The optional TripoSG flash decoder is unavailable.")

        module.DiffDMC = DiffDMC
        sys.modules["diso"] = module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--source")
    parser.add_argument("--model")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--guidance", type=float, default=7.0)
    parser.add_argument("--dense-octree-depth", type=int, default=8)
    parser.add_argument("--hierarchical-octree-depth", type=int, default=9)
    args = parser.parse_args()

    source, model = _discover_paths(args)
    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    report_path = (
        args.report.expanduser().resolve()
        if args.report
        else output_path.with_suffix(".json")
    )
    _validate_rgba_input(input_path)

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["DIFFUSERS_OFFLINE"] = "1"
    sys.path.insert(0, str(source))
    sys.path.insert(0, str(source / "scripts"))
    _install_optional_diso_stub()

    import numpy as np
    import torch
    import trimesh
    from image_process import prepare_image
    from triposg.pipelines.pipeline_triposg import TripoSGPipeline

    if not torch.cuda.is_available():
        raise RuntimeError("TripoSG teacher generation requires a CUDA GPU.")

    device = torch.device("cuda")
    dtype = torch.float16
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device)
    started = time.perf_counter()

    # A valid alpha channel makes the official preprocessor skip RMBG entirely.
    image = prepare_image(
        str(input_path), bg_color=np.array([1.0, 1.0, 1.0]), rmbg_net=None
    )
    pipe = TripoSGPipeline.from_pretrained(
        str(model), local_files_only=True, torch_dtype=dtype
    ).to(device)
    outputs = pipe(
        image=image,
        generator=torch.Generator(device=device).manual_seed(args.seed),
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        use_flash_decoder=False,
        dense_octree_depth=args.dense_octree_depth,
        hierarchical_octree_depth=args.hierarchical_octree_depth,
    ).samples[0]
    mesh = trimesh.Trimesh(
        outputs[0].astype(np.float32), np.ascontiguousarray(outputs[1])
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(output_path)
    elapsed = time.perf_counter() - started

    report = {
        "role": "disposable_shape_teacher",
        "approved_asset": False,
        "backend": "TripoSG_hierarchical_portable",
        "source": str(source),
        "model": str(model),
        "input": str(input_path),
        "output": str(output_path),
        "seed": args.seed,
        "steps": args.steps,
        "guidance": args.guidance,
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "connected_components": int(len(mesh.split(only_watertight=False))),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "elapsed_seconds": elapsed,
        "peak_cuda_allocated_bytes": int(torch.cuda.max_memory_allocated(device)),
        "peak_cuda_reserved_bytes": int(torch.cuda.max_memory_reserved(device)),
        "gpu": torch.cuda.get_device_name(device),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
