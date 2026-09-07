#!/usr/bin/env python3
"""Submit a low-VRAM FLUX.2 Klein generation/edit job to local ComfyUI."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def request_json(url: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def sample_nvidia_gpu() -> dict[str, int | str] | None:
    """Return a lightweight whole-GPU sample without adding Python GPU deps."""
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        first_line = completed.stdout.strip().splitlines()[0]
        name, total_mib, used_mib = [part.strip() for part in first_line.split(",", 2)]
        return {
            "name": name,
            "total_mib": int(total_mib),
            "used_mib": int(used_mib),
        }
    except (FileNotFoundError, IndexError, subprocess.SubprocessError, ValueError):
        return None


def write_metrics(path: str | None, payload: dict) -> None:
    if not path:
        return
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_prompt(args: argparse.Namespace) -> dict:
    style_reference_image = getattr(args, "style_reference_image", None)
    mask_image = getattr(args, "mask_image", None)
    mask_expand = getattr(args, "mask_expand", 0)
    mask_feather = getattr(args, "mask_feather", 0)
    composite_mask = getattr(args, "composite_mask", True)
    model_output = ["18", 0] if args.lora else ["1", 0]
    prompt = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": args.model,
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": args.text_encoder,
                "type": "flux2",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": args.vae},
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": args.prompt, "clip": ["2", 0]},
        },
        "5": {
            "class_type": "ConditioningZeroOut",
            "inputs": {"conditioning": ["4", 0]},
        },
        "6": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {
                "width": args.width,
                "height": args.height,
                "batch_size": 1,
            },
        },
        "7": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": args.seed},
        },
        "8": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
        },
        "9": {
            "class_type": "Flux2Scheduler",
            "inputs": {
                "steps": args.steps,
                "width": args.width,
                "height": args.height,
            },
        },
        "10": {
            "class_type": "CFGGuider",
            "inputs": {
                "model": model_output,
                "positive": (
                    ["26", 0]
                    if style_reference_image
                    else (["16", 0] if args.reference_image else ["4", 0])
                ),
                "negative": (
                    ["27", 0]
                    if style_reference_image
                    else (["17", 0] if args.reference_image else ["5", 0])
                ),
                "cfg": args.cfg,
            },
        },
        "11": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["7", 0],
                "guider": ["10", 0],
                "sampler": ["8", 0],
                "sigmas": ["9", 0],
                "latent_image": ["21", 0] if mask_image else ["6", 0],
            },
        },
        "12": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["11", 0], "vae": ["3", 0]},
        },
        "13": {
            "class_type": "SaveImage",
            "inputs": {
                "images": (
                    ["23", 0] if mask_image and composite_mask else ["12", 0]
                ),
                "filename_prefix": args.prefix,
            },
        },
    }

    if args.lora:
        prompt["18"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["1", 0],
                "lora_name": args.lora,
                "strength_model": args.lora_strength,
            },
        }

    if args.reference_image:
        # Match ComfyUI's official FLUX.2 Klein distilled edit workflow: encode
        # the source image once and attach it to both positive and negative
        # conditioning as a guiding reference latent.
        prompt.update(
            {
                "14": {
                    "class_type": "LoadImage",
                    "inputs": {"image": args.reference_image},
                },
                "15": {
                    "class_type": "VAEEncode",
                    "inputs": {"pixels": ["14", 0], "vae": ["3", 0]},
                },
                "16": {
                    "class_type": "ReferenceLatent",
                    "inputs": {
                        "conditioning": ["4", 0],
                        "latent": ["15", 0],
                    },
                },
                "17": {
                    "class_type": "ReferenceLatent",
                    "inputs": {
                        "conditioning": ["5", 0],
                        "latent": ["15", 0],
                    },
                },
            }
        )

    if style_reference_image:
        if not args.reference_image:
            raise ValueError("--style-reference-image requires --reference-image")
        prompt.update(
            {
                "24": {
                    "class_type": "LoadImage",
                    "inputs": {"image": style_reference_image},
                },
                "25": {
                    "class_type": "VAEEncode",
                    "inputs": {"pixels": ["24", 0], "vae": ["3", 0]},
                },
                "26": {
                    "class_type": "ReferenceLatent",
                    "inputs": {
                        "conditioning": ["16", 0],
                        "latent": ["25", 0],
                    },
                },
                "27": {
                    "class_type": "ReferenceLatent",
                    "inputs": {
                        "conditioning": ["17", 0],
                        "latent": ["25", 0],
                    },
                },
            }
        )

    if mask_image:
        if not args.reference_image:
            raise ValueError("--mask-image requires --reference-image")
        prompt.update(
            {
                "19": {
                    "class_type": "LoadImageMask",
                    "inputs": {"image": mask_image, "channel": "red"},
                },
                "20": {
                    "class_type": "GrowMask",
                    "inputs": {
                        "mask": ["19", 0],
                        "expand": mask_expand,
                        "tapered_corners": True,
                    },
                },
                "21": {
                    "class_type": "SetLatentNoiseMask",
                    "inputs": {"samples": ["15", 0], "mask": ["20", 0]},
                },
            }
        )
        if composite_mask:
            prompt.update(
                {
                    "22": {
                        "class_type": "FeatherMask",
                        "inputs": {
                            "mask": ["20", 0],
                            "left": mask_feather,
                            "top": mask_feather,
                            "right": mask_feather,
                            "bottom": mask_feather,
                        },
                    },
                    "23": {
                        "class_type": "ImageCompositeMasked",
                        "inputs": {
                            "destination": ["14", 0],
                            "source": ["12", 0],
                            "x": 0,
                            "y": 0,
                            "resize_source": False,
                            "mask": ["22", 0],
                        },
                    },
                }
            )

    return prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8190")
    parser.add_argument("--prompt", required=True)
    parser.add_argument(
        "--reference-image",
        help="Filename relative to ComfyUI's input directory; enables image editing",
    )
    parser.add_argument(
        "--style-reference-image",
        help="Optional second ComfyUI input image used only as style evidence",
    )
    parser.add_argument(
        "--style-reference-mode",
        default="appearance_only",
        choices=("appearance_only", "feature_prototype"),
    )
    parser.add_argument(
        "--mask-image",
        help="Optional red-channel ComfyUI input mask; requires --reference-image",
    )
    parser.add_argument("--mask-expand", type=int, default=4)
    parser.add_argument("--mask-feather", type=int, default=12)
    parser.add_argument(
        "--no-composite-mask",
        action="store_false",
        dest="composite_mask",
        help="Return the raw decoded image instead of restoring pixels outside the mask",
    )
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--cfg", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument("--prefix", default="flux2_klein_test")
    parser.add_argument(
        "--model", default="flux-2-klein-4b-fp8.safetensors"
    )
    parser.add_argument("--text-encoder", default="qwen_3_4b.safetensors")
    parser.add_argument("--vae", default="flux2-vae.safetensors")
    parser.add_argument(
        "--lora",
        help="Optional filename relative to ComfyUI's models/loras directory",
    )
    parser.add_argument("--lora-strength", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument(
        "--metrics-json",
        help="Optional path for elapsed time and whole-GPU peak-memory telemetry",
    )
    args = parser.parse_args()

    if args.width % 16 or args.height % 16:
        parser.error("width and height must be multiples of 16")

    client_id = str(uuid.uuid4())
    baseline_gpu = sample_nvidia_gpu()
    peak_used_mib = baseline_gpu["used_mib"] if baseline_gpu else None
    started = time.perf_counter()
    result = request_json(
        f"{args.server}/prompt",
        {"prompt": build_prompt(args), "client_id": client_id},
    )
    prompt_id = result["prompt_id"]
    print(f"queued prompt_id={prompt_id}", flush=True)

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        gpu = sample_nvidia_gpu()
        if gpu and (peak_used_mib is None or gpu["used_mib"] > peak_used_mib):
            peak_used_mib = gpu["used_mib"]
        history = request_json(f"{args.server}/history/{prompt_id}")
        if prompt_id in history:
            item = history[prompt_id]
            status = item.get("status", {})
            if status.get("status_str") == "error":
                print(json.dumps(item, ensure_ascii=False, indent=2))
                return 1

            outputs: list[str] = []
            for node_output in item.get("outputs", {}).values():
                for image in node_output.get("images", []):
                    filename = image.get("filename")
                    subfolder = image.get("subfolder", "")
                    if filename:
                        outputs.append(str(Path(subfolder) / filename))
            elapsed = time.perf_counter() - started
            metrics = {
                "schema": "assetsstudio_local_inference_probe_v1",
                "backend": "flux2_klein_4b_distilled_fp8",
                "server": args.server,
                "prompt_id": prompt_id,
                "width": args.width,
                "height": args.height,
                "steps": args.steps,
                "cfg": args.cfg,
                "seed": args.seed,
                "reference_image": args.reference_image,
                "style_reference_image": args.style_reference_image,
                "style_reference_mode": args.style_reference_mode,
                "reference_roles": {
                    "image_1": (
                        "structure_authority"
                        if args.style_reference_image
                        else "reference_authority"
                    ),
                    **(
                        {
                            "image_2": "style_only_evidence",
                            "conflict_rule": "image_1_wins_geometry_and_semantics",
                        }
                        if args.style_reference_image
                        else {}
                    ),
                },
                "mask_image": args.mask_image,
                "mask_expand": args.mask_expand if args.mask_image else None,
                "mask_feather": args.mask_feather if args.mask_image else None,
                "composite_mask": args.composite_mask if args.mask_image else None,
                "lora": args.lora,
                "lora_strength": args.lora_strength if args.lora else None,
                "elapsed_seconds": round(elapsed, 2),
                "gpu": None,
                "outputs": outputs,
                "qualification": "3060_memory_cap_prescreen_only",
            }
            if baseline_gpu and peak_used_mib is not None:
                metrics["gpu"] = {
                    "name": baseline_gpu["name"],
                    "total_mib": baseline_gpu["total_mib"],
                    "baseline_used_mib": baseline_gpu["used_mib"],
                    "peak_used_mib": peak_used_mib,
                    "peak_delta_mib": peak_used_mib - baseline_gpu["used_mib"],
                }
            write_metrics(args.metrics_json, metrics)
            print(f"completed seconds={elapsed:.2f}")
            for output in outputs:
                print(f"output={output}")
            return 0 if outputs else 2

        time.sleep(2)

    print(f"timed out prompt_id={prompt_id}")
    return 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        raise SystemExit(f"ComfyUI request failed: {exc}") from exc
