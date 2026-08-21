from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


BOOTS = {
    "left": "Wearable_Adventurer_Boot_L_V1",
    "right": "Wearable_Adventurer_Boot_R_V1",
}
FRAMES = [1, 11, 21, 31, 41, 51, 61, 71]


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def main() -> int:
    options = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    scene = bpy.context.scene
    report = {"schema": "boot_sole_contact_workflow_v1", "frames": {}, "boots": {}}

    sole_indices: dict[str, list[int]] = {}
    for side, name in BOOTS.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise RuntimeError(f"boot missing: {name}")
        local_z = [vertex.co.z for vertex in obj.data.vertices]
        sole_limit = percentile(local_z, 0.08)
        sole_indices[side] = [vertex.index for vertex in obj.data.vertices if vertex.co.z <= sole_limit]
        used_groups = sorted(
            group.name
            for group in obj.vertex_groups
            if any(
                item.group == group.index and item.weight > 0.0
                for vertex in obj.data.vertices
                for item in vertex.groups
            )
        )
        report["boots"][side] = {
            "object": name,
            "sole_vertex_count": len(sole_indices[side]),
            "local_sole_limit": sole_limit,
            "used_groups": used_groups,
            "binding_mode": obj.get("binding_mode"),
        }

    for frame in FRAMES:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        frame_report = {}
        for side, name in BOOTS.items():
            obj = bpy.data.objects[name]
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            points = [evaluated.matrix_world @ mesh.vertices[index].co for index in sole_indices[side]]
            z_values = [point.z for point in points]
            minimum = min(z_values)
            near_ground = sum(value <= minimum + 0.008 for value in z_values)
            frame_report[side] = {
                "minimum_z": minimum,
                "p05_z": percentile(z_values, 0.05),
                "median_z": percentile(z_values, 0.50),
                "p95_z": percentile(z_values, 0.95),
                "sole_height_spread_p95_p05": percentile(z_values, 0.95) - percentile(z_values, 0.05),
                "near_lowest_fraction_8mm": near_ground / len(z_values),
            }
            evaluated.to_mesh_clear()
        report["frames"][str(frame)] = frame_report

    spreads = [
        values[side]["sole_height_spread_p95_p05"]
        for values in report["frames"].values()
        for side in BOOTS
    ]
    report["summary"] = {
        "maximum_sole_height_spread": max(spreads),
        "interpretation": "large spread means the rigid sole is rotating instead of preserving a planted contact plane",
    }
    options.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
