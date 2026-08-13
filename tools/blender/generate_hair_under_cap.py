"""Generate a reproducible Actor-derived hair under-cap candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hair_fit_support as fit_tools


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--profile", choices=("rear_side_top", "full_upper_head", "seed04_scalp_base"), default="rear_side_top")
    parser.add_argument("--variant", choices=("conservative", "coverage"), default="coverage")
    parser.add_argument("--bottom-offset", type=float, default=0.64)
    parser.add_argument("--surface-offset", type=float, default=0.018)
    parser.add_argument("--smooth-levels", type=int, default=1)
    parser.add_argument("--color", nargs=4, type=float, default=(0.035, 0.012, 0.008, 1.0))
    return parser.parse_args(argv)


def select_cap_faces(body: bpy.types.Object, head_top: float, bottom: float, profile: str) -> list[bpy.types.MeshPolygon]:
    body_to_world = body.matrix_world
    selected: list[bpy.types.MeshPolygon] = []
    for polygon in body.data.polygons:
        points = [body_to_world @ body.data.vertices[index].co for index in polygon.vertices]
        center = sum(points, Vector()) / len(points)
        if center.z < bottom and not any(point.z >= bottom for point in points):
            continue
        if profile == "rear_side_top":
            in_side = abs(center.x) >= 0.52 and center.y >= -0.36
            in_rear = center.y >= -0.08
            if not (in_side or in_rear):
                continue
        selected.append(polygon)
    if not selected:
        raise RuntimeError(f"under-cap face selection is empty at z={bottom}")
    return selected


def create_under_cap(
    armature: bpy.types.Object,
    body: bpy.types.Object,
    head_top: float,
    bottom_offset: float,
    surface_offset: float,
    profile: str,
    variant: str,
    material: bpy.types.Material,
    smooth_levels: int,
) -> tuple[bpy.types.Object, dict[str, int | float]]:
    if bottom_offset <= 0 or surface_offset <= 0:
        raise RuntimeError("under-cap offsets must be positive")
    body.data.update()
    if profile == "full_upper_head":
        return create_smooth_under_cap(
            armature,
            body,
            head_top,
            bottom_offset,
            surface_offset,
            material,
        )
    if profile == "seed04_scalp_base":
        return create_seed04_scalp_base(
            armature,
            body,
            head_top,
            bottom_offset,
            surface_offset,
            material,
            variant,
        )
    head_center, _, _ = fit_tools.head_target(armature, body)
    radial_center = Vector((head_center.x, head_center.y, head_top - 0.40))
    selected_faces = select_cap_faces(body, head_top, head_top - bottom_offset, profile)
    used = sorted({index for polygon in selected_faces for index in polygon.vertices})
    index_map = {old: new for new, old in enumerate(used)}
    body_to_world = body.matrix_world
    normal_to_world = body.matrix_world.to_3x3()
    normal_by_vertex: dict[int, Vector] = {index: Vector() for index in used}
    for polygon in selected_faces:
        for index in polygon.vertices:
            normal_by_vertex[index] += polygon.normal
    vertices = []
    for index in used:
        point = body_to_world @ body.data.vertices[index].co
        normal = normal_to_world @ normal_by_vertex[index]
        if normal.length <= 1e-6:
            normal = point - radial_center
        normal.normalize()
        radial = point - radial_center
        if normal.dot(radial) < 0:
            normal.negate()
        vertices.append(tuple(point + normal * surface_offset))
    faces = [tuple(index_map[index] for index in polygon.vertices) for polygon in selected_faces]
    mesh = bpy.data.meshes.new("HairUnderCapMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    cap = bpy.data.objects.new("HairUnderCapCandidate", mesh)
    bpy.context.scene.collection.objects.link(cap)
    cap.data.materials.append(material)
    for polygon in cap.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    solidify = cap.modifiers.new("HairUnderCapThickness", "SOLIDIFY")
    solidify.thickness = 0.012
    solidify.offset = 1.0
    if profile == "full_upper_head" and smooth_levels > 0:
        smooth = cap.modifiers.new("HairUnderCapSurfaceSmooth", "SUBSURF")
        smooth.subdivision_type = "CATMULL_CLARK"
        smooth.levels = smooth_levels
        smooth.render_levels = smooth_levels
        shrink = cap.modifiers.new("HairUnderCapSurfaceFit", "SHRINKWRAP")
        shrink.target = body
        shrink.wrap_method = "NEAREST_SURFACEPOINT"
        shrink.wrap_mode = "OUTSIDE_SURFACE"
        shrink.offset = surface_offset
    world = cap.matrix_world.copy()
    cap.parent = armature
    cap.parent_type = "BONE"
    cap.parent_bone = fit_tools.HEAD_BONE
    cap.matrix_world = world
    cap["assetsstudio_role"] = "hair_under_cap"
    cap["assetsstudio_profile"] = profile
    cap["assetsstudio_source"] = "actor_head_surface"
    return cap, {
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "selected_faces": len(selected_faces),
        "surface_offset": surface_offset,
    }


def create_smooth_under_cap(
    armature: bpy.types.Object,
    body: bpy.types.Object,
    head_top: float,
    bottom_offset: float,
    surface_offset: float,
    material: bpy.types.Material,
) -> tuple[bpy.types.Object, dict[str, int | float]]:
    """Create a continuous scalp volume for hiding gaps under outer hair."""
    head_center, head_width, _ = fit_tools.head_target(armature, body)
    cap_center = Vector((head_center.x, head_center.y - 0.015, head_top - 0.50))
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=48,
        ring_count=24,
        radius=1.0,
        location=cap_center,
    )
    cap = bpy.context.object
    cap.name = "HairUnderCapCandidate"
    # Slightly wider/deeper than the Actor head so gaps between outer hair
    # pieces reveal the same hair-colored under-layer instead of white scalp.
    cap.scale = (head_width * 0.68, head_width * 0.62, 0.72)
    bpy.context.view_layer.objects.active = cap
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    # Keep the sphere closed and continuous. The lower half is hidden inside
    # the Actor head; deleting selected faces here is unstable on some Blender
    # builds and creates an unnecessary open boundary for an under-layer.
    cap.data.materials.append(material)
    for polygon in cap.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    world = cap.matrix_world.copy()
    cap.parent = armature
    cap.parent_type = "BONE"
    cap.parent_bone = fit_tools.HEAD_BONE
    cap.matrix_world = world
    cap["assetsstudio_role"] = "hair_under_cap"
    cap["assetsstudio_profile"] = "full_upper_head_smooth"
    cap["assetsstudio_source"] = "actor_head_bounds_continuous_surface"
    return cap, {
        "vertices": len(cap.data.vertices),
        "polygons": len(cap.data.polygons),
        "selected_faces": len(cap.data.polygons),
        "surface_offset": surface_offset,
    }


def create_seed04_scalp_base(
    armature: bpy.types.Object,
    body: bpy.types.Object,
    head_top: float,
    bottom_offset: float,
    surface_offset: float,
    material: bpy.types.Material,
    variant: str,
) -> tuple[bpy.types.Object, dict[str, int | float]]:
    """Create a seed_04-specific scalp layer from the continuous Actor head.

    The lower boundary is intentionally placed below the visible outer hair
    line. The copied Actor topology remains smooth and animation-safe, while
    the positive normal offset makes it a real coverage layer instead of a
    depth-fighting duplicate of the Actor head.
    """
    body.data.update()
    body_to_world = body.matrix_world
    normal_to_world = body.matrix_world.to_3x3()
    head_center, _, _ = fit_tools.head_target(armature, body)
    radial_center = Vector((head_center.x, head_center.y, head_top - 0.40))
    bottom = head_top - bottom_offset
    selected_faces = []
    for polygon in body.data.polygons:
        points = [body_to_world @ body.data.vertices[index].co for index in polygon.vertices]
        if not any(point.z >= bottom for point in points):
            continue
        center = sum(points, Vector()) / len(points)
        # The conservative variant protects the visible forehead/bangs zone.
        # Front is -Y in the Actor coordinate contract. Keep the crown row so
        # the boundary remains hidden behind the front bangs instead of making
        # the cap stop at the top of the head.
        if variant == "conservative":
            in_front_forehead = center.y < -0.22 and center.z < head_top - 0.18
            if in_front_forehead:
                continue
        selected_faces.append(polygon)
    if not selected_faces:
        raise RuntimeError("seed04 scalp base face selection is empty")
    used = sorted({index for polygon in selected_faces for index in polygon.vertices})
    index_map = {old: new for new, old in enumerate(used)}
    vertices = []
    normal_by_vertex = {index: Vector() for index in used}
    for polygon in selected_faces:
        for index in polygon.vertices:
            normal_by_vertex[index] += polygon.normal
    for index in used:
        point = body_to_world @ body.data.vertices[index].co
        normal = normal_to_world @ normal_by_vertex[index]
        if normal.length <= 1e-6:
            normal = point - radial_center
        if normal.dot(point - radial_center) < 0:
            normal.negate()
        normal.normalize()
        vertices.append(tuple(point + normal * surface_offset))
    faces = [tuple(index_map[index] for index in polygon.vertices) for polygon in selected_faces]
    mesh = bpy.data.meshes.new("HairSeed04ScalpBaseMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    cap = bpy.data.objects.new("HairUnderCapCandidate", mesh)
    bpy.context.scene.collection.objects.link(cap)
    cap.data.materials.append(material)
    for polygon in cap.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    world = cap.matrix_world.copy()
    cap.parent = armature
    cap.parent_type = "BONE"
    cap.parent_bone = fit_tools.HEAD_BONE
    cap.matrix_world = world
    cap["assetsstudio_role"] = "hair_scalp_base"
    cap["assetsstudio_profile"] = "seed04_scalp_base"
    cap["assetsstudio_variant"] = variant
    cap["assetsstudio_hair_style"] = "female_seed_04_bangs04_v2"
    cap["assetsstudio_source"] = "actor_head_surface"
    return cap, {
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "selected_faces": len(selected_faces),
        "surface_offset": surface_offset,
    }


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    armature = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
    body = next(obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("ChibiBase"))
    _, _, head_top = fit_tools.head_target(armature, body)
    material = fit_tools.make_material(tuple(options.color))
    cap, geometry = create_under_cap(
        armature,
        body,
        head_top,
        options.bottom_offset,
        options.surface_offset,
        options.profile,
        options.variant,
        material,
        options.smooth_levels,
    )
    fit_tools.configure_render(bpy.context.scene)
    output_dir = options.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    renders = fit_tools.render_views(bpy.context.scene, output_dir, body, cap)
    options.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output_blend.resolve()))
    manifest = {
        "schema": "assetsstudio_hair_under_cap_v1",
        "status": "candidate",
        "actor_blend": str(options.actor_blend.resolve()),
        "object": cap.name,
        "profile": options.profile,
        "variant": options.variant,
        "binding": {"bone": fit_tools.HEAD_BONE, "web_contract": "single_bone_skin"},
        "geometry": geometry,
        "fit": {"head_top": head_top, "bottom_offset": options.bottom_offset},
        "renders": renders,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"HAIR_UNDER_CAP_PASS profile={options.profile} vertices={geometry['vertices']} output={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
