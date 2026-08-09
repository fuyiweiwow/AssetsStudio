"""Build the checked-in F001 registry from the authoritative asset status."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "docs" / "ASSET_STATUS.json"
OUTPUT_PATH = ROOT / "studio" / "src" / "generated" / "asset-registry.json"


CATEGORY_METADATA = {
    "body": {
        "label": "身体与动作",
        "workflow": "docs/WORKFLOW_BODY.md",
        "visibility_group": None,
    },
    "hair": {
        "label": "发型组件池",
        "workflow": "docs/WORKFLOW_HAIR.md",
        "visibility_group": "hair",
    },
    "face": {
        "label": "五官与耳朵",
        "workflow": "docs/WORKFLOW_FACE.md",
        "visibility_group": "face",
    },
    "tops": {
        "label": "短袖上衣",
        "workflow": "docs/WORKFLOW_TOPS.md",
        "visibility_group": "top",
    },
    "pants": {
        "label": "短裤",
        "workflow": "docs/WORKFLOW_PANTS.md",
        "visibility_group": "pants",
    },
    "shoes": {
        "label": "卡通运动鞋",
        "workflow": "docs/WORKFLOW_SHOES.md",
        "visibility_group": "shoes",
    },
}


def main() -> int:
    status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    if status.get("schema") != "assetsstudio_asset_status_v1":
        raise RuntimeError(f"unexpected asset status schema: {STATUS_PATH}")

    assets = []
    seen_categories: set[str] = set()
    for record in status.get("milestones", []):
        category = str(record.get("category", ""))
        if category not in CATEGORY_METADATA:
            raise RuntimeError(f"unsupported category in asset status: {category}")
        source_path = str(record.get("path", ""))
        if not (ROOT / source_path).is_file():
            raise FileNotFoundError(ROOT / source_path)
        if category in seen_categories:
            raise RuntimeError(f"duplicate category in asset status: {category}")
        seen_categories.add(category)
        metadata = CATEGORY_METADATA[category]
        assets.append(
            {
                "id": str(record["id"]),
                "category": category,
                "label": metadata["label"],
                "status": str(record["status"]),
                "source_path": source_path,
                "workflow": metadata["workflow"],
                "known_issue": record.get("known_issue"),
                "visibility_group": metadata["visibility_group"],
            }
        )

    missing_categories = sorted(set(CATEGORY_METADATA) - seen_categories)
    if missing_categories:
        raise RuntimeError("asset registry is missing categories: " + ", ".join(missing_categories))

    payload = {
        "schema": "assetsstudio_asset_registry_v1",
        "studio_version": "0.1.0",
        "updated": str(status["updated"]),
        "preview": {
            "model_url": "/generated/actor-composite-v1.glb",
            "manifest_url": "/generated/actor-composite-v1.manifest.json",
            "storage_policy": "local",
        },
        "assets": assets,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"ASSETSSTUDIO_REGISTRY_PASS assets={len(assets)} output={OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
