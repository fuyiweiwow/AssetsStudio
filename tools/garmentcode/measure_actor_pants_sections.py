"""Measure Actor waist, hips, and both thigh sections for GarmentCode Pants."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import ConvexHull


def perimeter(points: np.ndarray) -> float:
    hull = ConvexHull(points)
    ring = points[hull.vertices]
    return float(np.linalg.norm(np.roll(ring, -1, axis=0) - ring, axis=1).sum())


def section_loops(mesh: trimesh.Trimesh, y: float) -> list[dict[str, object]]:
    path = mesh.section(plane_origin=[0.0, y, 0.0], plane_normal=[0.0, 1.0, 0.0])
    if path is None:
        return []
    planar, transform = path.to_2D()
    loops = []
    for discrete in planar.discrete:
        points = np.asarray(discrete, dtype=float)
        if len(points) < 4:
            continue
        if np.linalg.norm(points[0] - points[-1]) < 1e-6:
            points = points[:-1]
        if len(points) < 3:
            continue
        homogeneous = np.column_stack([points, np.zeros(len(points)), np.ones(len(points))])
        world = (transform @ homogeneous.T).T[:, :3]
        loops.append({
            "centroid_gc_m": world.mean(axis=0).tolist(),
            "perimeter_cm": perimeter(points) * 100.0,
            "bounds_gc_m": [world.min(axis=0).tolist(), world.max(axis=0).tolist()],
            "point_count": len(points),
        })
    return loops


def choose_center(loops: list[dict[str, object]]) -> dict[str, object]:
    if not loops:
        raise RuntimeError("no closed section loop")
    compatible = [row for row in loops if abs(row["centroid_gc_m"][0]) < 0.12]
    return max(compatible or loops, key=lambda row: row["perimeter_cm"])


def choose_side(loops: list[dict[str, object]], target_x: float) -> dict[str, object]:
    if not loops:
        raise RuntimeError("no thigh section loop")
    same_side = [row for row in loops if row["centroid_gc_m"][0] * target_x > 0]
    return min(same_side or loops, key=lambda row: abs(row["centroid_gc_m"][0] - target_x))


def optimized(mesh, initial_y, chooser, mode, radius=0.02, step=0.005):
    candidates = []
    offset = -radius
    while offset <= radius + 1e-9:
        loops = section_loops(mesh, initial_y + offset)
        if loops:
            selected = chooser(loops)
            candidates.append({"y_m": initial_y + offset, "offset_m": offset, **selected})
        offset += step
    if not candidates:
        raise RuntimeError(f"no valid section near y={initial_y}")
    return (max if mode == "MAX" else min)(candidates, key=lambda row: row["perimeter_cm"]), candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", required=True, type=Path)
    parser.add_argument("--landmarks", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    mesh = trimesh.load_mesh(args.mesh.resolve(), process=False)
    if not isinstance(mesh, trimesh.Trimesh) or mesh.is_empty:
        raise RuntimeError("Actor source must be one non-empty mesh")
    landmarks = json.loads(args.landmarks.read_text(encoding="utf-8"))
    points = landmarks["landmarks_gc_m"]

    waist, waist_candidates = optimized(mesh, points["waist"][1], choose_center, "MIN")
    hips, hips_candidates = optimized(mesh, points["hips"][1], choose_center, "MAX")
    left_x, left_y = points["left_thigh_section"][0:2]
    right_x, right_y = points["right_thigh_section"][0:2]
    left, left_candidates = optimized(mesh, left_y, lambda loops: choose_side(loops, left_x), "MAX", 0.015)
    right, right_candidates = optimized(mesh, right_y, lambda loops: choose_side(loops, right_x), "MAX", 0.015)
    payload = {
        "schema": "assetsstudio_actor_complete_pants_measurements_v1",
        "source_actor": landmarks["source_actor"],
        "source_mesh": str(args.mesh.resolve()),
        "landmarks_source": str(args.landmarks.resolve()),
        "pose": "REST",
        "units": "centimetres",
        "body": {
            "waist": waist,
            "hips": hips,
            "left_thigh": left,
            "right_thigh": right,
            "leg_circ": max(left["perimeter_cm"], right["perimeter_cm"]),
        },
        "landmarks_gc_m": points,
        "candidates": {
            "waist": waist_candidates,
            "hips": hips_candidates,
            "left_thigh": left_candidates,
            "right_thigh": right_candidates,
        },
        "measurement_policy": "Actor REST horizontal sections; centered waist/hips and side-specific thighs",
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
