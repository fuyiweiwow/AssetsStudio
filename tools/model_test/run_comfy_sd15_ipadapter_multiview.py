"""Generate four controlled character views with local ComfyUI.

Actor orthographic renders provide per-view lineart structure. One approved
front concept provides a shared IP-Adapter appearance condition. Views are
submitted sequentially with the same seed to stay inside 12 GB VRAM.
"""

import argparse
import json
import shutil
import time
import uuid
from pathlib import Path

import cv2
import numpy as np
import requests
from PIL import Image


VIEW_ORDER = ("front", "right", "back", "left")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument(
        "--reference",
        default=r"E:\env\outputs\local_threeview_20260823\actor_v2_animagine_canny_front.png",
    )
    parser.add_argument(
        "--controls-dir",
        default=r"E:\WorkProject\AssetsStudio\references\actor_v2\base_v1\rgb",
    )
    parser.add_argument(
        "--output-dir", default=r"E:\env\outputs\local_threeview_20260823\sd15_ipadapter"
    )
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument("--steps", type=int, default=28)
    parser.add_argument("--cfg", type=float, default=7.0)
    parser.add_argument("--ip-weight", type=float, default=0.66)
    parser.add_argument("--control-strength", type=float, default=1.10)
    parser.add_argument("--control-end", type=float, default=0.95)
    return parser.parse_args()


def prepare_inputs(args: argparse.Namespace) -> tuple[str, dict[str, str]]:
    comfy_input = Path(r"E:\Env\ComfyUI\input")
    input_dir = comfy_input / "local_threeview_20260823"
    input_dir.mkdir(parents=True, exist_ok=True)
    reference_name = "local_threeview_20260823/ip_reference.png"
    reference = Image.open(args.reference).convert("RGB")
    reference.thumbnail((512, 512), Image.Resampling.LANCZOS)
    reference_canvas = Image.new("RGB", (512, 512), (224, 224, 224))
    reference_canvas.paste(
        reference, ((512 - reference.width) // 2, (512 - reference.height) // 2)
    )
    reference_canvas.save(comfy_input / reference_name)

    controls: dict[str, str] = {}
    for view in VIEW_ORDER:
        source = cv2.imread(str(Path(args.controls_dir) / f"{view}.png"))
        if source is None:
            raise FileNotFoundError(Path(args.controls_dir) / f"{view}.png")
        resized = cv2.resize(source, (512, 512), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 70, 150)
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
            (edges > 0).astype(np.uint8), connectivity=8
        )
        cleaned = np.zeros_like(edges)
        for component in range(1, component_count):
            x, y, width, height, area = stats[component]
            touches_edge = x == 0 or y == 0 or x + width >= 512 or y + height >= 512
            is_frame_line = height > 420 or width > 420
            if area >= 2 and not touches_edge and not is_frame_line:
                cleaned[labels == component] = 255
        points = cv2.findNonZero(cleaned)
        if points is None:
            raise RuntimeError(f"No usable lineart extracted for {view}")
        x, y, width, height = cv2.boundingRect(points)
        margin = 8
        x0, y0 = max(0, x - margin), max(0, y - margin)
        x1, y1 = min(512, x + width + margin), min(512, y + height + margin)
        crop = cleaned[y0:y1, x0:x1]
        scale = min(430 / crop.shape[0], 430 / crop.shape[1])
        scaled = cv2.resize(
            crop,
            (max(1, round(crop.shape[1] * scale)), max(1, round(crop.shape[0] * scale))),
            interpolation=cv2.INTER_NEAREST,
        )
        edges = np.zeros((512, 512), dtype=np.uint8)
        paste_y = (512 - scaled.shape[0]) // 2
        paste_x = (512 - scaled.shape[1]) // 2
        edges[paste_y : paste_y + scaled.shape[0], paste_x : paste_x + scaled.shape[1]] = scaled
        edges = cv2.dilate(edges, np.ones((2, 2), dtype=np.uint8), iterations=1)
        lineart = 255 - edges
        name = f"local_threeview_20260823/control_{view}.png"
        cv2.imwrite(str(comfy_input / name), lineart)
        controls[view] = name
    return reference_name, controls


