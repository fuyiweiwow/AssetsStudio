#!/usr/bin/env python3
"""Measure basic consistency gates for a three-panel character turnaround."""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np


def foreground_mask(panel: np.ndarray) -> np.ndarray:
    height, width = panel.shape[:2]
    border = max(4, min(height, width) // 64)
    samples = np.concatenate(
        [
            panel[:border].reshape(-1, 3),
            panel[:, :border].reshape(-1, 3),
            panel[:, -border:].reshape(-1, 3),
        ]
    )
    background = np.median(samples, axis=0).astype(np.uint8)
    lab = cv2.cvtColor(panel, cv2.COLOR_BGR2LAB).astype(np.float32)
    bg_lab = cv2.cvtColor(background.reshape(1, 1, 3), cv2.COLOR_BGR2LAB).astype(
        np.float32
    )[0, 0]
    distance = np.linalg.norm(lab - bg_lab, axis=2)
    mask = (distance > 18).astype(np.uint8) * 255
    mask[:border] = 0
    mask[:, :border] = 0
    mask[:, -border:] = 0
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        return mask
    center_x = width / 2
    candidates: list[tuple[float, int]] = []
    for label in range(1, count):
        x, y, w, h, area = stats[label]
        if area < height * width * 0.002:
            continue
        component_center = x + w / 2
        score = area / (1 + abs(component_center - center_x) / width)
        candidates.append((score, label))
    if not candidates:
        return mask
    selected = max(candidates)[1]
    return (labels == selected).astype(np.uint8) * 255


def histogram(panel: np.ndarray, mask: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(panel, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], mask, [24, 16], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist


def normalized_front_width_profile(
    image_path: Path, panel_count: int
) -> np.ndarray:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Unable to read {image_path}")
    panel_width = image.shape[1] // panel_count
    panel = image[:, :panel_width]
    mask = foreground_mask(panel)
    points = cv2.findNonZero(mask)
    if points is None:
        raise RuntimeError(f"No foreground detected in proportion reference {image_path}")
    x, y, width, height = cv2.boundingRect(points)
    normalized = cv2.resize(
        mask[y : y + height, x : x + width],
        (256, 256),
        interpolation=cv2.INTER_NEAREST,
    )
    return (normalized > 0).mean(axis=1)


def infer_reference_panel_count(image_path: Path) -> int:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Unable to read {image_path}")
    height, width = image.shape[:2]
    return 3 if width / height >= 1.5 else 1


def analyze_turnaround(
    image_path: Path,
    panel_count: int = 3,
    proportion_reference: Path | None = None,
) -> dict:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Unable to read {image_path}")
    image_height, image_width = image.shape[:2]
    edges = np.linspace(0, image_width, panel_count + 1, dtype=int)
    panel_reports = []
    histograms = []

    for index in range(panel_count):
        panel = image[:, edges[index] : edges[index + 1]]
        mask = foreground_mask(panel)
        points = cv2.findNonZero(mask)
        if points is None:
            raise RuntimeError(f"No foreground detected in panel {index + 1}")
        x, y, width, height = cv2.boundingRect(points)
        panel_width = panel.shape[1]
        panel_reports.append(
            {
                "panel": index + 1,
                "bbox_px": [int(x), int(y), int(width), int(height)],
                "height_ratio": round(height / image_height, 4),
                "width_ratio": round(width / panel_width, 4),
                "center_x_ratio": round((x + width / 2) / panel_width, 4),
                "ground_y_ratio": round((y + height) / image_height, 4),
            }
        )
        histograms.append(histogram(panel, mask))

    height_values = np.array([p["height_ratio"] for p in panel_reports])
    ground_values = np.array([p["ground_y_ratio"] for p in panel_reports])
    center_values = np.array([p["center_x_ratio"] for p in panel_reports])
    pairwise = {}
    for left, right in combinations(range(panel_count), 2):
        key = f"{left + 1}-{right + 1}"
        pairwise[key] = round(
            float(cv2.compareHist(histograms[left], histograms[right], cv2.HISTCMP_CORREL)),
            4,
        )

    metrics = {
        "height_cv": round(float(height_values.std() / height_values.mean()), 4),
        "ground_range": round(float(ground_values.max() - ground_values.min()), 4),
        "center_max_offset": round(float(np.max(np.abs(center_values - 0.5))), 4),
        "minimum_color_histogram_correlation": min(pairwise.values()),
    }
    gates = {
        "panel_count_matches_expected": len(panel_reports) == panel_count,
        "height_cv_lte_0_05": metrics["height_cv"] <= 0.05,
        "ground_range_lte_0_03": metrics["ground_range"] <= 0.03,
        "center_offset_lte_0_09": metrics["center_max_offset"] <= 0.09,
        "color_histogram_correlation_gte_0_55": metrics[
            "minimum_color_histogram_correlation"
        ]
        >= 0.55,
    }
    proportion_comparison = None
    if proportion_reference is not None:
        reference_panels = infer_reference_panel_count(proportion_reference)
        candidate_profile = normalized_front_width_profile(image_path, panel_count)
        reference_profile = normalized_front_width_profile(
            proportion_reference, reference_panels
        )
        width_profile_mae = round(
            float(np.abs(candidate_profile - reference_profile).mean()), 4
        )
        proportion_comparison = {
            "reference": str(proportion_reference.resolve()),
            "reference_panel_count": reference_panels,
            "front_width_profile_mae": width_profile_mae,
            "method": "normalized_front_silhouette_row_width_v1",
        }
        metrics["front_width_profile_mae"] = width_profile_mae
        gates["front_width_profile_mae_lte_0_13"] = width_profile_mae <= 0.13
    return {
        "image": str(image_path.resolve()),
        "image_size": [image_width, image_height],
        "panels": panel_reports,
        "pairwise_color_histogram_correlation": pairwise,
        "metrics": metrics,
        "proportion_comparison": proportion_comparison,
        "automatic_gates": gates,
        "automatic_pass": all(gates.values()),
        "manual_gates_required": [
            "front/right-profile/back orientation",
            "same character and outfit construction",
            "no extra limbs, props, or perspective pose",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--panels", type=int, default=3)
    args = parser.parse_args()

    report = analyze_turnaround(args.image, args.panels)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
