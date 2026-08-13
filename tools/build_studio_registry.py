"""Build the checked-in Studio registry from the authoritative asset status."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "docs" / "ASSET_STATUS.json"
OUTPUT_PATH = ROOT / "studio" / "src" / "generated" / "asset-registry.json"
HAIR_COMPONENT_CATALOG = ROOT / "milestones" / "hair" / "hair_component_catalog_v1.json"
HAIR_RANDOM_POOL = ROOT / "milestones" / "hair" / "hair_random_pool_v1.json"
HAIR_GALLERY_CATALOG = ROOT / "milestones" / "hair" / "hair_gallery_catalog_v1.json"
HAIR_FIRST_BUNDLE_RECIPE = ROOT / "milestones" / "hair" / "first_bundle_recipe_v1.json"
GARMENT_MATERIAL_LIBRARY = ROOT / "milestones" / "tops" / "garmentcode_short_sleeve_v1" / "materials" / "material_recipes.json"
THUMBNAIL_OUTPUT = ROOT / "studio" / "public" / "generated" / "thumbnails"


THUMBNAIL_SOURCES = {
    "face": (ROOT / "milestones" / "body" / "eye_textures" / "eye_left.png", "full"),
    "tops": (ROOT / "milestones" / "tops" / "garmentcode_short_sleeve_v1" / "review" / "four_view_frame00_contact_sheet.png", "horizontal_front"),
    "pants": (ROOT / "milestones" / "pants" / "native_control_v0" / "four_view_frame00_contact_sheet.png", "horizontal_front"),
    "shoes": (ROOT / "milestones" / "shoes" / "cartoon_sneaker_v10" / "four_view_contact_sheet.png", "grid_front"),
}


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

    first_hair_bundle = json.loads(HAIR_FIRST_BUNDLE_RECIPE.read_text(encoding="utf-8"))
    if first_hair_bundle.get("schema") != "assetsstudio_hair_bundle_recipe_v1":
        raise RuntimeError("unexpected first hair bundle recipe schema")
    hair_thumbnail = ROOT / first_hair_bundle["cache"]["directory"] / first_hair_bundle["cache"]["thumbnail"]
    thumbnail_sources = {**THUMBNAIL_SOURCES, "hair": (hair_thumbnail, "full")}

    THUMBNAIL_OUTPUT.mkdir(parents=True, exist_ok=True)
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
        thumbnail_spec = thumbnail_sources.get(category)
        thumbnail_url = None
        thumbnail_kind = None
        if thumbnail_spec is not None:
            thumbnail_source, crop_mode = thumbnail_spec
            if not thumbnail_source.is_file() and category != "hair":
                raise FileNotFoundError(thumbnail_source)
            if thumbnail_source.is_file():
                thumbnail_name = f"{category}.png"
                destination = THUMBNAIL_OUTPUT / thumbnail_name
                if crop_mode == "full":
                    if thumbnail_source.suffix.lower() == ".png":
                        shutil.copy2(thumbnail_source, destination)
                    else:
                        with Image.open(thumbnail_source) as image:
                            image.convert("RGBA").save(destination)
                else:
                    with Image.open(thumbnail_source) as image:
                        if crop_mode == "horizontal_front":
                            crop = (0, 0, image.width // 4, image.height)
                        elif crop_mode == "grid_front":
                            crop = (0, 0, image.width // 2, image.height // 2)
                        else:
                            raise RuntimeError(f"unsupported thumbnail crop mode: {crop_mode}")
                        image.crop(crop).convert("RGBA").save(destination)
                thumbnail_url = f"/generated/thumbnails/{thumbnail_name}"
                thumbnail_kind = "texture" if category == "face" else "fixed_front"
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
                "thumbnail_url": thumbnail_url,
                "thumbnail_kind": thumbnail_kind,
            }
        )

    missing_categories = sorted(set(CATEGORY_METADATA) - seen_categories)
    if missing_categories:
        raise RuntimeError("asset registry is missing categories: " + ", ".join(missing_categories))

    hair_components = json.loads(HAIR_COMPONENT_CATALOG.read_text(encoding="utf-8"))
    hair_pool = json.loads(HAIR_RANDOM_POOL.read_text(encoding="utf-8"))
    hair_galleries = json.loads(HAIR_GALLERY_CATALOG.read_text(encoding="utf-8"))
    garment_materials = json.loads(GARMENT_MATERIAL_LIBRARY.read_text(encoding="utf-8"))
    if hair_components.get("schema") != "assetslab_hair_component_catalog_v1":
        raise RuntimeError("unexpected hair component catalog schema")
    if hair_pool.get("schema") != "assetslab_hair_random_pool_v1":
        raise RuntimeError("unexpected hair random pool schema")
    if hair_galleries.get("schema") != "assetslab_hair_gallery_catalog_v1":
        raise RuntimeError("unexpected hair gallery catalog schema")
    if garment_materials.get("schema") != "assetsstudio_garment_material_library_v1":
        raise RuntimeError("unexpected garment material library schema")

    payload = {
        "schema": "assetsstudio_asset_registry_v1",
        "studio_version": "0.6.0",
        "updated": str(status["updated"]),
        "preview": {
            "model_url": "/generated/actor-composite-v1.glb",
            "manifest_url": "/generated/actor-composite-v1.manifest.json",
            "storage_policy": "local",
        },
        "assets": assets,
        "garment_materials": garment_materials,
        "hair": {
            "first_bundle": {
                "id": first_hair_bundle["id"],
                "gender": first_hair_bundle["gender"],
                "status": first_hair_bundle["status"],
                "components": first_hair_bundle["components"],
                "head_bone": first_hair_bundle["binding"]["bone"],
                "known_issue": first_hair_bundle.get("known_issue"),
            },
            "component_groups": [
                {
                    "id": group["id"],
                    "gender": group["gender"],
                    "role": group["role"],
                    "status": group["status"],
                    "objects": group["objects"],
                }
                for group in hair_components.get("component_groups", [])
            ],
            "random_pool": hair_pool.get("components", []),
            "galleries": hair_galleries.get("galleries", []),
        },
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
