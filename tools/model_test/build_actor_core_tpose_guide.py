#!/usr/bin/env python3
"""Build a T-pose guide by rotating the frozen A93 actor's own arm pixels.

The guide preserves the approved head, torso and legs.  It is diagnostic pose
evidence only: the local image model must redraw the shoulder transitions and
the guide must never be registered as an asset or training target.
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


def actor_mask(image: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] > 12) & (hsv[:, :, 2] > 120)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count < 2:
        raise RuntimeError("Unable to isolate actor")
    component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == component).astype(np.uint8) * 255


def polygon_mask(shape: tuple[int, int], points: list[tuple[int, int]]) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.fillPoly(mask, [np.asarray(points, dtype=np.int32)], 255, cv2.LINE_AA)
    return mask


def background_plate(source: np.ndarray, actor: np.ndarray) -> np.ndarray:
    """Fit the smooth studio sweep per row without using actor pixels."""
    height, width = actor.shape
    x = np.arange(width, dtype=np.float64)
    xn = x / (width - 1) * 2.0 - 1.0
    terms = np.stack([np.ones_like(xn), xn, xn * xn], axis=1)
    plate = np.empty_like(source)
    for y in range(height):
        valid = actor[y] == 0
        if int(valid.sum()) < 16:
            plate[y] = source[y]
            continue
        for channel in range(3):
            coefficients, *_ = np.linalg.lstsq(
                terms[valid], source[y, valid, channel].astype(np.float64), rcond=None
            )
            plate[y, :, channel] = np.clip(terms @ coefficients, 0, 255).astype(np.uint8)
    return plate


def rotate_layer(
    source: np.ndarray,
    mask: np.ndarray,
    pivot: tuple[int, int],
    angle: float,
) -> tuple[np.ndarray, np.ndarray]:
    matrix = cv2.getRotationMatrix2D(pivot, angle, 1.0)
    image = cv2.warpAffine(
        source,
        matrix,
        (source.shape[1], source.shape[0]),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    alpha = cv2.warpAffine(
        mask,
        matrix,
        (source.shape[1], source.shape[0]),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return image, alpha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mask-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    source = cv2.imread(str(args.source), cv2.IMREAD_COLOR)
    if source is None:
        raise FileNotFoundError(args.source)
    if source.shape[:2] != (768, 768):
        raise ValueError(f"Expected 768x768, got {source.shape[1]}x{source.shape[0]}")

    actor = actor_mask(source)
    left_region = polygon_mask(
        actor.shape,
        [(294, 444), (333, 448), (321, 489), (299, 532), (282, 590),
         (272, 612), (252, 614), (240, 596), (244, 565), (263, 514)],
    )
    right_region = polygon_mask(
        actor.shape,
        [(435, 448), (474, 444), (505, 514), (524, 565), (528, 596),
         (516, 614), (496, 612), (486, 590), (469, 532), (447, 489)],
    )
    left = cv2.bitwise_and(actor, left_region)
    right = cv2.bitwise_and(actor, right_region)
    # Erase the complete reviewed polygons, not merely the saturation mask, so
    # low-saturation antialiased edges from the relaxed arms cannot ghost into
    # the pose guide.
    original_arms = cv2.dilate(
        cv2.bitwise_or(left_region, right_region),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )

    plate = background_plate(source, actor)
    erase_alpha = cv2.GaussianBlur(original_arms, (0, 0), 1.0).astype(np.float32)[:, :, None] / 255.0
    guide = np.clip(plate * erase_alpha + source * (1.0 - erase_alpha), 0, 255).astype(np.uint8)

    transforms = [
        (left, (318, 458), -63.0),
        (right, (450, 458), 63.0),
    ]
    posed_mask = np.zeros(actor.shape, dtype=np.uint8)
    for arm_mask, pivot, angle in transforms:
        rotated, alpha_u8 = rotate_layer(source, arm_mask, pivot, angle)
        alpha = (alpha_u8.astype(np.float32) / 255.0)[:, :, None]
        guide = np.clip(rotated * alpha + guide * (1.0 - alpha), 0, 255).astype(np.uint8)
        posed_mask = cv2.max(posed_mask, alpha_u8)

    total_mask = cv2.max(original_arms, posed_mask)
    for path, image in ((args.output, guide), (args.mask_output, total_mask)):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"Unable to write {path}")
    report = {
        "schema": "assetsstudio_actor_core_tpose_guide_v1",
        "status": "diagnostic_pose_guide_only",
        "source": str(args.source),
        "source_sha256": sha256(args.source),
        "output": str(args.output),
        "output_sha256": sha256(args.output),
        "pivots_xy": {"left": [318, 458], "right": [450, 458]},
        "rotations_degrees": {"left": -63.0, "right": 63.0},
        "restrictions": [
            "source pixels define limb length and thickness",
            "guide defines pose only",
            "not an asset candidate",
            "not a training target",
            "local model redraw and human review required",
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
