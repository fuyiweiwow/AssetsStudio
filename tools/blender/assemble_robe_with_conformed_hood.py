"""Assemble GarmentCode torso/sleeve panel meshes with an Actor hood shell."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panels", type=Path, required=True)
    parser.add_argument("--hood", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--flip-panels-depth", action="store_true")
    parser.add_argument("--panels-depth-scale", type=float, default=1.0)
    blender_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(blender_args)


def import_obj(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(path))
    return [obj for obj in bpy.data.objects if obj not in before]


def main() -> None:
    args = parse_args()
    if not args.panels.is_dir():
        raise FileNotFoundError(args.panels)
    if not args.hood.is_file():
        raise FileNotFoundError(args.hood)
    if args.panels_depth_scale <= 0.0:
        raise ValueError("panels depth scale must be positive")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    selected: list[bpy.types.Object] = []
    panel_files = sorted(
        p for p in args.panels.glob("*.obj")
        if "hood" not in p.name.lower()
    )
    if not panel_files:
        raise RuntimeError("no torso/sleeve panels found")
    for path in panel_files:
        imported = import_obj(path)
        if args.flip_panels_depth:
            for obj in imported:
                obj.scale.z *= -1.0
        for obj in imported:
            obj.scale.z *= args.panels_depth_scale
        selected.extend(imported)
    selected.extend(import_obj(args.hood))

    mesh_objects = [obj for obj in selected if obj.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in mesh_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objects[0]
    bpy.ops.object.join()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.obj_export(
        filepath=str(args.output),
        export_selected_objects=True,
        export_materials=False,
    )
    print(
        f"ASSEMBLED_ROBE_WITH_HOOD {args.output} parts={len(panel_files)} "
        f"flip_panels_depth={args.flip_panels_depth} "
        f"panels_depth_scale={args.panels_depth_scale}"
    )


main()
