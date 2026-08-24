"""Compare two four-view silhouette render sets with deterministic gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


VIEWS = ("front", "right", "back", "left")


def mask(path: Path) -> tuple[set[int], tuple[int, int, int, int], tuple[int, int]]:
    image = Image.open(path).convert("L")
    width, height = image.size
    pixels = image.load()
    occupied = {
        y * width + x
        for y in range(height)
        for x in range(width)
        if pixels[x, y] >= 128
    }
    if not occupied:
        raise RuntimeError(f"No foreground pixels in {path}")
    xs = [index % width for index in occupied]
    ys = [index // width for index in occupied]
    return occupied, (min(xs), min(ys), max(xs), max(ys)), (width, height)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-iou", type=float, default=0.995)
    parser.add_argument("--max-bbox-drift", type=float, default=0.005)
    args = parser.parse_args()

    results = {}
    for view in VIEWS:
        source, source_bbox, source_size = mask(args.source_dir / f"{view}.png")
        candidate, candidate_bbox, candidate_size = mask(args.candidate_dir / f"{view}.png")
        if source_size != candidate_size:
            raise RuntimeError(f"Image sizes differ for {view}: {source_size} vs {candidate_size}")
        intersection = len(source & candidate)
        union = len(source | candidate)
        iou = intersection / union
        bbox_drift = max(
            abs(candidate_bbox[index] - source_bbox[index])
            / (source_size[0] if index % 2 == 0 else source_size[1])
            for index in range(4)
        )
        area_drift = abs(len(candidate) - len(source)) / len(source)
        results[view] = {
            "iou": iou,
            "source_bbox": source_bbox,
            "candidate_bbox": candidate_bbox,
            "max_normalized_bbox_drift": bbox_drift,
            "relative_area_drift": area_drift,
            "pass": iou >= args.min_iou and bbox_drift <= args.max_bbox_drift,
        }

    report = {
        "schema": "assetsstudio_silhouette_comparison_v1",
        "status": "pass" if all(item["pass"] for item in results.values()) else "fail",
        "thresholds": {
            "min_iou": args.min_iou,
            "max_normalized_bbox_drift": args.max_bbox_drift,
        },
        "source_dir": str(args.source_dir.resolve()),
        "candidate_dir": str(args.candidate_dir.resolve()),
        "views": results,
        "minimum_iou": min(item["iou"] for item in results.values()),
        "maximum_bbox_drift": max(item["max_normalized_bbox_drift"] for item in results.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"SILHOUETTE_COMPARE_{report['status'].upper()} "
        f"min_iou={report['minimum_iou']:.6f} max_bbox_drift={report['maximum_bbox_drift']:.6f}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
