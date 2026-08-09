"""Render a component variant together with selected shared-pool components."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fit_blend_hair_candidate as fit_hair
import generate_hair_component_variant as variant_tools


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant-manifest", required=True, type=Path)
    parser.add_argument("--additional-components", required=True, type=Path, help="JSON list of source blend/object/anchor records")
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--q-height-ratio", type=float, default=1.15)
    parser.add_argument("--width-ratio", type=float, default=1.08)
    parser.add_argument("--color", nargs=4, type=float, default=(0.12, 0.045, 0.025, 1.0))
    return parser.parse_args(argv)


def append_source_component(source_blend: Path, object_name: str, anchor: bpy.types.Object) -> bpy.types.Object:
    component = fit_hair.append_object(source_blend, object_name, object_name)
    reference_object = variant_tools.normalize_to_numbered_reference(source_blend, component, anchor)
    # Keep the original source name long enough for normalization, then use a
    # stable generated name for the joined assembly.
    component.name = f"AssemblyPart_{object_name}"
    return component


def main() -> int:
    options = cli_args()
    manifest = json.loads(options.variant_manifest.read_text(encoding="utf-8"))
    additional = json.loads(options.additional_components.read_text(encoding="utf-8"))
    if manifest.get("schema") != "assetslab_hair_component_variant_v1":
        raise RuntimeError("unexpected component variant manifest schema")
    if not isinstance(additional, list):
        raise RuntimeError("additional components must be a list")
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    armature = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
    body = next(obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("ChibiBase"))
    source_blend = Path(str(manifest["source_blend"]))
    anchor_name = str(manifest.get("source_anchor_object") or "")
    anchor = fit_hair.append_object(source_blend, anchor_name, "AssemblySourceHeadAnchor")
    fit_hair.bake_source_transform(anchor)
    anchor.hide_render = True
    anchor.hide_viewport = True
    parts = [append_source_component(source_blend, str(manifest["source_object"]), anchor)]
    variant_tools.transform_variant(
        parts[0],
        int(manifest["variant_seed"]),
        float(manifest.get("variant", {}).get("strength", 0.12)),
    )
    for item in additional:
        item_source = Path(str(item["source_blend"]))
        item_anchor_name = str(item.get("source_anchor_object") or anchor_name)
        if item_source.resolve() != source_blend.resolve():
            raise RuntimeError("assembly components must use the same source bundle as the variant")
        parts.append(append_source_component(item_source, str(item["object"]), anchor))
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    assembly = parts[0]
    assembly.name = "HairComponentAssembly"
    fit = fit_hair.fit_to_actor(
        assembly,
        armature,
        body,
        argparse.Namespace(
            rotation_z=0.0,
            width_ratio=options.width_ratio,
            q_height_ratio=options.q_height_ratio,
        ),
        anchor,
    )
    material = fit_hair.fit_tools.make_material(tuple(options.color))
    assembly.data.materials.clear()
    assembly.data.materials.append(material)
    for polygon in assembly.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    fit_hair.fit_tools.configure_render(bpy.context.scene)
    output_dir = options.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    renders = fit_hair.fit_tools.render_views(bpy.context.scene, output_dir, body, assembly)
    model_glb = output_dir / "model.glb"
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.data.objects:
        if obj.type in {"MESH", "ARMATURE"}:
            obj.select_set(True)
    bpy.context.view_layer.objects.active = assembly
    bpy.ops.export_scene.gltf(
        filepath=str(model_glb),
        export_format="GLB",
        use_selection=True,
        export_animations=False,
    )
    options.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output_blend.resolve()))
    output_manifest = {
        "schema": "assetslab_hair_component_assembly_preview_v1",
        "lifecycle": "assembly_candidate",
        "variant_id": str(manifest.get("variant_id") or options.variant_manifest.parent.name),
        "variant_source_object": manifest["source_object"],
        "variant_seed": manifest["variant_seed"],
        "components": [manifest["source_object"], *[item["object"] for item in additional]],
        "source_blend": str(source_blend),
        "actor_blend": str(options.actor_blend.resolve()),
        "fit": fit,
        "renders": renders,
        "model_glb": str(model_glb),
        "status": "assembly_review_required",
    }
    (output_dir / "manifest.json").write_text(json.dumps(output_manifest, indent=2), encoding="utf-8")
    print(f"HAIR_COMPONENT_ASSEMBLY_PASS variant={output_manifest['variant_id']} components={len(output_manifest['components'])} output={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
