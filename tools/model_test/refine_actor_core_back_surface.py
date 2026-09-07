#!/usr/bin/env python3
"""Remove back-center anatomy grooves from the frozen Actor Core back view."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


EXPECTED_SOURCE_SHA256 = "076c2e9fc299326f1b6c34b75d97ed83f8a87fd5b7f17946908bd0ea6cc70a88"
CENTER_X = 386


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def foreground_component(image: np.ndarray) -> np.ndarray:
    saturation = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
    mask = (saturation > 35).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count < 2:
        raise RuntimeError("Unable to isolate actor")
    component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == component


def smooth_center_surface(source: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    subject = foreground_component(source)
    output = source.copy()
    edit_mask = np.zeros(subject.shape, dtype=np.uint8)
    control_y = np.asarray([438, 470, 510, 535, 555, 575, 595, 612, 622])
    control_half_width = np.asarray([5, 7, 9, 14, 24, 32, 31, 18, 7])
    rows: list[dict] = []

    for y in range(int(control_y[0]), int(control_y[-1]) + 1):
        half_width = int(round(np.interp(y, control_y, control_half_width)))
        xs = np.flatnonzero(subject[y])
        if not xs.size:
            continue
        subject_left = int(xs[0])
        subject_right = int(xs[-1])
        left = max(subject_left + 4, CENTER_X - half_width)
        right = min(subject_right - 4, CENTER_X + half_width)
        if right <= left:
            continue

        sample_left = np.arange(max(subject_left + 4, left - 16), max(subject_left + 4, left - 4))
        sample_right = np.arange(min(subject_right - 3, right + 5), min(subject_right - 3, right + 17))
        sample_x = np.concatenate([sample_left, sample_right])
        if sample_x.size < 8:
            continue
        xn = (sample_x.astype(np.float64) - CENTER_X) / 64.0
        design = np.stack([np.ones_like(xn), xn, xn * xn], axis=1)
        target_x = np.arange(left, right + 1)
        target_xn = (target_x.astype(np.float64) - CENTER_X) / 64.0
        target_design = np.stack(
            [np.ones_like(target_xn), target_xn, target_xn * target_xn], axis=1
        )
        fitted = np.empty((target_x.size, 3), dtype=np.float64)
        for channel in range(3):
            coefficients, *_ = np.linalg.lstsq(
                design,
                source[y, sample_x, channel].astype(np.float64),
                rcond=None,
            )
            fitted[:, channel] = target_design @ coefficients
        fitted = np.clip(fitted, 0, 255).astype(np.uint8)

        width = target_x.size
        edge = min(5, max(1, width // 4))
        alpha = np.ones(width, dtype=np.float64)
        alpha[:edge] = np.linspace(0.0, 1.0, edge, endpoint=False)
        alpha[-edge:] = np.linspace(1.0, 0.0, edge, endpoint=False)
        alpha = alpha[:, None]
        original = source[y, target_x].astype(np.float64)
        output[y, target_x] = np.clip(
            fitted.astype(np.float64) * alpha + original * (1.0 - alpha), 0, 255
        ).astype(np.uint8)
        edit_mask[y, target_x] = 255
        rows.append({"y": y, "left": left, "right": right})

    return output, edit_mask, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mask-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    source_hash = sha256(args.source)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"Source is not frozen back seed 1008: {source_hash}")
    source = cv2.imread(str(args.source), cv2.IMREAD_COLOR)
    if source is None:
        raise FileNotFoundError(args.source)
    output, edit_mask, rows = smooth_center_surface(source)
    difference = np.abs(output.astype(np.int16) - source.astype(np.int16))
    outside = edit_mask == 0

    for path, image in ((args.output, output), (args.mask_output, edit_mask)):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"Unable to write {path}")

    report = {
        "schema": "assetsstudio_actor_core_back_surface_refinement_v1",
        "status": "human_review_required",
        "source": str(args.source),
        "source_sha256": source_hash,
        "output": str(args.output),
        "output_sha256": sha256(args.output),
        "edit_mask": str(args.mask_output),
        "outside_edit_mask_rgb_mae_0_255": round(float(difference[outside].mean()), 6),
        "center_surface_summary": {
            "center_x": CENTER_X,
            "row_count": len(rows),
            "y_range": [rows[0]["y"], rows[-1]["y"]],
            "max_half_width_px": max((item["right"] - item["left"]) // 2 for item in rows),
        },
        "invariants": [
            "head, silhouette, shoulders, arms, hands, legs and feet unchanged",
            "only the torso and pelvis center surface is smoothed",
            "no diffusion or remote model used for refinement",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
