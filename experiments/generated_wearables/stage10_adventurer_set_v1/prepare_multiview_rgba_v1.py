from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
OFFICIAL_SOURCE = Path(
    os.environ.get("HUNYUAN3D_SOURCE", ROOT.parent / "Hunyuan3D-2-main")
).expanduser().resolve()
if str(OFFICIAL_SOURCE) not in sys.path:
    sys.path.insert(0, str(OFFICIAL_SOURCE))

from hy3dgen.rembg import BackgroundRemover  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--slot", required=True)
    return parser.parse_args()


def main() -> int:
    options = arguments()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    remover = BackgroundRemover()
    records = []
    for view in ("front", "right", "back", "left"):
        source = options.source_dir / f"{view}.png"
        image = Image.open(source).convert("RGB")
        rgba = remover(image).convert("RGBA")
        alpha = rgba.getchannel("A")
        bbox = alpha.getbbox()
        if bbox is None:
            raise RuntimeError(f"official rembg found no foreground: {source}")
        output = options.output_dir / f"{view}_rgba.png"
        rgba.save(output)
        records.append(
            {
                "view": view,
                "source": str(source.resolve()),
                "output": str(output.resolve()),
                "size": list(rgba.size),
                "alpha_bbox": list(bbox),
            }
        )
    manifest = {
        "schema": "hunyuan_official_rembg_multiview_v1",
        "slot": options.slot,
        "view_order": ["front", "left", "back", "right"],
        "records": records,
        "status": "pass",
    }
    (options.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
