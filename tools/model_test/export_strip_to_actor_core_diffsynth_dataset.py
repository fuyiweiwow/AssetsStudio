#!/usr/bin/env python3
"""Export approved generic edit pairs for ModelScope DiffSynth FLUX.2 training."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ROOT = ROOT / "workspace" / "training" / "strip_to_actor_core" / "v1"


def approved_pairs(pairs_root: Path) -> list[tuple[Path, dict]]:
    approved: list[tuple[Path, dict]] = []
    for record_path in sorted(pairs_root.glob("*/pair.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("status") != "approved":
            continue
        if record.get("task") != "strip_to_actor_core":
            raise RuntimeError(f"Unexpected task in {record_path}")
        if not all(record.get("manual_gates", {}).values()):
            raise RuntimeError(f"Approved pair has incomplete manual gates: {record_path}")
        approved.append((record_path.parent, record))
    return approved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    dataset_root = args.dataset_root.resolve()
    approved = approved_pairs(dataset_root / "pairs")
    if not approved:
        raise RuntimeError("No approved strip_to_actor_core pairs are available")
    print(f"approved_pairs={len(approved)}")
    if args.validate_only:
        return 0

    export_root = dataset_root / "diffsynth_flux2_export"
    images_root = export_root / "images"
    edits_root = export_root / "edit"
    images_root.mkdir(parents=True, exist_ok=True)
    edits_root.mkdir(parents=True, exist_ok=True)

    metadata: list[dict] = []
    manifest: list[dict] = []
    for pair_dir, record in approved:
        pair_id = record["pair_id"]
        target_name = f"images/{pair_id}.png"
        source_name = f"edit/{pair_id}.png"
        shutil.copy2(
            pair_dir / record["target"]["filename"], export_root / target_name
        )
        shutil.copy2(
            pair_dir / record["source"]["filename"], export_root / source_name
        )
        metadata.append(
            {
                "image": target_name,
                "prompt": record["caption"].strip(),
                "edit_image": [source_name],
            }
        )
        manifest.append(
            {
                "pair_id": pair_id,
                "source_sha256": record["source"]["sha256"],
                "target_sha256": record["target"]["sha256"],
            }
        )

    (export_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (export_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "assetsstudio_diffsynth_flux2_edit_export_v1",
                "model_id": "black-forest-labs/FLUX.2-klein-base-4B",
                "approved_pairs": manifest,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"metadata={export_root / 'metadata.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
