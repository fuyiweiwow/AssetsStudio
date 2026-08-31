#!/usr/bin/env python3
"""Local-only HTTP bridge between AssetsStudio and ComfyUI FLUX.2 Klein."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
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

from analyze_actor_core_shape import analyze_actor_core_shape
from analyze_turnaround_sheet import analyze_turnaround
from run_comfy_flux2_klein import build_prompt
from blender_environment import discover_blender


ROOT = Path(__file__).resolve().parents[2]


def discover_comfy_root() -> Path:
    configured = os.environ.get("ASSETSSTUDIO_COMFY_ROOT")
    candidates = [
        configured,
        ROOT.parent / "ComfyUI",
        Path.home() / "ComfyUI",
        Path(r"D:\Env\ComfyUI"),
        Path(r"E:\Env\ComfyUI"),
    ]
    for value in candidates:
        if not value:
            continue
        candidate = Path(value).expanduser().resolve()
        if (candidate / "main.py").is_file():
            return candidate
    raise RuntimeError(
        "ComfyUI was not found. Set ASSETSSTUDIO_COMFY_ROOT or place it beside AssetsStudio."
    )


COMFY_ROOT = discover_comfy_root()
COMFY_URL = os.environ.get("ASSETSSTUDIO_COMFY_URL", "http://127.0.0.1:8190").rstrip("/")
COMFY_OUTPUT = COMFY_ROOT / "output"
COMFY_INPUT = COMFY_ROOT / "input"
TURNAROUND_ARTIFACT_ROOT = ROOT / "workspace" / "local_generation" / "turnarounds"
STYLE_SEED_ARTIFACT_ROOT = ROOT / "workspace" / "local_generation" / "style_seeds"
BASE_ACTOR_ARTIFACT_ROOT = ROOT / "workspace" / "local_generation" / "base_actors"
ACCESSORY_ARTIFACT_ROOT = ROOT / "workspace" / "local_generation" / "accessories"
LOCAL_LIBRARY_ROOT = ROOT / "workspace" / "local_asset_library"
LOCAL_3D_CANDIDATE_ROOT = ROOT / "workspace" / "local_3d_generation" / "base_actors"
LOCAL_3D_LIBRARY_ROOT = ROOT / "workspace" / "local_3d_asset_library" / "base_actors"
LOCAL_3D_ACCESSORY_CANDIDATE_ROOT = ROOT / "workspace" / "local_3d_generation" / "accessories"
LOCAL_3D_ACCESSORY_LIBRARY_ROOT = ROOT / "workspace" / "local_3d_asset_library" / "accessories"
LOCAL_ANIMATION_LIBRARY_ROOT = ROOT / "workspace" / "local_animation_library"
TRAINING_PAIR_ROOT = (
    ROOT / "workspace" / "training" / "strip_to_actor_core" / "v1" / "pairs"
)
TRAINING_PREVIEW_ROOT = ROOT / "workspace" / "previews" / "strip_to_actor_core"
HARDWARE_QUALIFICATION_PATH = (
    ROOT
    / "workspace"
    / "hardware_validation"
    / "actor_core"
    / "rtx3060_qualification.json"
)
WORKSPACE_ROOT = ROOT / "workspace"
MAX_RIG_UPLOAD_BYTES = 1024 * 1024 * 1024
PROFILE_REGISTRY_PATH = ROOT / "studio" / "src" / "generated" / "style-slot-profiles.json"
PUBLISHED_STYLE_SEED_ROOT = ROOT / "references" / "style_profiles" / "published_seeds"

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


def discover_actor_core_lora() -> str | None:
    lora_root = (COMFY_ROOT / "models" / "loras").resolve()
    configured_value = os.environ.get("ASSETSSTUDIO_ACTOR_CORE_LORA")
    candidates: list[Path] = []
    if configured_value:
        candidates.append(Path(configured_value))
    discovered_root = lora_root / "assetsstudio"
    if discovered_root.is_dir():
        candidates.extend(
            sorted(
                discovered_root.glob("strip_to_actor_core*.safetensors"),
                key=lambda path: (path.stat().st_mtime_ns, path.name),
                reverse=True,
            )
        )
    for configured in candidates:
        candidate = configured if configured.is_absolute() else lora_root / configured
        candidate = candidate.expanduser().resolve()
        if candidate.is_file() and lora_root in candidate.parents:
            # ComfyUI validates this value against its platform-native model list.
            return str(candidate.relative_to(lora_root))
    return None


ACTOR_CORE_LORA = discover_actor_core_lora()
ACTOR_CORE_LORA_STRENGTHS = {2.0, 2.5, 3.0}
PRODUCTION_ACTOR_CORE_LORA_SHA256 = (
    "f0656f068ca5a76092af289a3129451e3faace67467f552c85ab27a97131da4c"
)

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

ROUTE_CONFIG = {
    "style-seeds": {
        "kind": "style_seed",
        "root": STYLE_SEED_ARTIFACT_ROOT,
        "filename": "style_seed.png",
    },
    "base-actors": {
        "kind": "base_actor",
        "root": BASE_ACTOR_ARTIFACT_ROOT,
        "filename": "base_actor_turnaround.png",
    },
    "turnarounds": {
        "kind": "base_actor",
        "root": BASE_ACTOR_ARTIFACT_ROOT,
        "filename": "base_actor_turnaround.png",
    },
    "accessories": {
        "kind": "accessory",
        "root": ACCESSORY_ARTIFACT_ROOT,
        "filename": "accessory_turnaround.png",
    },
}

LIBRARY_KIND_DIR = {
    "style_seed": "style_seeds",
    "base_actor": "base_actors",
    "accessory": "accessories",
}

THREE_D_MANUAL_GATES = [
    "front/right/back/left renders preserve the approved canonical Actor silhouette",
    "head is bald and earless with a smooth blank face and no facial-feature geometry",
    "mesh contains no hair, garment, footwear, accessory, cuff, seam, or clothing relief",
    "no obvious fused limbs or missing body parts",
    "candidate is acknowledged as an untextured source mesh, not game-ready",
]


def load_profile_registry() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    payload = json.loads(PROFILE_REGISTRY_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "assetsstudio_style_slot_registry_v1":
        raise RuntimeError("Style/slot registry schema is incompatible")
    styles = {profile["id"]: profile for profile in payload.get("styles", [])}
    actors = {profile["id"]: profile for profile in payload.get("actors", [])}
    if not styles or not actors:
        raise RuntimeError("Style/slot registry is empty")
    return styles, actors


STYLE_PROFILES, ACTOR_PROFILES = load_profile_registry()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hardware_validation_status() -> str:
    if not HARDWARE_QUALIFICATION_PATH.is_file():
        return "memory_cap_prescreen_passed_real_3060_pending"
    try:
        payload = json.loads(HARDWARE_QUALIFICATION_PATH.read_text(encoding="utf-8"))
        contract = payload["generation_contract"]
        persistence = payload["persistence_check"]
        gpu = payload["hardware"]
        if (
            payload.get("schema")
            == "assetsstudio_rtx3060_actor_core_qualification_v1"
            and payload.get("status") == "passed"
            and payload.get("automatic_pass") is True
            and payload.get("cold_start_observed") is True
            and persistence.get("passed") is True
            and contract.get("lora_sha256") == PRODUCTION_ACTOR_CORE_LORA_SHA256
            and "RTX 3060" in str(gpu.get("name", "")).upper()
            and int(gpu.get("total_mib", 0)) >= 11000
        ):
            return "rtx_3060_12gb_cold_start_inference_persistence_passed"
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
        pass
    return "memory_cap_prescreen_passed_real_3060_pending"


def normalize_request_path(path: str) -> str:
    if path.startswith("/api/local-generation/"):
        return "/api/" + path.removeprefix("/api/local-generation/")
    first = path.strip("/").split("/", 1)[0]
    if first in {
        "health",
        "library",
        "3d-assets",
        "3d-candidates",
        "3d-library",
        "animation-library",
        "training-pairs",
        "training-previews",
        *ROUTE_CONFIG.keys(),
    }:
        return "/api" + path
    return path


def request_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc


def comfy_reachable() -> bool:
    try:
        request_json(f"{COMFY_URL}/system_stats", timeout=3)
        return True
    except (OSError, urllib.error.URLError, RuntimeError, TimeoutError):
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


def compile_profile_turnaround_prompt(
    subject: str, style_profile: dict[str, Any], *, style_seed: bool = False
) -> str:
    positive = ", ".join(style_profile["prompt_contract"]["positive"])
    negative = ", ".join(style_profile["prompt_contract"]["negative"])
    immutable = ", ".join(style_profile["prompt_contract"]["immutable_traits"])
    if not style_seed:
        actor_contract = style_profile.get(
            "actor_core_contract", style_profile["prompt_contract"]
        )
        actor_positive = ", ".join(actor_contract["positive"])
        actor_negative = ", ".join(actor_contract["negative"])
        actor_immutable = ", ".join(actor_contract["immutable_traits"])
        return (
            f"Design ONE canonical modular Actor body core: {subject.strip()}. "
            "This is not a complete character and must contain no identity or equipment slots. "
            "The selected style authority is compiled into a proportion-and-shape contract "
            "and a post-generation silhouette gate. Preserve its relative head height and width, "
            "shallow anime facial plane, narrow torso taper, limb lengths, hand and foot mass, "
            "three-view layout and soft low-frequency silhouette. Remove and do not reproduce "
            "its identity, hair, ears, eyes, eyebrows, clothing, footwear, colors or accessories. "
            "Create one production orthographic turnaround sheet with exactly three separate "
            "full-body views arranged left to right: exact front, exact right profile, exact "
            "back. Keep exactly the same smooth body shell, body proportions, neutral "
            "symmetrical A-pose, scale and ground line in every view. The head must be fully "
            "bald and earless. The face must be a smooth blank surface with no eyes, eyebrows, "
            "eyelashes, eye sockets, mouth, mouth line, lips, nose, nose bridge or nostrils. "
            "The body must be a non-sexual neutral mannequin shell with no anatomical detail. "
            "There must be no hair, scalp cap, ears, clothes, bodysuit, underwear, shoes, gloves, "
            "jewelry, accessory, prop, seam, cuff, collar, waistband, boot sole or garment-like "
            "topology. Use a single matte neutral clay material; color regions must not imply "
            "clothing. Preserve only the Actor-safe projection of the selected style profile: "
            f"{actor_positive}. Actor-core immutable traits: {actor_immutable}. Uniform light "
            "gray background, soft neutral studio lighting, no "
            "perspective, no three-quarter view, no action pose, no props, no text, no labels, "
            "no borders, no extra characters, no duplicated body parts and no cropped feet. "
            f"Avoid: {actor_negative}."
        )
    purpose = (
        "This is a style-seed calibration image: identity, hair, outfit and colors are "
        "examples only; the selected profile's immutable grammar is the authority."
    )
    return (
        f"Design ONE neutral game character: {subject.strip()}. {purpose} "
        "Create one production orthographic turnaround sheet with exactly three separate "
        "full-body views arranged left to right: exact front, exact right profile, exact "
        "back. Keep the same character, body proportions, face, hair, construction, colors, "
        "neutral symmetrical A-pose, scale and ground line in every view. "
        "Treat the hairstyle as one fixed three-dimensional construction: its length, rear "
        "mass, side locks, bangs and parting must be geometrically compatible in front, "
        "right profile and back. If any hair hangs below the head in profile, the same hair "
        "must remain visible at the matching length in back; never turn long hair into a "
        "short rear hair cap. "
        f"Selected style profile: {positive}. Immutable traits: {immutable}. "
        "The face must have large expressive anime eyes and simple eyebrows, but absolutely "
        "no visible mouth, mouth line, lips, nose, nose bridge or nostrils. Uniform light gray "
        "background, soft neutral studio lighting, no perspective, no three-quarter view, "
        "no action pose, no props, no text, no labels, no borders, no extra characters, no "
        f"duplicated body parts and no cropped feet. Avoid: {negative}."
    )


def find_slot(actor: dict[str, Any], slot_id: str) -> dict[str, Any]:
    slot = next((item for item in actor["slots"] if item["slot_id"] == slot_id), None)
    if slot is None:
        raise ValueError(f"unknown slot for Actor profile: {slot_id}")
    return slot


def compile_accessory_prompt(
    subject: str,
    style_profile: dict[str, Any],
    actor_profile: dict[str, Any],
    slot: dict[str, Any],
    base_actor_asset_id: str | None = None,
) -> str:
    policy = slot["generation_policy"]
    if policy["preferred_mode"] in {"reuse_only", "parametric"}:
        raise ValueError(
            f"slot {slot['slot_id']} requires {policy['preferred_mode']} and cannot use image generation"
        )
    if not slot.get("generation_reference"):
        raise ValueError(
            f"slot {slot['slot_id']} has no isolated generation reference and cannot guarantee accessory-only output"
        )
    positive = ", ".join(style_profile["prompt_contract"]["positive"])
    negative = ", ".join(style_profile["prompt_contract"]["negative"])
    palette = ", ".join(
        f"{item['role']} {item['color_srgb']}" for item in style_profile["palette"]
    )
    envelope = slot.get("fit_envelope")
    fit_text = ""
    if envelope:
        if "bounds_m" in envelope:
            low = envelope["bounds_m"]["min"]
            high = envelope["bounds_m"]["max"]
            size = [round(high[index] - low[index], 4) for index in range(3)]
        else:
            low = envelope["bounds_h"]["min"]
            high = envelope["bounds_h"]["max"]
            actor_height = float(actor_profile["measurements"]["actor_height_m"])
            size = [
                round((high[index] - low[index]) * actor_height, 4)
                for index in range(3)
            ]
        fit_text = (
            f" Target Actor rest-space fit envelope is approximately {size[0]}m wide, "
            f"{size[1]}m deep, and {size[2]}m high."
        )
    rig_text = ""
    if actor_profile.get("coordinate_contract", {}).get("rig_state") == "unbound_tpose":
        rig_text = (
            " This is an unbound static T-Pose fitting proxy: preserve the normalized "
            "rest-space pivot and envelope; do not invent bones, skin weights, a wearer, "
            "or animation clearance claims."
        )
    return (
        f"Design ONE standalone game accessory: {subject.strip()}. It belongs to Actor "
        f"slot {slot['slot_id']} ({slot['label']}) on {actor_profile['label']}. "
        f"Its accepted base-actor lineage is {base_actor_asset_id or actor_profile['actor_asset_id']}; "
        "use that lineage for scale and fit, not as an image to reproduce. "
        f"Allowed asset kinds: {', '.join(policy['allowed_asset_kinds'])}.{fit_text}{rig_text} "
        "Use the supplied reference image only as visual style, proportion, material, and "
        "palette authority; do not reproduce the person. Create one production orthographic "
        "turnaround sheet with exactly three separate views arranged left to right: exact "
        "front, exact right profile, exact back. The same single accessory, construction, "
        "colors, scale, pivot orientation, and ground line in every view. Accessory only, "
        "fully visible and centered, no wearer, no body, no hands, no mannequin, no stand. "
        f"Style contract: {positive}. Semantic palette: {palette}. Uniform light gray "
        "background, soft studio lighting, no perspective, no three-quarter view, no text, "
        f"no labels, no borders, no extra objects. Avoid: {negative}."
    )


def prepare_slot_reference(slot: dict[str, Any]) -> tuple[str, str]:
    authority = slot["generation_reference"]
    source = (ROOT / authority["path"]).resolve()
    if not source.is_file() or ROOT.resolve() not in source.parents:
        raise FileNotFoundError(source)
    destination_dir = COMFY_INPUT / "assetsstudio" / "style_refs"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{authority['sha256'][:16]}{source.suffix.lower()}"
    if not destination.is_file() or destination.stat().st_size != source.stat().st_size:
        shutil.copy2(source, destination)
    relative = destination.relative_to(COMFY_INPUT).as_posix()
    return relative, authority["path"]


def prepare_reference_file(source: Path, source_label: str) -> tuple[str, str]:
    source = source.resolve()
    allowed_roots = [ROOT.resolve(), LOCAL_LIBRARY_ROOT.resolve()]
    if not source.is_file() or not any(
        source == root or root in source.parents for root in allowed_roots
    ):
        raise FileNotFoundError(source)
    destination_dir = COMFY_INPUT / "assetsstudio" / "style_refs"
    destination_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    destination = destination_dir / f"{digest}{source.suffix.lower()}"
    if not destination.is_file() or destination.stat().st_size != source.stat().st_size:
        shutil.copy2(source, destination)
    return destination.relative_to(COMFY_INPUT).as_posix(), source_label


def prepare_style_reference(style_profile: dict[str, Any]) -> tuple[str, str]:
    authority = next(
        (
            item
            for item in style_profile["authorities"]
            if item["role"] == "primary_proportion" and item["required"]
        ),
        None,
    )
    if authority is None:
        raise ValueError("StyleProfile has no required primary proportion authority")
    return prepare_reference_file(ROOT / authority["path"], authority["path"])


def library_asset_dir(kind: str, asset_id: str) -> Path:
    if kind not in LIBRARY_KIND_DIR or not asset_id or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for character in asset_id
    ):
        raise ValueError("invalid local library asset id")
    return LOCAL_LIBRARY_ROOT / LIBRARY_KIND_DIR[kind] / asset_id


def load_published_style_seed(seed_path: Path) -> dict[str, Any]:
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "assetsstudio_published_style_seed_v1":
        raise RuntimeError(f"unsupported published seed schema: {seed_path}")
    asset_id = payload.get("asset_id")
    if seed_path.parent.name != asset_id:
        raise RuntimeError(f"published seed directory/id mismatch: {seed_path}")
    if payload.get("kind") != "style_seed" or payload.get("review_status") != "approved":
        raise RuntimeError(f"published seed is not approved: {asset_id}")
    style_profile_id = payload.get("style_profile_id")
    if style_profile_id not in STYLE_PROFILES:
        raise RuntimeError(f"published seed uses an unknown StyleProfile: {asset_id}")
    for key in ("artifact", "metrics"):
        contract = payload.get(key, {})
        source = (seed_path.parent / contract.get("path", "")).resolve()
        if seed_path.parent.resolve() not in source.parents or not source.is_file():
            raise RuntimeError(f"published seed {key} is missing: {asset_id}")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != contract.get("sha256"):
            raise RuntimeError(f"published seed {key} hash mismatch: {asset_id}")
    return payload


def sync_published_style_seeds() -> int:
    """Bootstrap approved Git seed packages without overwriting local assets."""
    if not PUBLISHED_STYLE_SEED_ROOT.is_dir():
        return 0
    imported = 0
    for seed_path in sorted(PUBLISHED_STYLE_SEED_ROOT.glob("*/seed.json")):
        payload = load_published_style_seed(seed_path)
        asset_id = payload["asset_id"]
        destination = library_asset_dir("style_seed", asset_id)
        if destination.exists():
            if not (destination / "asset_manifest.json").is_file():
                raise RuntimeError(
                    f"local seed destination is occupied without a manifest: {asset_id}"
                )
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{asset_id}.published-{uuid.uuid4().hex}")
        temporary.mkdir()
        try:
            artifact = payload["artifact"]
            metrics_contract = payload["metrics"]
            shutil.copy2(seed_path.parent / artifact["path"], temporary / "style_seed.png")
            shutil.copy2(
                seed_path.parent / metrics_contract["path"],
                temporary / "turnaround.metrics.json",
            )
            metrics = json.loads(
                (temporary / "turnaround.metrics.json").read_text(encoding="utf-8")
            )
            style_profile = STYLE_PROFILES[payload["style_profile_id"]]
            generation = payload["generation"]
            record = {
                "id": asset_id,
                "job_kind": "style_seed",
                "status": "completed",
                "created_at": payload["accepted_at"],
                "updated_at": payload["accepted_at"],
                "subject": payload["subject"],
                "compiled_prompt": compile_profile_turnaround_prompt(
                    payload["subject"], style_profile, style_seed=True
                ),
                "style": "soft_3d",
                "style_profile_id": payload["style_profile_id"],
                "style_seed_asset_id": None,
                "seed": generation["seed"],
                "library_status": "accepted",
                "profile_snapshot": {"style": style_profile},
                "artifact": "style_seed.png",
                "qa_status": "visual_review_required",
                "automatic_qa": metrics,
                "manual_gates_required": payload["manual_confirmations"],
                "manual_confirmations": payload["manual_confirmations"],
                "generation_contract": {
                    "views": ["front", "right", "back"],
                    "width": artifact["width"],
                    "height": artifact["height"],
                    "steps": generation["steps"],
                    "cfg": generation["cfg"],
                    "reference_latent": generation["reference_latent"],
                    "reference_source": generation["reference_source"],
                },
                "publication_source": seed_path.relative_to(ROOT).as_posix(),
            }
            manifest = {
                "schema": "assetsstudio_local_asset_v1",
                "asset_id": asset_id,
                "kind": "style_seed",
                "asset_role": payload["asset_role"],
                "subject": payload["subject"],
                "style_profile_id": payload["style_profile_id"],
                "consumer_tags": payload.get("consumer_tags", []),
                "parent_asset_ids": [],
                "source_job_id": asset_id,
                "accepted_at": payload["accepted_at"],
                "artifact_filename": "style_seed.png",
                "record_filename": "record.json",
                "local_only": True,
                "published_seed": True,
                "review_status": "approved",
                "reviewed_at": payload["accepted_at"],
                "manual_confirmations": payload["manual_confirmations"],
                "route": "style-seeds",
            }
            (temporary / "record.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (temporary / "asset_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(destination)
            imported += 1
        finally:
            if temporary.is_dir():
                shutil.rmtree(temporary)
    return imported


def library_reference_path(kind: str, asset_id: str) -> tuple[Path, str]:
    asset_dir = library_asset_dir(kind, asset_id)
    manifest_path = asset_dir / "asset_manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"local {kind} asset is not accepted: {asset_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("review_status", "approved") != "approved":
        raise ValueError(f"local {kind} asset is not approved: {asset_id}")
    artifact = asset_dir / manifest["artifact_filename"]
    if not artifact.is_file():
        raise ValueError(f"local {kind} artifact is missing: {asset_id}")
    return artifact, f"local_asset_library/{LIBRARY_KIND_DIR[kind]}/{asset_id}"


def resolve_library_reference(kind: str, asset_id: str) -> tuple[str, str]:
    artifact, source_label = library_reference_path(kind, asset_id)
    return prepare_reference_file(artifact, source_label)


def list_library_assets(kind: str | None = None) -> list[dict[str, Any]]:
    kinds = [kind] if kind else list(LIBRARY_KIND_DIR)
    assets: list[dict[str, Any]] = []
    for current_kind in kinds:
        if current_kind not in LIBRARY_KIND_DIR:
            raise ValueError("unsupported library kind")
        root = LOCAL_LIBRARY_ROOT / LIBRARY_KIND_DIR[current_kind]
        if not root.is_dir():
            continue
        for manifest_path in root.glob("*/asset_manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            manifest = dict(manifest)
            manifest["image_url"] = (
                f"/api/library/{current_kind}/{manifest['asset_id']}/image"
            )
            assets.append(manifest)
    return sorted(assets, key=lambda item: item.get("accepted_at", ""), reverse=True)


def safe_asset_id(asset_id: str) -> str:
    if not asset_id or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for character in asset_id
    ):
        raise ValueError("invalid local 3D asset id")
    return asset_id


def local_3d_roots(scope: str) -> tuple[Path, ...]:
    roots = {
        "candidate": (LOCAL_3D_CANDIDATE_ROOT, LOCAL_3D_ACCESSORY_CANDIDATE_ROOT),
        "library": (LOCAL_3D_LIBRARY_ROOT, LOCAL_3D_ACCESSORY_LIBRARY_ROOT),
    }.get(scope)
    if roots is None:
        raise ValueError("invalid local 3D asset scope")
    return roots


def local_3d_dir(scope: str, asset_id: str, asset_kind: str | None = None) -> Path:
    safe_id = safe_asset_id(asset_id)
    roots = local_3d_roots(scope)
    for root in roots:
        candidate = root / safe_id
        if candidate.exists():
            return candidate
    if asset_kind == "accessory_3d":
        return roots[1] / safe_id
    return roots[0] / safe_id


def safe_3d_artifact(asset_dir: Path, relative_path: str) -> Path:
    candidate = (asset_dir / relative_path).resolve()
    resolved_root = asset_dir.resolve()
    if resolved_root not in candidate.parents:
        raise ValueError("unsafe local 3D artifact path")
    return candidate


def rig_artifact(manifest: dict[str, Any], relative_path: str) -> Path:
    preparation = manifest.get("rig_preparation")
    if not isinstance(preparation, dict):
        raise FileNotFoundError("Actor rig preparation is not available")
    rig_root_relative = preparation.get("workspace_root_relative")
    if not isinstance(rig_root_relative, str):
        raise ValueError("Actor rig workspace root is missing")
    workspace_root = WORKSPACE_ROOT.resolve()
    rig_root = (workspace_root / rig_root_relative).resolve()
    if workspace_root not in rig_root.parents:
        raise ValueError("unsafe Actor rig workspace root")
    candidate = (rig_root / relative_path).resolve()
    if rig_root not in candidate.parents:
        raise ValueError("unsafe Actor rig artifact path")
    return candidate


def actor_core_workspace_dir(manifest: dict[str, Any]) -> Path:
    preparation = manifest.get("rig_preparation")
    if not isinstance(preparation, dict):
        raise FileNotFoundError("Actor rig preparation is not available")
    relative = preparation.get("workspace_root_relative")
    if not isinstance(relative, str):
        raise ValueError("Actor rig workspace root is missing")
    workspace_root = WORKSPACE_ROOT.resolve()
    directory = (workspace_root / relative).resolve()
    if workspace_root not in directory.parents:
        raise ValueError("unsafe Actor rig workspace root")
    return directory


def rig_intake_directory(asset_id: str, job_id: str | None = None) -> Path:
    library_manifest = json.loads(
        (local_3d_dir("library", asset_id) / "candidate_manifest.json").read_text(encoding="utf-8")
    )
    root = actor_core_workspace_dir(library_manifest) / "manual_accurig"
    if job_id is None:
        return root
    return root / "intakes" / safe_asset_id(job_id)


def write_rig_intake(directory: Path, manifest: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "intake.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def current_rig_intake(asset_id: str) -> dict[str, Any] | None:
    root = rig_intake_directory(asset_id)
    current_path = root / "current.json"
    if not current_path.is_file():
        return None
    pointer = json.loads(current_path.read_text(encoding="utf-8"))
    job_id = safe_asset_id(str(pointer.get("job_id", "")))
    directory = rig_intake_directory(asset_id, job_id)
    intake = json.loads((directory / "intake.json").read_text(encoding="utf-8"))
    public = dict(intake)
    route = f"/api/3d-library/{asset_id}"
    if intake.get("status") == "ready":
        public["preview_urls"] = {
            view: f"{route}/rigged-preview/{view}"
            for view in ("front", "right", "back", "left")
        }
        public["model_url"] = f"{route}/rigged-model"
        public["blend_url"] = f"{route}/rigged-blend"
        public["validation_url"] = f"{route}/rigged-validation"
    return public


def process_rig_intake(asset_id: str, job_id: str) -> None:
    directory = rig_intake_directory(asset_id, job_id)
    manifest_path = directory / "intake.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(status="processing", updated_at=utc_now())
    write_rig_intake(directory, manifest)
    try:
        blender = discover_blender()
        library_manifest = json.loads(
            (local_3d_dir("library", asset_id) / "candidate_manifest.json").read_text(encoding="utf-8")
        )
        preparation = library_manifest["rig_preparation"]
        expected_manifest = (WORKSPACE_ROOT / preparation["accurig_manifest"]).resolve()
        workspace_root = WORKSPACE_ROOT.resolve()
        if workspace_root not in expected_manifest.parents or not expected_manifest.is_file():
            raise FileNotFoundError("AccuRIG handoff manifest for the selected Actor is missing")
        processed = directory / "processed"
        processed.mkdir(parents=True, exist_ok=True)
        command = [
            str(blender),
            "--factory-startup",
            "--background",
            "--python-exit-code",
            "1",
            "--python",
            str((ROOT / "tools" / "model_test" / "process_actor_core_accurig_rig.py").resolve()),
            "--",
            "--input",
            str((directory / manifest["source_relative_path"]).resolve()),
            "--output-dir",
            str(processed.resolve()),
            "--asset-id",
            preparation["asset_id"],
            "--expected-manifest",
            str(expected_manifest),
        ]
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            check=False,
        )
        (directory / "blender.stdout.log").write_text(result.stdout, encoding="utf-8")
        (directory / "blender.stderr.log").write_text(result.stderr, encoding="utf-8")
        if result.returncode != 0:
            stderr_lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
            detail = next(
                (
                    line
                    for line in reversed(stderr_lines)
                    if line.startswith(("RuntimeError:", "ValueError:", "FileNotFoundError:"))
                ),
                stderr_lines[-1] if stderr_lines else f"Blender exited with code {result.returncode}",
            )
            raise RuntimeError(detail)
        validation = json.loads((processed / "validation.json").read_text(encoding="utf-8"))
        if validation.get("status") != "pass":
            raise RuntimeError("AccuRIG validation report did not pass")
        manifest.update(
            status="ready",
            updated_at=utc_now(),
            blender=str(blender),
            validation_summary={
                "bones": validation["armature"]["bones"],
                "vertices": validation["mesh"]["vertices"],
                "faces": validation["mesh"]["faces"],
                "max_influences_runtime": validation["runtime_weight_optimization"]["after_max_influences"],
            },
            error=None,
        )
    except Exception as exc:  # Keep the failed upload available for diagnosis.
        manifest.update(status="failed", updated_at=utc_now(), error=str(exc))
    write_rig_intake(directory, manifest)


def create_rig_intake(
    asset_id: str,
    filename: str,
    length: int,
    source,
) -> dict[str, Any]:
    library_manifest = load_3d_manifest("library", asset_id)
    if not isinstance(library_manifest.get("rig_preparation"), dict):
        raise ValueError("Selected 3D Actor has no AccuRIG handoff contract")
    original_name = Path(filename).name
    if not original_name or Path(original_name).suffix.lower() != ".fbx":
        raise ValueError("AccuRIG upload must be an .fbx file")
    if length <= 0 or length > MAX_RIG_UPLOAD_BYTES:
        raise ValueError("AccuRIG FBX size must be between 1 byte and 1 GiB")

    job_id = uuid.uuid4().hex
    directory = rig_intake_directory(asset_id, job_id)
    source_dir = directory / "source"
    source_dir.mkdir(parents=True, exist_ok=False)
    destination = source_dir / "accurig_export.fbx"
    remaining = length
    with destination.open("wb") as output:
        while remaining:
            chunk = source.read(min(1024 * 1024, remaining))
            if not chunk:
                raise OSError("AccuRIG upload ended before Content-Length bytes were received")
            output.write(chunk)
            remaining -= len(chunk)

    now = utc_now()
    manifest = {
        "schema": "assetsstudio_actor_rig_intake_v1",
        "job_id": job_id,
        "asset_id": asset_id,
        "rig_asset_id": library_manifest["rig_preparation"]["asset_id"],
        "status": "uploaded",
        "created_at": now,
        "updated_at": now,
        "original_filename": original_name,
        "bytes": length,
        "source_relative_path": "source/accurig_export.fbx",
        "local_only": True,
        "one_to_one_contract": {
            "source_3d_asset_id": asset_id,
            "accurig_handoff_manifest": library_manifest["rig_preparation"]["accurig_manifest"],
        },
    }
    write_rig_intake(directory, manifest)
    root = rig_intake_directory(asset_id)
    root.mkdir(parents=True, exist_ok=True)
    (root / "current.json").write_text(
        json.dumps({"job_id": job_id}, indent=2) + "\n",
        encoding="utf-8",
    )
    threading.Thread(
        target=process_rig_intake,
        args=(asset_id, job_id),
        daemon=True,
        name=f"accurig-{asset_id[:8]}-{job_id[:8]}",
    ).start()
    return manifest


def animation_asset_directory(animation_asset_id: str) -> Path:
    return LOCAL_ANIMATION_LIBRARY_ROOT / safe_asset_id(animation_asset_id)


def load_animation_asset(animation_asset_id: str) -> dict[str, Any]:
    directory = animation_asset_directory(animation_asset_id)
    manifest_path = directory / "asset_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("local animation asset manifest not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "assetsstudio_local_animation_asset_v1"
        or manifest.get("asset_id") != animation_asset_id
        or manifest.get("kind") != "skeletal_animation"
    ):
        raise ValueError("local animation asset manifest is incompatible")
    source = (directory / manifest.get("source_filename", "")).resolve()
    if directory.resolve() not in source.parents or not source.is_file():
        raise FileNotFoundError("local animation source FBX is missing")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != str(manifest.get("sha256", "")).lower():
        raise ValueError("local animation source hash mismatch")
    public = dict(manifest)
    public["source_available"] = True
    return public


def list_animation_assets() -> list[dict[str, Any]]:
    if not LOCAL_ANIMATION_LIBRARY_ROOT.is_dir():
        return []
    assets = []
    for manifest_path in LOCAL_ANIMATION_LIBRARY_ROOT.glob("*/asset_manifest.json"):
        try:
            assets.append(load_animation_asset(manifest_path.parent.name))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return sorted(assets, key=lambda item: item.get("label", item["asset_id"]))


def animation_preview_directory(asset_id: str, animation_asset_id: str) -> Path:
    intake = current_rig_intake(asset_id)
    if not intake or intake.get("status") != "ready":
        raise ValueError("current Actor does not have a ready AccuRIG intake")
    root = rig_intake_directory(asset_id, intake["job_id"]) / "animation_previews"
    destination = (root / safe_asset_id(animation_asset_id)).resolve()
    if root.resolve() not in destination.parents:
        raise ValueError("unsafe animation preview directory")
    return destination


def public_animation_preview(asset_id: str, animation_asset_id: str) -> dict[str, Any]:
    animation = load_animation_asset(animation_asset_id)
    directory = animation_preview_directory(asset_id, animation_asset_id)
    job_path = directory / "job.json"
    report_path = directory / "retarget.json"
    job = (
        json.loads(job_path.read_text(encoding="utf-8"))
        if job_path.is_file()
        else {}
    )
    report = (
        json.loads(report_path.read_text(encoding="utf-8"))
        if report_path.is_file()
        else None
    )
    job_status = job.get("status")
    ready = bool(
        report
        and report.get("status") == "pass"
        and job_status in {None, "ready"}
        and (directory / "retargeted.glb").is_file()
        and all((directory / f"{view}.gif").is_file() for view in ("front", "right", "back", "left"))
    )
    visible_status = "ready" if ready else job_status or "not_generated"
    visible_error = job.get("error")
    if job_status == "ready" and not ready:
        visible_status = "failed"
        visible_error = "animation job outputs are incomplete; regenerate the preview"
    route = f"/api/3d-library/{asset_id}/animation-previews/{animation_asset_id}"
    result = {
        "schema": "assetsstudio_actor_animation_preview_v1",
        "actor_asset_id": asset_id,
        "animation_asset_id": animation_asset_id,
        "animation_label": animation["label"],
        "motion": animation["motion"],
        "status": visible_status,
        "updated_at": job.get("updated_at"),
        "error": visible_error,
        "model_url": f"{route}/model" if ready else None,
        "report_url": f"{route}/report" if ready else None,
        "contact_sheet_url": f"{route}/contact-sheet" if ready else None,
        "preview_urls": {
            view: f"{route}/preview/{view}"
            for view in ("front", "right", "back", "left")
        } if ready else {},
    }
    if report:
        result["validation_summary"] = {
            "mapped_bones": len(report.get("mapped_bones", {})),
            "frame_range": report.get("frame_range"),
            "fps": report.get("fps"),
            "automatic_gates": report.get("gates", {}),
        }
    return result


def list_animation_previews(asset_id: str) -> list[dict[str, Any]]:
    try:
        return [
            public_animation_preview(asset_id, animation["asset_id"])
            for animation in list_animation_assets()
        ]
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return []


def write_animation_job(directory: Path, job: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "job.json").write_text(
        json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def process_animation_preview(asset_id: str, animation_asset_id: str) -> None:
    directory = animation_preview_directory(asset_id, animation_asset_id)
    job_path = directory / "job.json"
    job = json.loads(job_path.read_text(encoding="utf-8"))
    job.update(status="processing", updated_at=utc_now(), error=None)
    write_animation_job(directory, job)
    try:
        blender = discover_blender()
        animation = load_animation_asset(animation_asset_id)
        intake = current_rig_intake(asset_id)
        if not intake or intake.get("status") != "ready":
            raise ValueError("current Actor AccuRIG intake is not ready")
        intake_dir = rig_intake_directory(asset_id, intake["job_id"])
        actor_blend = (
            intake_dir
            / "processed"
            / f"{safe_asset_id(intake['rig_asset_id'])}_runtime_4weights.blend"
        )
        animation_fbx = animation_asset_directory(animation_asset_id) / animation["source_filename"]
        command = [
            str(blender),
            "--background",
            "--python-exit-code",
            "1",
            "--python",
            str((ROOT / "tools" / "model_test" / "retarget_mixamo_to_actor_core.py").resolve()),
            "--",
            "--actor-blend",
            str(actor_blend.resolve()),
            "--animation-fbx",
            str(animation_fbx.resolve()),
            "--output-dir",
            str(directory.resolve()),
            "--actor-id",
            asset_id,
            "--animation-asset-id",
            animation_asset_id,
            "--fps",
            str(animation.get("fps", 30)),
        ]
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            check=False,
        )
        (directory / "blender.stdout.log").write_text(result.stdout, encoding="utf-8")
        (directory / "blender.stderr.log").write_text(result.stderr, encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError(f"Blender retarget exited with code {result.returncode}")
        gif_result = subprocess.run(
            [
                sys.executable,
                str((ROOT / "tools" / "model_test" / "build_animation_preview_gifs.py").resolve()),
                "--report",
                str((directory / "retarget.json").resolve()),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        (directory / "preview.stdout.log").write_text(gif_result.stdout, encoding="utf-8")
        (directory / "preview.stderr.log").write_text(gif_result.stderr, encoding="utf-8")
        if gif_result.returncode != 0:
            raise RuntimeError(f"preview GIF build exited with code {gif_result.returncode}")
        report = json.loads((directory / "retarget.json").read_text(encoding="utf-8"))
        if report.get("status") != "pass":
            raise RuntimeError("retarget report did not pass automatic gates")
        job.update(
            status="ready",
            updated_at=utc_now(),
            blender=str(blender),
            mapped_bones=len(report["mapped_bones"]),
            frame_range=report["frame_range"],
            error=None,
        )
    except Exception as exc:
        job.update(status="failed", updated_at=utc_now(), error=str(exc))
    write_animation_job(directory, job)


def create_animation_preview(
    asset_id: str,
    animation_asset_id: str,
    force: bool = False,
) -> dict[str, Any]:
    load_3d_manifest("library", asset_id)
    load_animation_asset(animation_asset_id)
    current = public_animation_preview(asset_id, animation_asset_id)
    if current["status"] in {"queued", "processing"} or (
        current["status"] == "ready" and not force
    ):
        return current
    directory = animation_preview_directory(asset_id, animation_asset_id)
    now = utc_now()
    job = {
        "schema": "assetsstudio_actor_animation_preview_job_v1",
        "actor_asset_id": asset_id,
        "animation_asset_id": animation_asset_id,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "local_only": True,
        "error": None,
    }
    write_animation_job(directory, job)
    threading.Thread(
        target=process_animation_preview,
        args=(asset_id, animation_asset_id),
        daemon=True,
        name=f"animation-{asset_id[:8]}-{animation_asset_id[:16]}",
    ).start()
    return public_animation_preview(asset_id, animation_asset_id)


def load_3d_manifest(scope: str, asset_id: str) -> dict[str, Any]:
    asset_dir = local_3d_dir(scope, asset_id)
    manifest_path = asset_dir / "candidate_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("local 3D manifest not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("candidate_id") != asset_id:
        raise ValueError("local 3D manifest id mismatch")
    route = "3d-candidates" if scope == "candidate" else "3d-library"
    public = dict(manifest)
    public["model_url"] = f"/api/{route}/{asset_id}/model"
    if manifest.get("combined_model_filename"):
        public["combined_model_url"] = f"/api/{route}/{asset_id}/combined-model"
    public["preview_urls"] = {
        view: f"/api/{route}/{asset_id}/preview/{view}"
        for view in manifest.get("preview_filenames", {})
    }
    if scope == "library" and isinstance(manifest.get("rig_preparation"), dict):
        rig_asset_id = safe_asset_id(manifest["rig_preparation"]["asset_id"])
        public["rig_preview_urls"] = {
            view: f"/api/{route}/{asset_id}/rig-preview/{view}"
            for view in ("front", "right", "back", "left")
        }
        public["rig_mesh_url"] = f"/api/{route}/{asset_id}/rig-mesh"
        public["accurig_fbx_url"] = f"/api/{route}/{asset_id}/accurig-fbx"
        public["rig_preparation"]["asset_id"] = rig_asset_id
        try:
            public["rig_intake"] = current_rig_intake(asset_id)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            public["rig_intake"] = None
        public["animation_previews"] = list_animation_previews(asset_id)
    return public


def list_3d_assets() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {"candidates": [], "assets": []}
    for scope, key in (("candidate", "candidates"), ("library", "assets")):
        for root in local_3d_roots(scope):
            if not root.is_dir():
                continue
            for manifest_path in root.glob("*/candidate_manifest.json"):
                try:
                    manifest = load_3d_manifest(scope, manifest_path.parent.name)
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
                if manifest.get("studio_visibility", "active") != "active":
                    continue
                if scope == "candidate" and manifest.get("library_status") != "candidate":
                    continue
                result[key].append(manifest)
        result[key].sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return result


def write_3d_manifest(directory: Path, manifest: dict[str, Any]) -> None:
    (directory / "candidate_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def accept_3d_candidate(asset_id: str, confirmations: list[str]) -> dict[str, Any]:
    candidate_dir = local_3d_dir("candidate", asset_id)
    manifest = load_3d_manifest("candidate", asset_id)
    if manifest.get("library_status") != "candidate":
        raise ValueError("local 3D candidate is no longer pending review")
    required = manifest.get("manual_gates_required", THREE_D_MANUAL_GATES)
    missing = [gate for gate in required if gate not in confirmations]
    if not required or missing:
        raise ValueError(
            "manual 3D review is incomplete: "
            + "; ".join(missing or ["no gates recorded"])
        )
    destination = local_3d_dir("library", asset_id, manifest.get("asset_kind"))
    if destination.exists():
        raise FileExistsError("local 3D library destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(candidate_dir, destination)
    accepted_at = utc_now()
    accepted = {
        key: value
        for key, value in manifest.items()
        if key not in {"model_url", "preview_urls"}
    }
    accepted.update(
        library_status="accepted",
        accepted_at=accepted_at,
        manual_confirmations=confirmations,
        local_only=True,
    )
    write_3d_manifest(destination, accepted)
    source_manifest = dict(accepted)
    write_3d_manifest(candidate_dir, source_manifest)
    return load_3d_manifest("library", asset_id)


def destroy_3d_candidate(asset_id: str) -> None:
    candidate_dir = local_3d_dir("candidate", asset_id).resolve()
    expected_roots = [root.resolve() for root in local_3d_roots("candidate")]
    if not any(root in candidate_dir.parents for root in expected_roots):
        raise ValueError("unsafe local 3D candidate path")
    manifest = load_3d_manifest("candidate", asset_id)
    if manifest.get("library_status") != "candidate":
        raise ValueError("accepted local 3D assets must be removed from the library explicitly")
    shutil.rmtree(candidate_dir)


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
        job_kind = job.get("job_kind", "base_actor")
        proportion_reference: Path | None = None
        reference_role = "style_edit"
        lora = None
        lora_strength = 1.0
        if job_kind == "accessory":
            reference_image, reference_source = prepare_slot_reference(
                job["profile_snapshot"]["slot"]
            )
            artifact_root = ACCESSORY_ARTIFACT_ROOT
            artifact_name = "accessory_turnaround.png"
            route = "accessories"
            prefix = f"assetsstudio/accessories/{job_id}"
        elif job_kind == "style_seed":
            reference_image, reference_source = prepare_style_reference(
                job["profile_snapshot"]["style"]
            )
            artifact_root = STYLE_SEED_ARTIFACT_ROOT
            artifact_name = "style_seed.png"
            route = "style-seeds"
            prefix = f"assetsstudio/style_seeds/{job_id}"
        else:
            if job.get("style_seed_asset_id"):
                proportion_reference, reference_source = library_reference_path(
                    "style_seed", job["style_seed_asset_id"]
                )
                reference_image, reference_source = prepare_reference_file(
                    proportion_reference, reference_source
                )
                reference_source = f"actor-core-lora-edit:{reference_source}"
                reference_role = "approved_style_seed_pixels_with_actor_core_lora"
                if ACTOR_CORE_LORA is None:
                    raise FileNotFoundError("strip_to_actor_core LoRA was not found")
                lora = ACTOR_CORE_LORA
                lora_strength = float(job["lora_strength"])
            else:
                raise ValueError(
                    "base_actor generation requires an approved StyleSeed and the "
                    "strip_to_actor_core edit workflow"
                )
            artifact_root = BASE_ACTOR_ARTIFACT_ROOT
            artifact_name = "base_actor_turnaround.png"
            route = "base-actors"
            prefix = f"assetsstudio/base_actors/{job_id}"
        args = Namespace(
            model="flux-2-klein-4b-fp8.safetensors",
            text_encoder="qwen_3_4b.safetensors",
            vae="flux2-vae.safetensors",
            prompt=job["compiled_prompt"],
            reference_image=reference_image,
            width=1536,
            height=768,
            steps=4,
            cfg=1.0,
            seed=job["seed"],
            prefix=prefix,
            lora=lora,
            lora_strength=lora_strength,
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
        job_dir = artifact_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        artifact = job_dir / artifact_name
        shutil.copy2(source, artifact)
        automatic_qa = None
        qa_status = "visual_review_required"
        metrics_url = None
        if job_kind == "base_actor":
            automatic_qa = analyze_turnaround(artifact, 3)
            if proportion_reference is not None:
                reference_report = analyze_turnaround(
                    artifact, 3, proportion_reference=proportion_reference
                )
                automatic_qa["reference_profile_diagnostic"] = reference_report[
                    "proportion_comparison"
                ]
            actor_core_shape = analyze_actor_core_shape(artifact, 3)
            automatic_qa["actor_core_shape"] = actor_core_shape
            automatic_qa["automatic_gates"].update(
                {
                    f"actor_core_shape.{key}": value
                    for key, value in actor_core_shape["automatic_gates"].items()
                }
            )
            automatic_qa["automatic_pass"] = (
                automatic_qa["automatic_pass"]
                and actor_core_shape["automatic_pass"]
            )
        else:
            automatic_qa = analyze_turnaround(
                artifact, 3, proportion_reference=proportion_reference
            )
        if job_kind == "accessory":
            manual_gates_required = [
                "front/right-profile/back orientation is correct",
                "same accessory construction and attachment geometry in every view",
                "no wearer, body, hands, mannequin or unrelated object",
                "material and detail density match the selected StyleProfile",
                "scale, pivot and slot-fit intent are plausible",
            ]
        elif job_kind == "style_seed":
            manual_gates_required = [
                "front/right-profile/back orientation is correct",
                "same character identity and body proportions in every view",
                "hair length, rear mass, side locks, bangs and parting form one compatible topology",
                "no visible mouth, mouth line, lips, nose, nose bridge or nostrils",
                "same outfit construction and colors in every view",
                "no extra limbs, props, perspective pose or cropped feet",
            ]
        else:
            manual_gates_required = [
                "front/right-profile/back orientation is correct",
                "same canonical Actor body proportions and neutral A-pose in every view",
                "head is completely bald and earless in every view",
                "face is a smooth blank surface with no eyes, eyebrows, eyelashes, mouth, or nose",
                "no hair, clothes, bodysuit, underwear, footwear, gloves, accessories, seams, cuffs, or garment-like topology",
                "single neutral mannequin material does not imply clothing or identity",
                "front silhouette preserves the approved reference's flattened anime head, narrow torso taper, and compact limb masses rather than a spherical baby or pear-shaped body",
                "lower legs flow continuously into small compact rounded feet with no ankle band, boot volume, sole, heel block or toe block",
                "no extra limbs, props, perspective pose or cropped feet",
            ]
        automatic_qa["manual_gates_required"] = manual_gates_required
        metrics_path = job_dir / "turnaround.metrics.json"
        metrics_path.write_text(
            json.dumps(automatic_qa, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        metrics_url = f"/api/{route}/{job_id}/metrics"
        if not automatic_qa["automatic_pass"]:
            qa_status = "automatic_review_failed"

        record = {
            **job,
            "status": "completed",
            "updated_at": utc_now(),
            "comfy_prompt_id": prompt_id,
            "artifact": str(artifact),
            "qa_status": qa_status,
            "automatic_qa": automatic_qa,
            "manual_gates_required": manual_gates_required,
            "generation_contract": {
                "views": ["front", "right", "back"],
                "width": 1536,
                "height": 768,
                "steps": 4,
                "cfg": 1.0,
                "reference_latent": reference_image is not None,
                "reference_source": reference_source,
                "reference_role": reference_role,
                "lora": lora,
                "lora_strength": lora_strength if lora else None,
            },
        }
        (job_dir / "record.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        update_job(
            job_id,
            status="completed",
            image_url=f"/api/{route}/{job_id}/image",
            record_url=f"/api/{route}/{job_id}/record",
            metrics_url=metrics_url,
            qa_status=qa_status,
            library_status="candidate",
            manual_gates_required=manual_gates_required,
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
        "job_kind",
        "style_profile_id",
        "actor_profile_id",
        "slot_id",
        "style_seed_asset_id",
        "lora_strength",
        "base_actor_asset_id",
        "seed",
        "image_url",
        "record_url",
        "metrics_url",
        "qa_status",
        "library_status",
        "library_asset_id",
        "manual_gates_required",
        "manual_confirmations",
        "error",
    }
    return {key: value for key, value in job.items() if key in allowed}


def restore_persisted_jobs() -> int:
    """Restore completed/failed local candidates after a Bridge restart.

    Lifecycle actions must keep working after reboot; otherwise failed records
    remain visible on disk but cannot be destroyed through the Studio API.
    """
    restored = 0
    visited_roots: set[Path] = set()
    for route in ("style-seeds", "base-actors", "accessories"):
        config = ROUTE_CONFIG[route]
        root = config["root"].resolve()
        if root in visited_roots or not root.is_dir():
            continue
        visited_roots.add(root)
        for record_path in root.glob("*/record.json"):
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
                job_id = str(record["id"])
                if record_path.parent.name != job_id:
                    continue
                if record.get("job_kind") != config["kind"]:
                    continue
                if record.get("status") not in {"completed", "failed"}:
                    continue
                if record.get("library_status") == "destroyed":
                    continue
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            JOBS[job_id] = record
            restored += 1
    return restored


def config_for_job(job: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    kind = job.get("job_kind", "base_actor")
    route = {
        "style_seed": "style-seeds",
        "base_actor": "base-actors",
        "accessory": "accessories",
    }.get(kind)
    if route is None:
        raise ValueError("unsupported job kind")
    return route, ROUTE_CONFIG[route]


def accept_job_into_library(
    job_id: str, manual_confirmations: list[str]
) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise KeyError("job not found")
        snapshot = dict(job)
    if snapshot.get("status") != "completed":
        raise ValueError("only completed candidates can enter the local library")
    if snapshot.get("qa_status") == "automatic_review_failed":
        raise ValueError("automatic QA failed; regenerate or destroy this candidate")
    required = snapshot.get("manual_gates_required", [])
    missing = [gate for gate in required if gate not in manual_confirmations]
    if not required or missing:
        raise ValueError(
            "manual review is incomplete: " + "; ".join(missing or ["no gates recorded"])
        )
    route, config = config_for_job(snapshot)
    asset_id = snapshot.get("library_asset_id") or job_id
    source_dir = (config["root"] / job_id).resolve()
    expected_root = config["root"].resolve()
    if expected_root not in source_dir.parents or not source_dir.is_dir():
        raise FileNotFoundError("candidate artifact directory is missing")
    destination = library_asset_dir(config["kind"], asset_id)
    if destination.exists():
        manifest_path = destination / "asset_manifest.json"
        if manifest_path.is_file():
            update_job(
                job_id,
                library_status="accepted",
                library_asset_id=asset_id,
                manual_confirmations=manual_confirmations,
            )
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        raise FileExistsError("local library destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, destination)
    manifest = {
        "schema": "assetsstudio_local_asset_v1",
        "asset_id": asset_id,
        "kind": config["kind"],
        "asset_role": {
            "style_seed": "style_calibration_anchor",
            "base_actor": "canonical_actor_core",
            "accessory": "isolated_slot_source",
        }[config["kind"]],
        "subject": snapshot["subject"],
        "style_profile_id": snapshot.get("style_profile_id"),
        "consumer_tags": snapshot.get("profile_snapshot", {})
        .get("style", {})
        .get("consumer_tags", []),
        "parent_asset_ids": [
            asset_id
            for asset_id in (
                snapshot.get("style_seed_asset_id"),
                snapshot.get("base_actor_asset_id"),
            )
            if asset_id
        ],
        "source_job_id": job_id,
        "accepted_at": utc_now(),
        "artifact_filename": config["filename"],
        "record_filename": "record.json",
        "local_only": True,
        "review_status": "approved",
        "reviewed_at": utc_now(),
        "manual_confirmations": manual_confirmations,
        "route": route,
    }
    (destination / "asset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    update_job(
        job_id,
        library_status="accepted",
        library_asset_id=asset_id,
        manual_confirmations=manual_confirmations,
    )
    return manifest


def destroy_candidate(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise KeyError("job not found")
        snapshot = dict(job)
    if snapshot.get("status") not in {"completed", "failed"}:
        raise ValueError("a running job cannot be destroyed")
    if snapshot.get("library_status") == "accepted":
        raise ValueError("accepted library assets are preserved; remove them from the library explicitly")
    _, config = config_for_job(snapshot)
    candidate_dir = (config["root"] / job_id).resolve()
    expected_root = config["root"].resolve()
    if expected_root not in candidate_dir.parents:
        raise ValueError("unsafe candidate path")
    if candidate_dir.is_dir():
        shutil.rmtree(candidate_dir)
    update_job(
        job_id,
        library_status="destroyed",
        image_url=None,
        record_url=None,
        metrics_url=None,
    )


def training_pair_directory(pair_id: str) -> Path:
    if not pair_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("invalid training pair id")
    root = TRAINING_PAIR_ROOT.resolve()
    directory = (root / pair_id).resolve()
    if root not in directory.parents:
        raise ValueError("unsafe training pair path")
    return directory


def public_training_pair(pair_dir: Path) -> dict[str, Any]:
    record = json.loads((pair_dir / "pair.json").read_text(encoding="utf-8"))
    pair_id = record["pair_id"]
    return {
        "pair_id": pair_id,
        "task": record["task"],
        "status": record["status"],
        "style_profile_id": record["style_profile_id"],
        "caption": record["caption"],
        "data_contract": record.get("data_contract"),
        "provenance": record.get("provenance", {}),
        "automatic_pass": bool(record.get("automatic_qa", {}).get("automatic_pass")),
        "automatic_gates": record.get("automatic_qa", {}).get("automatic_gates", {}),
        "manual_gates": record.get("manual_gates", {}),
        "source_url": f"/api/training-pairs/{pair_id}/source",
        "target_url": f"/api/training-pairs/{pair_id}/target",
        "record_url": f"/api/training-pairs/{pair_id}/record",
        "created_at": record["created_at"],
        "local_only": True,
    }


def list_training_pairs() -> list[dict[str, Any]]:
    pairs = []
    record_paths = list(TRAINING_PAIR_ROOT.glob("*/pair.json"))
    record_paths.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for record_path in record_paths:
        try:
            pairs.append(public_training_pair(record_path.parent))
        except (KeyError, OSError, json.JSONDecodeError):
            continue
    return pairs


def training_preview_files(preview_id: str) -> tuple[Path, Path, Path]:
    if not preview_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("invalid training preview id")
    root = TRAINING_PREVIEW_ROOT.resolve()
    image = (root / f"{preview_id}.png").resolve()
    metrics = (root / f"{preview_id}.metrics.json").resolve()
    review = (root / f"{preview_id}.review.json").resolve()
    if any(root != path.parent for path in (image, metrics, review)):
        raise ValueError("unsafe training preview path")
    return image, metrics, review


def public_training_preview(metrics_path: Path) -> dict[str, Any]:
    suffix = ".metrics.json"
    if not metrics_path.name.endswith(suffix):
        raise ValueError("invalid training preview metrics file")
    preview_id = metrics_path.name[: -len(suffix)]
    image, _, review_path = training_preview_files(preview_id)
    if not image.is_file():
        raise FileNotFoundError(image)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    review = (
        json.loads(review_path.read_text(encoding="utf-8"))
        if review_path.is_file()
        else {"review_status": "visual_review_required", "known_issues": []}
    )
    return {
        "preview_id": preview_id,
        "task": "strip_to_actor_core",
        "backend": metrics.get("backend"),
        "lora": metrics.get("lora"),
        "lora_strength": metrics.get("lora_strength"),
        "seed": metrics.get("seed"),
        "width": metrics.get("width"),
        "height": metrics.get("height"),
        "steps": metrics.get("steps"),
        "elapsed_seconds": metrics.get("elapsed_seconds"),
        "gpu": metrics.get("gpu"),
        "qualification": metrics.get("qualification"),
        "review_status": review.get("review_status", "visual_review_required"),
        "known_issues": review.get("known_issues", []),
        "image_url": f"/api/training-previews/{preview_id}/image",
        "metrics_url": f"/api/training-previews/{preview_id}/metrics",
        "review_url": f"/api/training-previews/{preview_id}/review" if review_path.is_file() else None,
        "local_only": True,
    }


def list_training_previews() -> list[dict[str, Any]]:
    if not TRAINING_PREVIEW_ROOT.is_dir():
        return []
    metrics_paths = sorted(
        TRAINING_PREVIEW_ROOT.glob("*.metrics.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    previews = []
    for metrics_path in metrics_paths:
        try:
            previews.append(public_training_preview(metrics_path))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return previews


class Handler(BaseHTTPRequestHandler):
    server_version = "AssetsStudioLocalGeneration/0.3"

    def log_message(self, format: str, *args: object) -> None:
        # Hidden/detached Windows launchers may close their inherited console pipe.
        # Access logging must never be part of request correctness.
        return

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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-AssetsStudio-Filename")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = normalize_request_path(parsed.path)
        if path == "/api/health":
            models = {name: file.is_file() for name, file in MODEL_FILES.items()}
            self.send_json(
                HTTPStatus.OK,
                {
                    "status": "ready" if comfy_reachable() and all(models.values()) else "offline",
                    "api_version": 5,
                    "comfyui": comfy_reachable(),
                    "model_ready": all(models.values()),
                    "models": models,
                    "production_backend": "flux2_klein_4b_distilled_fp8",
                    "training_backend": "flux2_klein_4b_distilled_native_lora",
                    "teacher_backend_required": False,
                    "hardware_target": "rtx_3060_12gb",
                    "hardware_validation": hardware_validation_status(),
                    "comfy_url": COMFY_URL,
                    "artifact_root": str(TURNAROUND_ARTIFACT_ROOT.parent),
                    "local_library_root": str(LOCAL_LIBRARY_ROOT),
                    "local_3d_candidate_root": str(LOCAL_3D_CANDIDATE_ROOT),
                    "local_3d_library_root": str(LOCAL_3D_LIBRARY_ROOT),
                    "local_animation_library_root": str(LOCAL_ANIMATION_LIBRARY_ROOT),
                    "local_animation_assets": len(list_animation_assets()),
                    "training_pairs": len(list_training_pairs()),
                    "training_previews": len(list_training_previews()),
                    "actor_core_lora": ACTOR_CORE_LORA,
                    "profile_registry": str(PROFILE_REGISTRY_PATH),
                    "style_profiles": len(STYLE_PROFILES),
                    "actor_profiles": len(ACTOR_PROFILES),
                },
            )
            return

        if path == "/api/library":
            query = urllib.parse.parse_qs(parsed.query)
            kind = query.get("kind", [None])[0]
            try:
                assets = list_library_assets(kind)
            except ValueError as exc:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self.send_json(HTTPStatus.OK, {"assets": assets})
            return

        if path == "/api/3d-assets":
            self.send_json(HTTPStatus.OK, list_3d_assets())
            return

        if path == "/api/animation-library":
            self.send_json(HTTPStatus.OK, {"assets": list_animation_assets()})
            return

        if path == "/api/training-pairs":
            self.send_json(HTTPStatus.OK, {"pairs": list_training_pairs()})
            return

        if path == "/api/training-previews":
            self.send_json(HTTPStatus.OK, {"previews": list_training_previews()})
            return

        parts = [part for part in path.split("/") if part]
        if (
            len(parts) == 4
            and parts[:2] == ["api", "training-pairs"]
            and parts[3] in {"source", "target", "record"}
        ):
            try:
                directory = training_pair_directory(parts[2])
                record = json.loads(
                    (directory / "pair.json").read_text(encoding="utf-8")
                )
                if parts[3] == "record":
                    self.send_file(
                        directory / "pair.json", "application/json; charset=utf-8"
                    )
                else:
                    artifact = record[parts[3]]["filename"]
                    self.send_file(directory / artifact, "image/png")
            except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return
        if (
            len(parts) == 4
            and parts[:2] == ["api", "training-previews"]
            and parts[3] in {"image", "metrics", "review"}
        ):
            try:
                image, metrics, review = training_preview_files(parts[2])
                artifact, content_type = {
                    "image": (image, "image/png"),
                    "metrics": (metrics, "application/json; charset=utf-8"),
                    "review": (review, "application/json; charset=utf-8"),
                }[parts[3]]
                self.send_file(artifact, content_type)
            except (OSError, ValueError) as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return
        if (
            len(parts) in {5, 6, 7}
            and parts[:2] == ["api", "3d-library"]
            and parts[3] == "animation-previews"
        ):
            asset_id, animation_asset_id = parts[2], parts[4]
            try:
                preview = public_animation_preview(asset_id, animation_asset_id)
                directory = animation_preview_directory(asset_id, animation_asset_id)
                if len(parts) == 5:
                    self.send_json(HTTPStatus.OK, {"animation_preview": preview})
                    return
                if len(parts) == 6 and parts[5] == "model":
                    self.send_file(directory / "retargeted.glb", "model/gltf-binary")
                    return
                if len(parts) == 6 and parts[5] == "report":
                    self.send_file(directory / "retarget.json", "application/json; charset=utf-8")
                    return
                if len(parts) == 6 and parts[5] == "contact-sheet":
                    self.send_file(directory / "four_direction_contact_sheet.png", "image/png")
                    return
                if len(parts) == 7 and parts[5] == "preview":
                    if parts[6] not in {"front", "right", "back", "left"}:
                        raise FileNotFoundError("animation preview view is invalid")
                    self.send_file(directory / f"{parts[6]}.gif", "image/gif")
                    return
                raise FileNotFoundError("animation preview artifact not found")
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
        if (
            len(parts) in {4, 5}
            and parts[0] == "api"
            and parts[1] in {"3d-candidates", "3d-library"}
        ):
            scope = "candidate" if parts[1] == "3d-candidates" else "library"
            asset_id = parts[2]
            try:
                manifest = load_3d_manifest(scope, asset_id)
                asset_dir = local_3d_dir(scope, asset_id)
                if len(parts) == 4 and parts[3] == "model":
                    artifact = safe_3d_artifact(asset_dir, manifest["model_filename"])
                    self.send_file(artifact, "model/gltf-binary")
                    return
                if len(parts) == 4 and parts[3] == "combined-model":
                    relative = manifest.get("combined_model_filename")
                    if not relative:
                        raise FileNotFoundError("combined 3D review model not found")
                    artifact = safe_3d_artifact(asset_dir, relative)
                    self.send_file(artifact, "model/gltf-binary")
                    return
                if len(parts) == 5 and parts[3] == "preview":
                    relative = manifest.get("preview_filenames", {}).get(parts[4])
                    if not relative:
                        raise FileNotFoundError("local 3D preview not found")
                    artifact = safe_3d_artifact(asset_dir, relative)
                    self.send_file(artifact, "image/png")
                    return
                if scope == "library" and len(parts) == 5 and parts[3] == "rig-preview":
                    if parts[4] not in {"front", "right", "back", "left"}:
                        raise FileNotFoundError("Actor rig preview view is invalid")
                    artifact = rig_artifact(
                        manifest,
                        f"rig_calibration_v2/preview/{parts[4]}.png",
                    )
                    self.send_file(artifact, "image/png")
                    return
                if scope == "library" and len(parts) == 4 and parts[3] == "rig-mesh":
                    rig_asset_id = safe_asset_id(manifest["rig_preparation"]["asset_id"])
                    artifact = rig_artifact(
                        manifest,
                        f"rig_mesh_lod0/{rig_asset_id}_rig_mesh.glb",
                    )
                    self.send_file(artifact, "model/gltf-binary")
                    return
                if scope == "library" and len(parts) == 4 and parts[3] == "accurig-fbx":
                    rig_asset_id = safe_asset_id(manifest["rig_preparation"]["asset_id"])
                    artifact = rig_artifact(
                        manifest,
                        f"accurig_handoff/{rig_asset_id}_accurig_input.fbx",
                    )
                    self.send_file(artifact, "application/octet-stream")
                    return
                if scope == "library" and len(parts) == 5 and parts[3] == "rigged-preview":
                    if parts[4] not in {"front", "right", "back", "left"}:
                        raise FileNotFoundError("rigged Actor preview view is invalid")
                    intake = current_rig_intake(asset_id)
                    if not intake or intake.get("status") != "ready":
                        raise FileNotFoundError("rigged Actor preview is not ready")
                    directory = rig_intake_directory(asset_id, intake["job_id"])
                    self.send_file(directory / "processed" / "preview" / f"{parts[4]}.png", "image/png")
                    return
                if scope == "library" and len(parts) == 4 and parts[3] in {
                    "rigged-model",
                    "rigged-blend",
                    "rigged-validation",
                }:
                    intake = current_rig_intake(asset_id)
                    if not intake or intake.get("status") != "ready":
                        raise FileNotFoundError("rigged Actor artifact is not ready")
                    directory = rig_intake_directory(asset_id, intake["job_id"]) / "processed"
                    rig_asset_id = safe_asset_id(manifest["rig_preparation"]["asset_id"])
                    if parts[3] == "rigged-model":
                        self.send_file(directory / f"{rig_asset_id}_rigged_preview.glb", "model/gltf-binary")
                    elif parts[3] == "rigged-blend":
                        self.send_file(directory / f"{rig_asset_id}_runtime_4weights.blend", "application/octet-stream")
                    else:
                        self.send_file(directory / "validation.json", "application/json; charset=utf-8")
                    return
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
        if (
            len(parts) == 5
            and parts[:2] == ["api", "library"]
            and parts[4] == "image"
        ):
            kind, asset_id = parts[2], parts[3]
            try:
                asset_dir = library_asset_dir(kind, asset_id)
                manifest = json.loads(
                    (asset_dir / "asset_manifest.json").read_text(encoding="utf-8")
                )
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            self.send_file(asset_dir / manifest["artifact_filename"], "image/png")
            return
        if len(parts) >= 3 and parts[0] == "api" and parts[1] in ROUTE_CONFIG:
            route = parts[1]
            job_id = parts[2]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if job is None:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "job not found"})
                return
            if len(parts) == 3:
                self.send_json(HTTPStatus.OK, public_job(job))
                return
            config = ROUTE_CONFIG[route]
            if job.get("job_kind", "base_actor") != config["kind"]:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "job not found"})
                return
            job_dir = config["root"] / job_id
            if len(parts) == 4 and parts[3] == "image":
                self.send_file(job_dir / config["filename"], "image/png")
                return
            if len(parts) == 4 and parts[3] == "record":
                self.send_file(job_dir / "record.json", "application/json; charset=utf-8")
                return
            if len(parts) == 4 and parts[3] == "metrics":
                self.send_file(
                    job_dir / "turnaround.metrics.json",
                    "application/json; charset=utf-8",
                )
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
        parsed = urllib.parse.urlparse(self.path)
        path = normalize_request_path(parsed.path)
        parts = [part for part in path.split("/") if part]
        if (
            len(parts) == 5
            and parts[:2] == ["api", "3d-library"]
            and parts[3] == "animation-previews"
        ):
            try:
                query = urllib.parse.parse_qs(parsed.query)
                force = query.get("force", ["false"])[0].lower() in {"1", "true", "yes"}
                preview = create_animation_preview(parts[2], parts[4], force=force)
            except FileNotFoundError as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self.send_json(HTTPStatus.ACCEPTED, {"animation_preview": preview})
            return
        if (
            len(parts) == 4
            and parts[:2] == ["api", "3d-library"]
            and parts[3] == "rig-intakes"
        ):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                filename = urllib.parse.unquote(
                    self.headers.get("X-AssetsStudio-Filename", "")
                )
                intake = create_rig_intake(parts[2], filename, length, self.rfile)
            except FileNotFoundError as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self.send_json(HTTPStatus.ACCEPTED, {"rig_intake": intake})
            return
        if (
            len(parts) == 4
            and parts[:2] == ["api", "3d-candidates"]
            and parts[3] == "accept"
        ):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = (
                    json.loads(self.rfile.read(length)) if 0 < length <= 16_384 else {}
                )
                confirmations = payload.get("manual_confirmations", [])
                if not isinstance(confirmations, list) or not all(
                    isinstance(item, str) for item in confirmations
                ):
                    raise ValueError("manual_confirmations must be a string array")
                asset = accept_3d_candidate(parts[2], confirmations)
            except FileNotFoundError as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            except (ValueError, FileExistsError, json.JSONDecodeError) as exc:
                self.send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
                return
            self.send_json(HTTPStatus.OK, {"asset": asset})
            return
        if (
            len(parts) == 4
            and parts[0] == "api"
            and parts[1] in ROUTE_CONFIG
            and parts[3] == "accept"
        ):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = (
                    json.loads(self.rfile.read(length)) if 0 < length <= 16_384 else {}
                )
                confirmations = payload.get("manual_confirmations", [])
                if not isinstance(confirmations, list) or not all(
                    isinstance(item, str) for item in confirmations
                ):
                    raise ValueError("manual_confirmations must be a string array")
                manifest = accept_job_into_library(parts[2], confirmations)
            except KeyError as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            except (ValueError, FileNotFoundError, FileExistsError) as exc:
                self.send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
                return
            self.send_json(HTTPStatus.OK, {"job": public_job(JOBS[parts[2]]), "asset": manifest})
            return

        create_paths = {f"/api/{route}" for route in ROUTE_CONFIG}
        if path not in create_paths:
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
            if path == "/api/turnarounds" and style not in STYLE_PROMPTS:
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
        if path == "/api/accessories":
            try:
                style_profile_id = str(payload.get("style_profile_id", ""))
                actor_profile_id = str(payload.get("actor_profile_id", ""))
                slot_id = str(payload.get("slot_id", ""))
                style_profile = STYLE_PROFILES.get(style_profile_id)
                actor_profile = ACTOR_PROFILES.get(actor_profile_id)
                if style_profile is None:
                    raise ValueError("unknown style_profile_id")
                if actor_profile is None:
                    raise ValueError("unknown actor_profile_id")
                if actor_profile["style_profile_id"] != style_profile_id:
                    raise ValueError("Actor profile does not belong to selected style")
                slot = find_slot(actor_profile, slot_id)
                base_actor_asset_id = str(payload.get("base_actor_asset_id", "")).strip()
                if base_actor_asset_id:
                    resolve_library_reference("base_actor", base_actor_asset_id)
                compiled_prompt = compile_accessory_prompt(
                    subject,
                    style_profile,
                    actor_profile,
                    slot,
                    base_actor_asset_id or None,
                )
            except ValueError as exc:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            job = {
                "id": job_id,
                "job_kind": "accessory",
                "status": "queued",
                "created_at": created,
                "updated_at": created,
                "subject": subject,
                "compiled_prompt": compiled_prompt,
                "style_profile_id": style_profile_id,
                "actor_profile_id": actor_profile_id,
                "slot_id": slot_id,
                "base_actor_asset_id": base_actor_asset_id or None,
                "seed": seed,
                "library_status": "candidate",
                "profile_snapshot": {
                    "style": style_profile,
                    "actor": {
                        "id": actor_profile["id"],
                        "revision": actor_profile["revision"],
                        "actor_asset_id": actor_profile["actor_asset_id"],
                        "measurements": actor_profile["measurements"],
                    },
                    "slot": slot,
                },
            }
        elif path in {"/api/style-seeds", "/api/base-actors"}:
            try:
                style_profile_id = str(payload.get("style_profile_id", ""))
                style_profile = STYLE_PROFILES.get(style_profile_id)
                if style_profile is None:
                    raise ValueError("unknown style_profile_id")
                style_seed_asset_id = str(payload.get("style_seed_asset_id", "")).strip()
                lora_strength = None
                if path == "/api/base-actors":
                    if not style_seed_asset_id:
                        raise ValueError(
                            "base_actor requires an approved style_seed_asset_id"
                        )
                    resolve_library_reference("style_seed", style_seed_asset_id)
                    if ACTOR_CORE_LORA is None:
                        raise ValueError("strip_to_actor_core LoRA was not found")
                    lora_strength = float(payload.get("lora_strength", 3.0))
                    if lora_strength not in ACTOR_CORE_LORA_STRENGTHS:
                        raise ValueError(
                            "lora_strength must use the review ladder: 2.0, 2.5 or 3.0"
                        )
            except ValueError as exc:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            job_kind = "style_seed" if path == "/api/style-seeds" else "base_actor"
            job = {
                "id": job_id,
                "job_kind": job_kind,
                "status": "queued",
                "created_at": created,
                "updated_at": created,
                "subject": subject,
                "compiled_prompt": compile_profile_turnaround_prompt(
                    subject, style_profile, style_seed=job_kind == "style_seed"
                ),
                "style": "soft_3d",
                "style_profile_id": style_profile_id,
                "style_seed_asset_id": style_seed_asset_id or None,
                "lora_strength": lora_strength,
                "seed": seed,
                "library_status": "candidate",
                "profile_snapshot": {"style": style_profile},
            }
        else:
            style_profile = next(iter(STYLE_PROFILES.values()))
            job = {
                "id": job_id,
                "job_kind": "base_actor",
                "status": "queued",
                "created_at": created,
                "updated_at": created,
                "subject": subject,
                "compiled_prompt": compile_profile_turnaround_prompt(subject, style_profile),
                "style": style,
                "style_profile_id": style_profile["id"],
                "seed": seed,
                "library_status": "candidate",
                "profile_snapshot": {"style": style_profile},
            }
        with JOBS_LOCK:
            JOBS[job_id] = job
        threading.Thread(target=run_generation, args=(job_id,), daemon=True).start()
        self.send_json(HTTPStatus.ACCEPTED, public_job(job))

    def do_DELETE(self) -> None:
        path = normalize_request_path(urllib.parse.urlparse(self.path).path)
        parts = [part for part in path.split("/") if part]
        if len(parts) == 3 and parts[:2] == ["api", "3d-candidates"]:
            try:
                destroy_3d_candidate(parts[2])
            except FileNotFoundError as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                self.send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
                return
            self.send_json(HTTPStatus.OK, {"candidate_id": parts[2], "library_status": "destroyed"})
            return
        if len(parts) != 3 or parts[0] != "api" or parts[1] not in ROUTE_CONFIG:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "route not found"})
            return
        try:
            destroy_candidate(parts[2])
        except KeyError as exc:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return
        except ValueError as exc:
            self.send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
            return
        self.send_json(HTTPStatus.OK, public_job(JOBS[parts[2]]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    TURNAROUND_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    STYLE_SEED_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    BASE_ACTOR_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    ACCESSORY_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    LOCAL_LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    LOCAL_ANIMATION_LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    TRAINING_PAIR_ROOT.mkdir(parents=True, exist_ok=True)
    imported_seeds = sync_published_style_seeds()
    restored_jobs = restore_persisted_jobs()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"AssetsStudio local generation API: http://{args.host}:{args.port}", flush=True)
    print(f"Published style seeds imported: {imported_seeds}", flush=True)
    print(f"Persisted candidate jobs restored: {restored_jobs}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
