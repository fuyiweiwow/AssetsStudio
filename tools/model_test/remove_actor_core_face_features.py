#!/usr/bin/env python3
"""Remove eyes and brows from the frozen Actor Core A image.

The edit fits a low-frequency skin surface from the source image and blends it
inside a declared face region.  It never invokes a diffusion model, rescales
the actor, or changes pixels outside the published effective edit mask.
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


def build_mask() -> np.ndarray:
    mask = np.zeros((768, 768), dtype=np.uint8)
    # Brows, then eyes including lashes and sclera.  These coordinates are
    # frozen against a93_earless_candidate_v5.png.
    regions = [
        ((267, 244), (352, 291)),
        ((424, 244), (512, 291)),
        ((248, 279), (367, 382)),
        ((405, 279), (528, 382)),
    ]
    for top_left, bottom_right in regions:
        center = (
            (top_left[0] + bottom_right[0]) // 2,
            (top_left[1] + bottom_right[1]) // 2,
        )
        axes = (
            (bottom_right[0] - top_left[0]) // 2,
            (bottom_right[1] - top_left[1]) // 2,
        )
        cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1, cv2.LINE_AA)
    mask = cv2.dilate(
        mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
        iterations=1,
    )
    return mask


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


def reconstruct_blank_face(
    source: np.ndarray,
    feature_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    height, width = source.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    xn = (xx.astype(np.float64) - 384.0) / 180.0
    yn = (yy.astype(np.float64) - 315.0) / 150.0
    terms = polynomial_terms(xn, yn)

    face_roi = np.zeros((height, width), dtype=np.uint8)
    cv2.ellipse(face_roi, (384, 315), (172, 132), 0, 0, 360, 255, -1)
    excluded = cv2.dilate(
        feature_mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)),
        iterations=1,
    )
    hsv = cv2.cvtColor(source, cv2.COLOR_BGR2HSV)
    skin_like = (hsv[:, :, 1] > 30) & (hsv[:, :, 2] > 145)
    samples = (face_roi > 0) & (excluded == 0) & skin_like
    design = terms[samples]
    fitted = np.empty_like(source, dtype=np.float64)
    for channel in range(3):
        coefficients, *_ = np.linalg.lstsq(
            design,
            source[:, :, channel][samples].astype(np.float64),
            rcond=None,
        )
        fitted[:, :, channel] = terms @ coefficients
    fitted = np.clip(fitted, 0, 255).astype(np.uint8)

    poisson_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.ellipse(poisson_mask, (384, 316), (151, 105), 0, 0, 360, 255, -1)
    poisson = cv2.seamlessClone(
        fitted,
        source,
        poisson_mask,
        (384, 316),
        cv2.NORMAL_CLONE,
    )
    # OpenCV's Poisson solver can update pixels throughout the mask bounding
    # rectangle, including pixels outside the non-zero ellipse.  Publish that
    # complete deterministic rectangle as the effective edit mask so audits do
    # not incorrectly claim preservation in pixels the solver may touch.
    x, y, width, height = cv2.boundingRect(poisson_mask)
    poisson_effective_mask = np.zeros_like(poisson_mask)
    poisson_effective_mask[y : y + height, x : x + width] = 255
    return poisson, poisson_effective_mask


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mask-output", type=Path, required=True)
    parser.add_argument("--feature-mask-output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    source = cv2.imread(str(args.source))
    if source is None:
        raise FileNotFoundError(args.source)
    if source.shape[:2] != (768, 768):
        raise ValueError(f"Expected 768x768, got {source.shape[1]}x{source.shape[0]}")

    mask = build_mask()
    output, edit_mask = reconstruct_blank_face(source, mask)

    for path, image in (
        (args.output, output),
        (args.mask_output, edit_mask),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"Failed to write {path}")
    if args.feature_mask_output:
        args.feature_mask_output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.feature_mask_output), mask):
            raise RuntimeError(f"Failed to write {args.feature_mask_output}")

    outside = edit_mask == 0
    difference = np.abs(output.astype(np.int16) - source.astype(np.int16))
    report = {
        "schema": "assetsstudio_actor_core_face_feature_removal_v1",
        "status": "human_review_required",
        "source": str(args.source),
        "source_sha256": sha256(args.source),
        "edit_mask": str(args.mask_output),
        "feature_mask": str(args.feature_mask_output) if args.feature_mask_output else None,
        "output": str(args.output),
        "output_sha256": sha256(args.output),
        "outside_edit_mask_rgb_mae": round(float(difference[outside].mean()), 6),
        "invariants": [
            "head silhouette and proportions unchanged",
            "body, pose, background and lighting outside the face edit mask unchanged",
            "no diffusion or remote model used for feature removal",
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
