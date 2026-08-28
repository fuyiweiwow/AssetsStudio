"""Compare Hunyuan renders with their multiview RGBA source silhouettes.

The comparison removes canvas placement and global scale while preserving each
view's aspect ratio.  It is therefore useful for ranking 3D candidates without
rewarding a camera framing coincidence.  Thresholds are deliberately optional:
until the project has enough accepted and rejected meshes, the report remains a
diagnostic rather than an automatic approval gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


VIEWS = ("front", "right", "back", "left")
CANVAS_SIZE = 1024
TARGET_HEIGHT = 900


def foreground_mask(path: Path) -> Image.Image:
    with Image.open(path) as source:
        rgba = source.convert("RGBA")
        alpha = rgba.getchannel("A")
        alpha_extrema = alpha.getextrema()
        if alpha_extrema != (255, 255):
            return alpha.point(lambda value: 255 if value >= 128 else 0)
        gray = rgba.convert("L")
        return gray.point(lambda value: 255 if value >= 128 else 0)


def normalized_mask(path: Path) -> tuple[Image.Image, dict[str, float | list[int]]]:
    mask = foreground_mask(path)
    bbox = mask.getbbox()
    if bbox is None:
        raise RuntimeError(f"No foreground found: {path}")
    crop = mask.crop(bbox)
    width, height = crop.size
    scale = TARGET_HEIGHT / height
    scaled_width = max(1, round(width * scale))
    if scaled_width > CANVAS_SIZE:
        raise RuntimeError(
            f"Foreground becomes wider than comparison canvas: {path} ({scaled_width}px)"
        )
    resized = crop.resize((scaled_width, TARGET_HEIGHT), Image.Resampling.NEAREST)
    canvas = Image.new("L", (CANVAS_SIZE, CANVAS_SIZE), 0)
    canvas.paste(
        resized,
        ((CANVAS_SIZE - scaled_width) // 2, (CANVAS_SIZE - TARGET_HEIGHT) // 2),
    )
    return canvas, {
        "source_bbox": list(bbox),
        "source_width_height_ratio": width / height,
        "normalized_width": scaled_width,
    }


def occupied(mask: Image.Image) -> set[int]:
    return {
        index
        for index, value in enumerate(mask.get_flattened_data())
        if value >= 128
    }


def save_overlay(source: Image.Image, candidate: Image.Image, output: Path) -> None:
    source_pixels = source.load()
    candidate_pixels = candidate.load()
    overlay = Image.new("RGB", source.size, (0, 0, 0))
    overlay_pixels = overlay.load()
    for y in range(source.height):
        for x in range(source.width):
            in_source = source_pixels[x, y] >= 128
            in_candidate = candidate_pixels[x, y] >= 128
            if in_source and in_candidate:
                overlay_pixels[x, y] = (255, 255, 255)
            elif in_source:
                overlay_pixels[x, y] = (255, 64, 64)
            elif in_candidate:
                overlay_pixels[x, y] = (64, 224, 255)
    output.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overlay-dir", type=Path)
    parser.add_argument("--min-iou", type=float)
    parser.add_argument("--max-aspect-drift", type=float)
    args = parser.parse_args()

    if (args.min_iou is None) != (args.max_aspect_drift is None):
        parser.error("provide both --min-iou and --max-aspect-drift, or neither")

    views: dict[str, dict[str, object]] = {}
    for view in VIEWS:
        source, source_info = normalized_mask(args.source_dir / f"{view}.png")
        candidate, candidate_info = normalized_mask(args.candidate_dir / f"{view}.png")
        source_pixels = occupied(source)
        candidate_pixels = occupied(candidate)
        intersection = len(source_pixels & candidate_pixels)
        union = len(source_pixels | candidate_pixels)
        iou = intersection / union
        source_aspect = float(source_info["source_width_height_ratio"])
        candidate_aspect = float(candidate_info["source_width_height_ratio"])
        aspect_drift = abs(candidate_aspect - source_aspect) / source_aspect
        passed = None
        if args.min_iou is not None:
            passed = iou >= args.min_iou and aspect_drift <= args.max_aspect_drift
        views[view] = {
            "iou": iou,
            "relative_aspect_drift": aspect_drift,
            "source": source_info,
            "candidate": candidate_info,
            "pass": passed,
        }
        if args.overlay_dir:
            save_overlay(source, candidate, args.overlay_dir / f"{view}.png")

    gated = args.min_iou is not None
    report = {
        "schema": "assetsstudio_hunyuan_source_silhouette_comparison_v1",
        "status": (
            "pass"
            if gated and all(item["pass"] for item in views.values())
            else "fail"
            if gated
            else "diagnostic_only"
        ),
        "normalization": {
            "canvas_size": CANVAS_SIZE,
            "target_height": TARGET_HEIGHT,
            "preserves_aspect_ratio": True,
            "removes_canvas_placement": True,
        },
        "thresholds": (
            {
                "min_iou": args.min_iou,
                "max_relative_aspect_drift": args.max_aspect_drift,
            }
            if gated
            else None
        ),
        "source_dir": str(args.source_dir.resolve()),
        "candidate_dir": str(args.candidate_dir.resolve()),
        "views": views,
        "minimum_iou": min(float(item["iou"]) for item in views.values()),
        "mean_iou": sum(float(item["iou"]) for item in views.values()) / len(views),
        "maximum_relative_aspect_drift": max(
            float(item["relative_aspect_drift"]) for item in views.values()
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"HUNYUAN_SILHOUETTE_{report['status'].upper()} "
        f"mean_iou={report['mean_iou']:.6f} "
        f"min_iou={report['minimum_iou']:.6f} "
        f"max_aspect_drift={report['maximum_relative_aspect_drift']:.6f}"
    )
    return 0 if report["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
