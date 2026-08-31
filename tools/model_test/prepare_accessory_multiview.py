"""Split an isolated four-view accessory authority into Hunyuan inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops


VIEW_ORDER = ("front", "right", "back", "left")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    rgb = image.convert("RGB")
    saturation = rgb.convert("HSV").getchannel("S")
    chroma_mask = saturation.point(lambda value: 255 if value > 18 else 0)
    bbox = chroma_mask.getbbox()
    if bbox is not None:
        return bbox
    background = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    difference = ImageChops.difference(rgb, background).convert("L")
    mask = difference.point(lambda value: 255 if value > 10 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        raise RuntimeError("panel contains no foreground")
    return bbox


def square_panel(panel: Image.Image, resolution: int) -> tuple[Image.Image, tuple[int, int, int, int]]:
    source_bbox = content_bbox(panel)
    left, top, right, bottom = source_bbox
    width = right - left
    height = bottom - top
    pad = max(8, round(max(width, height) * 0.12))
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(panel.width, right + pad)
    bottom = min(panel.height, bottom + pad)
    crop = panel.crop((left, top, right, bottom)).convert("RGB")
    target = round(resolution * 0.8)
    scale = min(target / crop.width, target / crop.height)
    crop = crop.resize(
        (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGB", (resolution, resolution), (255, 255, 255))
    offset = ((resolution - crop.width) // 2, (resolution - crop.height) // 2)
    canvas.paste(crop, offset)
    return canvas, source_bbox


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=1024)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(args.input)
    if args.resolution < 256:
        raise ValueError("resolution must be at least 256")

    source = Image.open(args.input).convert("RGB")
    panel_width = source.width // len(VIEW_ORDER)
    if panel_width * len(VIEW_ORDER) != source.width:
        raise ValueError("turnaround width must divide evenly into four panels")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, dict[str, object]] = {}
    for index, view in enumerate(VIEW_ORDER):
        panel = source.crop((index * panel_width, 0, (index + 1) * panel_width, source.height))
        prepared, source_bbox = square_panel(panel, args.resolution)
        output = args.output_dir / f"{view}.png"
        prepared.save(output)
        outputs[view] = {
            "path": str(output.resolve()),
            "sha256": sha256(output),
            "size": list(prepared.size),
            "source_bbox": list(source_bbox),
            "foreground_aspect_width_over_height": round(
                (source_bbox[2] - source_bbox[0]) / (source_bbox[3] - source_bbox[1]), 6
            ),
        }

    manifest = {
        "schema": "assetsstudio_accessory_multiview_preparation_v1",
        "input": str(args.input.resolve()),
        "input_sha256": sha256(args.input),
        "panel_order": list(VIEW_ORDER),
        "background": "white_pending_official_hunyuan_rembg",
        "outputs": outputs,
    }
    manifest_path = args.manifest or args.output_dir / "preparation_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        "ASSETSSTUDIO_ACCESSORY_MULTIVIEW_PASS "
        f"input={args.input.resolve()} output={args.output_dir.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
