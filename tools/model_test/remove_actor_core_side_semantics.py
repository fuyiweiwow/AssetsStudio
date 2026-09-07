#!/usr/bin/env python3
"""Remove ear and nose semantics from the frozen right-profile Actor Core A."""

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
            np.ones_like(x), x, y, x * x, x * y, y * y,
            x * x * x, x * x * y, x * y * y, y * y * y,
        ],
        axis=-1,
    )


def remove_inner_ear(source: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    height, width = source.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    xn = (xx.astype(np.float64) - 390.0) / 190.0
    yn = (yy.astype(np.float64) - 255.0) / 190.0
    terms = polynomial_terms(xn, yn)

    head_roi = np.zeros((height, width), dtype=np.uint8)
    cv2.ellipse(head_roi, (390, 255), (170, 178), 0, 0, 360, 255, -1)
    ear = np.zeros_like(head_roi)
    cv2.ellipse(ear, (399, 326), (47, 64), 0, 0, 360, 255, -1)
    excluded = cv2.dilate(ear, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    hsv = cv2.cvtColor(source, cv2.COLOR_BGR2HSV)
    skin = (hsv[:, :, 1] > 25) & (hsv[:, :, 2] > 145)
    samples = (head_roi > 0) & (excluded == 0) & skin
    design = terms[samples]
    fitted = np.empty_like(source, dtype=np.float64)
    for channel in range(3):
        coefficients, *_ = np.linalg.lstsq(
            design, source[:, :, channel][samples].astype(np.float64), rcond=None
        )
        fitted[:, :, channel] = terms @ coefficients
    fitted = np.clip(fitted, 0, 255).astype(np.uint8)

    output = cv2.seamlessClone(fitted, source, ear, (399, 326), cv2.NORMAL_CLONE)
    x, y, box_width, box_height = cv2.boundingRect(ear)
    effective = np.zeros_like(ear)
    effective[y : y + box_height, x : x + box_width] = 255
    return output, effective


def foreground_component(image: np.ndarray) -> np.ndarray:
    saturation = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
    mask = (saturation > 35).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count < 2:
        raise RuntimeError("Unable to isolate actor")
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
            design[valid], row[valid, channel].astype(np.float64), rcond=None
        )
        fitted[:, channel] = design @ coefficients
    return np.clip(fitted, 0, 255).astype(np.uint8)


def remove_profile_bump(source: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    subject = foreground_component(source)
    remove = np.zeros(subject.shape, dtype=np.uint8)
    plate = source.copy()
    control_y = np.asarray([338, 345, 355, 365, 375, 385, 395, 405, 415, 425])
    control_x = np.asarray([240, 238, 236, 236, 237, 238, 240, 244, 250, 260])
    rows = []
    for y in range(int(control_y[0]), int(control_y[-1]) + 1):
        xs = np.flatnonzero(subject[y])
        if not xs.size:
            continue
        current_left = int(xs[0])
        current_right = int(xs[-1])
        target_left = int(round(np.interp(y, control_y, control_x)))
        if target_left > current_left:
            remove[y, max(0, current_left - 14) : target_left] = 255
        plate[y] = fit_background_row(source[y], subject[y], current_left, current_right)
        sample_left = max(0, current_left - 44)
        sample_right = max(sample_left + 1, current_left - 20)
        local_background = np.median(
            source[y, sample_left:sample_right].astype(np.float64), axis=0
        )
        plate[y, max(0, current_left - 14) : target_left] = np.clip(
            local_background, 0, 255
        ).astype(np.uint8)
        rows.append(
            {
                "y": y,
                "source_left": current_left,
                "target_left": target_left,
                "background_bgr": local_background.tolist(),
            }
        )
    alpha = cv2.GaussianBlur(remove, (0, 0), 0.85).astype(np.float32)[:, :, None] / 255.0
    output = np.clip(plate * alpha + source * (1.0 - alpha), 0, 255).astype(np.uint8)
    # Feather only the former subject pixels. Restoring the already-approved
    # source background prevents a low-contrast halo outside the old profile.
    output[~subject] = source[~subject]
    for item in rows:
        y = item["y"]
        start = max(0, item["source_left"] - 16)
        target = item["target_left"]
        background = np.asarray(item["background_bgr"], dtype=np.float64)
        output[y, start : max(start, target - 1)] = np.clip(background, 0, 255).astype(np.uint8)
        if target - 1 >= start:
            output[y, target - 1] = np.clip(
                background * 0.7 + source[y, target - 1].astype(np.float64) * 0.3,
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
    output, profile_mask, rows = remove_profile_bump(earless)
    edit_mask = cv2.max(ear_mask, profile_mask)
    difference = np.abs(output.astype(np.int16) - source.astype(np.int16))
    outside = edit_mask == 0

    for path, image in ((args.output, output), (args.mask_output, edit_mask)):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"Unable to write {path}")

    report = {
        "schema": "assetsstudio_actor_core_side_semantic_removal_v1",
        "status": "human_review_required",
        "source": str(args.source),
        "source_sha256": source_hash,
        "output": str(args.output),
        "output_sha256": sha256(args.output),
        "edit_mask": str(args.mask_output),
        "outside_edit_mask_rgb_mae_0_255": round(float(difference[outside].mean()), 6),
        "profile_boundary_summary": {
            "row_count": len(rows),
            "y_range": [rows[0]["y"], rows[-1]["y"]],
            "source_left_range": [
                min(item["source_left"] for item in rows),
                max(item["source_left"] for item in rows),
            ],
            "target_left_range": [
                min(item["target_left"] for item in rows),
                max(item["target_left"] for item in rows),
            ],
        },
        "invariants": [
            "head crown, back cranium and jaw bottom unchanged",
            "visible eye and eyebrow unchanged",
            "body, pose, ground line and lighting unchanged",
            "no diffusion or remote model used",
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
