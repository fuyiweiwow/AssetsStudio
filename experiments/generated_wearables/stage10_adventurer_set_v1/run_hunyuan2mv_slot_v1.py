from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import torch
from PIL import Image


ROOT = Path(__file__).resolve().parent
OFFICIAL_SOURCE = Path(
    os.environ.get("HUNYUAN3D_SOURCE", ROOT.parent / "Hunyuan3D-2-main")
).expanduser().resolve()
if str(OFFICIAL_SOURCE) not in sys.path:
    sys.path.insert(0, str(OFFICIAL_SOURCE))

from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--slot", required=True)
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--guidance", type=float, default=5.0)
    parser.add_argument("--octree", type=int, default=256)
    parser.add_argument("--chunks", type=int, default=8000)
    return parser.parse_args()


def main() -> int:
    options = arguments()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for Hunyuan3D-2mv")
    model = Path(
        os.environ.get("HUNYUAN3D_2MV_MODEL", ROOT.parent / "local_models" / "Hunyuan3D-2mv")
    ).expanduser().resolve()
    if not model.exists():
        raise FileNotFoundError(
            f"Hunyuan3D-2mv model not found: {model}. "
            "Set HUNYUAN3D_2MV_MODEL to the local model directory."
        )
    images = {
        view: Image.open(options.input_dir / f"{view}_rgba.png").convert("RGBA")
        for view in ("front", "left", "back", "right")
    }
    print(f"GPU={torch.cuda.get_device_name(0)} SLOT={options.slot}")
    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        str(model),
        subfolder="hunyuan3d-dit-v2-mv",
        use_safetensors=False,
        device="cuda",
        dtype=torch.float16,
    )
    generator = torch.Generator(device="cuda").manual_seed(options.seed)
    outputs = pipeline(
        image=images,
        num_inference_steps=options.steps,
        guidance_scale=options.guidance,
        generator=generator,
        octree_resolution=options.octree,
        num_chunks=options.chunks,
        output_type="trimesh",
        enable_pbar=True,
    )
    mesh = outputs[0]
    options.output.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(options.output)
    report = {
        "schema": "hunyuan3d_2mv_slot_generation_v1",
        "slot": options.slot,
        "input_dir": str(options.input_dir.resolve()),
        "output": str(options.output.resolve()),
        "seed": options.seed,
        "steps": options.steps,
        "guidance": options.guidance,
        "octree": options.octree,
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "status": "pass",
    }
    options.manifest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
