#!/usr/bin/env python3
"""Build the bilateral local-edit mask for the A93 T-pose shoulder roots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


LEFT = [(282, 448), (330, 443), (359, 450), (361, 479), (346, 510), (306, 501), (282, 479)]
RIGHT = [(486, 448), (438, 443), (409, 450), (407, 479), (422, 510), (462, 501), (486, 479)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    source = cv2.imread(str(args.source), cv2.IMREAD_COLOR)
    if source is None:
        raise FileNotFoundError(args.source)
    if source.shape[:2] != (768, 768):
        raise ValueError(f"Expected 768x768, got {source.shape[1]}x{source.shape[0]}")

    mask = np.zeros(source.shape[:2], dtype=np.uint8)
    polygons = [np.asarray(points, dtype=np.int32) for points in (LEFT, RIGHT)]
    cv2.fillPoly(mask, polygons, 255, cv2.LINE_AA)

    preview = source.copy()
    overlay = np.zeros_like(preview)
    overlay[:, :, 2] = mask
    preview = cv2.addWeighted(preview, 0.72, overlay, 0.28, 0)
    cv2.polylines(preview, polygons, True, (0, 0, 255), 2, cv2.LINE_AA)

    for path, image in ((args.output, mask), (args.preview, preview)):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"Unable to write {path}")

    report = {
        "schema": "assetsstudio_actor_core_shoulder_repair_mask_v1",
        "status": "local_edit_input_only",
        "source": str(args.source),
        "mask": str(args.output),
        "polygons_xy": {"left": LEFT, "right": RIGHT},
        "intent": "widen only the shoulder-to-upper-arm roots while retaining open armpits",
        "invariants": [
            "head silhouette and face unchanged",
            "arm endpoints, span and level unchanged",
            "torso below y=510 unchanged",
            "legs and feet unchanged",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"mask={args.output.resolve()}")
    print(f"preview={args.preview.resolve()}")
    print(f"report={args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
