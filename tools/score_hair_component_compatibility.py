"""Score one generated hair component against the shared pool.

This is an offline screening score, not a replacement for final four-view
review. It combines the catalog compatibility graph, source-bundle identity,
required-base rules, and cached standalone geometry metadata when available.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def preview_dimensions(root: Path | None) -> dict[str, list[float]]:
    result: dict[str, list[float]] = {}
    if root is None or not root.is_dir():
        return result
    for path in root.rglob("manifest.json"):
        data = load_json(path)
        if data.get("schema") != "assetslab_hair_component_preview_v1":
            continue
        dimensions = data.get("fit", {}).get("dimensions")
        if isinstance(dimensions, list) and len(dimensions) == 3:
            result[str(data.get("source_object", ""))] = [float(value) for value in dimensions]
    return result


def compatibility_link(group: dict, other_group: dict) -> bool:
    group_id = str(group.get("id", ""))
    other_id = str(other_group.get("id", ""))
    return other_id in group.get("compatible_with", []) or group_id in other_group.get("compatible_with", [])


def geometry_score(source_dimensions: list[float] | None, other_dimensions: list[float] | None) -> tuple[float, str]:
    if not source_dimensions or not other_dimensions:
        return 10.0, "未缓存几何尺寸，使用中性分"
    ratios = [min(a, b) / max(a, b) for a, b in zip(source_dimensions, other_dimensions) if max(a, b) > 0]
    score = round(sum(ratios) / len(ratios) * 20.0, 2) if ratios else 0.0
    return score, "已使用独立部件预览的尺寸数据"


def score_variant(variant: dict, component_catalog: dict, pool_catalog: dict, preview_root: Path | None) -> dict:
    groups = {item["id"]: item for item in component_catalog.get("component_groups", [])}
    pool = [item for item in pool_catalog.get("components", []) if item.get("pool") and not item.get("preset")]
    source_object = str(variant.get("source_object", ""))
    source_item = next((item for item in pool if item.get("object") == source_object), None)
    source_group = None
    warnings: list[str] = []
    if source_item:
        source_group = groups.get(source_item.get("group_id"), {})
    else:
        source_group = next((group for group in groups.values() if source_object in group.get("objects", [])), None)
        if not source_group:
            raise RuntimeError(f"variant source object is not registered in component catalog: {source_object}")
        source_item = {"gender": source_group.get("gender"), "role": source_group.get("role"), "group_id": source_group.get("id")}
        warnings.append("该参考部件尚未进入正式随机池，评分仅用于实验筛选")
    gender = source_item.get("gender")
    role = source_item.get("role")
    dimensions = preview_dimensions(preview_root)
    variant_dimensions = variant.get("fit", {}).get("dimensions")
    matches: dict[str, list[dict[str, object]]] = {}
    for target_role in sorted({item.get("role") for item in pool if item.get("gender") == gender and item.get("role") != role}):
        ranked = []
        for item in pool:
            if item.get("gender") != gender or item.get("role") != target_role:
                continue
            target_group = groups.get(item.get("group_id"), {})
            reasons = []
            score = 0.0
            if item.get("gender") == gender:
                score += 15.0
                reasons.append("性别一致")
            if str(target_group.get("source_blend")) == str(source_group.get("source_blend")):
                score += 25.0
                reasons.append("共享同一源发型包")
            if compatibility_link(source_group, target_group):
                score += 35.0
                reasons.append("兼容矩阵允许")
            if target_role == "base_cap":
                score += 15.0
                reasons.append("可作为必选 base")
            geometry, geometry_reason = geometry_score(variant_dimensions, dimensions.get(str(item.get("object"))))
            score += geometry
            reasons.append(geometry_reason)
            ranked.append(
                {
                    "component_id": item.get("component_id"),
                    "object": item.get("object"),
                    "role": target_role,
                    "score": round(min(score, 100.0), 2),
                    "reasons": reasons,
                }
            )
        matches[target_role] = sorted(ranked, key=lambda item: (-float(item["score"]), str(item["object"])))[:5]
    best_scores = [float(items[0]["score"]) for items in matches.values() if items]
    overall = round(sum(best_scores) / len(best_scores), 2) if best_scores else 0.0
    measured = bool(dimensions.get(source_object))
    return {
        "schema": "assetslab_hair_component_compatibility_v1",
        "variant_id": variant.get("variant_id"),
        "source_object": source_object,
        "gender": gender,
        "role": role,
        "overall_score": overall,
        "score_meaning": "离线筛选分，不替代联合四视图验收",
        "geometry_measured": measured,
        "best_matches": matches,
        "warnings": warnings + ([] if measured else ["共享部件尚未全部生成独立预览，几何项使用中性分"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant-manifest", required=True, type=Path)
    parser.add_argument("--component-catalog", required=True, type=Path)
    parser.add_argument("--pool-catalog", required=True, type=Path)
    parser.add_argument("--component-preview-root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    variant = load_json(args.variant_manifest.resolve())
    if variant.get("schema") != "assetslab_hair_component_variant_v1":
        raise RuntimeError("unexpected variant manifest schema")
    variant.setdefault("variant_id", args.variant_manifest.resolve().parent.name)
    result = score_variant(variant, load_json(args.component_catalog.resolve()), load_json(args.pool_catalog.resolve()), args.component_preview_root.resolve() if args.component_preview_root else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"HAIR_COMPONENT_SCORE_PASS score={result['overall_score']} output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
