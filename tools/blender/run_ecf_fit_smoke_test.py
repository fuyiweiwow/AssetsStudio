"""Run Elastic Clothing Fit against the current Actor in background Blender.

This is a route-C toolchain smoke test. It intentionally uses the current
route-B garment prototype as an input mesh; it does not promote that mesh to a
quality candidate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ecf-source", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    return parser.parse_args(argv)


def remove_cloth_blockers(garment: bpy.types.Object) -> None:
    for modifier in list(garment.modifiers):
        if modifier.type == "CLOTH":
            garment.modifiers.remove(modifier)


def main() -> int:
    options = parse_args()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(options.ecf_source))

    import elastic_fit

    elastic_fit.register()
    body = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    garment = bpy.data.objects.get("WorkflowSmoke_CloakBody")
    if body is None or garment is None:
        raise RuntimeError("expected Actor body and WorkflowSmoke_CloakBody")

    remove_cloth_blockers(garment)
    props = bpy.context.scene.efit_props
    props.body_obj = body
    props.clothing_obj = garment
    props.fit_mode = "FULL"
    props.fit_amount = 0.42
    props.offset = 0.035
    props.use_proxy_hull = True
    props.elastic_strength = 0.35
    props.elastic_iterations = 4
    props.use_laplacian = True
    props.laplacian_factor = 0.12
    props.laplacian_iterations = 1

    bpy.ops.object.select_all(action="DESELECT")
    garment.select_set(True)
    bpy.context.view_layer.objects.active = garment
    result = bpy.ops.efit.fit()
    print(f"ECF_FIT_RESULT {result}")
    if "FINISHED" not in result:
        raise RuntimeError("Elastic Clothing Fit did not finish")

    apply_result = bpy.ops.efit.preview_apply()
    print(f"ECF_APPLY_RESULT {apply_result}")
    if "FINISHED" not in apply_result:
        raise RuntimeError("Elastic Clothing Fit preview apply did not finish")

    bpy.context.scene.render.filepath = str(options.output_dir / "route_c_ecf_fit.png")
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output_dir / "route_c_ecf_fit.blend"))
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    garment.select_set(True)
    bpy.context.view_layer.objects.active = garment
    bpy.ops.export_scene.gltf(
        filepath=str(options.output_dir / "route_c_ecf_fit.glb"),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )
    print(f"ROUTE_C_ECF_SMOKE_PASS output={options.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
