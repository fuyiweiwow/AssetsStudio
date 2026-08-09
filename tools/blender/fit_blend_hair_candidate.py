"""Append one hair object from a Blend and fit it to the current chibi actor."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_hair_style_candidate as fit_tools


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--hair-source-blend", required=True, type=Path)
    parser.add_argument("--hair-object")
    parser.add_argument(
        "--hair-objects",
        nargs="+",
        help="multiple source mesh objects to join into one hairstyle before fitting",
    )
    parser.add_argument(
        "--source-anchor-object",
        help="optional companion head object used to preserve source hair-to-head alignment",
    )
    parser.add_argument(
        "--normalize-source-component-layout",
        action="store_true",
        help="move numbered bangs/side/back variants onto the source's assembled set-01 layout",
    )
    parser.add_argument(
        "--normalize-components-to-head",
        action="store_true",
        help="reassemble source-grid components around the companion source head",
    )
    parser.add_argument("--texture-root", type=Path)
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--q-height-ratio", type=float, default=1.15)
    parser.add_argument("--width-ratio", type=float, default=1.08)
    parser.add_argument("--add-actor-cap", action="store_true")
    parser.add_argument(
        "--rear-scalp-cap",
        action="store_true",
        help="limit the cap to the ear-side and rear scalp; leave the forehead uncovered",
    )
    parser.add_argument(
        "--surface-fit-cap",
        action="store_true",
        help="smooth and shrinkwrap the actor-shaped scalp cap back to the actor head",
    )
    parser.add_argument(
        "--lattice-right-front",
        action="store_true",
        help="apply a small local lattice correction to the front-right hairline",
    )
    parser.add_argument(
        "--add-right-hairline-patch",
        action="store_true",
        help="add a small actor-surface hairline patch on the front-right scalp",
    )
    parser.add_argument(
        "--add-smooth-scalp-cap",
        action="store_true",
        help="add a smooth Q-style ellipsoid scalp cap under the imported hair",
    )
    parser.add_argument(
        "--shrinkwrap-hair",
        action="store_true",
        help="shrinkwrap the imported hair shell toward the actor head",
    )
    parser.add_argument(
        "--add-source-scalp-cap",
        action="store_true",
        help="use the companion source head's upper surface as a fitted hair cap",
    )
    parser.add_argument(
        "--add-side-locks",
        action="store_true",
        help="add two narrow, stylized side locks to close small actor-side gaps",
    )
    parser.add_argument(
        "--paint-side-scalp",
        action="store_true",
        help="assign hair color to a narrow side/rear scalp region on the actor mesh",
    )
    parser.add_argument("--cap-bottom-offset", type=float, default=0.64)
    parser.add_argument("--cap-surface-offset", type=float, default=0.025)
    parser.add_argument("--rotation-z", type=float, default=0.0)
    parser.add_argument("--color", nargs=4, type=float, default=(0.12, 0.045, 0.025, 1.0))
    parser.add_argument("--keep-source-materials", action="store_true")
    return parser.parse_args(argv)


def append_object(
    source_blend: Path,
    object_name: str,
    scene_name: str = "HairCandidate_Blend",
) -> bpy.types.Object:
    with bpy.data.libraries.load(str(source_blend.resolve()), link=False) as (data_from, data_to):
        if object_name not in data_from.objects:
            raise RuntimeError(f"source blend is missing object: {object_name}")
        data_to.objects = [object_name]
    source = next((obj for obj in data_to.objects if obj is not None), None)
    if source is None:
        raise RuntimeError("hair object could not be appended")
    bpy.context.scene.collection.objects.link(source)
    source.name = scene_name
    return source


def _bounds_center(obj: bpy.types.Object) -> Vector:
    low, high = fit_tools.bounds(obj)
    return (low + high) * 0.5


def normalize_source_component_layout(
    source_blend: Path,
    parts: list[bpy.types.Object],
) -> None:
    """Undo the source file's presentation-grid offsets for numbered variants.

    Chloe's source file lays individual variants out in a large grid, while
    the *_01 objects form the assembled hairstyle around Chloe_head_dummy.
    Align each selected variant's bounding-box center to its corresponding
    *_01 component center before joining the parts.
    """
    references: dict[str, bpy.types.Object] = {}
    for part in parts:
        if part.name.endswith("_01"):
            continue
        for prefix in ("Chloe_hair_bangs", "Chloe_hair_side", "Chloe_hair_back"):
            if part.name.startswith(prefix):
                reference_name = f"{prefix}_01"
                references.setdefault(
                    reference_name,
                    append_object(source_blend, reference_name, f"HairCandidate_Reference_{reference_name}"),
                )
                break
    for reference in references.values():
        bake_source_transform(reference)
    try:
        for part in parts:
            prefix = next(
                (value for value in ("Chloe_hair_bangs", "Chloe_hair_side", "Chloe_hair_back") if part.name.startswith(value)),
                None,
            )
            if prefix is None or part.name.endswith("_01"):
                continue
            reference = references[f"{prefix}_01"]
            part.location += _bounds_center(reference) - _bounds_center(part)
    finally:
        for reference in references.values():
            bpy.data.objects.remove(reference, do_unlink=True)


def normalize_components_to_head(
    parts: list[bpy.types.Object],
    source_anchor: bpy.types.Object,
) -> None:
    """Move catalog-grid components into a common source-head layout.

    Some hair kits keep base, fringe, sideburn and back pieces in separate
    presentation rows. Their individual source positions are not assembly
    coordinates, so place each selected piece around the source head before
    joining them. The small category offsets preserve a natural layered order.
    """
    anchor_center = _bounds_center(source_anchor)
    for part in parts:
        target = anchor_center.copy()
        if "_base_" in part.name:
            target.z -= 0.30
        elif "_bangs_" in part.name:
            target.y -= 0.08
            target.z += 0.02
        elif "_side_" in part.name:
            target.y += 0.015
            target.z -= 0.14
        elif "_back_" in part.name:
            target.z -= 0.01
        part.location += target - _bounds_center(part)


def append_hair_group(
    source_blend: Path,
    object_names: list[str],
    normalize_components: bool = False,
    source_anchor: bpy.types.Object | None = None,
    normalize_to_head: bool = False,
) -> bpy.types.Object:
    parts = [
        append_object(source_blend, name, name)
        for name in object_names
    ]
    for part in parts:
        bake_source_transform(part)
    if normalize_components:
        normalize_source_component_layout(source_blend, parts)
    if normalize_to_head:
        if source_anchor is None:
            raise RuntimeError("--normalize-components-to-head requires --source-anchor-object")
        normalize_components_to_head(parts, source_anchor)
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    parts[0].name = "HairCandidate_Blend"
    return parts[0]


def bake_source_transform(obj: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    if obj.parent is not None:
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def repair_texture_paths(obj: bpy.types.Object, texture_root: Path | None) -> list[str]:
    if texture_root is None:
        return []
    repaired: list[str] = []
    for material in obj.data.materials:
        if material is None or not material.use_nodes:
            continue
        for node in material.node_tree.nodes:
            if node.type != "TEX_IMAGE" or node.image is None:
                continue
            candidate = texture_root / Path(node.image.filepath).name
            if not candidate.is_file():
                continue
            image = bpy.data.images.load(str(candidate.resolve()), check_existing=False)
            image.pack()
            node.image = image
            repaired.append(str(candidate.resolve()))
    return repaired


def fit_to_actor(
    tile: bpy.types.Object,
    armature: bpy.types.Object,
    body: bpy.types.Object,
    options: argparse.Namespace,
    source_anchor: bpy.types.Object | None = None,
) -> dict[str, object]:
    bake_source_transform(tile)
    # Blend hair objects often carry authored location, rotation and non-uniform
    # scale. Bake the complete source transform first; fitting only the scale
    # leaves most of the cap inside the actor after it is parented to the head.
    if tile.parent is not None:
        world = tile.matrix_world.copy()
        tile.parent = None
        tile.matrix_world = world
    if options.rotation_z:
        tile.rotation_euler.z += math.radians(options.rotation_z)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    low, high = fit_tools.bounds(tile)
    source_hair_center = (low + high) * 0.5
    source_anchor_center = None
    if source_anchor is not None:
        anchor_low, anchor_high = fit_tools.bounds(source_anchor)
        source_anchor_center = (anchor_low + anchor_high) * 0.5
    head_center, head_width, head_top = fit_tools.head_target(armature, body)
    current_width = max(high.x - low.x, 0.001)
    fit_scale = (head_width * options.width_ratio) / current_width
    tile.scale = (fit_scale, fit_scale, fit_scale)
    bpy.context.view_layer.update()
    low, high = fit_tools.bounds(tile)
    current_height = max(high.z - low.z, 0.001)
    max_height = max(head_width * options.q_height_ratio, 0.001)
    q_height_scale = min(1.0, max_height / current_height)
    tile.scale.z *= q_height_scale
    bpy.context.view_layer.update()
    low, high = fit_tools.bounds(tile)
    desired_xy = Vector((head_center.x, head_center.y, 0.0))
    if source_anchor_center is not None:
        relative_xy = (source_hair_center - source_anchor_center) * fit_scale
        desired_xy += Vector((relative_xy.x, relative_xy.y, 0.0))
    tile.location += Vector(
        (
            desired_xy.x - (low.x + high.x) * 0.5,
            desired_xy.y - (low.y + high.y) * 0.5,
            head_top + 0.06 - high.z,
        )
    )
    bpy.context.view_layer.update()
    world = tile.matrix_world.copy()
    tile.parent = armature
    tile.parent_type = "BONE"
    tile.parent_bone = fit_tools.HEAD_BONE
    tile.matrix_world = world
    return {
        "fit_scale": fit_scale,
        "q_height_ratio": options.q_height_ratio,
        "width_ratio": options.width_ratio,
        "q_height_scale": q_height_scale,
        "rotation_z_degrees": options.rotation_z,
        "dimensions": [float(value) for value in tile.dimensions],
        "parent_bone": fit_tools.HEAD_BONE,
        "head_width": head_width,
        "head_top": head_top,
        "source_anchor": source_anchor.name if source_anchor else None,
    }


def create_actor_cap(
    armature: bpy.types.Object,
    body: bpy.types.Object,
    head_top: float,
    bottom_offset: float,
    surface_offset: float,
    material: bpy.types.Material,
    surface_fit: bool = False,
    rear_only: bool = False,
) -> bpy.types.Object:
    """Create a thin, actor-shaped cap to hide source-hair scalp gaps."""
    body.data.update()
    body_to_world = body.matrix_world
    normal_to_world = body.matrix_world.to_3x3()
    bottom = head_top - bottom_offset
    selected_faces = []
    for polygon in body.data.polygons:
        points = [body_to_world @ body.data.vertices[index].co for index in polygon.vertices]
        center = sum(points, Vector()) / len(points)
        if rear_only:
            # Front is -Y. Keep the forehead clear and begin around the ears:
            # side surfaces are accepted only after they move behind the eye
            # plane, while the central rear surface wraps continuously.
            in_ear_side = abs(center.x) >= 0.58 and center.y >= -0.34
            in_rear = center.y >= -0.08
            if not (in_ear_side or in_rear):
                continue
            if center.z < bottom:
                continue
        elif not any(point.z >= bottom for point in points):
            continue
        selected_faces.append(polygon)
    if not selected_faces:
        raise RuntimeError(f"actor cap selection is empty at z={bottom}")
    used = sorted({index for polygon in selected_faces for index in polygon.vertices})
    index_map = {old: new for new, old in enumerate(used)}
    vertices = []
    for old in used:
        vertex = body.data.vertices[old]
        point = body_to_world @ vertex.co
        # The source actor has a few inconsistent local normals.  For this
        # camera-facing patch, use an explicit front offset instead of
        # trusting the mesh normal and accidentally pushing the patch inside.
        front_offset = max(0.10, surface_offset * 4.0)
        vertices.append(tuple(point + Vector((0.0, -front_offset, surface_offset * 0.2))))
    faces = [tuple(index_map[index] for index in polygon.vertices) for polygon in selected_faces]
    mesh = bpy.data.meshes.new("ActorHairCapMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    cap = bpy.data.objects.new("HairCandidate_ActorCap", mesh)
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
    if surface_fit:
        smooth = cap.modifiers.new("HairCapSurfaceSmooth", "SUBSURF")
        smooth.subdivision_type = "CATMULL_CLARK"
        smooth.levels = 1
        smooth.render_levels = 1
        shrink = cap.modifiers.new("HairCapShrinkwrap", "SHRINKWRAP")
        shrink.target = body
        shrink.wrap_method = "NEAREST_SURFACEPOINT"
        shrink.wrap_mode = "OUTSIDE_SURFACE"
        shrink.offset = surface_offset
    return cap


def create_right_front_lattice(tile: bpy.types.Object) -> bpy.types.Object:
    """Gently move only the front-right hair mass toward the head surface."""
    low, high = fit_tools.bounds(tile)
    center = (low + high) * 0.5
    half = (high - low) * 0.5
    lattice_data = bpy.data.lattices.new("HairCandidate_RightFrontLatticeData")
    lattice_data.points_u = 4
    lattice_data.points_v = 4
    lattice_data.points_w = 5
    lattice = bpy.data.objects.new("HairCandidate_RightFrontLattice", lattice_data)
    bpy.context.scene.collection.objects.link(lattice)
    lattice.location = center
    lattice.scale = (half.x * 1.08, half.y * 1.08, half.z * 1.08)
    for point in lattice_data.points:
        # Lattice coordinates are normalized to approximately [-1, 1].
        # The actor camera convention is front=-Y, right=+X.
        if point.co.x > 0.05 and point.co.y < -0.05:
            right_weight = min(1.0, max(0.0, (point.co.x + 1.0) * 0.55))
            front_weight = min(1.0, max(0.0, (-point.co.y + 1.0) * 0.55))
            weight = right_weight * front_weight
            coordinate = point.co.copy()
            coordinate.y -= 0.12 * weight
            coordinate.x += 0.035 * weight
            coordinate.z -= 0.025 * weight
            point.co_deform = coordinate
    modifier = tile.modifiers.new("HairlineRightFrontLattice", "LATTICE")
    modifier.object = lattice
    modifier.strength = 0.72
    return lattice


def create_right_hairline_patch(
    armature: bpy.types.Object,
    body: bpy.types.Object,
    head_top: float,
    surface_offset: float,
    material: bpy.types.Material,
) -> bpy.types.Object | None:
    """Copy a bounded scalp region so a foreign hairline cannot expose the head."""
    body_to_world = body.matrix_world
    normal_to_world = body.matrix_world.to_3x3()
    selected_faces = []
    for polygon in body.data.polygons:
        points = [body_to_world @ body.data.vertices[index].co for index in polygon.vertices]
        center = sum(points, Vector()) / len(points)
        if center.x > 0.24 and center.y < -0.12 and center.z > head_top - 0.58:
            selected_faces.append(polygon)
    if not selected_faces:
        return None
    used = sorted({index for polygon in selected_faces for index in polygon.vertices})
    index_map = {old: new for new, old in enumerate(used)}
    vertices = []
    for old in used:
        vertex = body.data.vertices[old]
        point = body_to_world @ vertex.co
        normal = (normal_to_world @ vertex.normal).normalized()
        vertices.append(tuple(point + normal * surface_offset))
    faces = [tuple(index_map[index] for index in polygon.vertices) for polygon in selected_faces]
    mesh = bpy.data.meshes.new("ActorRightHairlinePatchMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    patch = bpy.data.objects.new("HairCandidate_RightHairlinePatch", mesh)
    bpy.context.scene.collection.objects.link(patch)
    patch.data.materials.append(material)
    for polygon in patch.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    world = patch.matrix_world.copy()
    patch.parent = armature
    patch.parent_type = "BONE"
    patch.parent_bone = fit_tools.HEAD_BONE
    patch.matrix_world = world
    return patch


def create_smooth_scalp_cap(
    armature: bpy.types.Object,
    head_center: Vector,
    head_width: float,
    head_top: float,
    material: bpy.types.Material,
) -> bpy.types.Object:
    """Create a smooth, open ellipsoid cap with a curved front hairline."""
    cap_center = Vector((head_center.x, head_center.y - 0.015, head_top - 0.50))
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=32,
        ring_count=16,
        radius=1.0,
        location=cap_center,
    )
    cap = bpy.context.object
    cap.name = "HairCandidate_SmoothScalpCap"
    cap.scale = (head_width * 0.66, head_width * 0.50, 0.68)
    bpy.context.view_layer.objects.active = cap
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bottom = head_top - 0.64
    mesh = cap.data
    delete_faces = [
        face
        for face in mesh.polygons
        if (cap.matrix_world @ face.center).z < bottom
    ]
    if delete_faces:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.object.mode_set(mode="OBJECT")
        for face in delete_faces:
            face.select = True
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.delete(type="ONLY_FACE")
        bpy.ops.object.mode_set(mode="OBJECT")
    cap.data.materials.append(material)
    for polygon in cap.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    world = cap.matrix_world.copy()
    cap.parent = armature
    cap.parent_type = "BONE"
    cap.parent_bone = fit_tools.HEAD_BONE
    cap.matrix_world = world
    return cap


def add_hair_shrinkwrap(tile: bpy.types.Object, body: bpy.types.Object) -> bpy.types.Modifier:
    modifier = tile.modifiers.new("HairCandidateHeadShrinkwrap", "SHRINKWRAP")
    modifier.target = body
    modifier.wrap_method = "NEAREST_SURFACEPOINT"
    modifier.wrap_mode = "OUTSIDE_SURFACE"
    modifier.offset = 0.045
    return modifier


def create_source_scalp_cap(
    source_head: bpy.types.Object,
    armature: bpy.types.Object,
    fitted_hair: bpy.types.Object,
    head_top: float,
    material: bpy.types.Material,
) -> bpy.types.Object:
    """Reuse the source head's upper surface, transformed with its hair pair."""
    cap = source_head.copy()
    cap.data = source_head.data.copy()
    cap.name = "HairCandidate_SourceScalpCap"
    bpy.context.scene.collection.objects.link(cap)
    cap.hide_viewport = False
    cap.hide_render = False
    cap.matrix_world = fitted_hair.matrix_world.copy()
    cap.scale.x *= 1.18
    cap.scale.y *= 1.10
    cap.location.y -= 0.055
    bottom = head_top - 0.58
    selected_faces = [
        polygon
        for polygon in cap.data.polygons
        if (cap.matrix_world @ polygon.center).z >= bottom
    ]
    if not selected_faces:
        raise RuntimeError("source scalp cap selection is empty")
    selected = {polygon.index for polygon in selected_faces}
    bpy.context.view_layer.objects.active = cap
    bpy.ops.object.select_all(action="DESELECT")
    cap.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for polygon in cap.data.polygons:
        polygon.select = polygon.index not in selected
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="ONLY_FACE")
    bpy.ops.object.mode_set(mode="OBJECT")
    cap.data.materials.clear()
    cap.data.materials.append(material)
    for polygon in cap.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    world = cap.matrix_world.copy()
    cap.parent = armature
    cap.parent_type = "BONE"
    cap.parent_bone = fit_tools.HEAD_BONE
    cap.matrix_world = world
    return cap


