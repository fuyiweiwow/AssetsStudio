#!/usr/bin/env python3
"""Local-only HTTP bridge between AssetsStudio and ComfyUI FLUX.2 Klein."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from argparse import Namespace
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from run_comfy_flux2_klein import build_prompt


ROOT = Path(__file__).resolve().parents[2]
COMFY_ROOT = Path(os.environ.get("ASSETSSTUDIO_COMFY_ROOT", r"E:\Env\ComfyUI"))
COMFY_URL = os.environ.get("ASSETSSTUDIO_COMFY_URL", "http://127.0.0.1:8190").rstrip("/")
COMFY_OUTPUT = COMFY_ROOT / "output"
ARTIFACT_ROOT = ROOT / "workspace" / "local_generation" / "turnarounds"

MODEL_FILES = {
    "diffusion_model": COMFY_ROOT
    / "models"
    / "diffusion_models"
    / "flux-2-klein-4b-fp8.safetensors",
    "text_encoder": COMFY_ROOT
    / "models"
    / "text_encoders"
    / "qwen_3_4b.safetensors",
    "vae": COMFY_ROOT / "models" / "vae" / "flux2-vae.safetensors",
}

STYLE_PROMPTS = {
    "soft_3d": (
        "polished soft 3D Japanese-anime game figurine, smooth rounded low-frequency "
        "geometry, soft studio light, subtle ambient occlusion, clean material colors"
    ),
    "clean_2d": (
        "clean Japanese-anime game character design sheet, controlled cel shading, "
        "crisp coherent shapes, restrained linework"
    ),
}

JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def comfy_reachable() -> bool:
    try:
        request_json(f"{COMFY_URL}/system_stats", timeout=3)
        return True
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def compile_prompt(subject: str, style: str) -> str:
    return (
        f"Design ONE character: {subject.strip()}. Create one production orthographic "
        "turnaround sheet with exactly three separate full-body views arranged left to "
        "right: exact front, exact right profile, exact back. The same character, identity, "
        "face, hairstyle, outfit construction, colors, neutral symmetrical A-pose, scale, "
        "compact chibi proportion, and ground line in every view. "
        f"Render style: {STYLE_PROMPTS[style]}. Uniform light gray background. No perspective, "
        "no three-quarter view, no action pose, no props, no text, no labels, no borders, "
        "no extra characters, no duplicated body parts, no cropped feet."
    )


def update_job(job_id: str, **updates: Any) -> None:
    with JOBS_LOCK:
        JOBS[job_id].update(updates)
        JOBS[job_id]["updated_at"] = utc_now()


def safe_comfy_output(subfolder: str, filename: str) -> Path:
    candidate = (COMFY_OUTPUT / subfolder / filename).resolve()
    output_root = COMFY_OUTPUT.resolve()
    if output_root not in candidate.parents:
        raise ValueError("ComfyUI returned an unsafe output path")
    return candidate


def run_generation(job_id: str) -> None:
    with JOBS_LOCK:
        job = dict(JOBS[job_id])
    try:
        update_job(job_id, status="submitting")
        args = Namespace(
            model="flux-2-klein-4b-fp8.safetensors",
            text_encoder="qwen_3_4b.safetensors",
            vae="flux2-vae.safetensors",
            prompt=job["compiled_prompt"],
            reference_image=None,
            width=1536,
            height=768,
            steps=4,
            cfg=1.0,
            seed=job["seed"],
            prefix=f"assetsstudio/turnarounds/{job_id}",
        )
        response = request_json(
            f"{COMFY_URL}/prompt",
            {"prompt": build_prompt(args), "client_id": str(uuid.uuid4())},
        )
        prompt_id = response["prompt_id"]
        update_job(job_id, status="generating", comfy_prompt_id=prompt_id)

        deadline = time.monotonic() + 1800
        output_entry: dict[str, str] | None = None
        while time.monotonic() < deadline:
            history = request_json(f"{COMFY_URL}/history/{prompt_id}")
            if prompt_id not in history:
                time.sleep(2)
                continue
            item = history[prompt_id]
            if item.get("status", {}).get("status_str") == "error":
                raise RuntimeError("ComfyUI generation failed; inspect its server log")
            for node_output in item.get("outputs", {}).values():
                images = node_output.get("images", [])
                if images:
                    output_entry = images[0]
                    break
            break
        if output_entry is None:
            raise TimeoutError("ComfyUI generation timed out or returned no image")

        source = safe_comfy_output(
            output_entry.get("subfolder", ""), output_entry["filename"]
        )
        if not source.is_file():
            raise FileNotFoundError(source)
        job_dir = ARTIFACT_ROOT / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        artifact = job_dir / "turnaround.png"
        shutil.copy2(source, artifact)

        record = {
            **job,
            "status": "completed",
            "updated_at": utc_now(),
            "comfy_prompt_id": prompt_id,
            "artifact": str(artifact),
            "qa_status": "visual_review_required",
            "generation_contract": {
                "views": ["front", "right", "back"],
                "width": 1536,
                "height": 768,
                "steps": 4,
                "cfg": 1.0,
            },
        }
        (job_dir / "record.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        update_job(
            job_id,
            status="completed",
            image_url=f"/api/turnarounds/{job_id}/image",
            record_url=f"/api/turnarounds/{job_id}/record",
            qa_status="visual_review_required",
        )
    except Exception as exc:  # expose a concise local diagnostic to Studio
        update_job(job_id, status="failed", error=str(exc))


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "id",
        "status",
        "created_at",
        "updated_at",
        "subject",
        "compiled_prompt",
        "style",
        "seed",
        "image_url",
        "record_url",
        "qa_status",
        "error",
    }
    return {key: value for key, value in job.items() if key in allowed}


class Handler(BaseHTTPRequestHandler):
    server_version = "AssetsStudioLocalGeneration/0.1"

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}", flush=True)

    def send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:4173")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:4173")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/health":
            models = {name: file.is_file() for name, file in MODEL_FILES.items()}
            self.send_json(
                HTTPStatus.OK,
                {
                    "status": "ready" if comfy_reachable() and all(models.values()) else "offline",
                    "comfyui": comfy_reachable(),
                    "model_ready": all(models.values()),
                    "models": models,
                    "comfy_url": COMFY_URL,
                    "artifact_root": str(ARTIFACT_ROOT),
                },
            )
            return

        parts = [part for part in path.split("/") if part]
        if len(parts) >= 3 and parts[:2] == ["api", "turnarounds"]:
            job_id = parts[2]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if job is None:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "job not found"})
                return
            if len(parts) == 3:
                self.send_json(HTTPStatus.OK, public_job(job))
                return
            job_dir = ARTIFACT_ROOT / job_id
            if len(parts) == 4 and parts[3] == "image":
                self.send_file(job_dir / "turnaround.png", "image/png")
                return
            if len(parts) == 4 and parts[3] == "record":
                self.send_file(job_dir / "record.json", "application/json; charset=utf-8")
                return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "route not found"})

    def send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "artifact not ready"})
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:4173")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path != "/api/turnarounds":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "route not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16_384:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length))
            subject = str(payload.get("subject", "")).strip()
            style = str(payload.get("style", "soft_3d"))
            seed = int(payload.get("seed", 20260823))
            if not 8 <= len(subject) <= 1000:
                raise ValueError("subject must contain 8-1000 characters")
            if style not in STYLE_PROMPTS:
                raise ValueError("unsupported style")
            if not 0 <= seed <= 2**63 - 1:
                raise ValueError("seed out of range")
            if not comfy_reachable() or not all(path.is_file() for path in MODEL_FILES.values()):
                self.send_json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"error": "ComfyUI or required FLUX.2 model files are not ready"},
                )
                return
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        job_id = uuid.uuid4().hex
        created = utc_now()
        job = {
            "id": job_id,
            "status": "queued",
            "created_at": created,
            "updated_at": created,
            "subject": subject,
            "compiled_prompt": compile_prompt(subject, style),
            "style": style,
            "seed": seed,
        }
        with JOBS_LOCK:
            JOBS[job_id] = job
        threading.Thread(target=run_generation, args=(job_id,), daemon=True).start()
        self.send_json(HTTPStatus.ACCEPTED, public_job(job))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"AssetsStudio local generation API: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
