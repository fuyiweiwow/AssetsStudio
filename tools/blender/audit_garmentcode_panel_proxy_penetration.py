"""Measure GarmentCode panel vertices against matching Actor proxy regions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--garment-obj", required=True, type=Path)
    parser.add_argument("--body-obj", required=True, type=Path)
    parser.add_argument("--body-segmentation", required=True, type=Path)
    parser.add_argument("--panel-membership", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source", required=True)
    return parser.parse_args(argv)


def read_vertices(path: Path, scale: float) -> list[Vector]:
    result = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            fields = line.split()
            result.append(Vector(tuple(float(value) * scale for value in fields[1:4])))
    return result


def read_faces(path: Path) -> list[tuple[int, ...]]:
    result = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("f "):
            result.append(tuple(int(value.split("/")[0]) - 1 for value in line.split()[1:]))
    return result


def family(panel_names: list[str]) -> str:
    names = set(panel_names)
    if any(name.startswith("left_sleeve_") or name.startswith("sl_left_cuff_") for name in names):
        return "left_arm"
    if any(name.startswith("right_sleeve_") or name.startswith("sl_right_cuff_") for name in names):
        return "right_arm"
    return "body"


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return float(ordered[index])


def main() -> int:
    options = arguments()
    garment_points = read_vertices(options.garment_obj.resolve(), 1.0)
    # GarmentCode cloth is centimetres; Actor proxy OBJ is metres and is
    # multiplied by 100 in Cloth.build_stage.
    body_points = read_vertices(options.body_obj.resolve(), 100.0)
    body_faces = read_faces(options.body_obj.resolve())
    body_segmentation = json.loads(options.body_segmentation.read_text(encoding="utf-8"))
    membership = json.loads(options.panel_membership.read_text(encoding="utf-8"))
    vertex_panels = membership["vertex_panels"]
    if len(garment_points) != len(vertex_panels):
        raise RuntimeError("garment/membership vertex count mismatch")

    region_bvhs = {}
    for region in ("body", "left_arm", "right_arm"):
        allowed = set(int(value) for value in body_segmentation[region])
        faces = [face for face in body_faces if all(index in allowed for index in face)]
        if not faces:
            raise RuntimeError(f"body region has no faces: {region}")
        region_bvhs[region] = BVHTree.FromPolygons(body_points, faces, all_triangles=False)

    signed_by_family: dict[str, list[float]] = defaultdict(list)
    examples: dict[str, list[dict[str, object]]] = defaultdict(list)
    panel_signed: dict[str, list[float]] = defaultdict(list)
    for index, point in enumerate(garment_points):
        region = family(vertex_panels[index])
        nearest = region_bvhs[region].find_nearest(point)
        if nearest is None:
            continue
        location, normal, _face_index, distance = nearest
        signed = float((point - location).dot(normal.normalized()))
        signed_by_family[region].append(signed)
        for panel in vertex_panels[index]:
            panel_signed[panel].append(signed)
        if signed < 0.0:
            examples[region].append({
                "vertex": index,
                "signed_cm": signed,
                "distance_cm": float(distance),
                "panels": vertex_panels[index],
                "point_cm": [float(value) for value in point],
            })

    def stats(values: list[float]) -> dict[str, object]:
        return {
            "count": len(values),
            "negative": sum(value < 0.0 for value in values),
            "negative_fraction": sum(value < 0.0 for value in values) / max(len(values), 1),
            "below_minus_0p25cm": sum(value < -0.25 for value in values),
            "below_minus_1cm": sum(value < -1.0 for value in values),
            "below_minus_2cm": sum(value < -2.0 for value in values),
            "min_signed_cm": min(values, default=None),
            "median_signed_cm": percentile(values, 0.5),
            "p10_signed_cm": percentile(values, 0.1),
        }

    report = {
        "schema": "assetsstudio_garmentcode_panel_proxy_penetration_v1",
        "source": options.source,
        "garment_obj": str(options.garment_obj.resolve()),
        "body_obj": str(options.body_obj.resolve()),
        "coordinate_contract": "garment cm and Actor proxy metres scaled by 100, both in GarmentCode x/y-up/z-depth",
        "families": {name: stats(values) for name, values in signed_by_family.items()},
        "panels": {name: stats(values) for name, values in sorted(panel_signed.items())},
        "deepest_examples": {
            name: sorted(items, key=lambda item: item["signed_cm"])[:12]
            for name, items in examples.items()
        },
        "interpretation": "negative means the garment vertex lies behind the outward normal of the matching proxy region",
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
