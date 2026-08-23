"""Export a DressCode sewing pattern as a flat Blender/GLB inspection asset.

This is an intermediate 2D pattern preview, not a worn garment or cloth
simulation. It lets the offline workflow inspect canonical panels in Blender
before Actor fitting and simulation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--blend", type=Path)
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def material(name: str, color: tuple[float, float, float, float]):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


def role_for(panel_name: str) -> str:
    if panel_name.startswith("cuff_extension"):
        return "cuff_extension"
    if panel_name.startswith("hood_extension"):
        return "hood_extension"
    return {
        "panel_2": "sleeve",
        "panel_3": "hood_candidate",
        "panel_4": "robe_body",
        "panel_5": "hood_candidate",
        "panel_6": "sleeve",
    }.get(panel_name, "accessory")


def create_panel(name: str, panel: dict, offset_x: float, materials: dict) -> float:
    vertices = [Vector((point[0] + offset_x, point[1], 0.0)) for point in panel["vertices"]]
    polygon = [Vector((point.x, point.y, point.z)) for point in vertices]
    triangles = tessellate_polygon([polygon])
    if triangles and isinstance(triangles[0][0], int):
        faces = [tuple(triangle) for triangle in triangles]
    else:
        index_by_coord = {tuple(point): index for index, point in enumerate(vertices)}
        faces = [
            tuple(index_by_coord[tuple(point)] for point in triangle)
            for triangle in triangles
        ]
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    role = role_for(name)
    obj["source_panel"] = name
    obj["role"] = role
    obj.data.materials.append(materials[role])
    width = max(point[0] for point in panel["vertices"]) - min(point[0] for point in panel["vertices"])
    return width + 12.0


def main() -> int:
    options = parse_args()
    payload = json.loads(options.spec.read_text(encoding="utf-8"))
    options.output.parent.mkdir(parents=True, exist_ok=True)
    clear_scene()

    materials = {
        "robe_body": material("Mage Navy", (0.04, 0.08, 0.25, 1.0)),
        "sleeve": material("Mage Purple", (0.22, 0.07, 0.32, 1.0)),
        "hood_candidate": material("Hood Violet", (0.35, 0.12, 0.45, 1.0)),
        "cuff_extension": material("Cuff Gold", (0.72, 0.42, 0.08, 1.0)),
        "hood_extension": material("Hood Gold", (0.85, 0.58, 0.12, 1.0)),
        "accessory": material("Accessory Blue", (0.12, 0.23, 0.48, 1.0)),
    }

    offset_x = 0.0
    for panel_name, panel in payload["pattern"]["panels"].items():
        offset_x += create_panel(panel_name, panel, offset_x, materials)

    bpy.ops.object.select_all(action="SELECT")
    for obj in bpy.context.selected_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]

    if options.blend:
        options.blend.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(options.blend))
    bpy.ops.export_scene.gltf(
        filepath=str(options.output),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )
    print(f"DRESSCODE_PATTERN_GLB_PASS panels={len(payload['pattern']['panels'])} output={options.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
