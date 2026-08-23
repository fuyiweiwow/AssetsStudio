"""Fit the downloaded CC0 robe mesh to the shared Actor as a reversible candidate."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", type=Path)
    parser.add_argument("--source-blend", type=Path)
    parser.add_argument("--ecf-source", type=Path)
    parser.add_argument("--output-dir", type=Path)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    values, _ = parser.parse_known_args(argv)
    values.actor_blend = values.actor_blend or Path(os.environ["ACTOR_BLEND"])
    values.source_blend = values.source_blend or Path(os.environ["SOURCE_BLEND"])
    values.ecf_source = values.ecf_source or Path(os.environ["ECF_SOURCE"])
    values.output_dir = values.output_dir or Path(os.environ["FIT_OUTPUT_DIR"])
    return values


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def import_mesh_from_blend(source_blend: Path, object_name: str) -> bpy.types.Object:
    with bpy.data.libraries.load(str(source_blend.resolve()), link=False) as (data_from, data_to):
        if object_name not in data_from.objects:
            raise RuntimeError(f"source object missing: {object_name}; found={data_from.objects}")
        data_to.objects = [object_name]
    garment = next((obj for obj in data_to.objects if obj is not None), None)
    if garment is None or garment.type != "MESH":
        raise RuntimeError("source garment did not load as a mesh")
    bpy.context.scene.collection.objects.link(garment)
    garment.name = "ExternalLongRobe_Raw"

    # Bake the source object's old world transform into its vertices so that
    # fitting starts from a clean Actor-local scene.
    source_matrix = garment.matrix_world.copy()
    for vertex in garment.data.vertices:
        vertex.co = source_matrix @ vertex.co
    garment.matrix_world = Matrix.Identity(4)
    return garment


def apply_geometry_modifiers(garment: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    garment.select_set(True)
    bpy.context.view_layer.objects.active = garment
    for modifier in list(garment.modifiers):
        if modifier.type in {"MIRROR", "SUBSURF"}:
            try:
                bpy.ops.object.modifier_apply(modifier=modifier.name)
            except RuntimeError as exc:
                print(f"MODIFIER_APPLY_WARNING {modifier.name}: {exc}")


def make_material(garment: bpy.types.Object) -> None:
    material = bpy.data.materials.get("AssetsStudio_ExternalRobeDiagnostic") or bpy.data.materials.new(
        "AssetsStudio_ExternalRobeDiagnostic"
    )
    material.diffuse_color = (0.06, 0.16, 0.46, 1.0)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = (0.06, 0.16, 0.46, 1.0)
        principled.inputs["Roughness"].default_value = 0.82
    garment.data.materials.clear()
    garment.data.materials.append(material)


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def render_views(scene: bpy.types.Scene, body: bpy.types.Object, garment: bpy.types.Object, output: Path) -> None:
    low, high = bounds(body)
    target = (low + high) * 0.5
    span = max((high - low).x, (high - low).y, (high - low).z)
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.035, 0.035, 0.05)
    original_visibility = {obj.name: obj.hide_render for obj in scene.objects}
    for obj in scene.objects:
        if obj.type == "MESH" and obj not in {body, garment}:
            obj.hide_render = True
    for direction, location in {
        "front": (0.0, -span * 4.2, target.z),
        "side": (span * 4.2, 0.0, target.z),
        "three_quarter": (span * 3.2, -span * 3.2, target.z),
    }.items():
        camera_data = bpy.data.cameras.new(f"ExternalRobeCamera_{direction}")
        camera = bpy.data.objects.new(f"ExternalRobeCamera_{direction}", camera_data)
        scene.collection.objects.link(camera)
        camera.location = location
        camera.data.lens = 55
        look_at(camera, target)
        scene.camera = camera
        scene.render.filepath = str(output / f"external_robe_{direction}.png")
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(camera, do_unlink=True)
    for name, hidden in original_visibility.items():
        if name in scene.objects:
            scene.objects[name].hide_render = hidden


def main() -> int:
    options = args()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    body = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    if body is None:
        raise RuntimeError("Actor body missing")
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    garment = import_mesh_from_blend(options.source_blend, "garment")
    apply_geometry_modifiers(garment)
    make_material(garment)

    body_low, body_high = bounds(body)
    garment_low, garment_high = bounds(garment)
    body_size = body_high - body_low
    garment_size = garment_high - garment_low
    target_size = Vector((body_size.x * 1.34, body_size.y * 1.28, body_size.z * 0.96))
    garment.scale = Vector(
        (
            target_size.x / max(garment_size.x, 1e-6),
            target_size.y / max(garment_size.y, 1e-6),
            target_size.z / max(garment_size.z, 1e-6),
        )
    )
    bpy.context.view_layer.update()
    garment_low, garment_high = bounds(garment)
    garment.location += Vector(
        (
            (body_low.x + body_high.x) * 0.5 - (garment_low.x + garment_high.x) * 0.5,
            (body_low.y + body_high.y) * 0.5 - (garment_low.y + garment_high.y) * 0.5,
            body_low.z + 0.035 - garment_low.z,
        )
    )
    bpy.context.view_layer.update()
    garment.name = "ExternalLongRobe_FitCandidate"

    # Apply the open-source fit add-on in-process, leaving the downloaded source untouched.
    sys.path.insert(0, str(options.ecf_source.resolve()))
    import elastic_fit

    elastic_fit.register()
    props = bpy.context.scene.efit_props
    props.body_obj = body
    props.clothing_obj = garment
    props.fit_mode = "FULL"
    props.fit_amount = float(os.environ.get("ECF_FIT_AMOUNT", "0.72"))
    props.offset = float(os.environ.get("ECF_OFFSET", "0.02"))
    props.use_proxy_hull = True
    props.elastic_strength = float(os.environ.get("ECF_ELASTIC_STRENGTH", "0.45"))
    props.elastic_iterations = int(os.environ.get("ECF_ELASTIC_ITERATIONS", "8"))
    props.use_laplacian = True
    props.laplacian_factor = float(os.environ.get("ECF_LAPLACIAN_FACTOR", "0.08"))
    props.laplacian_iterations = int(os.environ.get("ECF_LAPLACIAN_ITERATIONS", "2"))
    bpy.ops.object.select_all(action="DESELECT")
    garment.select_set(True)
    bpy.context.view_layer.objects.active = garment
    fit_result = bpy.ops.efit.fit()
    if "FINISHED" not in fit_result:
        raise RuntimeError(f"ECF fit failed: {fit_result}")
    apply_result = bpy.ops.efit.preview_apply()
    if "FINISHED" not in apply_result:
        raise RuntimeError(f"ECF apply failed: {apply_result}")
    bpy.context.view_layer.update()

    render_views(bpy.context.scene, body, garment, options.output_dir)
    output_blend = options.output_dir / "external_long_robe_actor_fit.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    report = {
        "schema": "external_long_robe_actor_fit_v1",
        "source_blend": str(options.source_blend.resolve()),
        "actor_blend": str(options.actor_blend.resolve()),
        "output_blend": str(output_blend.resolve()),
        "garment_object": garment.name,
        "fit_operator": "Elastic Clothing Fit",
        "fit_result": str(fit_result),
        "apply_result": str(apply_result),
        "body_dimensions": [round(float(value), 6) for value in body_size],
        "initial_target_dimensions": [round(float(value), 6) for value in target_size],
        "final_dimensions": [round(float(value), 6) for value in garment.dimensions],
        "status": "needs_visual_review",
    }
    (options.output_dir / "fit_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
