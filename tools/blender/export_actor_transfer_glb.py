"""Export an Actor transfer blend as a self-contained GLB review asset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--garment-object", required=True)
    parser.add_argument("--garment-only", action="store_true")
    return parser.parse_args(argv)


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    garment = bpy.data.objects.get(options.garment_object)
    if garment is None or garment.type != "MESH":
        raise RuntimeError(f"garment object is missing or not a mesh: {options.garment_object}")

    selected = [garment]
    armature = bpy.data.objects.get("Armature")
    if armature is not None:
        selected.append(armature)
    if not options.garment_only:
        selected.extend(
            obj for obj in bpy.data.objects
            if obj.type == "MESH" and obj not in selected and not obj.name.startswith("GarmentCode")
        )

    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in selected:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = garment

    options.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(options.output.resolve()),
        export_format="GLB",
        use_selection=True,
        export_extras=True,
        export_animations=armature is not None,
        export_animation_mode="ACTIVE_ACTIONS",
        export_frame_range=True,
        export_force_sampling=True,
        export_def_bones=True,
        export_optimize_animation_size=True,
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )
    if not options.output.resolve().is_file() or options.output.resolve().stat().st_size == 0:
        raise RuntimeError(f"GLB export did not produce a file: {options.output.resolve()}")
    print(f"ACTOR_TRANSFER_GLB_PASS output={options.output.resolve()} objects={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
