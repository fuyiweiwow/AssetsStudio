#!/usr/bin/env python3
"""Run the isolated Qwen-Image-Edit-2511 Actor Core benchmark in ComfyUI."""

from __future__ import annotations

import argparse
import json
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
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def build_prompt(args: argparse.Namespace) -> dict:
    prompt = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": args.reference_image},
        },
        "2": {
            "class_type": "FluxKontextImageScale",
            "inputs": {"image": ["1", 0]},
        },
        "3": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {"unet_name": args.model},
        },
        "4": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["3", 0], "shift": 3.1},
        },
        "5": {
            "class_type": "CFGNorm",
            "inputs": {"model": ["4", 0], "strength": 1.0},
        },
        "6": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": args.text_encoder,
                "type": "qwen_image",
                "device": "default",
            },
        },
        "7": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": args.vae},
        },
        "8": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {
                "clip": ["6", 0],
                "vae": ["7", 0],
                "image1": ["2", 0],
                "prompt": args.prompt,
            },
        },
        "9": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {
                "clip": ["6", 0],
                "vae": ["7", 0],
                "image1": ["2", 0],
                "prompt": "",
            },
        },
        "10": {
            "class_type": "FluxKontextMultiReferenceLatentMethod",
            "inputs": {
                "conditioning": ["8", 0],
                "reference_latents_method": "index_timestep_zero",
            },
        },
        "11": {
            "class_type": "FluxKontextMultiReferenceLatentMethod",
            "inputs": {
                "conditioning": ["9", 0],
                "reference_latents_method": "index_timestep_zero",
            },
        },
        "12": {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["2", 0], "vae": ["7", 0]},
        },
        "13": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["5", 0],
                "positive": ["10", 0],
                "negative": ["11", 0],
                "latent_image": ["20", 0] if args.mask_image else ["12", 0],
                "seed": args.seed,
                "steps": args.steps,
                "cfg": args.cfg,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "14": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["13", 0], "vae": ["7", 0]},
        },
        "15": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["22", 0] if args.mask_image else ["14", 0],
                "filename_prefix": args.prefix,
            },
        },
    }

    if args.reference_image_2:
        prompt.update(
            {
                "16": {
                    "class_type": "LoadImage",
                    "inputs": {"image": args.reference_image_2},
                },
                "17": {
                    "class_type": "FluxKontextImageScale",
                    "inputs": {"image": ["16", 0]},
                },
            }
        )
        prompt["8"]["inputs"]["image2"] = ["17", 0]
        prompt["9"]["inputs"]["image2"] = ["17", 0]

    if args.mask_image:
        prompt.update(
            {
                "18": {
                    "class_type": "LoadImageMask",
                    "inputs": {"image": args.mask_image, "channel": "red"},
                },
                "19": {
                    "class_type": "GrowMask",
                    "inputs": {
                        "mask": ["18", 0],
                        "expand": args.mask_expand,
                        "tapered_corners": True,
                    },
                },
                "20": {
                    "class_type": "SetLatentNoiseMask",
                    "inputs": {"samples": ["12", 0], "mask": ["19", 0]},
                },
                "21": {
                    "class_type": "FeatherMask",
                    "inputs": {
                        "mask": ["19", 0],
                        "left": args.mask_feather,
                        "top": args.mask_feather,
                        "right": args.mask_feather,
                        "bottom": args.mask_feather,
                    },
                },
                "22": {
                    "class_type": "ImageCompositeMasked",
                    "inputs": {
                        "destination": ["2", 0],
                        "source": ["14", 0],
                        "x": 0,
                        "y": 0,
                        "resize_source": False,
                        "mask": ["21", 0],
                    },
                },
            }
        )

    return prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8190")
    parser.add_argument("--reference-image", required=True)
    parser.add_argument(
        "--reference-image-2",
        help="Optional second image used only as a proportion/style authority",
    )
    parser.add_argument(
        "--mask-image",
        help="Optional red-channel mask relative to ComfyUI's input directory",
    )
    parser.add_argument("--mask-expand", type=int, default=4)
    parser.add_argument("--mask-feather", type=int, default=12)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--cfg", type=float, default=4.0)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--prefix", default="actor_core_qwen2511_benchmark")
    parser.add_argument(
        "--model", default="qwen-image-edit-2511-Q3_K_M.gguf"
    )
    parser.add_argument(
        "--text-encoder",
        default="qwen_2.5_vl_7b_fp8_scaled.safetensors",
    )
    parser.add_argument("--vae", default="qwen_image_vae.safetensors")
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()

    client_id = str(uuid.uuid4())
    started = time.perf_counter()
    result = request_json(
        f"{args.server}/prompt",
        {"prompt": build_prompt(args), "client_id": client_id},
    )
    prompt_id = result["prompt_id"]
    print(f"queued prompt_id={prompt_id}", flush=True)

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
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
