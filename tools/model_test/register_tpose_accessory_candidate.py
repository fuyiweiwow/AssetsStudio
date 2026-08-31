"""Register a passing static T-Pose accessory as a local-only 3D candidate."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATE_ROOT = ROOT / "workspace" / "local_3d_generation" / "accessories"


def safe_id(value: str) -> str:
    if not value or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in value):
        raise ValueError("invalid candidate id")
    return value


def copy(source: Path, destination: Path) -> str:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination.relative_to(destination.parents[1]).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit-report", type=Path, required=True)
    parser.add_argument("--shape-manifest", type=Path, required=True)
    parser.add_argument("--source-preparation", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--subject", default="Q-style leather belt and waist pouch")
    args = parser.parse_args()
    report = json.loads(args.fit_report.read_text(encoding="utf-8"))
    shape = json.loads(args.shape_manifest.read_text(encoding="utf-8"))
    if report.get("status") != "pass_static_tpose":
        raise RuntimeError("only a passing static T-Pose fit may become a candidate")
    if shape.get("status") != "pass" or shape.get("asset_kind") != "accessory":
        raise RuntimeError("accessory shape manifest did not pass its topology gate")
    candidate_id = safe_id(report["asset_id"])
    candidate_root = args.candidate_root.resolve()
    workspace_root = (ROOT / "workspace").resolve()
    if workspace_root not in candidate_root.parents:
        raise ValueError("candidate root must stay under the local workspace")
    destination = candidate_root / candidate_id
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir(parents=True)

    outputs = report["outputs"]
    model_filename = "model/accessory.glb"
    combined_filename = "review/combined_actor_accessory.glb"
    copy(Path(outputs["accessory_glb"]), destination / model_filename)
    copy(Path(outputs["combined_glb"]), destination / combined_filename)
    preview_filenames: dict[str, str] = {}
    for view, path in outputs["previews"].items():
        relative = f"preview/{view}.png"
        copy(Path(path), destination / relative)
        preview_filenames[view] = relative
    copy(args.fit_report, destination / "qa/fit_report.json")
    copy(args.shape_manifest, destination / "qa/shape_manifest.json")
    copy(args.source_preparation, destination / "qa/source_preparation.json")

    manual_gates = [
        "四方向确认腰带与腰包为同一结构，方向和比例没有明显错位",
        "确认静态 T-Pose 下配件完整环绕腰部且没有可见穿透",
        "确认下载的独立配件 GLB 不包含素体网格，可单独销毁或复用",
        "确认当前只批准静态适配；骨骼、蒙皮、动作和手腿动态间隙仍待后续验证",
    ]
    now = datetime.now(timezone.utc).isoformat()
    mesh = shape["mesh_audit"]
    manifest = {
        "schema": "assetsstudio_local_3d_candidate_v1",
        "candidate_id": candidate_id,
        "asset_kind": "accessory_3d",
        "actor_profile_id": report["actor_profile_id"],
        "source_base_actor_asset_id": report["actor_asset_id"],
        "slot_id": report["slot_id"],
        "style_profile_id": "qstyle_anime_western_fantasy_chibi3_no_face_v1",
        "subject": args.subject,
        "created_at": now,
        "library_status": "candidate",
        "usage_scope": "static_tpose_accessory_fit",
        "production_canonical_status": "manual_static_review_pending",
        "known_issues": [
            "当前素体是 v9b 实验适配代理，不是最终 production canonical",
            "尚未执行骨骼映射、蒙皮、关节形变、走路动画和动态穿插 Gate",
        ],
        "local_only": True,
        "model_filename": model_filename,
        "combined_model_filename": combined_filename,
        "preview_filenames": preview_filenames,
        "mesh_audit": {
            "vertices": shape["vertices"],
            "faces": shape["faces"],
            "connected_components": mesh["connected_components"],
            "watertight": mesh["watertight"],
            "winding_consistent": mesh["winding_consistent"],
            "peak_cuda_memory_bytes": shape["peak_cuda_memory_bytes"],
        },
        "qa_status": "pass_static_tpose_manual_review_required",
        "manual_gates_required": manual_gates,
        "manual_confirmations": [],
        "qa": {
            "fit_report": "qa/fit_report.json",
            "shape_manifest": "qa/shape_manifest.json",
            "source_preparation": "qa/source_preparation.json",
        },
    }
    (destination / "candidate_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "ASSETSSTUDIO_TPOSE_ACCESSORY_CANDIDATE_PASS "
        f"candidate={candidate_id} destination={destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