def create_side_lock(
    armature: bpy.types.Object,
    material: bpy.types.Material,
    side: float,
) -> bpy.types.Object:
    """Create one tapered low-poly lock behind the imported front strands."""
    # The actor's eyes occupy roughly z=1.77..2.38.  These locks stay just
    # outside the eye silhouette and close only the scalp-colored slits.
    rings = [
        (0.50, -0.785, 2.88, 0.060),
        (0.57, -0.805, 2.68, 0.075),
        (0.63, -0.770, 2.43, 0.055),
    ]
    vertices = []
    for center_x, front_y, z, width in rings:
        x = side * center_x
        vertices.extend(
            [
                (x - side * width, front_y - 0.012, z),
                (x + side * width, front_y - 0.012, z),
                (x + side * width, front_y + 0.052, z),
                (x - side * width, front_y + 0.052, z),
            ]
        )
    faces = []
    for ring in range(len(rings) - 1):
        a = ring * 4
        b = (ring + 1) * 4
        faces.extend(
            [
                (a + 0, b + 0, b + 1, a + 1),
                (a + 3, a + 2, b + 2, b + 3),
                (a + 0, a + 3, b + 3, b + 0),
                (a + 1, b + 1, b + 2, a + 2),
            ]
        )
    faces.extend([(0, 1, 2, 3), (8, 11, 10, 9)])
    mesh = bpy.data.meshes.new(f"SideLockMesh_{'R' if side > 0 else 'L'}")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    lock = bpy.data.objects.new(
        f"HairCandidate_SideLock_{'R' if side > 0 else 'L'}", mesh
    )
    bpy.context.scene.collection.objects.link(lock)
    lock.data.materials.append(material)
    for polygon in lock.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    bevel = lock.modifiers.new("SideLockSoftEdge", "BEVEL")
    bevel.width = 0.012
    bevel.segments = 2
    bevel.limit_method = "ANGLE"
    world = lock.matrix_world.copy()
    lock.parent = armature
    lock.parent_type = "BONE"
    lock.parent_bone = fit_tools.HEAD_BONE
    lock.matrix_world = world
    return lock


