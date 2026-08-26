#!/usr/bin/env python3
"""Register a local-only, gated Qwen-Image-Edit training pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2

from analyze_turnaround_sheet import analyze_turnaround


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ROOT = (
    ROOT / "workspace" / "training" / "strip_to_actor_core" / "v1" / "pairs"
)
REQUIRED_MANUAL_GATES = (
    "blank_head_no_ears_or_face",
    "no_hair_clothing_footwear_or_accessories",
    "continuous_featureless_non_anatomical_shell",
    "narrow_tapered_torso_not_pear_shaped",
    "front_right_back_describe_one_volume",
    "no_seams_holes_marks_or_compositing_artifacts",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_info(path: Path, filename: str) -> dict:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"Unable to read {path}")
    height, width = image.shape[:2]
    return {
        "filename": filename,
        "sha256": sha256(path),
        "width": width,
        "height": height,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--mask", type=Path)
    parser.add_argument("--style-profile-id", required=True)
    parser.add_argument("--caption", required=True)
    parser.add_argument("--consumer-tag", action="append", default=[])
    parser.add_argument("--pair-id")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--approve", action="store_true")
    parser.add_argument(
        "--confirm-manual-gates",
        action="store_true",
        help="Required with --approve after a human has checked every gate",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    target = args.target.resolve()
    mask = args.mask.resolve() if args.mask else None
    for path in (source, target, mask):
        if path is not None and not path.is_file():
            parser.error(f"file not found: {path}")
    if args.approve and not args.confirm_manual_gates:
        parser.error("--approve requires --confirm-manual-gates")

    pair_id = args.pair_id or uuid.uuid4().hex
    if not pair_id.replace("_", "").replace("-", "").isalnum():
        parser.error("pair id may contain only letters, numbers, '_' and '-'")
    pair_dir = args.dataset_root.resolve() / pair_id
    if pair_dir.exists():
        raise RuntimeError(f"Pair already exists: {pair_dir}")
    pair_dir.mkdir(parents=True)

    filenames = {"source": "source.png", "target": "target.png"}
    shutil.copy2(source, pair_dir / filenames["source"])
    shutil.copy2(target, pair_dir / filenames["target"])
    if mask:
        filenames["mask"] = "edit_mask.png"
        shutil.copy2(mask, pair_dir / filenames["mask"])

    source_info = image_info(pair_dir / filenames["source"], filenames["source"])
    target_info = image_info(pair_dir / filenames["target"], filenames["target"])
    mask_info = None
    if mask:
        mask_info = image_info(pair_dir / filenames["mask"], filenames["mask"])
        if (mask_info["width"], mask_info["height"]) != (
            target_info["width"],
            target_info["height"],
        ):
            raise RuntimeError("Mask and target dimensions must match")

    automatic_qa = analyze_turnaround(pair_dir / filenames["target"], 3)
    if args.approve and not automatic_qa["automatic_pass"]:
        raise RuntimeError("Target failed automatic turnaround gates")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "schema": "assetsstudio_strip_to_actor_core_pair_v1",
        "pair_id": pair_id,
        "task": "strip_to_actor_core",
        "status": "approved" if args.approve else "candidate",
        "style_profile_id": args.style_profile_id,
        "consumer_tags": sorted(set(args.consumer_tag)),
        "caption": args.caption.strip(),
        "source": source_info,
        "target": target_info,
        "automatic_qa": automatic_qa,
        "manual_gates": {
            gate: bool(args.approve and args.confirm_manual_gates)
            for gate in REQUIRED_MANUAL_GATES
        },
        "created_at": now,
        "reviewed_at": now if args.approve else None,
    }
    if mask_info:
        record["mask"] = mask_info
    (pair_dir / "pair.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"pair={pair_dir}")
    print(f"status={record['status']}")
    print(f"automatic_pass={automatic_qa['automatic_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
