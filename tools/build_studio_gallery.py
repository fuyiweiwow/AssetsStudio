"""Build the single static human-review gallery for AssetsStudio milestones."""

from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "docs" / "ASSET_STATUS.json"
OUTPUT = ROOT / "gallery" / "index.html"


CARDS = [
    {
        "title": "Body / Actor V1 walk",
        "status": "accepted",
        "note": "Actor V1, AccuRIG skeleton and the retained four-direction walk runtime proof.",
        "media": [
            "milestones/face/runtime_chibi_eyes_ears_walk_v1/front.gif",
            "milestones/face/runtime_chibi_eyes_ears_walk_v1/right.gif",
        ],
        "doc": "docs/WORKFLOW_BODY.md",
    },
    {
        "title": "Hair component pool v1",
        "status": "source contract",
        "note": "Chloe/Colin source Blend files, base-cap rules, component catalog and deterministic pool. Generate new previews with the retained workbench tools.",
        "media": [],
        "doc": "docs/WORKFLOW_HAIR.md",
        "links": [
            ("gallery/hair_workbench.html", "Open combination workbench"),
            ("gallery/hair_components.html", "Open component workbench"),
        ],
    },
    {
        "title": "Face / eyes, brows and ears",
        "status": "technical baseline",
        "note": "Fixed face-layer registration, verified ears and retained blink-state source assets.",
        "media": [
            "milestones/face/base_features_v1/male/face_walk_4way.png",
            "milestones/face/base_features_v1/male/ear_walk_4way.png",
        ],
        "doc": "docs/WORKFLOW_FACE.md",
    },
    {
        "title": "Actor-native short sleeve v5",
        "status": "provisional",
        "note": "Current single-mesh shirt candidate. Known issue: pose-dependent right shoulder/sleeve protrusion.",
        "media": [
            "milestones/tops/actor_native_tshirt_v5/front_walk_8frames.gif",
            "milestones/tops/actor_native_tshirt_v5/right_walk_8frames.gif",
            "milestones/tops/actor_native_tshirt_v5/walk_4way_32frames.gif",
        ],
        "doc": "docs/WORKFLOW_TOPS.md",
    },
    {
        "title": "Blender-native shorts v0",
        "status": "provisional",
        "note": "Selected clean pants direction; old GarmentCode transfer sweeps are excluded.",
        "media": [
            "milestones/pants/native_control_v0/front_walk_8frames.gif",
            "milestones/pants/native_control_v0/right_walk_8frames.gif",
            "milestones/pants/native_control_v0/walk_4way_32frames.gif",
        ],
        "doc": "docs/WORKFLOW_PANTS.md",
    },
    {
        "title": "Cartoon sneaker v10",
        "status": "accepted",
        "note": "User-approved length-expanded Foot/ToeBase rigid binding milestone.",
        "media": [
            "milestones/shoes/cartoon_sneaker_v10/front_walk_8frames.gif",
            "milestones/shoes/cartoon_sneaker_v10/right_walk_8frames.gif",
            "milestones/shoes/cartoon_sneaker_v10/walk_4way_32frames.gif",
        ],
        "doc": "docs/WORKFLOW_SHOES.md",
    },
]


def rel_from_gallery(path: str) -> str:
    return "../" + "/".join(html.escape(part, quote=True) for part in Path(path).parts)


def main() -> int:
    payload = json.loads(STATUS.read_text(encoding="utf-8"))
    if payload.get("schema") != "assetsstudio_asset_status_v1":
        raise RuntimeError("unexpected asset status schema")

    cards = []
    for card in CARDS:
        media_html = []
        for media in card["media"]:
            source = ROOT / media
            if not source.is_file():
                raise FileNotFoundError(source)
            media_html.append(
                f'<figure><img src="{rel_from_gallery(media)}" alt="{html.escape(card["title"])} review animation"></figure>'
            )
        if not media_html:
            media_html.append('<div class="empty">Source milestone: generate candidate previews through the documented workbench.</div>')
        links = [(card["doc"], "Open workflow"), *card.get("links", [])]
        link_html = " ".join(
            f'<a href="{rel_from_gallery(path)}">{html.escape(label)}</a>' for path, label in links
        )
        cards.append(
            f'''<article class="card">
              <header><h2>{html.escape(card["title"])}</h2><span class="status">{html.escape(card["status"])}</span></header>
              <p>{html.escape(card["note"])}</p>
              <div class="media">{"".join(media_html)}</div>
              <div class="links">{link_html}</div>
            </article>'''
        )

    page = f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>AssetsStudio Milestone Gallery</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, system-ui, sans-serif; background:#0d1117; color:#e6edf3; }}
    body {{ margin:0; background:radial-gradient(circle at top,#1d2b43,#0d1117 52%); }}
    main {{ width:min(1180px,calc(100% - 28px)); margin:auto; padding:34px 0 70px; }}
    h1 {{ margin:0 0 8px; font-size:clamp(1.8rem,5vw,3rem); }}
    .lead {{ color:#a9b8c8; margin:0 0 26px; line-height:1.6; }}
    .grid {{ display:grid; gap:18px; }}
    .card {{ border:1px solid #34445a; border-radius:18px; padding:18px; background:#111a26dd; box-shadow:0 12px 38px #0006; }}
    header {{ display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }}
    h2 {{ margin:0; font-size:1.2rem; }}
    .status {{ padding:5px 10px; border-radius:999px; background:#263b54; color:#9ed0ff; font-size:.78rem; }}
    .card p {{ color:#b7c3d0; line-height:1.55; }}
    .media {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; margin:12px 0 15px; }}
    figure {{ margin:0; border-radius:12px; overflow:hidden; background:#0a0f15; }}
    img {{ width:100%; display:block; object-fit:contain; min-height:180px; max-height:420px; }}
    .empty {{ min-height:100px; display:grid; place-items:center; border:1px dashed #41536b; border-radius:12px; color:#91a1b2; padding:18px; text-align:center; }}
    a {{ color:#80c4ff; }} .links {{ display:flex; flex-wrap:wrap; gap:14px; }}
  </style>
</head>
<body><main>
  <h1>AssetsStudio Milestone Gallery</h1>
  <p class="lead">只展示正式里程碑和唯一当前候选。provisional 表示仍需人工修复，不能被自动报告冒充为 accepted。</p>
  <section class="grid">{"".join(cards)}</section>
</main></body></html>'''
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"ASSETSSTUDIO_GALLERY_PASS cards={len(cards)} output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
