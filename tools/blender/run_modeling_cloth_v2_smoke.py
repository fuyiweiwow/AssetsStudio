"""Compare the free Modeling-Cloth solver on the PatternSoft robe bridge mesh."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--addon-source", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--simulation-end", type=int, default=24)
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    return parser.parse_args(argv)


def copy_pin_group(garment: bpy.types.Object) -> None:
    source = garment.vertex_groups.get("PatternSoftShoulderPins")
    target = garment.vertex_groups.get("modeling_cloth_pin") or garment.vertex_groups.new(name="modeling_cloth_pin")
    if source is None:
        return
    pinned: list[int] = []
    for vertex in garment.data.vertices:
        try:
            weight = source.weight(vertex.index)
        except RuntimeError:
            weight = 0.0
        if weight > 0.5:
            pinned.append(vertex.index)
    if pinned:
        target.add(pinned, 1.0, "REPLACE")


def main() -> int:
    options = parse_args()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(options.addon_source))
    import ModelingCloth

    # The add-on targets Blender 2.78 and its legacy panel category cannot be
    # registered by Blender 4.5.  The solver only needs its properties and
    # module-level handlers, so skip the obsolete UI registration in headless
    # mode and keep this comparison focused on the free solver core.
    ModelingCloth.create_properties()
    ModelingCloth.global_setup()
    garment = bpy.data.objects.get("PatternSoft_MageRobe_V2")
    body = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    if garment is None or body is None:
        raise RuntimeError("PatternSoft robe or Actor body not found")

    for modifier in list(garment.modifiers):
        garment.modifiers.remove(modifier)
    copy_pin_group(garment)

    bpy.context.view_layer.objects.active = body
    body.modeling_cloth_object_collision = True
    bpy.context.view_layer.objects.active = garment
    garment.modeling_cloth_self_collision = False
    garment.modeling_cloth_object_detect = True
    garment.modeling_cloth_spring_force = 1.0
    garment.modeling_cloth_push_springs = 0.45
    garment.modeling_cloth_bend_stiff = 0.12
    garment.modeling_cloth_gravity = -1.0
    garment.modeling_cloth_iterations = 6
    garment.modeling_cloth_sew = 1.0
    garment.modeling_cloth = True
    garment.modeling_cloth_pause = False
    garment.modeling_cloth_handler_frame = True

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = options.simulation_end
    for frame in range(1, options.simulation_end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()

    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.filepath = str(options.output_dir / "patternsoft_robe_v2_modeling_cloth.png")
    bpy.ops.render.render(write_still=True)

    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    garment.select_set(True)
    bpy.context.view_layer.objects.active = garment
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output_dir / "patternsoft_robe_v2_modeling_cloth.blend"))
    bpy.ops.export_scene.gltf(
        filepath=str(options.output_dir / "patternsoft_robe_v2_modeling_cloth.glb"),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )
    print(
        "MODELING_CLOTH_ROBE_V2_PASS "
        f"frame={options.simulation_end} output={options.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
