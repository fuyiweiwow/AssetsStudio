"""Export the authoritative Actor body mesh from a Blender file as OBJ."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", default="ChibiBaseMesh_AccuRIG_InputMesh")
    parser.add_argument("--output", type=Path, required=True)
    blender_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = parser.parse_args(blender_args)

    obj = bpy.data.objects.get(args.mesh)
    if obj is None or obj.type != "MESH":
        raise RuntimeError(f"Mesh not found: {args.mesh}")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.obj_export(
        filepath=str(args.output),
        export_selected_objects=True,
        export_materials=False,
        apply_modifiers=True,
    )
    print(f"ACTOR_OBJ_EXPORTED {args.output}")


main()