def workflow_for_view(
    args: argparse.Namespace, reference_name: str, control_name: str, view: str
) -> dict:
    view_prompt = {
        "front": "strict orthographic front view, looking straight ahead",
        "right": "strict orthographic right side profile, exact 90 degree side view",
        "back": "strict orthographic back view, back of head visible, face not visible",
        "left": "strict orthographic left side profile, exact 90 degree side view",
    }[view]
    view_negative = {
        "front": "three-quarter view, side view, back view",
        "right": "front view, back view, three-quarter view, looking at viewer",
        "back": "face, eyes, front view, side view, three-quarter view, looking at viewer",
        "left": "front view, back view, three-quarter view, looking at viewer",
    }[view]
    positive = (
        "masterpiece, best quality, 1girl, chibi anime western fantasy adventurer, "
        "full body, neutral standing pose, same character, same short layered brown hair, "
        "same large blue eyes, same blue short adventurer jacket, cream shirt, red neck scarf, "
        "olive shorts, brown belt pouch, gloves and boots, clean polished anime game character, "
        f"simple neutral gray background, {view_prompt}"
    )
    negative = (
        "worst quality, low quality, text, watermark, logo, multiple characters, multiple views, "
        "turnaround sheet, cropped, weapon, action pose, tall realistic proportions, dress, skirt, "
        "cape, backpack, different hair, different clothes, changed colors, extra limbs, malformed, "
        f"{view_negative}"
    )
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "Counterfeit-V3.0_fp16.safetensors"},
        },
        "2": {
            "class_type": "CLIPVisionLoader",
            "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"},
        },
        "3": {
            "class_type": "IPAdapterModelLoader",
            "inputs": {"ipadapter_file": "ip-adapter_sd15.safetensors"},
        },
        "4": {"class_type": "LoadImage", "inputs": {"image": reference_name}},
        "5": {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": ["1", 0],
                "ipadapter": ["3", 0],
                "image": ["4", 0],
                "clip_vision": ["2", 0],
                "weight": args.ip_weight,
                "weight_type": "linear",
                "combine_embeds": "concat",
                "start_at": 0.0,
                "end_at": 0.88,
                "embeds_scaling": "K+V w/ C penalty",
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive, "clip": ["1", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["1", 1]},
        },
        "8": {
            "class_type": "ControlNetLoader",
            "inputs": {
                "control_net_name": "control_v11p_sd15s2_lineart_anime_fp16_verified.safetensors"
            },
        },
        "9": {"class_type": "LoadImage", "inputs": {"image": control_name}},
        "10": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": ["6", 0],
                "negative": ["7", 0],
                "control_net": ["8", 0],
                "image": ["9", 0],
                "strength": args.control_strength,
                "start_percent": 0.0,
                "end_percent": args.control_end,
                "vae": ["1", 2],
            },
        },
        "11": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
        },
        "12": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["5", 0],
                "seed": args.seed,
                "steps": args.steps,
                "cfg": args.cfg,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "positive": ["10", 0],
                "negative": ["10", 1],
                "latent_image": ["11", 0],
                "denoise": 1.0,
            },
        },
        "13": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["12", 0], "vae": ["1", 2]},
        },
        "14": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["13", 0],
                "filename_prefix": f"local_threeview_20260823/{view}",
            },
        },
    }


def wait_for_result(server: str, prompt_id: str, timeout: int = 600) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = requests.get(f"{server}/history/{prompt_id}", timeout=10)
        response.raise_for_status()
        history = response.json()
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(1)
    raise TimeoutError(f"ComfyUI prompt timed out: {prompt_id}")


def main() -> None:
    args = parse_args()
    reference_name, control_names = prepare_inputs(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    client_id = str(uuid.uuid4())
    images: list[Image.Image] = []
    records = []
    for view in VIEW_ORDER:
        workflow = workflow_for_view(args, reference_name, control_names[view], view)
        response = requests.post(
            f"{args.server}/prompt",
            json={"prompt": workflow, "client_id": client_id},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("node_errors"):
            raise RuntimeError(json.dumps(payload["node_errors"], ensure_ascii=False))
        prompt_id = payload["prompt_id"]
        result = wait_for_result(args.server, prompt_id)
        status = result.get("status", {})
        if status.get("status_str") != "success":
            raise RuntimeError(json.dumps(status, ensure_ascii=False))
        saved = result["outputs"]["14"]["images"][0]
        source = Path(r"E:\Env\ComfyUI\output") / saved.get("subfolder", "") / saved["filename"]
        destination = output_dir / f"{view}.png"
        shutil.copy2(source, destination)
        images.append(Image.open(destination).convert("RGB"))
        records.append({"view": view, "prompt_id": prompt_id, "file": str(destination)})
        print(f"COMFY_IPADAPTER_VIEW_PASS {view} {destination}")

    grid = Image.new("RGB", (512 * len(images), 512), (224, 224, 224))
    for index, image in enumerate(images):
        grid.paste(image, (index * 512, 0))
    grid_path = output_dir / "front_right_back_left.png"
    grid.save(grid_path)
    report = {
        "schema": "assetsstudio_sd15_ipadapter_multiview_v1",
        "reference": str(Path(args.reference).resolve()),
        "controls_dir": str(Path(args.controls_dir).resolve()),
        "views": records,
        "seed": args.seed,
        "steps": args.steps,
        "cfg": args.cfg,
        "ip_weight": args.ip_weight,
        "control_strength": args.control_strength,
        "control_end": args.control_end,
        "checkpoint": "Counterfeit-V3.0_fp16.safetensors",
        "ipadapter": "ip-adapter_sd15.safetensors",
        "controlnet": "control_v11p_sd15s2_lineart_anime_fp16_verified.safetensors",
        "grid": str(grid_path),
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"COMFY_IPADAPTER_MULTIVIEW_PASS {grid_path}")


if __name__ == "__main__":
    main()
