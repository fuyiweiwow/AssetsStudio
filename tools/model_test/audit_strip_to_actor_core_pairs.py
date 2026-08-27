#!/usr/bin/env python3
"""Re-audit local Actor Core pairs and quarantine failed approvals."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from analyze_actor_core_shape import analyze_actor_core_shape


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ROOT = ROOT / "workspace" / "training" / "strip_to_actor_core" / "v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Mark failed pairs rejected and move them out of the approved pair directory",
    )
    args = parser.parse_args()

    dataset_root = args.dataset_root.resolve()
    pairs_root = dataset_root / "pairs"
    rejected_root = dataset_root / "rejected"
    reports: list[dict] = []
    failed = 0
    pair_directories = sorted(path for path in pairs_root.iterdir() if path.is_dir())
    records = {
        pair_dir: json.loads((pair_dir / "pair.json").read_text(encoding="utf-8"))
        for pair_dir in pair_directories
    }
    canonical_authorities = {
        (
            record.get("provenance", {}).get("target_geometry_authority_id"),
            record.get("provenance", {}).get("target_geometry_authority_sha256"),
        )
        for record in records.values()
    }
    canonical_authority_consistent = (
        len(canonical_authorities) == 1
        and None not in next(iter(canonical_authorities), (None, None))
    )
    for pair_dir in pair_directories:
        record_path = pair_dir / "pair.json"
        record = records[pair_dir]
        target_path = pair_dir / record["target"]["filename"]
        shape_qa = analyze_actor_core_shape(target_path)
        provenance = record.get("provenance", {})
        canonical_geometry_qa = {
            "authority_declared": bool(
                provenance.get("target_geometry_authority_id")
                and provenance.get("target_geometry_authority_sha256")
                and provenance.get("target_geometry_operation")
            ),
            "authority_consistent_across_approved_pairs": canonical_authority_consistent,
        }
        passed = shape_qa["automatic_pass"] and all(canonical_geometry_qa.values())
        reports.append(
            {
                "pair_id": record["pair_id"],
                "status_before": record["status"],
                "shape_qa": shape_qa,
                "canonical_geometry_qa": canonical_geometry_qa,
                "result": "pass" if passed else "fail",
            }
        )
        print(
            f"{record['pair_id']} result={'pass' if passed else 'fail'} "
            f"torso={shape_qa['metrics']['front_lower_torso_width_ratio']} "
            f"foot={shape_qa['metrics']['side_foot_projection_ratio']} "
            f"canonical={all(canonical_geometry_qa.values())}"
        )
        if passed:
            continue
        failed += 1
        if not args.apply:
            continue
        destination = rejected_root / pair_dir.name
        if destination.exists():
            raise RuntimeError(f"Rejected destination already exists: {destination}")
        record["status"] = "rejected"
        record["automatic_qa_reaudit"] = shape_qa
        rejection_reason = (
            "actor_core_shape_qa_v1_failed"
            if not shape_qa["automatic_pass"]
            else "canonical_geometry_authority_mismatch"
        )
        record["rejection"] = {
            "reason": rejection_reason,
            "rejected_at": datetime.now(timezone.utc).isoformat(),
        }
        record_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        rejected_root.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pair_dir), str(destination))

    report = {
        "schema": "assetsstudio_actor_core_pair_audit_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "applied": args.apply,
        "pair_count": len(reports),
        "failed_count": failed,
        "canonical_authorities": [
            {"id": authority[0], "sha256": authority[1]}
            for authority in sorted(canonical_authorities, key=lambda item: str(item))
        ],
        "canonical_authority_consistent": canonical_authority_consistent,
        "pairs": reports,
    }
    report_path = dataset_root / "actor_core_shape_audit_v1.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"report={report_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
