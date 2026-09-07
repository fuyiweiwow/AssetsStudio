#!/usr/bin/env python3
"""Derive a pixel-space micro-adjustment guide from an approved direction.

This does not generate an Actor Core and is never an asset candidate.  It makes
small, reviewable proportion corrections explicit before FLUX redraws the
image: a slightly shorter head, shorter relaxed arms, and narrower lower legs.
Unlike the rejected primitive guide, every source pixel and silhouette region
comes from the selected model-generated direction itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


CANVAS = 768


def foreground_mask(image: np.ndarray) -> np.ndarray:
    saturation = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
    mask = (saturation > 35).astype(np.uint8) * 255
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        np.ones((7, 7), np.uint8),
        iterations=2,
    )
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count < 2:
        raise ValueError("Could not isolate the figure")
    component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == component).astype(np.uint8) * 255


def background_plate(image: np.ndarray, foreground: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    xn = xx.astype(np.float64) / (width - 1) * 2.0 - 1.0
    yn = yy.astype(np.float64) / (height - 1) * 2.0 - 1.0
    terms = np.stack(
        [np.ones_like(xn), xn, yn, xn * xn, yn * yn, xn * yn],
        axis=-1,
    )
    sample = (foreground == 0) & ((xx % 4) == 0) & ((yy % 4) == 0)
    design = terms[sample]
    plate = np.empty_like(image, dtype=np.float64)
    for channel in range(3):
        coefficients, *_ = np.linalg.lstsq(
            design,
            image[:, :, channel][sample].astype(np.float64),
            rcond=None,
        )
        plate[:, :, channel] = terms @ coefficients
    return np.clip(plate, 0, 255).astype(np.uint8)


def polygon_mask(points: list[tuple[int, int]], foreground: np.ndarray) -> np.ndarray:
    region = np.zeros_like(foreground)
    cv2.fillPoly(region, [np.array(points, dtype=np.int32)], 255)
    return cv2.bitwise_and(region, foreground)


def composite(base: np.ndarray, layer: np.ndarray, mask: np.ndarray, feather: float = 1.5) -> np.ndarray:
    alpha = cv2.GaussianBlur(mask, (0, 0), feather).astype(np.float32)[:, :, None] / 255.0
    return np.clip(layer * alpha + base * (1.0 - alpha), 0, 255).astype(np.uint8)


def erase(base: np.ndarray, plate: np.ndarray, mask: np.ndarray) -> np.ndarray:
    expanded = cv2.dilate(
        mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)),
        iterations=1,
    )
    return composite(base, plate, expanded, feather=2.0)


def warp_layer(image: np.ndarray, mask: np.ndarray, matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    size = (image.shape[1], image.shape[0])
    warped_image = cv2.warpAffine(
        image,
        matrix,
        size,
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    warped_mask = cv2.warpAffine(
        mask,
        matrix,
        size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return warped_image, warped_mask


def anchored_scale(center_x: float, anchor_y: float, scale_x: float, scale_y: float) -> np.ndarray:
    return np.array(
        [
            [scale_x, 0.0, (1.0 - scale_x) * center_x],
            [0.0, scale_y, (1.0 - scale_y) * anchor_y],
        ],
        dtype=np.float32,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--head-y-scale", type=float, default=0.96)
    parser.add_argument("--head-x-scale", type=float, default=0.985)
    parser.add_argument("--arm-scale", type=float, default=0.95)
    parser.add_argument("--lower-leg-x-scale", type=float, default=0.94)
    args = parser.parse_args()

    image = cv2.imread(str(args.source))
    if image is None:
        raise FileNotFoundError(args.source)
    if image.shape[:2] != (CANVAS, CANVAS):
        raise ValueError(f"Expected {CANVAS}x{CANVAS}, got {image.shape[1]}x{image.shape[0]}")

    foreground = foreground_mask(image)
    plate = background_plate(image, foreground)
    center_x = 384.0
    neck_y = 443.0

    head_region = np.zeros_like(foreground)
    head_region[: int(neck_y) + 1] = foreground[: int(neck_y) + 1]
    left_arm = polygon_mask(
        [(220, 438), (335, 438), (335, 515), (286, 628), (220, 628)],
        foreground,
    )
    right_arm = polygon_mask(
        [(433, 438), (548, 438), (548, 628), (482, 628), (433, 515)],
        foreground,
    )
    left_leg = polygon_mask([(286, 602), (386, 602), (386, 742), (276, 742)], foreground)
    right_leg = polygon_mask([(382, 602), (482, 602), (492, 742), (382, 742)], foreground)
    torso_restore = polygon_mask(
        [(310, 435), (458, 435), (472, 610), (296, 610)],
        foreground,
    )

    base = image.copy()
    for region in (head_region, left_arm, right_arm, left_leg, right_leg):
        base = erase(base, plate, region)

    layers = [
        (*warp_layer(image, left_arm, anchored_scale(324.0, 448.0, args.arm_scale, args.arm_scale)), "left_arm"),
        (*warp_layer(image, right_arm, anchored_scale(444.0, 448.0, args.arm_scale, args.arm_scale)), "right_arm"),
        (*warp_layer(image, left_leg, anchored_scale(342.0, 602.0, args.lower_leg_x_scale, 1.0)), "left_leg"),
        (*warp_layer(image, right_leg, anchored_scale(426.0, 602.0, args.lower_leg_x_scale, 1.0)), "right_leg"),
    ]
    for layer, mask, _ in layers:
        base = composite(base, layer, mask)
    base = composite(base, image, torso_restore, feather=1.0)
    head_layer, head_mask = warp_layer(
        image,
        head_region,
        anchored_scale(center_x, neck_y, args.head_x_scale, args.head_y_scale),
    )
    base = composite(base, head_layer, head_mask)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), base):
        raise RuntimeError(f"Failed to write {args.output}")

    report = {
        "schema": "assetsstudio_actor_core_micro_adjust_guide_v1",
        "status": "diagnostic_structure_guide_only",
        "source": str(args.source),
        "output": str(args.output),
        "adjustments": {
            "head_y_scale": args.head_y_scale,
            "head_x_scale": args.head_x_scale,
            "arm_scale_from_shoulder": args.arm_scale,
            "lower_leg_x_scale": args.lower_leg_x_scale,
        },
        "restrictions": [
            "not an asset candidate",
            "not a training target",
            "must be redrawn by the local image model",
            "human review remains required",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"output={args.output.resolve()}")
    print(f"report={args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
