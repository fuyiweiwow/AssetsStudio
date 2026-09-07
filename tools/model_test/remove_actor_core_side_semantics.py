#!/usr/bin/env python3
"""Refine the frozen right-profile Actor Core without regenerating its identity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


EXPECTED_SOURCE_SHA256 = "d96f3cabaabb69f06f8a3582f468d9057c495f61bff9d965118975e583b283f0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def polynomial_terms(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.stack(
        [
            np.ones_like(x),
            x,
            y,
            x * x,
            x * y,
            y * y,
            x * x * x,
            x * x * y,
            x * y * y,
            y * y * y,
        ],
        axis=-1,
    )


def foreground_component(image: np.ndarray) -> np.ndarray:
    saturation = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
    mask = (saturation > 35).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count < 2:
        raise RuntimeError("Unable to isolate actor")
    component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == component


def fit_head_skin(source: np.ndarray, excluded: np.ndarray) -> np.ndarray:
    height, width = source.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    xn = (xx.astype(np.float64) - 390.0) / 190.0
    yn = (yy.astype(np.float64) - 255.0) / 190.0
    terms = polynomial_terms(xn, yn)
    head_roi = np.zeros((height, width), dtype=np.uint8)
    cv2.ellipse(head_roi, (390, 255), (170, 178), 0, 0, 360, 255, -1)
    hsv = cv2.cvtColor(source, cv2.COLOR_BGR2HSV)
    skin = (
        (hsv[:, :, 0] <= 25)
        & (hsv[:, :, 1] > 25)
        & (hsv[:, :, 2] > 145)
    )
    samples = (head_roi > 0) & (excluded == 0) & skin
    design = terms[samples]
    if design.shape[0] < 1000:
        raise RuntimeError("Insufficient clean head samples")
    fitted = np.empty_like(source, dtype=np.float64)
    for channel in range(3):
        coefficients, *_ = np.linalg.lstsq(
            design, source[:, :, channel][samples].astype(np.float64), rcond=None
        )
        fitted[:, :, channel] = terms @ coefficients
    return np.clip(fitted, 0, 255).astype(np.uint8)


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
            design[valid], row[valid, channel].astype(np.float64), rcond=None
        )
        fitted[:, channel] = design @ coefficients
    return np.clip(fitted, 0, 255).astype(np.uint8)


def remove_inner_ear(source: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    height, width = source.shape[:2]
    ear = np.zeros((height, width), dtype=np.uint8)
    cv2.ellipse(ear, (399, 326), (47, 64), 0, 0, 360, 255, -1)
    excluded = cv2.dilate(ear, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    fitted = fit_head_skin(source, excluded)
    output = cv2.seamlessClone(fitted, source, ear, (399, 326), cv2.NORMAL_CLONE)
    x, y, box_width, box_height = cv2.boundingRect(ear)
    effective = np.zeros_like(ear)
    effective[y : y + box_height, x : x + box_width] = 255
    return output, effective


def remove_eye_and_eyebrow(source: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    height, width = source.shape[:2]
    subject = foreground_component(source)
    feature = np.zeros((height, width), dtype=np.uint8)
    cv2.ellipse(feature, (260, 315), (49, 78), 0, 0, 360, 255, -1)
    cv2.ellipse(feature, (252, 260), (42, 24), 0, 0, 360, 255, -1)
    excluded = cv2.dilate(
        feature, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    )
    fitted_skin = fit_head_skin(source, excluded)
    plate = source.copy()
    y_values = np.flatnonzero(np.any(feature > 0, axis=1))
    for y in y_values:
        xs = np.flatnonzero(subject[y])
        if not xs.size:
            continue
        left = int(xs[0])
        right = int(xs[-1])
        feature_x = np.flatnonzero(feature[y])
        if not feature_x.size:
            continue
        start = int(feature_x[0])
        end = int(feature_x[-1]) + 1
        background = fit_background_row(source[y], subject[y], left, right)
        split = min(max(left, start), end)
        plate[y, start:split] = background[start:split]
        plate[y, split:end] = fitted_skin[y, split:end]

    output = cv2.seamlessClone(plate, source, feature, (260, 315), cv2.NORMAL_CLONE)
    x, y, box_width, box_height = cv2.boundingRect(feature)
    effective = np.zeros_like(feature)
    effective[y : y + box_height, x : x + box_width] = 255
    return output, effective


def reduce_belly(source: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    subject = foreground_component(source)
    remove = np.zeros(subject.shape, dtype=np.uint8)
    plate = source.copy()
    control_y = np.asarray([438, 460, 480, 500, 520, 540, 555, 570, 590, 610])
    control_x = np.asarray([348, 343, 338, 334, 331, 329, 329, 331, 337, 346])
    rows: list[dict] = []
    for y in range(int(control_y[0]), int(control_y[-1]) + 1):
        xs = np.flatnonzero(subject[y])
        if not xs.size:
            continue
        current_left = int(xs[0])
        current_right = int(xs[-1])
        target_left = max(current_left, int(round(np.interp(y, control_y, control_x))))
        if target_left <= current_left:
            continue
        remove[y, max(0, current_left - 12) : target_left] = 255
        background = fit_background_row(source[y], subject[y], current_left, current_right)
        plate[y, max(0, current_left - 12) : target_left] = background[
            max(0, current_left - 12) : target_left
        ]
        rows.append(
            {"y": y, "source_left": current_left, "target_left": target_left}
        )
    alpha = cv2.GaussianBlur(remove, (0, 0), 0.8).astype(np.float32)[:, :, None] / 255.0
    output = np.clip(plate * alpha + source * (1.0 - alpha), 0, 255).astype(np.uint8)
    for item in rows:
        y = item["y"]
        start = max(0, item["source_left"] - 12)
        target = item["target_left"]
        background = fit_background_row(source[y], subject[y], item["source_left"], int(np.flatnonzero(subject[y])[-1]))
        output[y, start : max(start, target - 1)] = background[start : max(start, target - 1)]
        if target - 1 >= start:
            output[y, target - 1] = np.clip(
                background[target - 1].astype(np.float64) * 0.72
                + source[y, target - 1].astype(np.float64) * 0.28,
                0,
                255,
            ).astype(np.uint8)
    effective = (alpha[:, :, 0] > (1.0 / 255.0)).astype(np.uint8) * 255
    return output, effective, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mask-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    source_hash = sha256(args.source)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"Source is not frozen right seed 1005: {source_hash}")
    source = cv2.imread(str(args.source), cv2.IMREAD_COLOR)
    if source is None:
        raise FileNotFoundError(args.source)

    earless, ear_mask = remove_inner_ear(source)
    blank, face_mask = remove_eye_and_eyebrow(earless)
    output, belly_mask, belly_rows = reduce_belly(blank)
    edit_mask = cv2.max(cv2.max(ear_mask, face_mask), belly_mask)
    difference = np.abs(output.astype(np.int16) - source.astype(np.int16))
    outside = edit_mask == 0

    for path, image in ((args.output, output), (args.mask_output, edit_mask)):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"Unable to write {path}")

    report = {
        "schema": "assetsstudio_actor_core_side_refinement_v2",
        "status": "human_review_required",
        "source": str(args.source),
        "source_sha256": source_hash,
        "output": str(args.output),
        "output_sha256": sha256(args.output),
        "edit_mask": str(args.mask_output),
        "outside_edit_mask_rgb_mae_0_255": round(float(difference[outside].mean()), 6),
        "belly_boundary_summary": {
            "row_count": len(belly_rows),
            "y_range": [belly_rows[0]["y"], belly_rows[-1]["y"]],
            "max_inward_shift_px": max(
                item["target_left"] - item["source_left"] for item in belly_rows
            ),
        },
        "invariants": [
            "head crown, back cranium, shallow nose contour and jaw bottom unchanged",
            "eye, eyebrow and inner ear semantics removed",
            "belly front edge reduced without changing the back, pelvis or legs",
            "arm and hand projection unchanged for this isolated review",
            "pose, ground line, lighting and total height unchanged",
            "no diffusion or remote model used",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
