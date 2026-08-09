"""Build the extensible entry page for all hair review galleries."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


SCHEMA = "assetslab_hair_gallery_catalog_v1"


def url_path(path: str) -> str:
    return "/".join(html.escape(part, quote=True) for part in Path(path).parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    catalog_path = args.catalog.resolve()
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog.get("schema") != SCHEMA:
        raise RuntimeError(f"unexpected gallery catalog schema: {catalog_path}")
    records = catalog.get("galleries")
    if not isinstance(records, list) or not records:
        raise RuntimeError("gallery catalog needs at least one gallery")

    cards: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("invalid gallery catalog record")
        required = ("id", "gender", "title", "path", "category", "status", "description")
        if not all(isinstance(record.get(key), str) for key in required):
            raise RuntimeError(f"invalid gallery record: {record}")
        if record["gender"] not in {"female", "male"}:
            raise RuntimeError(f"invalid gallery gender: {record}")
        gallery = root / record["path"]
        if not gallery.is_file():
            raise RuntimeError(f"gallery page is missing: {gallery}")
        preview = record.get("preview")
        preview_tag = ""
        if isinstance(preview, str):
            preview_path = root / preview
            if not preview_path.is_file():
                raise RuntimeError(f"gallery preview is missing: {preview_path}")
            preview_url = url_path(preview)
            preview_tag = f'<img src="{preview_url}" alt="{html.escape(record["title"])} preview">'
        status_class = {
            "推荐": "recommended",
            "基础": "base",
            "实验": "experimental",
        }.get(record["status"], "experimental")
        cards.append(
            f"""
            <article class="card {status_class}" data-gender="{html.escape(record['gender'])}">
              <a class="card-link" href="{url_path(record['path'])}">
                {preview_tag}
                <div class="copy">
                  <p class="badge">{html.escape(record['status'])}</p>
                  <h2>{html.escape(record['title'])}</h2>
                  <p class="category">{html.escape(record['category'])}</p>
                  <p>{html.escape(record['description'])}</p>
                </div>
              </a>
            </article>
            """
        )

    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AssetsStudio Hair Galleries</title>
  <style>
    :root {{ color-scheme: dark; font-family: ui-rounded, system-ui, sans-serif; background: #17151d; color: #f7eee8; }}
    body {{ margin: 0; padding: 20px; background: radial-gradient(circle at top, #493329, #17151d 60%); }}
    main {{ max-width: 1060px; margin: auto; }}
    h1 {{ margin: 0 0 6px; font-size: clamp(1.55rem, 6vw, 2.5rem); }}
    .lead {{ margin: 0 0 22px; color: #d5b9ad; line-height: 1.5; }}
    .workbench-link {{ margin: -8px 0 18px; }}
    .tabs {{ display: flex; gap: 8px; margin: 0 0 18px; }}
    .tab {{ border: 1px solid #765247; border-radius: 999px; padding: 8px 15px; background: #2a2024cc; color: #d5b9ad; cursor: pointer; font: inherit; }}
    .tab.active {{ background: #b86649; border-color: #e59a73; color: #fff4ec; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }}
    .card.hidden {{ display: none; }}
    .card {{ overflow: hidden; border: 1px solid #765247; border-radius: 16px; background: #2a2024ee; box-shadow: 0 8px 24px #0007; }}
    .card.base {{ border-color: #5d7084; }}
    .card.experimental {{ border-color: #897249; }}
    .card-link {{ display: block; color: inherit; text-decoration: none; }}
    img {{ display: block; width: 100%; aspect-ratio: 1.7; object-fit: contain; image-rendering: pixelated; background: #151219; }}
    .copy {{ padding: 13px 15px 16px; }}
    h2 {{ margin: 6px 0; font-size: 1.1rem; }}
    p {{ margin: 5px 0; color: #d1b5a9; font-size: .86rem; line-height: 1.45; }}
    .category {{ color: #f0c2a5; }}
    .badge {{ display: inline-block; margin: 0; padding: 3px 8px; border-radius: 99px; background: #7d4938; color: #ffe6d6; font-size: .72rem; }}
    .base .badge {{ background: #4c6072; }}
    .experimental .badge {{ background: #75613b; }}
    footer {{ margin-top: 22px; color: #bda198; font-size: .76rem; }}
  </style>
</head>
<body><main>
  <h1>AssetsStudio Hair Galleries</h1>
  <p class="lead">统一发型评审入口 · 先按性别筛选，再进入基础、推荐或实验 Gallery。</p>
  <p class="workbench-link"><a href="workbench/index.html">打开发型组合装配与随机池评审页面</a> · <a href="hair_component_variants_2026_08_04/workbench/index.html">打开单部件变体工作台</a></p>
  <nav class="tabs" aria-label="按性别筛选">
    <button class="tab active" type="button" data-filter="all" aria-pressed="true">全部</button>
    <button class="tab" type="button" data-filter="female" aria-pressed="false">女性</button>
    <button class="tab" type="button" data-filter="male" aria-pressed="false">男性</button>
  </nav>
  <section class="grid">{"".join(cards)}</section>
  <footer>Catalog schema: {SCHEMA}</footer>
</main>
<script>
  const tabs = [...document.querySelectorAll('[data-filter]')];
  const cards = [...document.querySelectorAll('.card[data-gender]')];
  for (const tab of tabs) {{
    tab.addEventListener('click', () => {{
      const filter = tab.dataset.filter;
      for (const item of tabs) {{
        const active = item === tab;
        item.classList.toggle('active', active);
        item.setAttribute('aria-pressed', String(active));
      }}
      for (const card of cards) {{
        card.classList.toggle('hidden', filter !== 'all' && card.dataset.gender !== filter);
      }}
    }});
  }}
</script>
</body></html>"""
    output = (args.output or (root / "index.html")).resolve()
    output.write_text(page, encoding="utf-8")
    print(f"HAIR_GALLERY_INDEX_PASS cards={len(cards)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
