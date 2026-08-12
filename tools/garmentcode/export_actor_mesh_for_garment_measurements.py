"""Export the evaluated Actor mesh in GarmentCode body coordinates.

This is an audit input for a GarmentCodeData/GarmentMeasurements-style pass.
It deliberately exports the complete evaluated Actor object; filtering by
vertex weights here would change the surface being measured.  Blender metres
are retained, with the axis conversion Blender (x, y, z) -> GarmentCode
(x, z, -y).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def args_from_blender() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--object", default="ChibiBaseMesh_AccuRIG_InputMesh")
    parser.add_argument("--frame", type=int, default=1)
    return parser.parse_args(argv)


def main() -> int:
    options = args_from_blender()
    bpy.ops.wm.open_mainfile(filepath=str(options.actor.resolve()))
    bpy.context.scene.frame_set(options.frame)
    bpy.context.view_layer.update()
    actor = bpy.data.objects.get(options.object)
    if actor is None or actor.type != "MESH":
        raise RuntimeError(f"Actor mesh not found: {options.object}")

    evaluated = actor.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        world = evaluated.matrix_world
        vertices = []
        for vertex in mesh.vertices:
            point = world @ vertex.co
            vertices.append((point.x, point.z, -point.y))
        lines = [
            "# AssetsStudio complete Actor mesh for GarmentMeasurements audit\n",
            *[f"v {x:.9f} {y:.9f} {z:.9f}\n" for x, y, z in vertices],
        ]
        for polygon in mesh.polygons:
            lines.append("f " + " ".join(str(index + 1) for index in polygon.vertices) + "\n")

        output = options.output.resolve()
        report_path = options.report.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(lines), encoding="utf-8")
        bounds = {
            "min": [min(vertex[index] for vertex in vertices) for index in range(3)],
            "max": [max(vertex[index] for vertex in vertices) for index in range(3)],
        }
        report = {
            "schema": "assetsstudio_actor_garment_measurements_mesh_v1",
            "source_actor": str(options.actor.resolve()),
            "source_object": actor.name,
            "frame": options.frame,
            "units": "metres",
            "coordinate_mapping": "Blender (x,y,z) -> GarmentCode (x,z,-y)",
            "vertex_count": len(mesh.vertices),
            "face_count": len(mesh.polygons),
            "bounds_m": bounds,
            "output": str(output),
            "measurement_policy": {
                "surface": "complete evaluated Actor object; no weight filtering",
                "next": "horizontal GarmentCode-Y plane intersections, convex hull perimeter, +/-2cm at 5mm steps",
            },
        }
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    finally:
        evaluated.to_mesh_clear()


if __name__ == "__main__":
    raise SystemExit(main())
