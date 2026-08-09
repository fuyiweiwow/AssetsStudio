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
    "docs/PRODUCT_TECH_BASELINE.md",
    "docs/DEVELOPMENT_LOG.md",
    "docs/REMOVALS.md",
    "docs/features/README.md",
    "docs/decisions/README.md",
    "docs/decisions/0001-development-record-system.md",
    "docs/templates/FEATURE_TEMPLATE.md",
    "docs/templates/ADR_TEMPLATE.md",
    "milestones/body/chibi_actor_mixamo_walk_v1.blend",
    "milestones/body/actor_accurig_input.fbx",
    "milestones/body/release_manifest.json",
    "milestones/body/animation_sources/mixamo_standard_walk.fbx",
    "milestones/body/animation_sources/mixamo_run.fbx",
    "milestones/body/ear_source/miku_chibi_ear_source.fbx",
    "milestones/body/eye_textures/eye_left.png",
    "milestones/body/eye_textures/eye_right.png",
    "milestones/hair/Blender-Chloe_Hair.blend",
    "milestones/hair/male_source/Blend_Hair.blend",
    "milestones/hair/hair_component_catalog_v1.json",
    "milestones/hair/hair_random_pool_v1.json",
    "milestones/face/runtime_chibi_eyes_ears_walk_v1/runtime_manifest.json",
    "milestones/face/eye_assembly_v1/crops_half/imagegen_eye_assembly_L.png",
    "milestones/face/eye_assembly_v1/crops_closed/imagegen_eye_assembly_L.png",
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
    "docs/PRODUCT_TECH_BASELINE.md": [
        "状态：`draft_for_discussion`",
        "## 当前需要讨论确认的问题",
    ],
    "docs/REMOVALS.md": ["## 新记录要求"],
}


MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def main() -> int:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError("missing required milestone files:\n" + "\n".join(missing))

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

    for manifest in ROOT.rglob("*.json"):
        json.loads(manifest.read_text(encoding="utf-8"))

    broken_links = []
    for document in ROOT.rglob("*.md"):
        if ".git" in document.parts:
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
        content = manifest.read_text(encoding="utf-8")
        if any(root in content for root in stale_roots):
            stale.append(str(manifest.relative_to(ROOT)))
    if stale:
        raise RuntimeError("stale AssetsLab absolute paths:\n" + "\n".join(stale))

    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts)
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
