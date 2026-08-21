from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
HAIR_NAME = "Wearable_Adventurer_HeadHairV1"
HEAD_BONE = "CC_Base_Head"
HEAD_CENTER = Vector((0.0, 0.025, 2.299))
MIN_CLEARANCE = 0.008
MIN_ZONE_COVERAGE = 0.94


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def outer_hair_distance(bvh: BVHTree, direction: Vector) -> float | None:
    # Hunyuan output may contain both an inner fitted cap and outer locks.
    # Walk through all surfaces on this radial line and retain the outermost
    # one; the first hit alone would incorrectly report the inner cap.
    origin = HEAD_CENTER.copy()
    travelled = 0.0
    hits = []
    for _ in range(24):
        location, _normal, _face, distance = bvh.ray_cast(origin, direction, 2.2)
        if location is None or distance is None:
            break
        travelled += distance
        hits.append(travelled)
        step = 0.002
        origin = location + direction * step
        travelled += step
    return max(hits) if hits else None


def main() -> int:
    args = cli()
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    scene = bpy.context.scene
    scene.frame_set(1)
    actor = bpy.data.objects.get(ACTOR_NAME)
    hair = bpy.data.objects.get(HAIR_NAME)
    if actor is None or hair is None:
        raise RuntimeError("Actor or hair missing")

    # Audit base Actor skin, not the preview-only scalp mask.
    depsgraph = bpy.context.evaluated_depsgraph_get()
    hair_eval = hair.evaluated_get(depsgraph)
    hair_mesh = hair_eval.to_mesh()
    hair_points = [hair_eval.matrix_world @ vertex.co for vertex in hair_mesh.vertices]
    hair_faces = [list(face.vertices) for face in hair_mesh.polygons]
    hair_bvh = BVHTree.FromPolygons(hair_points, hair_faces, all_triangles=False)

    group_names = {group.index: group.name for group in actor.vertex_groups}
    zones: dict[str, list[dict[str, float | bool | None]]] = {
        "crown": [],
        "rear": [],
        "left_temple": [],
        "right_temple": [],
    }
    for vertex in actor.data.vertices:
        head_weight = sum(
            item.weight for item in vertex.groups if group_names.get(item.group) == HEAD_BONE
        )
        if head_weight < 0.25:
            continue
        point = actor.matrix_world @ vertex.co
        zone = None
        if point.z >= 2.58:
            zone = "crown"
        elif point.y >= 0.10 and point.z >= 1.78:
            zone = "rear"
        # Temple coverage is measured above the ears.  The generated design
        # intentionally has ear apertures, so including the ear-height radial
        # rays would punish the correct wearable opening.
        elif point.x <= -0.54 and point.z >= 2.18 and point.y >= -0.24:
            zone = "left_temple"
        elif point.x >= 0.54 and point.z >= 2.18 and point.y >= -0.24:
            zone = "right_temple"
        if zone is None:
            continue
        radial = point - HEAD_CENTER
        actor_distance = radial.length
        if actor_distance <= 1e-8:
            continue
        outer_distance = outer_hair_distance(hair_bvh, radial.normalized())
        clearance = None if outer_distance is None else outer_distance - actor_distance
        zones[zone].append(
            {
                "clearance": clearance,
                "covered": clearance is not None and clearance >= MIN_CLEARANCE,
            }
        )

    failures = []
    zone_reports = {}
    for name, samples in zones.items():
        clearances = [float(item["clearance"]) for item in samples if item["clearance"] is not None]
        covered = sum(bool(item["covered"]) for item in samples)
        coverage = covered / len(samples) if samples else 0.0
        report = {
            "samples": len(samples),
            "ray_hits": len(clearances),
            "covered_samples": covered,
            "coverage": round(coverage, 6),
            "clearance_min": round(min(clearances), 6) if clearances else None,
            "clearance_p05": round(percentile(clearances, 0.05), 6) if clearances else None,
            "clearance_median": round(statistics.median(clearances), 6) if clearances else None,
            "clearance_p95": round(percentile(clearances, 0.95), 6) if clearances else None,
            "clearance_max": round(max(clearances), 6) if clearances else None,
        }
        zone_reports[name] = report
        if coverage < MIN_ZONE_COVERAGE:
            failures.append(f"{name} enclosure coverage {coverage:.3f} < {MIN_ZONE_COVERAGE:.3f}")

    hair_eval.to_mesh_clear()
    report = {
        "schema": "actor_head_hair_enclosure_audit_v2",
        "input_blend": str(args.input_blend.resolve()),
        "head_center": list(HEAD_CENTER),
        "minimum_clearance": MIN_CLEARANCE,
        "minimum_zone_coverage": MIN_ZONE_COVERAGE,
        "zones": zone_reports,
        "failures": failures,
        "status": "pass" if not failures else "fail",
    }
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
