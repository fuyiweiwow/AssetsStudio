"""Validate the curated AssetsStudio milestone contract."""

from __future__ import annotations

import hashlib
import json
import re
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
    "docs/templates/FEATURE_TEMPLATE.md",
    "docs/templates/ADR_TEMPLATE.md",
    "milestones/body/chibi_actor_mixamo_walk_v1.blend",
    "milestones/body/actor_accurig_input.fbx",
    "milestones/body/release_manifest.json",
    "milestones/body/animation_sources/mixamo_standard_walk.fbx",
    "milestones/body/animation_sources/mixamo_run.fbx",
    "milestones/body/face_contract_v1.json",
    "milestones/body/eye_textures/eye_left.png",
    "milestones/body/eye_textures/eye_right.png",
    "milestones/hair/sources/female/chloe_hair_source.blend",
    "milestones/hair/sources/male/colin_hair_source.blend",
    "milestones/hair/hair_component_catalog_v1.json",
    "milestones/hair/hair_random_pool_v1.json",
    "references/face/miku_chibi_source/miku_chibi_source.fbx",
    "references/face/miku_chibi_source/reference_manifest.json",
    "tools/blender/render_accurig_chibi_walk_test.py",
    "tools/process_actor_3to2_pixels.py",
    "tools/validate_actor_3to2_pixels.py",
    "tools/blender/actor_asset_render_utils.py",
    "milestones/tops/actor_native_tshirt_v5/actor_native_tshirt_body_component_v5_upperarm_coverage.blend",
    "milestones/tops/actor_native_tshirt_v5/manifest.json",
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
        "状态：`draft_for_discussion`",
        "## 当前需要讨论确认的问题",
    ],
    "docs/REMOVALS.md": ["## 新记录要求"],
    "docs/decisions/0002-asset-lifecycle-sync-policy.md": [
        "状态：`accepted`",
        "## 清理规则",
        "## Git 与云端边界",
    ],
    "docs/features/F001-studio-shell-asset-registry-actor-preview.md": [
        "功能 ID：`F001`",
        "## 技术选型",
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
]


MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


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

    face_contract = json.loads(
        (ROOT / "milestones/body/face_contract_v1.json").read_text(encoding="utf-8")
    )
    face_paths = [
        str(face_contract["actor_blend"]),
        str(face_contract["eye_textures"]["left"]),
        str(face_contract["eye_textures"]["right"]),
        str(face_contract["ear_source"]["file"]),
        str(face_contract["actor_3to2_pipeline"]["render"]),
        str(face_contract["actor_3to2_pipeline"]["pixel_process"]),
        str(face_contract["actor_3to2_pipeline"]["validate"]),
    ]
    missing_face_paths = [path for path in face_paths if not (ROOT / path).is_file()]
    if missing_face_paths:
        raise RuntimeError("missing Actor face contract dependencies:\n" + "\n".join(missing_face_paths))

    for manifest in ROOT.rglob("*.json"):
        if "third_party" in manifest.relative_to(ROOT).parts:
            continue
        json.loads(manifest.read_text(encoding="utf-8"))

    broken_links = []
    for document in ROOT.rglob("*.md"):
        relative_parts = document.relative_to(ROOT).parts
        if ".git" in document.parts or "third_party" in relative_parts:
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
        if "third_party" in manifest.relative_to(ROOT).parts:
            continue
        content = manifest.read_text(encoding="utf-8")
        if any(root in content for root in stale_roots):
            stale.append(str(manifest.relative_to(ROOT)))
    if stale:
        raise RuntimeError("stale AssetsLab absolute paths:\n" + "\n".join(stale))

    files = sorted(
        path for path in ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "third_party" not in path.relative_to(ROOT).parts
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
