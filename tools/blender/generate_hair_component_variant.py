"""Generate one deterministic geometric variant from one hair component."""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fit_blend_hair_candidate as fit_hair


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--hair-source-blend", required=True, type=Path)
    parser.add_argument("--hair-object", required=True)
    parser.add_argument("--source-anchor-object", required=True)
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--variant-seed", required=True, type=int)
    parser.add_argument("--variant-strength", type=float, default=0.12)
    parser.add_argument("--q-height-ratio", type=float, default=1.15)
    parser.add_argument("--width-ratio", type=float, default=1.08)
    parser.add_argument("--texture-root", type=Path)
    parser.add_argument("--color", nargs=4, type=float, default=(0.12, 0.045, 0.025, 1.0))
    return parser.parse_args(argv)


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [v.co.copy() for v in obj.data.vertices]
    if not points:
        raise RuntimeError(f"hair component has no vertices: {obj.name}")
    low = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    high = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return low, high


def normalize_to_numbered_reference(
    source_blend: Path,
    component: bpy.types.Object,
    source_anchor: bpy.types.Object,
) -> str | None:
    """Undo presentation-grid placement for Chloe/Colin numbered components."""
    name = component.name
    if not name.rsplit("_", 1)[-1].isdigit():
        return None
    stem, suffix = name.rsplit("_", 1)
    if suffix == "01":
        return None
    reference_name = f"{stem}_01"
    reference = fit_hair.append_object(source_blend, reference_name, f"VariantReference_{reference_name}")
    fit_hair.bake_source_transform(reference)
    fit_hair.bake_source_transform(component)
    low, high = bounds(component)
    ref_low, ref_high = bounds(reference)
    component.location += (ref_low + ref_high) * 0.5 - (low + high) * 0.5
    # Some male source rows have the assembled bangs reference shifted sideways
    # relative to Colin_head_dummy. Keep the front/back depth authored by the
    # source, but align the reference's horizontal center to the head anchor.
    anchor_low, anchor_high = bounds(source_anchor)
    reference_center = (ref_low + ref_high) * 0.5
    anchor_center = (anchor_low + anchor_high) * 0.5
    component.location.x += anchor_center.x - reference_center.x
    bpy.data.objects.remove(reference, do_unlink=True)
    return reference_name


def transform_variant(component: bpy.types.Object, seed: int, strength: float) -> dict[str, float]:
    rng = random.Random(seed)
    low, high = bounds(component)
    center = (low + high) * 0.5
    half = (high - low) * 0.5
    half.x = max(half.x, 1e-5)
    half.y = max(half.y, 1e-5)
    half.z = max(half.z, 1e-5)
    width = 1.0 + rng.uniform(-strength, strength)
    depth = 1.0 + rng.uniform(-strength, strength)
    height = 1.0 + rng.uniform(-strength, strength)
    taper = rng.uniform(-strength, strength)
    front_curve = rng.uniform(-strength, strength)
    asymmetry = rng.uniform(-strength, strength) * 0.65
    angle_degrees = rng.uniform(-strength, strength) * 18.0
    for vertex in component.data.vertices:
        local = vertex.co - center
        nx = local.x / half.x
        ny = local.y / half.y
        nz = local.z / half.z
        local.x *= width * (1.0 + taper * nz * 0.35)
        local.y *= depth
        local.z *= height
        local.x += half.x * asymmetry * nz * 0.28
        local.y += half.y * front_curve * max(0.0, nz) * 0.24
        vertex.co = center + local
    rotation = Matrix.Rotation(math.radians(angle_degrees), 4, "Z")
    for vertex in component.data.vertices:
        vertex.co = center + rotation @ (vertex.co - center)
    component.data.update()
    return {
        "width_scale": width,
        "depth_scale": depth,
        "height_scale": height,
        "taper": taper,
        "front_curve": front_curve,
        "asymmetry": asymmetry,
        "rotation_z_degrees": angle_degrees,
        "strength": strength,
    }


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    armature = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
    body = next(obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("ChibiBase"))
    source_anchor = fit_hair.append_object(
        options.hair_source_blend,
        options.source_anchor_object,
        "VariantSourceHeadAnchor",
    )
    fit_hair.bake_source_transform(source_anchor)
    source_anchor.hide_render = True
    source_anchor.hide_viewport = True
    component = fit_hair.append_object(options.hair_source_blend, options.hair_object, options.hair_object)
    reference_object = normalize_to_numbered_reference(options.hair_source_blend, component, source_anchor)
    variant = transform_variant(component, options.variant_seed, options.variant_strength)
    component.name = "HairComponentVariant"
    fit_hair.repair_texture_paths(component, options.texture_root.resolve() if options.texture_root else None)
    fit = fit_hair.fit_to_actor(
        component,
        armature,
        body,
        argparse.Namespace(
            rotation_z=0.0,
            width_ratio=options.width_ratio,
            q_height_ratio=options.q_height_ratio,
        ),
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
    options.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output_blend.resolve()))
    manifest = {
        "schema": "assetslab_hair_component_variant_v1",
        "lifecycle": "pool_candidate",
        "source_blend": str(options.hair_source_blend.resolve()),
        "source_object": options.hair_object,
        "reference_object": reference_object or options.hair_object,
        "source_anchor_object": options.source_anchor_object,
        "actor_blend": str(options.actor_blend.resolve()),
        "variant_seed": options.variant_seed,
        "variant": variant,
        "fit": fit,
        "object": component.name,
        "vertices": len(component.data.vertices),
        "polygons": len(component.data.polygons),
        "renders": renders,
        "status": "component_variant_review_required",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"HAIR_COMPONENT_VARIANT_PASS object={options.hair_object} seed={options.variant_seed} output={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
