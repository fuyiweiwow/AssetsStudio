"""Fit the supplied cartoon sneaker FBX to the Actor foot bones."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector, kdtree

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_actor_derived_tshirt import render_review  # noqa: E402

RIGHT_PARTS = ("shoes.baseright", "shoes.009", "shoes.010", "shoes.023", "shoes.001", "shoes.005", "shoes", "shoes.021")
LEFT_PARTS = ("shoes.baseleft", "shoes.016", "shoes.017", "shoes.022", "shoes.019", "shoes.020", "shoes.028", "shoes.029")


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--reference-fbx", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--resolution", type=int, default=256)
    parser.add_argument("--extra-height", type=float, default=0.020)
    parser.add_argument("--toe-extra", type=float, default=0.035, help="extra length toward Actor front/toe direction")
    parser.add_argument("--heel-extra", type=float, default=0.010, help="extra length toward Actor heel direction")
    parser.add_argument("--extra-width", type=float, default=0.028)
    parser.add_argument("--radial-width-scale", type=float, default=1.0, help="minimum shoe width as a multiple of Actor foot width")
    parser.add_argument("--radial-height-scale", type=float, default=1.0, help="minimum shoe height as a multiple of Actor foot height")
    parser.add_argument("--toe-radial-width-scale", type=float, default=1.0, help="toe-zone width as a multiple of Actor foot width")
    parser.add_argument("--toe-radial-height-scale", type=float, default=1.0, help="toe-zone height as a multiple of Actor foot height")
    parser.add_argument("--toe-zone-end", type=float, default=0.42, help="normalized source length at which toe-zone enlargement fades out")
    parser.add_argument("--weight-mode", choices=("foot_toe", "rigid_foot_toe", "nearest_actor"), default="foot_toe")
    return parser.parse_args(argv)


def bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    return (
        Vector((min(point[i] for point in points) for i in range(3))),
        Vector((max(point[i] for point in points) for i in range(3))),
    )


def actor_foot_target(actor: bpy.types.Object, side: str, toe_extra: float, heel_extra: float, extra_width: float, extra_height: float, radial_width_scale: float, radial_height_scale: float) -> dict[str, float]:
    groups = {group.name: group.index for group in actor.vertex_groups}
    indices = {
        index
        for name, index in groups.items()
        if name.startswith(f"CC_Base_{side}_Foot") or name.startswith(f"CC_Base_{side}_Toe")
    }
    points = [
        actor.matrix_world @ vertex.co
        for vertex in actor.data.vertices
        if sum(item.weight for item in vertex.groups if item.group in indices) > 0.25
    ]
    if not points:
        raise RuntimeError(f"no foot-weighted Actor vertices for {side}")
    min_x, max_x = min(point.x for point in points), max(point.x for point in points)
    min_y, max_y = min(point.y for point in points), max(point.y for point in points)
    min_z, max_z = min(point.z for point in points), max(point.z for point in points)
    target_min_y = min_y - toe_extra
    target_max_y = max_y + heel_extra
    foot_width = max_x - min_x
    foot_height = max_z - min_z
    return {
        "center_x": (min_x + max_x) * 0.5,
        "center_y": (target_min_y + target_max_y) * 0.5,
        "bottom_z": min_z - 0.006,
        "length": target_max_y - target_min_y,
        # Conservative cylindrical/elliptical cross-section: the shoe must
        # not be narrower than the measured foot radius. Additive margins
        # remain as a lower bound for the older fit variants.
        "width": max(foot_width + extra_width, foot_width * radial_width_scale),
        "height": max(foot_height + extra_height, foot_height * radial_height_scale),
        "foot_width": foot_width,
        "foot_height": foot_height,
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
        "min_z": min_z,
        "max_z": max_z,
    }


def transform_point(point: Vector, ref_min: Vector, ref_max: Vector, target: dict[str, float], side: str, toe_radial_width_scale: float, toe_radial_height_scale: float, toe_zone_end: float) -> Vector:
    # FBX shoe length is X, width is Y; Actor foot length is Y, width is X.
    length_u = (point.x - ref_min.x) / max(ref_max.x - ref_min.x, 1e-8)
    width_v = (point.y - ref_min.y) / max(ref_max.y - ref_min.y, 1e-8)
    height_w = (point.z - ref_min.z) / max(ref_max.z - ref_min.z, 1e-8)
    side_sign = 1.0 if side == "L" else -1.0
    x = target["center_x"] + side_sign * (width_v - 0.5) * target["width"]
    y = target["center_y"] + (length_u - 0.5) * target["length"]
    z = target["bottom_z"] + height_w * target["height"]
    if toe_zone_end > 0.0 and length_u < toe_zone_end:
        t = max(0.0, min(1.0, length_u / toe_zone_end))
        fade = 1.0 - (t * t * (3.0 - 2.0 * t))
        target_toe_width = target["foot_width"] * toe_radial_width_scale
        target_toe_height = target["foot_height"] * toe_radial_height_scale
        width_factor = 1.0 + ((target_toe_width / max(target["width"], 1e-8)) - 1.0) * fade
        height_factor = 1.0 + ((target_toe_height / max(target["height"], 1e-8)) - 1.0) * fade
        x = target["center_x"] + (x - target["center_x"]) * width_factor
        z = target["bottom_z"] + (z - target["bottom_z"]) * height_factor
    return Vector((x, y, z))


def transfer_nearest_actor_weights(shoe: bpy.types.Object, actor: bpy.types.Object) -> None:
    tree = kdtree.KDTree(len(actor.data.vertices))
    for index, vertex in enumerate(actor.data.vertices):
        tree.insert(actor.matrix_world @ vertex.co, index)
    tree.balance()
    groups = {}
    for vertex in shoe.data.vertices:
        world = shoe.matrix_world @ vertex.co
        neighbours = tree.find_n(world, 3)
        blended = {}
        total = 0.0
        for _, actor_index, distance in neighbours:
            weight = 1.0 / max(distance, 1e-5)
            total += weight
            for item in actor.data.vertices[actor_index].groups:
                name = actor.vertex_groups[item.group].name
                blended[name] = blended.get(name, 0.0) + item.weight * weight
        if total <= 0.0:
            continue
        for name, value in blended.items():
            group = groups.setdefault(name, shoe.vertex_groups.new(name=name))
            group.add([vertex.index], value / total, "REPLACE")


def create_shoe_parts(source_objects: list[bpy.types.Object], ref_min: Vector, ref_max: Vector, target: dict[str, float], side: str, armature: bpy.types.Object, actor: bpy.types.Object, collection: bpy.types.Collection, toe_radial_width_scale: float, toe_radial_height_scale: float, toe_zone_end: float, weight_mode: str) -> list[bpy.types.Object]:
    created = []
    for source in source_objects:
        source_matrix = source.matrix_world.copy()
        mesh = source.data.copy()
        for vertex in mesh.vertices:
            vertex.co = transform_point(source_matrix @ vertex.co, ref_min, ref_max, target, side, toe_radial_width_scale, toe_radial_height_scale, toe_zone_end)
        mesh.update()
        shoe = bpy.data.objects.new(f"ActorCartoonSneaker_{side}_{source.name}", mesh)
        shoe.matrix_world = Matrix.Identity(4)
        collection.objects.link(shoe)
        if weight_mode == "nearest_actor":
            transfer_nearest_actor_weights(shoe, actor)
        else:
            foot_group = shoe.vertex_groups.new(name=f"CC_Base_{side}_Foot")
            toe_group = shoe.vertex_groups.new(name=f"CC_Base_{side}_ToeBase")
            for vertex in mesh.vertices:
                original = source_matrix @ source.data.vertices[vertex.index].co
                length_u = (original.x - ref_min.x) / max(ref_max.x - ref_min.x, 1e-8)
                toe_weight = max(0.0, min(1.0, (0.44 - length_u) / 0.44))
                if weight_mode == "rigid_foot_toe":
                    if length_u < 0.44:
                        toe_group.add([vertex.index], 1.0, "REPLACE")
                    else:
                        foot_group.add([vertex.index], 1.0, "REPLACE")
                else:
                    foot_group.add([vertex.index], 1.0 - toe_weight, "REPLACE")
                    if toe_weight > 0.0:
                        toe_group.add([vertex.index], toe_weight, "REPLACE")
        modifier = shoe.modifiers.new("ActorCartoonSneakerArmature", "ARMATURE")
        modifier.object = armature
        shoe["assetslab_clothing_type"] = "reference_footwear"
        shoe["assetslab_reference_source"] = "cartoon-sneakers-stylized-3d-shoes.zip"
        shoe["assetslab_binding"] = "nearest_actor_surface_weights" if weight_mode == "nearest_actor" else f"CC_Base_{side}_Foot + CC_Base_{side}_ToeBase"
        shoe["assetslab_fit_status"] = "review_required"
        created.append(shoe)
    return created


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    scene = bpy.context.scene
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if actor is None or armature is None:
        raise RuntimeError("actor blend must contain Actor mesh and Armature")
    if not bpy.ops.import_scene.fbx.poll():
        raise RuntimeError("FBX importer is unavailable")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(options.reference_fbx.resolve()), automatic_bone_orientation=False)
    imported = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    by_name = {obj.name: obj for obj in imported}
    if not set(RIGHT_PARTS).issubset(by_name) or not set(LEFT_PARTS).issubset(by_name):
        raise RuntimeError(f"FBX parts missing; imported={sorted(by_name)}")
    right_sources = [by_name[name] for name in RIGHT_PARTS]
    left_sources = [by_name[name] for name in LEFT_PARTS]
    ref_min, ref_max = bounds(right_sources)
    collection = bpy.data.collections.new("ActorCartoonSneakers")
    scene.collection.children.link(collection)
    for source in imported:
        source.hide_render = True
        source.hide_viewport = True
    targets = {side: actor_foot_target(actor, side, options.toe_extra, options.heel_extra, options.extra_width, options.extra_height, options.radial_width_scale, options.radial_height_scale) for side in ("L", "R")}
    created = []
    created.extend(create_shoe_parts(right_sources, ref_min, ref_max, targets["L"], "L", armature, actor, collection, options.toe_radial_width_scale, options.toe_radial_height_scale, options.toe_zone_end, options.weight_mode))
    created.extend(create_shoe_parts(right_sources, ref_min, ref_max, targets["R"], "R", armature, actor, collection, options.toe_radial_width_scale, options.toe_radial_height_scale, options.toe_zone_end, options.weight_mode))
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    frames = render_review(scene, output, actor, created[0], options.resolution)
    blend_path = output / f"{output.name}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    manifest = {
        "schema": "assetslab_actor_cartoon_sneaker_fbx_v1",
        "source_reference_fbx": str(options.reference_fbx.resolve()),
        "source_parts": list(RIGHT_PARTS),
        "source_pair_parts": {"right": list(RIGHT_PARTS), "left": list(LEFT_PARTS)},
        "construction": "FBX cartoon sneaker parts transformed to Actor foot envelope and bound to Foot/ToeBase",
        "fit_parameters": {
            "toe_extra": options.toe_extra,
            "heel_extra": options.heel_extra,
            "extra_width": options.extra_width,
            "extra_height": options.extra_height,
            "radial_width_scale": options.radial_width_scale,
            "radial_height_scale": options.radial_height_scale,
            "toe_radial_width_scale": options.toe_radial_width_scale,
            "toe_radial_height_scale": options.toe_radial_height_scale,
            "toe_zone_end": options.toe_zone_end,
            "weight_mode": options.weight_mode,
        },
        "reference_bounds": {"min": list(ref_min), "max": list(ref_max)},
        "actor_targets": targets,
        "created_objects": [obj.name for obj in created],
        "rig_status": "nearest_actor_surface_weights_with_armature_modifiers" if options.weight_mode == "nearest_actor" else "foot_and_toebase_armature_modifiers",
        "texture_status": "embedded_fbx_materials_uv_present_no_external_texture_pack",
        "frames": frames,
        "status": "review_required",
        "candidate_blend": str(blend_path),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "HUMAN_REVIEW.md").write_text(
        "# Human review: Actor cartoon sneaker FBX v1\n\n"
        "Status: `review_required`\n\n"
        "Review toe coverage, sole contact, ankle opening, left/right symmetry, "
        "and movement. This reference has embedded FBX materials and UVs but no "
        "external texture package or armature.\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
