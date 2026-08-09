"""Build a dependency-free mobile gallery for chibi face randomization reviews."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise RuntimeError(f"missing manifest: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"manifest root must be an object: {path}")
    return data


def rel_url(path: str) -> str:
    return "/".join(html.escape(part, quote=True) for part in Path(path).parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = read_json(root / "face_randomization_manifest.json")
    if manifest.get("schema") != "assetslab_chibi_face_randomization_preview_v1":
        raise RuntimeError("unexpected face randomization preview schema")
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        raise RuntimeError("gallery needs at least one face-style record")

    cards: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("invalid face-style record")
        seed = record.get("seed")
        style_id = record.get("style_id")
        style_name = record.get("style_name")
        front = record.get("front")
        right = record.get("right")
        if not isinstance(seed, int) or not isinstance(style_id, int) or not isinstance(style_name, str):
            raise RuntimeError("face-style record lacks seed or style metadata")
        if not isinstance(front, str) or not isinstance(right, str):
            raise RuntimeError("face-style record lacks pixel preview paths")
        for resource in (front, right):
            if not (root / resource).is_file():
                raise RuntimeError(f"gallery image is missing: {root / resource}")
        cards.append(
            """
            <article class=\"card\">
              <header><h2>{name}</h2><p>style {style_id} · seed {seed}</p></header>
              <div class=\"views\">
                <figure><img src=\"{front}\" alt=\"{name} front pixel preview\"><figcaption>Front</figcaption></figure>
                <figure><img src=\"{right}\" alt=\"{name} side pixel preview\"><figcaption>Side</figcaption></figure>
              </div>
              <p class=\"policy\">Ear: locked verified attachment<br>Brow: head-bone layer</p>
            </article>
            """.format(
                name=html.escape(style_name),
                style_id=style_id,
                seed=seed,
                front=rel_url(front),
                right=rel_url(right),
            )
        )

    page = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Chibi Face Randomization Gallery</title>
  <style>
    :root {{ color-scheme: dark; font-family: ui-rounded, system-ui, sans-serif; background: #21161a; color: #f8e8df; }}
    body {{ margin: 0; padding: 20px; background: radial-gradient(circle at top, #56362f, #21161a 55%); }}
    main {{ max-width: 1120px; margin: auto; }}
    h1 {{ margin: 0 0 6px; font-size: clamp(1.5rem, 5vw, 2.4rem); }}
    .lead {{ margin: 0 0 20px; color: #d9bdb0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }}
    .card {{ background: #342126e8; border: 1px solid #79534a; border-radius: 14px; overflow: hidden; box-shadow: 0 8px 24px #0006; }}
    header {{ padding: 12px 14px 4px; }} h2 {{ margin: 0; text-transform: capitalize; font-size: 1.1rem; }} header p, .policy {{ margin: 4px 0; color: #d4b5a8; font-size: .84rem; }}
    .views {{ display: grid; grid-template-columns: 1fr 1fr; gap: 2px; padding: 8px 8px 0; }}
    figure {{ margin: 0; text-align: center; color: #e9cfc1; font-size: .8rem; }}
    img {{ width: 100%; aspect-ratio: 1; object-fit: contain; image-rendering: pixelated; image-rendering: crisp-edges; background: #1c1114; border-radius: 8px; }}
    .policy {{ padding: 8px 14px 14px; line-height: 1.45; }}
    footer {{ margin-top: 20px; color: #c49e90; font-size: .78rem; }}
  </style>
</head>
<body><main>
  <h1>Chibi Face Randomization</h1>
  <p class=\"lead\">Static head-local review · 64px nearest-neighbour previews · not a final animation bake</p>
  <section class=\"grid\">{cards}</section>
  <footer>Generated from face_randomization_manifest.json</footer>
</main></body></html>""".format(cards="\n".join(cards))
    output = root / "gallery.html"
    output.write_text(page, encoding="utf-8")
    print(f"CHIBI_FACE_RANDOMIZATION_GALLERY_PASS cards={len(cards)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
