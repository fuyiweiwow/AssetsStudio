#!/usr/bin/env python3
"""Remove protruding ears from an approved relaxed-pose style baseline.

The edit is deterministic and local.  It replaces only pixels outside a
reviewed cheek/cranium curve with a row-fitted reconstruction of the existing
studio background.  It does not regenerate or rescale the head, face or body.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def foreground_component(image: np.ndarray) -> np.ndarray:
    saturation = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
    mask = (saturation > 35).astype(np.uint8) * 255
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        np.ones((5, 5), np.uint8),
        iterations=1,
    )
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count < 2:
        raise ValueError("Could not isolate the actor")
    component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == component


def fit_background_row(
    row: np.ndarray,
    subject_row: np.ndarray,
    left: int,
    right: int,
) -> np.ndarray:
    width = row.shape[0]
    x = np.arange(width, dtype=np.float64)
    valid = (~subject_row) & ((x < left - 8) | (x > right + 8))
    xn = x / (width - 1) * 2.0 - 1.0
    design = np.stack([np.ones_like(xn), xn, xn * xn], axis=1)
    fitted = np.empty_like(row, dtype=np.float64)
    for channel in range(3):
        coefficients, *_ = np.linalg.lstsq(
            design[valid],
            row[valid, channel].astype(np.float64),
            rcond=None,
        )
        fitted[:, channel] = design @ coefficients
    return np.clip(fitted, 0, 255).astype(np.uint8)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mask-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    source = cv2.imread(str(args.source))
    if source is None:
        raise FileNotFoundError(args.source)
    if source.shape[:2] != (768, 768):
        raise ValueError(f"Expected 768x768, got {source.shape[1]}x{source.shape[0]}")

    subject = foreground_component(source)
    remove = np.zeros(subject.shape, dtype=np.uint8)
    plate = source.copy()

    control_y = np.array(
        [270, 280, 290, 300, 310, 320, 330, 340, 350, 360, 370, 380, 390, 400, 410],
        dtype=np.float64,
    )
    control_left = np.array(
        [214, 216, 218, 221, 224, 227, 230, 233, 236, 239, 242, 245, 252, 258, 268],
        dtype=np.float64,
    )
    control_right = np.array(
        [558, 556, 554, 551, 548, 545, 542, 539, 536, 533, 530, 524, 519, 513, 504],
        dtype=np.float64,
    )

    rows = []
    for y in range(int(control_y[0]), int(control_y[-1]) + 1):
        xs = np.flatnonzero(subject[y])
        if not xs.size:
            continue
        current_left = int(xs[0])
        current_right = int(xs[-1])
        target_left = int(round(np.interp(y, control_y, control_left)))
        target_right = int(round(np.interp(y, control_y, control_right)))
        if target_left > current_left:
            # Include the low-saturation antialiased ear outline that falls
            # outside the saturation-derived foreground component.  The target
            # control curve itself already sits inside the ear-root shadow.
            remove[y, max(0, current_left - 16) : target_left] = 255
        if target_right < current_right:
            remove[y, target_right + 1 : min(source.shape[1], current_right + 17)] = 255
        plate[y] = fit_background_row(
            source[y],
            subject[y],
            current_left,
            current_right,
        )
        rows.append(
            {
                "y": y,
                "source": [current_left, current_right],
                "target": [target_left, target_right],
            }
        )

    alpha = cv2.GaussianBlur(remove, (0, 0), 0.85).astype(np.float32)[:, :, None] / 255.0
    output = np.clip(plate * alpha + source * (1.0 - alpha), 0, 255).astype(np.uint8)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.mask_output.parent.mkdir(parents=True, exist_ok=True)
    total_edit_mask = remove
    if not cv2.imwrite(str(args.output), output):
        raise RuntimeError(f"Failed to write {args.output}")
    if not cv2.imwrite(str(args.mask_output), total_edit_mask):
        raise RuntimeError(f"Failed to write {args.mask_output}")

    outside = total_edit_mask == 0
    outside_mae = float(np.abs(output.astype(np.int16) - source.astype(np.int16))[outside].mean())
    changed = np.max(np.abs(output.astype(np.int16) - source.astype(np.int16)), axis=2) > 3
    report = {
        "schema": "assetsstudio_actor_core_ear_removal_v1",
        "status": "human_review_required",
        "source": str(args.source),
        "source_sha256": sha256(args.source),
        "output": str(args.output),
        "output_sha256": sha256(args.output),
        "mask": str(args.mask_output),
        "edited_rows": [int(control_y[0]), int(control_y[-1])],
        "target_boundary_control_points": {
            "y": control_y.astype(int).tolist(),
            "left": control_left.astype(int).tolist(),
            "right": control_right.astype(int).tolist(),
        },
        "changed_pixels_over_3": int(changed.sum()),
        "outside_binary_mask_rgb_mae": round(outside_mae, 6),
        "invariants": [
            "no rescale or translation",
            "head crown, eyes, brows, jaw, neck and body unchanged",
            "only the protruding ear pixels are replaced",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"output={args.output.resolve()}")
    print(f"mask={args.mask_output.resolve()}")
    print(f"report={args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
