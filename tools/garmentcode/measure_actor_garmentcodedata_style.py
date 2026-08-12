"""Measure Actor sections using the GarmentCodeData/GarmentMeasurements rules.

The official project intersects the body mesh with a measurement plane,
optionally convexifies the resulting surface segments, and optimizes MAX/MIN
measurements over +/-2 cm in 5 mm steps.  This Python audit mirrors that
geometric rule for an evaluated Actor mesh and records every candidate rather
than silently replacing the existing body adapter.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import ConvexHull


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", required=True, type=Path)
    parser.add_argument("--landmarks", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--search-radius-m", type=float, default=0.02)
    parser.add_argument("--step-m", type=float, default=0.005)
    parser.add_argument("--max-center-distance-m", type=float, default=0.20)
    parser.add_argument("--continuity-ratio", type=float, default=0.10)
    return parser.parse_args()


def perimeter(points_2d: np.ndarray) -> float:
    if len(points_2d) < 3:
        return 0.0
    hull = ConvexHull(points_2d)
    ring = points_2d[hull.vertices]
    return float(np.linalg.norm(np.roll(ring, -1, axis=0) - ring, axis=1).sum())


def candidate(mesh: trimesh.Trimesh, y: float, max_center_distance_m: float) -> dict[str, object] | None:
    path = mesh.section(plane_origin=[0.0, y, 0.0], plane_normal=[0.0, 1.0, 0.0])
    if path is None:
        return None
    # The section is already represented in a 2D basis.  The basis choice is
    # immaterial to perimeter; use every discrete polyline and then select the
    # body-centered candidate. This mirrors the official face-candidate ring;
    # a global-largest-loop rule is unsafe for this Actor's hands and arms.
    planar, _ = path.to_2D()
    loops = []
    for polyline in planar.discrete:
        points = np.asarray(polyline, dtype=float)
        if len(points) < 3:
            continue
        closed = float(np.linalg.norm(points[0] - points[-1])) <= 1e-5
        if not closed:
            points = np.vstack([points, points[0]])
        ring = points[:-1]
        if len(ring) >= 3:
            loops.append({
                "points": ring,
                "closed": closed,
                "raw_perimeter_m": float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum()),
                "convex_perimeter_m": perimeter(ring),
                "centroid": np.asarray(ring, dtype=float).mean(axis=0),
            })
    if not loops:
        return None
    centered = [
        item for item in loops
        if float(np.linalg.norm(item["centroid"])) <= max_center_distance_m
    ]
    if not centered:
        return None
    centered.sort(key=lambda item: item["convex_perimeter_m"], reverse=True)
    selected = centered[0]
    points = selected["points"]
    return {
        "y_m": y,
        "component_count": len(loops),
        "selected_component": 0,
        "selected_vertex_count": len(points),
        "closed": bool(selected["closed"]),
        "center_distance_m": float(np.linalg.norm(selected["centroid"])),
        "center_compatible_component_count": len(centered),
        "raw_perimeter_cm": float(selected["raw_perimeter_m"]) * 100.0,
        "convex_perimeter_cm": float(selected["convex_perimeter_m"]) * 100.0,
        "bounds_cm": {
            "axis0": [float(points[:, 0].min()) * 100.0, float(points[:, 0].max()) * 100.0],
            "axis1": [float(points[:, 1].min()) * 100.0, float(points[:, 1].max()) * 100.0],
        },
    }


def optimize(mesh: trimesh.Trimesh, name: str, initial_y: float, mode: str, radius: float, step: float, max_center_distance_m: float, continuity_ratio: float) -> dict[str, object]:
    candidates = []
    initial = candidate(mesh, initial_y, max_center_distance_m)
    if initial is None:
        return {"name": name, "initial_y_m": initial_y, "optimization": mode, "valid": False, "reason": "no centered closed body loop at initial landmark", "candidates": []}
    initial_perimeter = float(initial["convex_perimeter_cm"])
    offset = -radius
    while offset <= radius + 1e-9:
        row = candidate(mesh, initial_y + offset, max_center_distance_m)
        if row is not None:
            ratio = float(row["convex_perimeter_cm"]) / max(initial_perimeter, 1e-6)
            row["initial_perimeter_ratio"] = ratio
            if abs(ratio - 1.0) > continuity_ratio:
                offset += step
                continue
            row["offset_m"] = offset
            candidates.append(row)
        offset += step
    if not candidates:
        return {"name": name, "initial_y_m": initial_y, "optimization": mode, "valid": False, "candidates": []}
    key = "convex_perimeter_cm"
    selected = max(candidates, key=lambda row: row[key]) if mode == "MAX" else min(candidates, key=lambda row: row[key])
    return {
        "name": name,
        "initial_y_m": initial_y,
        "optimization": mode,
        "search_radius_m": radius,
        "step_m": step,
        "max_center_distance_m": max_center_distance_m,
        "continuity_ratio": continuity_ratio,
        "valid": True,
        "initial_candidate": initial,
        "selected": selected,
        "candidates": candidates,
    }


def main() -> int:
    args = parse_args()
    mesh = trimesh.load(args.mesh.resolve(), process=False)
    if not isinstance(mesh, trimesh.Trimesh) or mesh.is_empty:
        raise RuntimeError("mesh must be a non-empty triangle mesh")
    landmark_payload = json.loads(args.landmarks.resolve().read_text(encoding="utf-8"))
    landmarks = landmark_payload.get("landmarks_gc_y_m")
    if landmarks is None:
        # Existing Actor reports store Blender world landmarks.  The axis
        # conversion used by the exporter maps Blender Z directly to
        # GarmentCode Y, so this is a lossless compatibility path.
        source = landmark_payload.get("landmarks_m")
        if not isinstance(source, dict):
            raise KeyError("landmarks_gc_y_m or landmarks_m")
        landmarks = {name: value for name, value in source.items()}
    results = {
        "bust": optimize(mesh, "bust", float(landmarks["bust"]), "MAX", args.search_radius_m, args.step_m, args.max_center_distance_m, args.continuity_ratio),
        "waist": optimize(mesh, "waist", float(landmarks["waist"]), "MIN", args.search_radius_m, args.step_m, args.max_center_distance_m, args.continuity_ratio),
        "hips": optimize(mesh, "hips", float(landmarks["hips"]), "MAX", args.search_radius_m, args.step_m, args.max_center_distance_m, args.continuity_ratio),
    }
    selected = {name: result.get("selected") for name, result in results.items()}
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "assetsstudio_actor_garmentcodedata_style_measurements_v1",
        "source_mesh": str(args.mesh.resolve()),
        "landmarks_source": str(args.landmarks.resolve()),
        "units": "centimetres for measurements; metres for coordinates",
        "algorithm": {
            "plane": "horizontal GarmentCode Y plane",
            "intersection": "mesh-plane surface polylines; centered body loop with continuity gate, then convex perimeter",
            "optimization": "bust/hips MAX, waist MIN",
            "search_radius_m": args.search_radius_m,
            "step_m": args.step_m,
            "max_center_distance_m": args.max_center_distance_m,
            "continuity_ratio": args.continuity_ratio,
        },
        "selected_measurements_cm": {
            name: (row["convex_perimeter_cm"] if row else None) for name, row in selected.items()
        },
        "selected_planes_m": {
            name: (row["y_m"] if row else None) for name, row in selected.items()
        },
        "results": results,
    }
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
