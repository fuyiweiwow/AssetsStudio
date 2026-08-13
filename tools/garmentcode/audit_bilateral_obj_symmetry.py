"""Measure bilateral X-axis symmetry of an OBJ vertex cloud."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


def read_vertices(path: Path) -> np.ndarray:
    vertices = []
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if line.startswith("v "):
                values = line.split()
                vertices.append([float(values[1]), float(values[2]), float(values[3])])
    if not vertices:
        raise RuntimeError(f"OBJ has no vertices: {path}")
    return np.asarray(vertices, dtype=np.float64)


def distance_summary(distances: np.ndarray) -> dict[str, float | int]:
    return {
        "count": int(len(distances)),
        "median_cm": float(np.median(distances)),
        "p95_cm": float(np.percentile(distances, 95)),
        "max_cm": float(np.max(distances)),
        "over_0p01_cm": int(np.count_nonzero(distances > 0.01)),
        "over_0p1_cm": int(np.count_nonzero(distances > 0.1)),
        "over_1cm": int(np.count_nonzero(distances > 1.0)),
    }


def worst_matches(
    source: np.ndarray,
    mirrored_source: np.ndarray,
    target: np.ndarray,
    distances: np.ndarray,
    target_indices: np.ndarray,
) -> list[dict]:
    result = []
    for index in np.argsort(distances)[::-1][:20]:
        result.append({
            "source_vertex_in_side": int(index),
            "source_point_cm": [float(value) for value in source[index]],
            "mirrored_point_cm": [float(value) for value in mirrored_source[index]],
            "nearest_opposite_point_cm": [
                float(value) for value in target[int(target_indices[index])]
            ],
            "distance_cm": float(distances[index]),
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--obj", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--center-epsilon-cm", type=float, default=1.0e-5)
    parser.add_argument(
        "--input-units",
        choices=("centimetres", "metres"),
        default="centimetres",
    )
    options = parser.parse_args()

    obj = options.obj.resolve()
    points = read_vertices(obj)
    if options.input_units == "metres":
        points *= 100.0
    positive = points[points[:, 0] > options.center_epsilon_cm]
    negative = points[points[:, 0] < -options.center_epsilon_cm]
    center = points[np.abs(points[:, 0]) <= options.center_epsilon_cm]
    if not len(positive) or not len(negative):
        raise RuntimeError("OBJ must contain vertices on both sides of X=0")

    mirrored_negative = negative.copy()
    mirrored_negative[:, 0] *= -1.0
    mirrored_positive = positive.copy()
    mirrored_positive[:, 0] *= -1.0
    negative_to_positive, negative_target_indices = cKDTree(positive).query(
        mirrored_negative, k=1
    )
    positive_to_negative, positive_target_indices = cKDTree(negative).query(
        mirrored_positive, k=1
    )

    payload = {
        "schema": "assetsstudio_bilateral_obj_symmetry_v1",
        "obj": str(obj),
        "input_units": options.input_units,
        "reported_units": "centimetres",
        "vertex_count": int(len(points)),
        "positive_x_vertices": int(len(positive)),
        "negative_x_vertices": int(len(negative)),
        "center_vertices": int(len(center)),
        "bounds_cm": [
            [float(value) for value in points.min(axis=0)],
            [float(value) for value in points.max(axis=0)],
        ],
        "negative_mirrored_to_positive": distance_summary(negative_to_positive),
        "positive_mirrored_to_negative": distance_summary(positive_to_negative),
        "worst_negative_mirrored_to_positive": worst_matches(
            negative,
            mirrored_negative,
            positive,
            negative_to_positive,
            negative_target_indices,
        ),
        "worst_positive_mirrored_to_negative": worst_matches(
            positive,
            mirrored_positive,
            negative,
            positive_to_negative,
            positive_target_indices,
        ),
    }
    if options.output:
        output = options.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
