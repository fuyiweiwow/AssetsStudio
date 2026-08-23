"""Measure Actor scalp occlusion by a fitted source hairstyle and its undercap."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frame", type=int, default=1)
    parser.add_argument("--grid", type=int, default=17)
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    return parser.parse_args(raw)


def object_bvh(obj: bpy.types.Object) -> tuple[BVHTree, callable]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
    bvh = BVHTree.FromPolygons(points, polygons, all_triangles=False)
    return bvh, evaluated.to_mesh_clear


def main() -> int:
    options = parse_args()
    calibration = json.loads(options.calibration.resolve().read_text(encoding="utf-8"))
    bounds = calibration["head_bounds"]
    low = Vector(bounds["min"])
    high = Vector(bounds["max"])
    center = Vector(bounds["center"])
    bpy.ops.wm.open_mainfile(filepath=str(options.input.resolve()))
    bpy.context.scene.frame_set(options.frame)
    bpy.context.view_layer.update()
    actor = next(obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.name.startswith("ChibiBaseMesh"))
    cap = bpy.data.objects.get("HairCandidate_ActorCap")
    if cap is None:
        raise RuntimeError("HairCandidate_ActorCap is missing")
    hair = bpy.data.objects.get("HairCandidate_Blend")
    if hair is None:
        raise RuntimeError("HairCandidate_Blend is missing")
    actor_bvh, clear_actor = object_bvh(actor)
    cap_bvh, clear_cap = object_bvh(cap)
    hair_bvh, clear_hair = object_bvh(hair)
    samples = []
    view_results = {}
    try:
        view_contracts = {
            # The lower front is the intentionally exposed forehead/hairline,
            # not scalp leakage. Other views gate the deeper crown envelope.
            "front": (1, low.y - 1.0, Vector((0.0, 1.0, 0.0)), low.x, high.x, 0.42),
            "back": (1, high.y + 1.0, Vector((0.0, -1.0, 0.0)), low.x, high.x, 0.50),
            "right": (0, high.x + 1.0, Vector((-1.0, 0.0, 0.0)), low.y, high.y, 0.50),
            "left": (0, low.x - 1.0, Vector((1.0, 0.0, 0.0)), low.y, high.y, 0.50),
        }
        for view, (axis, origin_axis, direction, u_low, u_high, crown_ratio) in view_contracts.items():
            crown_bottom = high.z - (high.x - low.x) * crown_ratio
            actor_hits = 0
            cap_covered = 0
            combined_covered = 0
            for zi in range(options.grid):
                z = high.z - (high.z - crown_bottom) * zi / max(options.grid - 1, 1)
                for ui in range(options.grid):
                    u = u_low + (u_high - u_low) * ui / max(options.grid - 1, 1)
                    if view == "front":
                        half_width = max((high.x - low.x) * 0.5, 1e-6)
                        x_ratio = min(abs(u - center.x) / half_width, 1.0)
                        expected_hairline = high.z - (high.x - low.x) * (
                            0.20 + 0.22 * x_ratio**1.7
                        )
                        if z < expected_hairline:
                            continue
                    origin = Vector((u, origin_axis, z)) if axis == 1 else Vector((origin_axis, u, z))
                    actor_hit = actor_bvh.ray_cast(origin, direction, 3.0)[0]
                    if actor_hit is None:
                        continue
                    actor_hits += 1
                    cap_hit = cap_bvh.ray_cast(origin, direction, 3.0)[0]
                    hair_hit = hair_bvh.ray_cast(origin, direction, 3.0)[0]
                    actor_distance = (actor_hit - origin).length
                    cap_distance = (cap_hit - origin).length if cap_hit is not None else None
                    hair_distance = (hair_hit - origin).length if hair_hit is not None else None
                    cap_ok = cap_distance is not None and actor_distance - cap_distance >= 0.001
                    candidate_distances = [value for value in (cap_distance, hair_distance) if value is not None]
                    nearest_distance = min(candidate_distances) if candidate_distances else None
                    combined_ok = nearest_distance is not None and actor_distance - nearest_distance >= 0.001
                    cap_covered += int(cap_ok)
                    combined_covered += int(combined_ok)
                    samples.append(
                        {
                            "view": view,
                            "u": float(u),
                            "z": float(z),
                            "actor_distance": float(actor_distance),
                            "cap_distance": float(cap_distance) if cap_distance is not None else None,
                            "hair_distance": float(hair_distance) if hair_distance is not None else None,
                            "cap_covered": cap_ok,
                            "combined_covered": combined_ok,
                        }
                    )
            view_results[view] = {
                "actor_samples": actor_hits,
                "undercap_covered_samples": cap_covered,
                "undercap_coverage_ratio": cap_covered / actor_hits if actor_hits else 0.0,
                "combined_covered_samples": combined_covered,
                "combined_coverage_ratio": combined_covered / actor_hits if actor_hits else 0.0,
            }
    finally:
        clear_actor()
        clear_cap()
        clear_hair()
    ratio = min(result["combined_coverage_ratio"] for result in view_results.values())
    report = {
        "schema": "assetsstudio_hair_scalp_coverage_v3",
        "front_hairline_contract": "curved_source_bangs_occlusion_v1",
        "status": "pass" if ratio >= 0.98 else "fail",
        "input": str(options.input.resolve()),
        "calibration": str(options.calibration.resolve()),
        "views": view_results,
        "minimum_combined_coverage_ratio": ratio,
        "threshold": 0.98,
        "samples": samples,
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"HAIR_SCALP_COVERAGE_{report['status'].upper()} minimum_ratio={ratio:.6f}")
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
