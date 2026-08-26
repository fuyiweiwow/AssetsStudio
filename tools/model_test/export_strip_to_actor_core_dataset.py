#!/usr/bin/env python3
"""Export approved local pairs to Musubi Tuner's control-image dataset format."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ROOT = ROOT / "workspace" / "training" / "strip_to_actor_core" / "v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--resolution", default="768,384")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    dataset_root = args.dataset_root.resolve()
    pairs_root = dataset_root / "pairs"
    approved: list[tuple[Path, dict]] = []
    for record_path in sorted(pairs_root.glob("*/pair.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("status") != "approved":
            continue
        if not all(record.get("manual_gates", {}).values()):
            raise RuntimeError(f"Approved pair has incomplete manual gates: {record_path}")
        approved.append((record_path.parent, record))
    if not approved:
        raise RuntimeError("No approved strip_to_actor_core pairs are available")
    print(f"approved_pairs={len(approved)}")
    if args.validate_only:
        return 0

    try:
        width, height = (int(value) for value in args.resolution.split(",", 1))
    except ValueError as exc:
        parser.error("--resolution must be WIDTH,HEIGHT")
        raise exc

    export_root = dataset_root / "musubi_export"
    images_root = export_root / "images"
    controls_root = export_root / "controls"
    cache_root = export_root / "cache"
    images_root.mkdir(parents=True, exist_ok=True)
    controls_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)

    manifest = []
    for pair_dir, record in approved:
        pair_id = record["pair_id"]
        image_name = f"{pair_id}.png"
        shutil.copy2(pair_dir / record["target"]["filename"], images_root / image_name)
        shutil.copy2(pair_dir / record["source"]["filename"], controls_root / image_name)
        (images_root / f"{pair_id}.txt").write_text(
            record["caption"].strip() + "\n", encoding="utf-8"
        )
        manifest.append(
            {
                "pair_id": pair_id,
                "source_sha256": record["source"]["sha256"],
                "target_sha256": record["target"]["sha256"],
            }
        )

    toml = (
        "[general]\n"
        f"resolution = [{width}, {height}]\n"
        'caption_extension = ".txt"\n'
        "batch_size = 1\n"
        "enable_bucket = true\n"
        "bucket_no_upscale = true\n\n"
        "[[datasets]]\n"
        f'image_directory = "{images_root.as_posix()}"\n'
        f'control_directory = "{controls_root.as_posix()}"\n'
        f'cache_directory = "{cache_root.as_posix()}"\n'
        "control_resolution = [1024, 1024]\n"
        "num_repeats = 1\n"
    )
    (export_root / "dataset.toml").write_text(toml, encoding="utf-8")
    (export_root / "manifest.json").write_text(
        json.dumps({"approved_pairs": manifest}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"dataset_config={export_root / 'dataset.toml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