def paint_side_scalp(
    body: bpy.types.Object,
    head_top: float,
    material: bpy.types.Material,
) -> int:
    """Use the actor's own surface as an invisible-under-hair color layer."""
    try:
        material_index = body.data.materials[:].index(material)
    except ValueError:
        body.data.materials.append(material)
        material_index = len(body.data.materials) - 1
    body_to_world = body.matrix_world
    painted = 0
    for polygon in body.data.polygons:
        points = [body_to_world @ body.data.vertices[index].co for index in polygon.vertices]
        center = sum(points, Vector()) / len(points)
        # Leave the frontal forehead untouched. Begin around the ear plane and
        # continue over the lateral/rear scalp only.
        in_lateral = abs(center.x) >= 0.45 and center.y >= -0.68
        in_rear = center.y >= -0.04
        if center.z >= head_top - 0.60 and (in_lateral or in_rear):
            polygon.material_index = material_index
            painted += 1
    return painted


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    armature = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
    body = next(obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("ChibiBase"))
    source_anchor = None
    if options.source_anchor_object:
        source_anchor = append_object(
            options.hair_source_blend,
            options.source_anchor_object,
            "HairCandidate_SourceHeadAnchor",
        )
        bake_source_transform(source_anchor)
        source_anchor.hide_render = True
        source_anchor.hide_viewport = True
    hair_names = options.hair_objects or ([options.hair_object] if options.hair_object else [])
    if not hair_names:
        raise RuntimeError("one of --hair-object or --hair-objects is required")
    tile = append_hair_group(
        options.hair_source_blend,
        hair_names,
        options.normalize_source_component_layout,
        source_anchor,
        options.normalize_components_to_head,
    )
    repaired_images = repair_texture_paths(tile, options.texture_root.resolve() if options.texture_root else None)
    fit = fit_to_actor(tile, armature, body, options, source_anchor)
    cap = None
    lattice = None
    patch = None
    smooth_cap = None
    shrinkwrap = None
    source_cap = None
    side_locks = []
    painted_scalp_faces = 0
    if not options.keep_source_materials:
        material = fit_tools.make_material(tuple(options.color))
        tile.data.materials.clear()
        tile.data.materials.append(material)
        for polygon in tile.data.polygons:
            polygon.material_index = 0
            polygon.use_smooth = True
        if options.add_actor_cap or options.rear_scalp_cap:
            head_top = float(fit["head_top"])
            cap = create_actor_cap(
                armature,
                body,
                head_top,
                options.cap_bottom_offset,
                options.cap_surface_offset,
                material,
                options.surface_fit_cap,
                options.rear_scalp_cap,
            )
        if options.lattice_right_front:
            lattice = create_right_front_lattice(tile)
        if options.add_right_hairline_patch:
            patch = create_right_hairline_patch(
                armature,
                body,
                float(fit["head_top"]),
                options.cap_surface_offset,
                material,
            )
        if options.add_smooth_scalp_cap:
            head_center, head_width, head_top = fit_tools.head_target(armature, body)
            smooth_cap = create_smooth_scalp_cap(
                armature,
                head_center,
                head_width,
                head_top,
                material,
            )
        if options.shrinkwrap_hair:
            shrinkwrap = add_hair_shrinkwrap(tile, body)
        if options.add_source_scalp_cap:
            if source_anchor is None:
                raise RuntimeError("--add-source-scalp-cap requires --source-anchor-object")
            source_cap = create_source_scalp_cap(
                source_anchor,
                armature,
                tile,
                float(fit["head_top"]),
                material,
            )
            bpy.data.objects.remove(source_anchor, do_unlink=True)
            source_anchor = None
        if options.add_side_locks:
            side_locks = [
                create_side_lock(armature, material, -1.0),
                create_side_lock(armature, material, 1.0),
            ]
        if options.paint_side_scalp:
            painted_scalp_faces = paint_side_scalp(
                body,
                float(fit["head_top"]),
                material,
            )
    fit_tools.configure_render(bpy.context.scene)
    output_dir = options.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    renders = fit_tools.render_views(bpy.context.scene, output_dir, body, tile)
    options.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output_blend.resolve()))
    manifest = {
        "schema": "assetslab_chibi_blend_hair_candidate_v1",
        "source_blend": str(options.hair_source_blend.resolve()),
        "source_object": options.hair_object,
        "source_objects": hair_names,
        "source_anchor_object": options.source_anchor_object,
        "actor_blend": str(options.actor_blend.resolve()),
        "object": tile.name,
        "actor_cap": cap.name if cap else None,
        "rear_scalp_cap": options.rear_scalp_cap,
        "lattice": lattice.name if lattice else None,
        "right_hairline_patch": patch.name if patch else None,
        "smooth_scalp_cap": smooth_cap.name if smooth_cap else None,
        "hair_shrinkwrap": shrinkwrap.name if shrinkwrap else None,
        "source_scalp_cap": source_cap.name if source_cap else None,
        "side_locks": [lock.name for lock in side_locks],
        "painted_scalp_faces": painted_scalp_faces,
        "vertices": len(tile.data.vertices),
        "polygons": len(tile.data.polygons),
        "repaired_images": repaired_images,
        "fit": fit,
        "renders": renders,
        "status": "attached_candidate_review_required",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"CHIBI_BLEND_HAIR_CANDIDATE_PASS vertices={len(tile.data.vertices)} output={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
