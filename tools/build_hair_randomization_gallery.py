"""Build a dependency-free mobile gallery for hair seed reviews."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from PIL import Image


SCHEMA = "assetslab_chloe_hair_randomization_gallery_v1"
DIRECTIONS = ("front", "right", "back", "left")


def rel_url(path: Path, root: Path) -> str:
    return "/".join(html.escape(part, quote=True) for part in path.relative_to(root).parts)


def display_sources(source_objects: list[str]) -> str:
    return " / ".join(name.removeprefix("Chloe_hair_") for name in source_objects)


def build_pixel_assets(candidate: Path) -> dict[str, str]:
    pixel_dir = candidate / "pixel"
    pixel_dir.mkdir(exist_ok=True)
    pixels: list[Image.Image] = []
    for direction in DIRECTIONS:
        source = candidate / f"{direction}.png"
        if not source.is_file():
            raise RuntimeError(f"missing render: {source}")
        image = Image.open(source).convert("RGBA")
        pixel = image.resize((64, 64), Image.Resampling.NEAREST)
        pixel.save(pixel_dir / f"{direction}_pixel.png")
        pixels.append(pixel.resize((256, 256), Image.Resampling.NEAREST))
    sheet = Image.new("RGBA", (1024, 256), (24, 24, 32, 255))
    for index, pixel in enumerate(pixels):
        sheet.alpha_composite(pixel, (index * 256, 0))
    sheet.save(pixel_dir / "four_view_pixel_sheet.png")
    return {
        "front": str(pixel_dir / "front_pixel.png"),
        "right": str(pixel_dir / "right_pixel.png"),
        "sheet": str(pixel_dir / "four_view_pixel_sheet.png"),
    }


def build_page(
    root: Path,
    records: list[dict[str, object]],
    title: str,
    lead: str,
    output: Path,
) -> None:
    cards: list[str] = []
    for record in records:
        candidate = root / str(record["directory"])
        name = str(record["name"])
        source = str(record["source"])
        pixel_front = rel_url(candidate / "pixel" / "front_pixel.png", root)
        pixel_right = rel_url(candidate / "pixel" / "right_pixel.png", root)
        sheet = rel_url(candidate / "pixel" / "four_view_pixel_sheet.png", root)
        raw_front = rel_url(candidate / "front.png", root)
        raw_right = rel_url(candidate / "right.png", root)
        cards.append(
            f"""
            <article class="card">
              <header><h2>{html.escape(name)}</h2><p>source: {html.escape(source)}</p></header>
              <div class="views">
                <figure><a href="{pixel_front}"><img src="{pixel_front}" alt="{html.escape(name)} front pixel preview"></a><figcaption>正面</figcaption></figure>
                <figure><a href="{pixel_right}"><img src="{pixel_right}" alt="{html.escape(name)} right pixel preview"></a><figcaption>侧面</figcaption></figure>
              </div>
              <p class="links"><a href="{sheet}">像素四视图</a> · <a href="{raw_front}">原始正面</a> · <a href="{raw_right}">原始侧面</a></p>
              <p class="note">当前为候选种子，需人工确认接缝、耳朵遮挡和动画表现。</p>
            </article>
            """
        )
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{ color-scheme: dark; font-family: ui-rounded, system-ui, sans-serif; background: #17151d; color: #f5ede8; }}
    body {{ margin: 0; padding: 18px; background: radial-gradient(circle at top, #493329, #17151d 58%); }}
    main {{ max-width: 1120px; margin: auto; }}
    h1 {{ margin: 0 0 5px; font-size: clamp(1.45rem, 5vw, 2.35rem); }}
    .lead {{ margin: 0 0 18px; color: #d6bbb0; line-height: 1.5; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }}
    .card {{ background: #2a2024ee; border: 1px solid #765247; border-radius: 14px; overflow: hidden; box-shadow: 0 8px 24px #0007; }}
    header {{ padding: 12px 14px 4px; }}
    h2 {{ margin: 0; font-size: 1.05rem; }}
    header p, .note, .links {{ margin: 5px 0; color: #d1b5a9; font-size: .78rem; line-height: 1.4; }}
    .views {{ display: grid; grid-template-columns: 1fr 1fr; gap: 3px; padding: 8px 8px 0; }}
    figure {{ margin: 0; text-align: center; color: #ecd7ce; font-size: .78rem; }}
    img {{ width: 100%; aspect-ratio: 1; object-fit: contain; image-rendering: pixelated; image-rendering: crisp-edges; background: #151219; border-radius: 8px; }}
    .links, .note {{ padding: 0 14px; }}
    a {{ color: #ffc7a3; }}
    footer {{ margin-top: 18px; color: #bda198; font-size: .76rem; }}
  </style>
</head>
<body><main>
  <h1>{html.escape(title)}</h1>
  <p class="lead">{html.escape(lead)}</p>
  <section class="grid">{"".join(cards)}</section>
  <footer>Generated from {SCHEMA}</footer>
</main></body></html>"""
    output.write_text(page, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--title", default="Chloe Hair Randomization Seeds")
    parser.add_argument(
        "--lead",
        default="Chloe low-poly 部件组合 · 64px 最近邻像素预览 · 点击图片可查看原图",
    )
    parser.add_argument("--output", type=Path, help="optional gallery HTML output path")
    parser.add_argument(
        "--candidate",
        action="append",
        dest="candidate_names",
        help="candidate directory to include; repeat for a curated gallery",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if args.candidate_names:
        candidates = [root / name for name in args.candidate_names]
        missing = [path for path in candidates if not (path.is_dir() and (path / "manifest.json").is_file())]
        if missing:
            raise RuntimeError("missing candidate directories: " + ", ".join(str(path) for path in missing))
    else:
        candidates = sorted(
            path for path in root.iterdir() if path.is_dir() and (path / "manifest.json").is_file()
        )
    if not candidates:
        raise RuntimeError(f"no candidate directories under {root}")
    records: list[dict[str, object]] = []
    for candidate in candidates:
        manifest = json.loads((candidate / "manifest.json").read_text(encoding="utf-8"))
        source_objects = manifest.get("source_objects")
        if not isinstance(source_objects, list) or not all(isinstance(item, str) for item in source_objects):
            raise RuntimeError(f"invalid source_objects in {candidate / 'manifest.json'}")
        build_pixel_assets(candidate)
        records.append(
            {
                "directory": candidate.name,
                "name": candidate.name.removeprefix("seed_").replace("_", " ").title(),
                "source": display_sources(source_objects),
                "source_objects": source_objects,
                "status": "review_required",
            }
        )
    gallery_manifest = {"schema": SCHEMA, "records": records}
    (root / "gallery_manifest.json").write_text(json.dumps(gallery_manifest, indent=2), encoding="utf-8")
    output = (args.output or (root / "gallery.html")).resolve()
    build_page(root, records, args.title, args.lead, output)
    print(f"HAIR_RANDOMIZATION_GALLERY_PASS cards={len(records)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
