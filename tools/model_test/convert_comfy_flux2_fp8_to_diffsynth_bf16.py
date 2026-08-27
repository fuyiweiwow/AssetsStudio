#!/usr/bin/env python3
"""Convert an existing Comfy FLUX.2 scaled-FP8 transformer to DiffSynth BF16 keys.

The conversion is local-only and intended for family-native LoRA training when
the production transformer is already present in ComfyUI. It does not download
or approximate weights: scaled FP8 tensors are dequantized with their recorded
per-tensor weight scale, and Comfy fused projections are deterministically split
through Comfy's own FLUX key map.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def discover_comfy_root() -> Path:
    configured = os.environ.get("ASSETSSTUDIO_COMFY_ROOT")
    candidates = ([Path(configured)] if configured else []) + [
        ROOT.parent / "ComfyUI",
        Path.home() / "ComfyUI",
    ]
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if (resolved / "comfy" / "utils.py").is_file():
            return resolved
    raise FileNotFoundError("Unable to discover ComfyUI source root")


def reexec_in_comfy_python(comfy_root: Path) -> int | None:
    if importlib.util.find_spec("torch") is not None and importlib.util.find_spec(
        "safetensors"
    ) is not None:
        return None
    python = next(
        (
            candidate
            for candidate in (
                comfy_root / ".venv" / "Scripts" / "python.exe",
                comfy_root / "venv" / "Scripts" / "python.exe",
                comfy_root / "python_embeded" / "python.exe",
            )
            if candidate.is_file()
        ),
        None,
    )
    if python is None:
        raise FileNotFoundError("No ComfyUI Python environment was found")
    return subprocess.run(
        [str(python), str(Path(__file__).resolve()), *sys.argv[1:]],
        cwd=ROOT,
        check=False,
    ).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--key-template",
        type=Path,
        help="Optional official DiffSynth transformer used only as an accepted key/shape template",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    comfy_root = discover_comfy_root()
    reexec_result = reexec_in_comfy_python(comfy_root)
    if reexec_result is not None:
        return reexec_result

    import torch
    from safetensors import safe_open
    from safetensors.torch import save_file

    sys.path.insert(0, str(comfy_root))
    from comfy.utils import flux_to_diffusers

    # Comfy's generic FLUX exporter still uses the Diffusers FLUX.1 names for
    # these shared FLUX.2 layers. DiffSynth's native FLUX.2 implementation uses
    # the names below. This is a key-only alias: all tensors still come from the
    # distilled Comfy checkpoint, never from the optional Base key template.
    native_flux2_aliases = {
        "double_stream_modulation_img.linear.weight": "double_stream_modulation_img.lin.weight",
        "double_stream_modulation_txt.linear.weight": "double_stream_modulation_txt.lin.weight",
        "single_stream_modulation.linear.weight": "single_stream_modulation.lin.weight",
        "time_guidance_embed.timestep_embedder.linear_1.weight": "time_in.in_layer.weight",
        "time_guidance_embed.timestep_embedder.linear_2.weight": "time_in.out_layer.weight",
    }

    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    template_keys: set[str] | None = None
    template_shapes: dict[str, tuple[int, ...]] = {}
    if args.key_template:
        template = args.key_template.expanduser().resolve()
        if not template.is_file():
            raise FileNotFoundError(template)
        with safe_open(template, framework="pt", device="cpu") as template_file:
            template_keys = set(template_file.keys())
            template_shapes = {
                key: tuple(template_file.get_slice(key).get_shape())
                for key in template_keys
            }

    with safe_open(source, framework="pt", device="cpu") as opened:
        source_keys = set(opened.keys())
        metadata = opened.metadata() or {}
        double_indices = {
            int(match.group(1))
            for key in source_keys
            if (match := re.match(r"double_blocks\.(\d+)\.", key))
        }
        single_indices = {
            int(match.group(1))
            for key in source_keys
            if (match := re.match(r"single_blocks\.(\d+)\.", key))
        }
        hidden_size = opened.get_slice("img_in.weight").get_shape()[0]
        mapping = flux_to_diffusers(
            {
                "depth": max(double_indices) + 1,
                "depth_single_blocks": max(single_indices) + 1,
                "hidden_size": hidden_size,
            }
        )
        mapping.update(native_flux2_aliases)

        converted: dict[str, torch.Tensor] = {}
        dequantized_sources: set[str] = set()
        missing: list[str] = []
        for diffusers_key, target in mapping.items():
            if template_keys is not None and diffusers_key not in template_keys:
                continue
            if isinstance(target, str):
                comfy_key = target
                offset = None
                transform = None
            else:
                comfy_key = target[0]
                offset = target[1]
                transform = target[2] if len(target) > 2 else None
            actual_key = comfy_key
            if actual_key not in source_keys and actual_key.endswith(".weight"):
                scale_key = actual_key.removesuffix(".weight") + ".scale"
                if scale_key in source_keys:
                    actual_key = scale_key
            if actual_key not in source_keys:
                missing.append(diffusers_key)
                continue

            tensor = opened.get_tensor(actual_key)
            if tensor.dtype in {torch.float8_e4m3fn, torch.float8_e5m2}:
                weight_scale_key = comfy_key.removesuffix(".weight") + ".weight_scale"
                if weight_scale_key not in source_keys:
                    raise RuntimeError(f"Missing FP8 scale for {comfy_key}")
                weight_scale = opened.get_tensor(weight_scale_key).float()
                tensor = (tensor.float() * weight_scale).to(torch.bfloat16)
                dequantized_sources.add(comfy_key)
            else:
                tensor = tensor.to(torch.bfloat16)
            if offset is not None:
                tensor = tensor.narrow(offset[0], offset[1], offset[2])
            if transform is not None:
                if getattr(transform, "__name__", "") != "swap_scale_shift":
                    raise RuntimeError(f"Unsupported inverse transform for {diffusers_key}")
                tensor = transform(tensor)
            converted[diffusers_key] = tensor.contiguous()

    if template_keys is not None:
        missing_template_keys = template_keys - set(converted)
        if missing_template_keys:
            raise RuntimeError(
                "Converted state dict is missing template keys: "
                + ", ".join(sorted(missing_template_keys))
            )
        shape_mismatches = {
            key: (tuple(converted[key].shape), template_shapes[key])
            for key in template_keys
            if tuple(converted[key].shape) != template_shapes[key]
        }
        if shape_mismatches:
            raise RuntimeError(f"Converted tensor shapes differ from template: {shape_mismatches}")

    required_markers = {
        "x_embedder.weight",
        "context_embedder.weight",
        "transformer_blocks.0.attn.to_q.weight",
        "single_transformer_blocks.0.attn.to_qkv_mlp_proj.weight",
        "proj_out.weight",
    }
    if not required_markers.issubset(converted):
        raise RuntimeError(
            "Converted state dict is incomplete: "
            + ", ".join(sorted(required_markers - set(converted)))
        )
    save_file(converted, output, metadata={"format": "pt"})
    report = {
        "schema": "assetsstudio_comfy_flux2_fp8_to_diffsynth_bf16_v1",
        "input": str(source),
        "output": str(output),
        "downloaded": False,
        "source_has_quantization_metadata": "_quantization_metadata" in metadata,
        "double_blocks": len(double_indices),
        "single_blocks": len(single_indices),
        "hidden_size": hidden_size,
        "source_tensors": len(source_keys),
        "output_tensors": len(converted),
        "key_template_used": str(args.key_template.expanduser().resolve()) if args.key_template else None,
        "key_template_tensors": len(template_keys) if template_keys is not None else None,
        "dequantized_fused_sources": len(dequantized_sources),
        "unavailable_optional_diffusers_keys": len(missing),
    }
    report_path = args.report.expanduser().resolve() if args.report else output.with_suffix(".json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
