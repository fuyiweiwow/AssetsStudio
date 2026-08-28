#!/usr/bin/env python3
"""Run one non-destructive Actor Core inference hardware/quality gate.

The command uses the same prompt compiler and ComfyUI graph as Studio, but it
never accepts, publishes, or deletes an asset.  Every run is copied into an
isolated result directory so it can be reviewed or moved between machines.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import urllib.error
import uuid
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

import cv2

from analyze_actor_core_shape import analyze_actor_core_shape
from analyze_turnaround_sheet import analyze_turnaround
from run_comfy_flux2_klein import build_prompt, request_json, sample_nvidia_gpu
from studio_local_generation_api import (
    ACTOR_CORE_LORA,
    COMFY_OUTPUT,
    COMFY_ROOT,
    COMFY_URL,
    MODEL_FILES,
    STYLE_PROFILES,
    compile_profile_turnaround_prompt,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STYLE_PROFILE = "qstyle_anime_western_fantasy_no_face_v1"
DEFAULT_SUBJECT = (
    "通用 Q 版模块化标准 Actor：非性化中性光滑 mannequin 素体，光头、无耳、"
    "无眼睛眉毛睫毛、无嘴鼻，完全没有头发、服装、鞋、手套或饰品，单一中性哑光材质"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def output_path(entry: dict[str, str]) -> Path:
    candidate = (
        COMFY_OUTPUT / entry.get("subfolder", "") / entry["filename"]
    ).resolve()
    if COMFY_OUTPUT.resolve() not in candidate.parents:
        raise ValueError("ComfyUI returned an output outside its output directory")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--style-profile", default=DEFAULT_STYLE_PROFILE)
    parser.add_argument("--subject", default=DEFAULT_SUBJECT)
    parser.add_argument("--lora-strength", type=float, default=3.0)
    parser.add_argument(
        "--lora",
        help="Optional LoRA filename relative to ComfyUI models/loras; otherwise discover it",
    )
    parser.add_argument("--expected-lora-sha256", required=True)
    parser.add_argument("--server", default=COMFY_URL)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--qualification-record", type=Path)
    parser.add_argument(
        "--cold-start-observed",
        action="store_true",
        help="Record that the caller started ComfyUI from a stopped state for this run.",
    )
    parser.add_argument(
        "--allow-non-target-gpu",
        action="store_true",
        help="Allow a development GPU other than RTX 3060; result remains prescreen only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Source is not a readable image: {source}")
    if image.shape[1] != 1536 or image.shape[0] != 768:
        raise ValueError(
            f"Hardware Gate source must be 1536x768, got {image.shape[1]}x{image.shape[0]}"
        )

    gpu = sample_nvidia_gpu()
    if gpu is None:
        raise RuntimeError("nvidia-smi did not return a usable NVIDIA GPU")
    is_target_gpu = (
        "RTX 3060" in gpu["name"].upper().replace("GEFORCE ", "")
        and gpu["total_mib"] >= 11000
    )
    if not is_target_gpu and not args.allow_non_target_gpu:
        raise RuntimeError(
            f"Target GPU is RTX 3060 12GB, found {gpu['name']} with "
            f"{gpu['total_mib']} MiB; "
            "use --allow-non-target-gpu only for development prescreening"
        )

    missing_models = [str(path) for path in MODEL_FILES.values() if not path.is_file()]
    if missing_models:
        raise FileNotFoundError("Missing ComfyUI model files: " + ", ".join(missing_models))
    selected_lora = args.lora or ACTOR_CORE_LORA
    if selected_lora is None:
        raise FileNotFoundError("No strip_to_actor_core LoRA was discovered")
    lora_root = (COMFY_ROOT / "models" / "loras").resolve()
    lora_path = (lora_root / selected_lora).resolve()
    if lora_root not in lora_path.parents or not lora_path.is_file():
        raise FileNotFoundError(f"LoRA is outside ComfyUI or missing: {lora_path}")
    lora_hash = sha256_file(lora_path)
    expected_hash = args.expected_lora_sha256.lower()
    if lora_hash != expected_hash:
        raise ValueError(
            f"Actor Core LoRA SHA256 mismatch: expected {expected_hash}, got {lora_hash}"
        )

    style_profile = STYLE_PROFILES.get(args.style_profile)
    if style_profile is None:
        raise ValueError(f"Unknown style profile: {args.style_profile}")
    compiled_prompt = compile_profile_turnaround_prompt(args.subject, style_profile)

    source_hash = sha256_file(source)
    run_id = f"seed_{args.seed}_{source_hash[:8]}"
    run_root = args.output_root.expanduser().resolve() / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    input_relative = Path("assetsstudio_actor_core_gate") / f"{source_hash}.png"
    input_path = COMFY_ROOT / "input" / input_relative
    input_path.parent.mkdir(parents=True, exist_ok=True)
    if not input_path.is_file() or sha256_file(input_path) != source_hash:
        shutil.copy2(source, input_path)

    workflow_args = Namespace(
        model=MODEL_FILES["diffusion_model"].name,
        text_encoder=MODEL_FILES["text_encoder"].name,
        vae=MODEL_FILES["vae"].name,
        prompt=compiled_prompt,
        reference_image=input_relative.as_posix(),
        width=1536,
        height=768,
        steps=4,
        cfg=1.0,
        seed=args.seed,
        prefix=f"AssetsStudio/actor_core_hardware_gate/{run_id}",
        lora=selected_lora,
        lora_strength=args.lora_strength,
    )

    baseline_gpu = sample_nvidia_gpu()
    peak_used_mib = baseline_gpu["used_mib"] if baseline_gpu else None
    started = time.perf_counter()
    response = request_json(
        f"{args.server.rstrip('/')}/prompt",
        {"prompt": build_prompt(workflow_args), "client_id": str(uuid.uuid4())},
    )
    prompt_id = response["prompt_id"]
    print(f"queued prompt_id={prompt_id}", flush=True)

    deadline = time.monotonic() + args.timeout
    entry: dict[str, str] | None = None
    while time.monotonic() < deadline:
        sampled_gpu = sample_nvidia_gpu()
        if sampled_gpu and (
            peak_used_mib is None or sampled_gpu["used_mib"] > peak_used_mib
        ):
            peak_used_mib = sampled_gpu["used_mib"]
        history = request_json(f"{args.server.rstrip('/')}/history/{prompt_id}")
        if prompt_id not in history:
            time.sleep(1)
            continue
        item = history[prompt_id]
        if item.get("status", {}).get("status_str") == "error":
            write_json(run_root / "comfy_error.json", item)
            raise RuntimeError(f"ComfyUI generation failed; see {run_root / 'comfy_error.json'}")
        for node_output in item.get("outputs", {}).values():
            images = node_output.get("images", [])
            if images:
                entry = images[0]
                break
        break
    if entry is None:
        raise TimeoutError("ComfyUI generation timed out or returned no image")

    elapsed = time.perf_counter() - started
    generated = output_path(entry)
    result_image = run_root / "actor_core.png"
    shutil.copy2(generated, result_image)
    turnaround = analyze_turnaround(result_image, 3)
    actor_shape = analyze_actor_core_shape(result_image, 3)
    automatic_pass = turnaround["automatic_pass"] and actor_shape["automatic_pass"]
    qualification = "rtx_3060_hardware_gate" if is_target_gpu else "development_gpu_prescreen_only"
    report = {
        "schema": "assetsstudio_actor_core_hardware_gate_v1",
        "qualification": qualification,
        "automatic_pass": automatic_pass,
        "manual_review_required": True,
        "source": {
            "filename": source.name,
            "sha256": source_hash,
            "width": image.shape[1],
            "height": image.shape[0],
        },
        "output": {
            "filename": result_image.name,
            "sha256": sha256_file(result_image),
        },
        "generation": {
            "prompt_id": prompt_id,
            "compiled_prompt": compiled_prompt,
            "seed": args.seed,
            "width": 1536,
            "height": 768,
            "steps": 4,
            "cfg": 1.0,
            "lora": selected_lora,
            "lora_sha256": lora_hash,
            "lora_strength": args.lora_strength,
            "elapsed_seconds": round(elapsed, 2),
        },
        "environment": {
            "gpu": gpu,
            "baseline_used_mib": baseline_gpu["used_mib"] if baseline_gpu else None,
            "peak_used_mib": peak_used_mib,
            "peak_delta_mib": (
                peak_used_mib - baseline_gpu["used_mib"]
                if baseline_gpu and peak_used_mib is not None
                else None
            ),
            "comfy_root_discovery": str(COMFY_ROOT),
        },
        "turnaround_qa": turnaround,
        "actor_core_shape_qa": actor_shape,
    }
    write_json(run_root / "report.json", report)
    if args.qualification_record and is_target_gpu and automatic_pass:
        qualification_status = (
            "passed" if args.cold_start_observed else "warm_runtime_passed_cold_start_pending"
        )
        qualification_record = {
            "schema": "assetsstudio_rtx3060_actor_core_qualification_v1",
            "status": qualification_status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hardware": gpu,
            "cold_start_observed": args.cold_start_observed,
            "generation_contract": {
                "width": 1536,
                "height": 768,
                "steps": 4,
                "cfg": 1.0,
                "seed": args.seed,
                "lora_sha256": lora_hash,
                "lora_strength": args.lora_strength,
            },
            "automatic_pass": True,
            "persistence_check": {
                "saved_image_sha256": report["output"]["sha256"],
                "reloaded_image_sha256": sha256_file(result_image),
                "passed": report["output"]["sha256"] == sha256_file(result_image),
            },
            "report": str((run_root / "report.json").resolve()),
        }
        write_json(args.qualification_record.expanduser().resolve(), qualification_record)
    print(
        f"completed automatic_pass={automatic_pass} seconds={elapsed:.2f} "
        f"result={result_image}"
    )
    return 0 if automatic_pass else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        raise SystemExit(f"ComfyUI request failed: {exc}") from exc
