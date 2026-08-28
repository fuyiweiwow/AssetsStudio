#!/usr/bin/env python3
"""Measure Actor Core torso taper and ankle/foot continuity.

The measurements are deliberately local to the body regions that previously
escaped the generic turnaround checks.  They are approval gates, not a target
generator and not a replacement for human review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from analyze_turnaround_sheet import foreground_mask


LOWER_TORSO_WIDTH_LIMIT = 0.54
FOOT_DETECTION_MINIMUM = 0.80
FOOT_PROJECTION_LIMIT = 1.20


def panel_geometry(panel: np.ndarray) -> tuple[int, int, int, int, np.ndarray]:
    high_confidence = foreground_mask(panel)
    points = cv2.findNonZero(high_confidence)
    if points is None:
        raise RuntimeError("No Actor Core foreground detected")
    x, y, width, height = cv2.boundingRect(points)

    lab = cv2.cvtColor(panel, cv2.COLOR_BGR2LAB).astype(np.float32)
    side_width = max(8, panel.shape[1] // 12)
    background = np.median(
        np.concatenate([lab[:, :side_width], lab[:, -side_width:]], axis=1),
        axis=1,
    )
    distance = np.linalg.norm(lab - background[:, None, :], axis=2)
    return x, y, width, height, distance


def row_runs(
    distance: np.ndarray,
    row: int,
    x: int,
    width: int,
    *,
    threshold: float = 4.0,
) -> list[tuple[int, int, int]]:
    occupied = (distance[row, x : x + width] > threshold).astype(np.uint8) * 255
    occupied = cv2.morphologyEx(
        occupied[None, :],
        cv2.MORPH_CLOSE,
        np.ones((1, 9), dtype=np.uint8),
    )[0] > 0
    changes = np.diff(np.r_[False, occupied, False].astype(np.int8))
    starts = np.flatnonzero(changes == 1)
    ends = np.flatnonzero(changes == -1)
    minimum_width = width * 0.04
    return [
        (int(left), int(right), int(right - left))
        for left, right in zip(starts, ends)
        if right - left >= minimum_width
    ]


def largest_run_ratios(
    distance: np.ndarray,
    x: int,
    y: int,
    width: int,
    height: int,
    start_ratio: float,
    end_ratio: float,
) -> list[float]:
    start = y + round(start_ratio * height)
    end = y + round(end_ratio * height)
    values: list[float] = []
    for row in range(start, max(start + 1, end)):
        runs = row_runs(distance, row, x, width)
        if runs:
            values.append(max(item[2] for item in runs) / width)
    return values


def front_lower_torso_width(
    panel: np.ndarray,
) -> tuple[float | None, int, int]:
    x, y, width, height, distance = panel_geometry(panel)
    values: list[float] = []
    sampled_rows = 0
    for row in range(y + round(0.64 * height), y + round(0.72 * height)):
        sampled_rows += 1
        runs = row_runs(distance, row, x, width)
        if not runs:
            continue
        center = width / 2
        central = min(runs, key=lambda item: abs((item[0] + item[1]) / 2 - center))
        if abs((central[0] + central[1]) / 2 - center) > width * 0.12:
            continue
        has_left_arm = any(item[1] < central[0] for item in runs)
        has_right_arm = any(item[0] > central[1] for item in runs)
        if has_left_arm and has_right_arm:
            values.append(central[2] / width)
    if len(values) < max(5, round(sampled_rows * 0.35)):
        return None, len(values), sampled_rows
    return float(np.median(values)), len(values), sampled_rows


def side_foot_projection(panel: np.ndarray) -> tuple[float | None, float | None, float | None]:
    x, y, width, height, distance = panel_geometry(panel)
    shaft_values = largest_run_ratios(distance, x, y, width, height, 0.78, 0.84)
    foot_values = largest_run_ratios(distance, x, y, width, height, 0.94, 0.97)
    if not shaft_values or not foot_values:
        return None, None, None
    shaft_width = float(np.median(shaft_values))
    foot_width = float(np.median(foot_values))
    return foot_width / max(shaft_width, 1e-6), shaft_width, foot_width


def analyze_actor_core_shape(image_path: Path, panel_count: int = 3) -> dict:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Unable to read {image_path}")
    if panel_count != 3:
        raise ValueError("Actor Core shape gate requires front/right/back panels")
    edges = np.linspace(0, image.shape[1], panel_count + 1, dtype=int)
    front = image[:, edges[0] : edges[1]]
    right = image[:, edges[1] : edges[2]]

    torso_width, torso_rows, torso_sampled = front_lower_torso_width(front)
    foot_ratio, shaft_width, foot_width = side_foot_projection(right)
    foot_detection_ratio = (
        None
        if shaft_width is None or foot_width is None
        else foot_width / max(shaft_width, 1e-6)
    )
    metrics = {
        "front_lower_torso_width_ratio": (
            None if torso_width is None else round(torso_width, 4)
        ),
        "front_torso_valid_rows": torso_rows,
        "front_torso_sampled_rows": torso_sampled,
        "side_leg_shaft_width_ratio": (
            None if shaft_width is None else round(shaft_width, 4)
        ),
        "side_foot_width_ratio": None if foot_width is None else round(foot_width, 4),
        "side_foot_detection_ratio": (
            None if foot_detection_ratio is None else round(foot_detection_ratio, 4)
        ),
        "side_foot_projection_ratio": (
            None if foot_ratio is None else round(foot_ratio, 4)
        ),
    }
    gates = {
        "front_lower_torso_detected": torso_width is not None,
        "front_lower_torso_width_ratio_lte_0_54": (
            torso_width is not None and torso_width <= LOWER_TORSO_WIDTH_LIMIT
        ),
        "side_foot_detected_relative_to_shaft": (
            foot_detection_ratio is not None
            and foot_detection_ratio >= FOOT_DETECTION_MINIMUM
        ),
        "side_foot_projection_ratio_lte_1_20": (
            foot_ratio is not None
            and foot_ratio <= FOOT_PROJECTION_LIMIT + 1e-9
        ),
    }
    return {
        "schema": "assetsstudio_actor_core_shape_qa_v1",
        "image": str(image_path.resolve()),
        "method": "row_adaptive_lab_body_regions_v1",
        "thresholds": {
            "front_lower_torso_width_ratio_max": LOWER_TORSO_WIDTH_LIMIT,
            "side_foot_detection_ratio_min": FOOT_DETECTION_MINIMUM,
            "side_foot_projection_ratio_max": FOOT_PROJECTION_LIMIT,
        },
        "metrics": metrics,
        "automatic_gates": gates,
        "automatic_pass": all(gates.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze_actor_core_shape(args.image)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if report["automatic_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
