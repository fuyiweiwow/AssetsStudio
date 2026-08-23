"""Combine an Actor-conformed robe shell with the measured hood shell."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--body", required=True, type=Path)
    parser.add_argument("--hood", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    return parser.parse_args(argv)


def import_one(path: Path) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(path))
    created = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    if len(created) != 1:
        raise RuntimeError(f"expected one mesh from {path}, got {len(created)}")
    return created[0]


def main() -> int:
    options = parse_args()
    options.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    body = import_one(options.body)
    hood = import_one(options.hood)
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    hood.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.name = "ActorConformedRobeWithMeasuredHood"
    bpy.ops.wm.obj_export(filepath=str(options.output), export_materials=False, export_selected_objects=True)
    print(f"COMBINE_ROBE_HOOD_PASS output={options.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
