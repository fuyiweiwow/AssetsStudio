#!/usr/bin/env python3
"""Measure preservation gates for the front-view Actor Core A -> B edit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from analyze_turnaround_sheet import central_component


def actor_foreground(image: np.ndarray) -> np.ndarray:
    """Separate the colored figure from the low-saturation gray studio sweep."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturated = (hsv[:, :, 1] > 12).astype(np.uint8) * 255
    saturated = cv2.morphologyEx(
        saturated,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
        iterations=2,
    )
    component = central_component(saturated)
    contours, _ = cv2.findContours(
        component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return component
    silhouette = np.zeros_like(component)
    cv2.drawContours(
        silhouette, [max(contours, key=cv2.contourArea)], -1, 255, thickness=-1
    )
    return silhouette


def bbox(mask: np.ndarray) -> list[int]:
    points = cv2.findNonZero(mask)
    if points is None:
        raise RuntimeError("No foreground was detected")
    x, y, width, height = cv2.boundingRect(points)
    return [int(x), int(y), int(x + width), int(y + height)]


def iou(left: np.ndarray, right: np.ndarray) -> float:
    a = left > 0
    b = right > 0
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 1.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", type=Path, required=True)
    parser.add_argument("--b", type=Path, required=True)
    parser.add_argument("--edit-mask", type=Path, required=True)
    parser.add_argument("--edit-margin", type=int, default=15)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview-output", type=Path)
    parser.add_argument("--a-prompt", type=Path)
    parser.add_argument("--b-prompt", type=Path)
    args = parser.parse_args()

    a = cv2.imread(str(args.a), cv2.IMREAD_COLOR)
    b = cv2.imread(str(args.b), cv2.IMREAD_COLOR)
    edit = cv2.imread(str(args.edit_mask), cv2.IMREAD_GRAYSCALE)
    if a is None or b is None or edit is None:
        raise RuntimeError("Unable to read one or more input images")
    if a.shape != b.shape or a.shape[:2] != edit.shape:
        raise ValueError(f"Input dimensions differ: A={a.shape}, B={b.shape}, mask={edit.shape}")

    a_silhouette = actor_foreground(a)
    b_silhouette = actor_foreground(b)
    a_bbox = bbox(a_silhouette)
    b_bbox = bbox(b_silhouette)
    height, width = edit.shape
    bbox_drift = [
        abs(a_bbox[0] - b_bbox[0]) / width,
        abs(a_bbox[1] - b_bbox[1]) / height,
        abs(a_bbox[2] - b_bbox[2]) / width,
        abs(a_bbox[3] - b_bbox[3]) / height,
    ]

    kernel_size = max(1, args.edit_margin * 2 + 1)
    effective_edit = cv2.dilate(
        (edit > 0).astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)),
    ) > 0
    human = np.logical_or(a_silhouette > 0, b_silhouette > 0)
    outside_human = np.logical_and(human, np.logical_not(effective_edit))
    difference = np.abs(a.astype(np.int16) - b.astype(np.int16))
    outside_values = difference[outside_human]
    outside_mae = float(outside_values.mean()) if outside_values.size else 0.0
    changed = np.max(difference, axis=2) > 8
    changed_ratio = (
        float(changed[outside_human].mean()) if outside_human.any() else 0.0
    )

    head_bottom = min(a_bbox[3], max(a_bbox[1] + 1, int(round(height * 0.46))))
    a_head = np.zeros_like(a_silhouette)
    b_head = np.zeros_like(b_silhouette)
    a_head[a_bbox[1] : head_bottom] = a_silhouette[a_bbox[1] : head_bottom]
    b_head[a_bbox[1] : head_bottom] = b_silhouette[a_bbox[1] : head_bottom]

    metrics = {
        "silhouette_iou": round(iou(a_silhouette, b_silhouette), 6),
        "head_silhouette_iou": round(iou(a_head, b_head), 6),
        "a_bbox_xyxy": a_bbox,
        "b_bbox_xyxy": b_bbox,
        "bbox_edge_drift_ratios": [round(value, 6) for value in bbox_drift],
        "bbox_max_drift_ratio": round(max(bbox_drift), 6),
        "outside_edit_human_rgb_mae_0_255": round(outside_mae, 6),
        "outside_edit_human_changed_pixel_ratio_gt_8": round(changed_ratio, 6),
        "outside_edit_human_pixel_count": int(outside_human.sum()),
        "effective_edit_margin_px": args.edit_margin,
    }
    gates = {
        "silhouette_iou_gte_0_98": metrics["silhouette_iou"] >= 0.98,
        "bbox_max_drift_lte_0_005": metrics["bbox_max_drift_ratio"] <= 0.005,
        "outside_edit_human_rgb_mae_lte_3": outside_mae <= 3.0,
        "outside_edit_human_changed_ratio_lte_0_05": changed_ratio <= 0.05,
    }
    report = {
        "schema": "assetsstudio_actor_core_front_ab_audit_v1",
        "a": str(args.a),
        "a_sha256": sha256(args.a),
        "b": str(args.b),
        "b_sha256": sha256(args.b),
        "edit_mask": str(args.edit_mask),
        "edit_mask_sha256": sha256(args.edit_mask),
        "prompts": {
            "a": str(args.a_prompt) if args.a_prompt else None,
            "b": str(args.b_prompt) if args.b_prompt else None,
        },
        "metrics": metrics,
        "automatic_gates": gates,
        "automatic_pass": all(gates.values()),
        "human_review_required": True,
        "human_checks": [
            "A keeps only eyes and eyebrows as temporary facial features",
            "B has no eyes, eyebrows, sockets, ghost lines, nose or mouth",
            "head remains broad and directional rather than spherical or flat",
            "torso and limbs read compact enough for the intended game style",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if args.preview_output:
        display_size = (512, 512)
        a_display = cv2.resize(a, display_size, interpolation=cv2.INTER_AREA)
        b_display = cv2.resize(b, display_size, interpolation=cv2.INTER_AREA)
        changed_display = cv2.resize(
            changed.astype(np.uint8), display_size, interpolation=cv2.INTER_NEAREST
        ) > 0
        diff_display = cv2.cvtColor(
            cv2.resize(a, display_size, interpolation=cv2.INTER_AREA),
            cv2.COLOR_BGR2GRAY,
        )
        diff_display = cv2.cvtColor(diff_display, cv2.COLOR_GRAY2BGR)
        diff_display[changed_display] = (45, 45, 230)
        for panel, label in ((a_display, "A: eyes + brows"), (b_display, "B: blank face"), (diff_display, "changed pixels")):
            cv2.rectangle(panel, (0, 0), (511, 42), (35, 35, 35), -1)
            cv2.putText(
                panel, label, (15, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (245, 245, 245), 2, cv2.LINE_AA,
            )
        preview = np.concatenate([a_display, b_display, diff_display], axis=1)
        args.preview_output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.preview_output), preview):
            raise RuntimeError(f"Unable to write preview {args.preview_output}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["automatic_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
