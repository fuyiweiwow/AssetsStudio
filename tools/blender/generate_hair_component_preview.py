"""Render and cache a standalone preview for one shared-pool hair component."""
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
    parser.add_argument("--hair-source-blend", required=True, type=Path)
    parser.add_argument("--hair-object", required=True)
    parser.add_argument("--source-anchor-object", required=True)
    parser.add_argument("--component-id", required=True)
    parser.add_argument("--gender", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--q-height-ratio", type=float, default=1.15)
    parser.add_argument("--width-ratio", type=float, default=1.08)
    parser.add_argument("--color", nargs=4, type=float, default=(0.12, 0.045, 0.025, 1.0))
    return parser.parse_args(argv)


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    armature = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
    body = next(obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("ChibiBase"))
    source_anchor = fit_hair.append_object(options.hair_source_blend, options.source_anchor_object, "ComponentPreviewSourceHeadAnchor")
    fit_hair.bake_source_transform(source_anchor)
    source_anchor.hide_render = True
    source_anchor.hide_viewport = True
    component = fit_hair.append_object(options.hair_source_blend, options.hair_object, options.hair_object)
    variant_tools.normalize_to_numbered_reference(options.hair_source_blend, component, source_anchor)
    component.name = "HairComponentPreview"
    fit = fit_hair.fit_to_actor(
        component,
        armature,
        body,
        argparse.Namespace(rotation_z=0.0, width_ratio=options.width_ratio, q_height_ratio=options.q_height_ratio),
        source_anchor,
    )
    material = fit_hair.fit_tools.make_material(tuple(options.color))
    component.data.materials.clear()
    component.data.materials.append(material)
    for polygon in component.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    fit_hair.fit_tools.configure_render(bpy.context.scene)
    output_dir = options.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    renders = fit_hair.fit_tools.render_views(bpy.context.scene, output_dir, body, component)
    manifest = {
        "schema": "assetslab_hair_component_preview_v1",
        "component_id": options.component_id,
        "gender": options.gender,
        "role": options.role,
        "source_blend": str(options.hair_source_blend.resolve()),
        "source_object": options.hair_object,
        "source_anchor_object": options.source_anchor_object,
        "fit": fit,
        "vertices": len(component.data.vertices),
        "polygons": len(component.data.polygons),
        "renders": renders,
        "status": "shared_pool_component_preview",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"HAIR_COMPONENT_PREVIEW_PASS component={options.component_id} output={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
