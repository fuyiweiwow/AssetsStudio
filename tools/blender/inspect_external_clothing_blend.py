"""Read-only inspection report for an externally downloaded clothing blend."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def vec3(value):
    return [round(float(v), 6) for v in value]


def inspect_blend(blend_path: Path, report_path: Path) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(blend_path.resolve()))
    objects = []
    for obj in bpy.data.objects:
        record = {
            "name": obj.name,
            "type": obj.type,
            "visible": bool(obj.visible_get()),
            "location": vec3(obj.location),
            "dimensions": vec3(obj.dimensions),
            "bound_box_world": [vec3(obj.matrix_world @ Vector(corner)) for corner in obj.bound_box]
            if obj.type == "MESH"
            else [],
            "modifiers": [modifier.type for modifier in obj.modifiers],
            "materials": [slot.material.name for slot in obj.material_slots if slot.material],
        }
        if obj.type == "MESH":
            mesh = obj.data
            record.update(
                {
                    "vertices": len(mesh.vertices),
                    "edges": len(mesh.edges),
                    "polygons": len(mesh.polygons),
                    "uv_layers": [layer.name for layer in mesh.uv_layers],
                    "vertex_groups": [group.name for group in obj.vertex_groups],
                    "armature_modifiers": [
                        modifier.object.name
                        for modifier in obj.modifiers
                        if modifier.type == "ARMATURE" and modifier.object
                    ],
                }
            )
        objects.append(record)

    meshes = [item for item in objects if item["type"] == "MESH"]
    report = {
        "schema": "external_clothing_blend_inspection_v1",
        "blend": str(blend_path.resolve()),
        "blender_version": list(bpy.app.version),
        "scene_unit_settings": {
            "system": bpy.context.scene.unit_settings.system,
            "scale_length": bpy.context.scene.unit_settings.scale_length,
            "length_unit": bpy.context.scene.unit_settings.length_unit,
        },
        "object_count": len(objects),
        "mesh_count": len(meshes),
        "objects": objects,
        "notes": [
            "This report is read-only and does not modify the downloaded source blend.",
            "World-space dimensions are reported before Actor fitting.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path)
    parser.add_argument("--report", type=Path)
    # Blender can consume the conventional `--` separator when launched from
    # PowerShell. Environment fallbacks keep this utility usable headlessly.
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    options, _ = parser.parse_known_args(argv)
    blend_path = options.blend or Path(os.environ["ASSET_BLEND"])
    report_path = options.report or Path(os.environ["ASSET_REPORT"])
    inspect_blend(blend_path, report_path)


if __name__ == "__main__":
    main()
