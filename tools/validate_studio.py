"""Validate the curated AssetsStudio milestone contract."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]


REQUIRED = [
    "PRINCIPLES.md",
    "docs/DEVELOPMENT.md",
    "docs/ART_DIRECTION.md",
    "docs/PRODUCT_TECH_BASELINE.md",
    "docs/DEVELOPMENT_LOG.md",
    "docs/REMOVALS.md",
    "docs/features/README.md",
    "docs/decisions/README.md",
    "docs/decisions/0001-development-record-system.md",
    "docs/decisions/0002-asset-lifecycle-sync-policy.md",
    "docs/features/F001-studio-shell-asset-registry-actor-preview.md",
    "docs/features/F002-actor-assembly-workflow.md",
    "docs/features/F003-asset-workbench-composite-review.md",
    "docs/features/F004-first-hair-bundle-integration.md",
    "docs/features/F005-workflow-scoped-library-collapsible-preview.md",
    "docs/features/F006-actor-garmentcode-short-sleeve.md",
    "schemas/asset-registry.v1.schema.json",
    "schemas/recipe.v1.schema.json",
    "schemas/run.v1.schema.json",
    "schemas/hair-bundle-recipe.v1.schema.json",
    "studio/package.json",
    "studio/package-lock.json",
    "studio/src/generated/asset-registry.json",
    "studio/src/App.tsx",
    "studio/src/components/WorkflowRail.tsx",
    "start-studio.cmd",
    "tools/build_studio_registry.py",
    "tools/blender/export_studio_actor_preview.py",
    "tools/export_studio_actor_preview.ps1",
    "tools/validate_studio_actor_preview.py",
    "tools/build_first_hair_bundle.ps1",
    "tools/render_first_hair_bundle_review.ps1",
    "tools/validate_first_hair_bundle.py",
    "tools/blender/hair_fit_support.py",
    "tools/blender/analyze_front_surface_coverage.py",
    "docs/templates/FEATURE_TEMPLATE.md",
    "docs/templates/ADR_TEMPLATE.md",
    "milestones/body/chibi_actor_mixamo_walk_v1.blend",
    "milestones/body/actor_accurig_input.fbx",
    "milestones/body/release_manifest.json",
    "milestones/body/animation_sources/mixamo_standard_walk.fbx",
    "milestones/body/animation_sources/mixamo_run.fbx",
    "milestones/body/face_contract_v2.json",
    "milestones/body/chibi_actor_eye_assembly_v2.blend",
    "milestones/body/eye_textures/eye_left.png",
    "milestones/body/eye_textures/eye_right.png",
    "milestones/body/eye_textures/eye_half_left.png",
    "milestones/body/eye_textures/eye_half_right.png",
    "milestones/body/eye_textures/eye_closed_left.png",
    "milestones/body/eye_textures/eye_closed_right.png",
    "milestones/hair/sources/female/chloe_hair_source.blend",
    "milestones/hair/sources/male/colin_hair_source.blend",
    "milestones/hair/hair_component_catalog_v1.json",
    "milestones/hair/hair_random_pool_v1.json",
    "milestones/hair/first_bundle_recipe_v1.json",
    "references/face/miku_chibi_source/miku_chibi_source.fbx",
    "references/face/miku_chibi_source/reference_manifest.json",
    "tools/blender/render_accurig_chibi_walk_test.py",
    "tools/process_actor_3to2_pixels.py",
    "tools/validate_actor_3to2_pixels.py",
    "tools/blender/actor_asset_render_utils.py",
    "tools/blender/build_actor_eye_assembly.py",
    "tools/blender/validate_actor_eye_assembly.py",
    "tools/blender/render_actor_eye_blink_review.py",
    "tools/build_actor_eye_assembly.ps1",
    "tools/render_actor_eye_blink_review.ps1",
    "tools/validate_actor_eye_blink_review.py",
    "milestones/tops/garmentcode_short_sleeve_v1/output/actor_transfer.blend",
    "milestones/tops/garmentcode_short_sleeve_v1/manifest.json",
    "milestones/tops/garmentcode_short_sleeve_v1/review/walk_4way_32frames.gif",
    "tools/validate_garmentcode_milestone.py",
    "milestones/pants/native_control_v0/native_control_shorts_v0.blend",
    "milestones/pants/native_control_v0/manifest.json",
    "milestones/shoes/cartoon_sneaker_v10/actor_cartoon_sneaker_fbx_v10_length_expanded.blend",
    "milestones/shoes/cartoon_sneaker_v10/manifest.json",
    "references/shoes/cartoon_sneaker/source/Shoessneakers.fbx",
    "references/shoes/cartoon_sneaker/reference_manifest.json",
]


REQUIRED_TEXT_MARKERS = {
    "PRINCIPLES.md": [
        "## 1. 文档是工作入口",
        "## 7. 及时删除，但必须可追溯",
        "## 8. 小步保存并留下时间线",
    ],
    "docs/DEVELOPMENT.md": [
        "## 主要功能开发流程",
        "## 保存与时间线",
        "## 完成定义",
    ],
    "docs/ART_DIRECTION.md": [
        "状态：`accepted_direction`",
        "## 核心方向",
        "## 旧 ImageGen 男女图的处理",
    ],
    "docs/PRODUCT_TECH_BASELINE.md": [
        "状态：`accepted_baseline`",
        "## 已确认的第一版技术边界",
    ],
    "docs/REMOVALS.md": ["## 新记录要求"],
    "docs/decisions/0002-asset-lifecycle-sync-policy.md": [
        "状态：`accepted`",
        "## 清理规则",
        "## Git 与云端边界",
    ],
    "docs/features/F001-studio-shell-asset-registry-actor-preview.md": [
        "功能 ID：`F001`",
        "状态：`in_progress`",
        "## 技术选型",
        "## 验收条件",
    ],
    "docs/features/F002-actor-assembly-workflow.md": [
        "功能 ID：`F002`",
        "状态：`in_progress`",
        "## 技术选型",
        "## 验收条件",
    ],
    "docs/features/F003-asset-workbench-composite-review.md": [
        "功能 ID：`F003`",
        "状态：`in_progress`",
        "## 分类边界",
        "## 验收条件",
    ],
}


FORBIDDEN_PATHS = [
    "milestones/face",
    "milestones/hair/Blender-Chloe_Hair.blend",
    "milestones/hair/male_source",
    "milestones/body/ear_source",
    "tools/process_accurig_walk_pixels.py",
    "tools/validate_pixel_runtime_package.py",
    "tools/validate_chibi_face_randomization.py",
    "tools/run_chibi_face_randomization_preview.ps1",
    "tools/build_chibi_face_variant_contact_sheet.py",
    "tools/build_chibi_face_randomization_gallery.py",
    "tools/blender/build_eye_assembly_v1.py",
    "tools/blender/render_eye_assembly_blink_walk.py",
    "tools/blender/render_procedural_anime_eye_on_accurig.py",
    "tools/blender/validate_eye_assembly_v1.py",
    "tools/blender/build_actor_derived_tshirt.py",
    "milestones/tops/actor_native_tshirt_v5",
]


MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def is_local_output(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    parts = relative.parts
    if "__pycache__" in parts:
        return True
    if parts and parts[0] in {"workspace", "third_party"}:
        return True
    local_roots = (
        ("studio", "node_modules"),
        ("studio", "dist"),
        ("studio", "coverage"),
        ("studio", "public", "generated"),
    )
    return any(parts[: len(prefix)] == prefix for prefix in local_roots)


def main() -> int:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError("missing required milestone files:\n" + "\n".join(missing))

    obsolete = [path for path in FORBIDDEN_PATHS if (ROOT / path).exists()]
    if obsolete:
        raise RuntimeError("obsolete asset paths must remain removed:\n" + "\n".join(obsolete))

    for relative_path, markers in REQUIRED_TEXT_MARKERS.items():
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        absent = [marker for marker in markers if marker not in content]
        if absent:
            raise RuntimeError(
                f"development baseline markers missing from {relative_path}:\n"
                + "\n".join(absent)
            )

    status = json.loads((ROOT / "docs" / "ASSET_STATUS.json").read_text(encoding="utf-8"))
    records = status.get("milestones", [])
    ids = [record.get("id") for record in records]
    if len(ids) != len(set(ids)) or len(ids) != 6:
        raise RuntimeError("asset status must contain six unique milestone ids")
    for record in records:
        path = ROOT / str(record["path"])
        if not path.is_file():
            raise FileNotFoundError(path)
        first_bundle = record.get("first_bundle")
        if first_bundle and not (ROOT / str(first_bundle)).is_file():
            raise FileNotFoundError(ROOT / str(first_bundle))

    hair_catalog = json.loads(
        (ROOT / "milestones/hair/hair_component_catalog_v1.json").read_text(encoding="utf-8")
    )
    hair_sources = {
        str(group["source_blend"])
        for group in hair_catalog.get("component_groups", [])
        if isinstance(group, dict) and group.get("source_blend")
    }
    if not hair_sources:
        raise RuntimeError("hair component catalog has no source Blend files")
    missing_hair_sources = [path for path in sorted(hair_sources) if not (ROOT / path).is_file()]
    if missing_hair_sources:
        raise RuntimeError("missing catalogued hair sources:\n" + "\n".join(missing_hair_sources))

    hair_bundle = json.loads(
        (ROOT / "milestones/hair/first_bundle_recipe_v1.json").read_text(encoding="utf-8")
    )
    if hair_bundle.get("schema") != "assetsstudio_hair_bundle_recipe_v1":
        raise RuntimeError("unexpected first hair bundle recipe schema")
    if hair_bundle.get("status") != "provisional":
        raise RuntimeError("first hair bundle must remain provisional until user review")
    if hair_bundle.get("binding", {}).get("bone") != "CC_Base_Head":
        raise RuntimeError("first hair bundle must bind to CC_Base_Head")

    face_contract = json.loads(
        (ROOT / "milestones/body/face_contract_v2.json").read_text(encoding="utf-8")
    )
    face_paths = [
        str(face_contract["source_actor_blend"]),
        str(face_contract["actor_face_blend"]),
        *[str(path) for path in face_contract["eye_textures"].values() if isinstance(path, str)],
        str(face_contract["ear_source"]["file"]),
        str(face_contract["actor_3to2_pipeline"]["render"]),
        str(face_contract["actor_3to2_pipeline"]["pixel_process"]),
        str(face_contract["actor_3to2_pipeline"]["validate"]),
        str(face_contract["rebuild"]),
        str(face_contract["review"]),
        str(face_contract["validate"]),
    ]
    missing_face_paths = [path for path in face_paths if not (ROOT / path).is_file()]
    if missing_face_paths:
        raise RuntimeError("missing Actor face contract dependencies:\n" + "\n".join(missing_face_paths))

    registry = json.loads(
        (ROOT / "studio/src/generated/asset-registry.json").read_text(encoding="utf-8")
    )
    if registry.get("schema") != "assetsstudio_asset_registry_v1":
        raise RuntimeError("unexpected Studio asset registry schema")
    registry_records = registry.get("assets", [])
    registry_projection = [
        (record.get("id"), record.get("category"), record.get("status"), record.get("source_path"))
        for record in registry_records
    ]
    status_projection = [
        (record.get("id"), record.get("category"), record.get("status"), record.get("path"))
        for record in records
    ]
    if registry_projection != status_projection:
        raise RuntimeError("Studio registry is stale; run python tools/build_studio_registry.py")

    garment_manifest = ROOT / "milestones/tops/garmentcode_short_sleeve_v1/manifest.json"
    milestone_result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/validate_garmentcode_milestone.py"),
            "--manifest",
            str(garment_manifest),
        ],
        text=True,
    )
    if milestone_result.returncode:
        raise RuntimeError("GarmentCode milestone asset validation failed")

    for manifest in ROOT.rglob("*.json"):
        if is_local_output(manifest) or ".git" in manifest.parts:
            continue
        json.loads(manifest.read_text(encoding="utf-8"))

    broken_links = []
    for document in ROOT.rglob("*.md"):
        if ".git" in document.parts or is_local_output(document):
            continue
        content = document.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK_RE.findall(content):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            linked_path = document.parent / unquote(target)
            if not linked_path.exists():
                broken_links.append(f"{document.relative_to(ROOT)} -> {raw_target}")
    if broken_links:
        raise RuntimeError("broken local Markdown links:\n" + "\n".join(broken_links))

    stale_roots = ("E:\\\\WorkProject\\\\AssetsLab", "D:\\\\Apps\\\\CodeXApp\\\\Tests\\\\AssetsLab")
    stale = []
    for manifest in ROOT.rglob("*.json"):
        if is_local_output(manifest) or ".git" in manifest.parts:
            continue
        content = manifest.read_text(encoding="utf-8")
        if any(root in content for root in stale_roots):
            stale.append(str(manifest.relative_to(ROOT)))
    if stale:
        raise RuntimeError("stale AssetsLab absolute paths:\n" + "\n".join(stale))

    files = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and ".git" not in path.parts and not is_local_output(path)
    )
    total = sum(path.stat().st_size for path in files)
    largest = max(files, key=lambda path: path.stat().st_size)
    if largest.stat().st_size >= 100 * 1024 * 1024:
        raise RuntimeError(f"GitHub 100 MB file limit exceeded: {largest}")
    digest = hashlib.sha256((ROOT / "docs" / "ASSET_STATUS.json").read_bytes()).hexdigest()[:12]
    print(
        f"ASSETSSTUDIO_VALIDATE_PASS milestones={len(records)} files={len(files)} "
        f"bytes={total} largest={largest.relative_to(ROOT)} status_sha256={digest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
