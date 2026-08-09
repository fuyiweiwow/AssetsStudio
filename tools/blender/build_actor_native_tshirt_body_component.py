"""Build a single Actor-native short-sleeve clothing component.

This experiment deliberately does not import or fit Colin_shirt_short.  It
extracts the Actor's own torso and upper-arm faces into one skinned mesh,
offsets that surface by a small rest-pose clearance, and keeps the original
Actor armature weights.  The sleeve and torso therefore share source topology
and cannot drift as two unrelated garment objects.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_actor_derived_tshirt import make_material, render_review  # noqa: E402


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bottom-z", type=float, default=0.70)
    parser.add_argument("--top-z", type=float, default=1.48)
    parser.add_argument("--torso-half-width", type=float, default=0.50)
    # Projection along the actual Actor upper-arm bone: 0 = shoulder and
    # 1 = elbow.  The earlier 0.48 probe exposed only a shoulder cap on this
    # Actor; 0.80 is the current short-sleeve review default.
    parser.add_argument("--sleeve-fraction", type=float, default=0.80)
    parser.add_argument("--clearance", type=float, default=0.012)
    parser.add_argument("--shell-thickness", type=float, default=0.008)
    parser.add_argument("--resolution", type=int, default=256)
    return parser.parse_args(argv)


def weight(face: bmesh.types.BMFace, actor: bpy.types.Object, groups: set[int]) -> float:
    if not groups:
        return 0.0
    values = []
    for vertex in face.verts:
        values.append(sum(a.weight for a in actor.data.vertices[vertex.index].groups if a.group in groups))
    return sum(values) / max(len(values), 1)


def clean_garment_boundaries(
    bm: bmesh.types.BMesh,
    world_matrix,
    armature: bpy.types.Object,
    bottom_z: float,
    sleeve_fraction: float,
) -> dict[str, int]:
    """Cut clean cuff planes, remove tiny islands, and regularize the hem."""
    stats = {"hem_vertices_flattened": 0, "cuff_vertices_flattened": 0, "tiny_islands_removed": 0}
    inverse = world_matrix.inverted()

    # Trim only faces that were explicitly tagged as sleeve faces. A world-space
    # arm plane is unsafe here because the shoulder and torso share surfaces.
    for side in ("L", "R"):
        upper = armature.data.bones.get(f"CC_Base_{side}_Upperarm")
        twist = armature.data.bones.get(f"CC_Base_{side}_UpperarmTwist02")
        if upper is None or twist is None:
            continue
        shoulder = armature.matrix_world @ upper.head_local
        elbow = armature.matrix_world @ twist.tail_local
        axis_vector = elbow - shoulder
        length = axis_vector.length
        if length <= 0.001:
            continue
        axis = axis_vector.normalized()
        bm.faces.ensure_lookup_table()
        outside = []
        for face in bm.faces:
            if not face.tag:
                continue
            point = world_matrix @ face.calc_center_median()
            if (point.x > 0.02) != (side == "L"):
                continue
            projection = (point - shoulder).dot(axis) / length
            if projection > sleeve_fraction + 0.045:
                outside.append(face)
        if outside:
            stats["cuff_faces_trimmed"] = stats.get("cuff_faces_trimmed", 0) + len(outside)
            bmesh.ops.delete(bm, geom=outside, context="FACES")
        loose = [vertex for vertex in bm.verts if not vertex.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")

    # Remove isolated one-to-three-face fragments left by the face extraction.
    bm.faces.ensure_lookup_table()
    unseen = set(bm.faces)
    tiny = []
    while unseen:
        seed = unseen.pop()
        component = {seed}
        stack = [seed]
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for neighbor in edge.link_faces:
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        component.add(neighbor)
                        stack.append(neighbor)
        if len(component) <= 3:
            tiny.extend(component)
    if tiny:
        stats["tiny_islands_removed"] = len(tiny)
        bmesh.ops.delete(bm, geom=tiny, context="FACES")
        loose = [vertex for vertex in bm.verts if not vertex.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")

    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    boundary = {vertex for edge in bm.edges if len(edge.link_faces) == 1 for vertex in edge.verts}

    # The extracted Actor faces leave an irregular polygonal hem. Flatten only
    # the lower torso boundary to a common world-Z plane; this preserves the
    # Actor silhouette above the hem while removing the saw-tooth cut.
    for vertex in boundary:
        point = world_matrix @ vertex.co
        if abs(point.z - bottom_z) <= 0.16 and abs(point.x) <= 0.62:
            point.z = bottom_z
            vertex.co = inverse @ point
            stats["hem_vertices_flattened"] += 1

    # A short sleeve cuff is a cross-section perpendicular to the upper-arm
    # bone. Project only boundary vertices near the selected sleeve endpoint;
    # shoulder and neck boundaries are outside this projection window.
    for side in ("L", "R"):
        upper = armature.data.bones.get(f"CC_Base_{side}_Upperarm")
        twist = armature.data.bones.get(f"CC_Base_{side}_UpperarmTwist02")
        if upper is None or twist is None:
            continue
        shoulder = armature.matrix_world @ upper.head_local
        elbow = armature.matrix_world @ twist.tail_local
        axis_vector = elbow - shoulder
        length = axis_vector.length
        if length <= 0.001:
            continue
        axis = axis_vector.normalized()
        cuff = shoulder + axis_vector * sleeve_fraction
        cuff_boundary = set()
        for edge in bm.edges:
            linked = list(edge.link_faces)
            sleeve_linked = [face for face in linked if face.tag]
            if not sleeve_linked:
                continue
            # A cuff edge is either open or borders a non-sleeve torso face.
            if len(linked) == 1 or len(sleeve_linked) != len(linked):
                cuff_boundary.update(edge.verts)
        for vertex in cuff_boundary:
            point = world_matrix @ vertex.co
            if (point.x > 0.02) != (side == "L"):
                continue
            projection = (point - shoulder).dot(axis) / length
            if sleeve_fraction - 0.14 <= projection <= sleeve_fraction + 0.10:
                point = point - axis * ((point - cuff).dot(axis))
                vertex.co = inverse @ point
                stats["cuff_vertices_flattened"] += 1
    bm.normal_update()
    return stats


def build_component(actor: bpy.types.Object, armature: bpy.types.Object, options: argparse.Namespace) -> tuple[bpy.types.Object, dict[str, int]]:
    output_collection = bpy.data.collections.new("ActorNativeClothing")
    actor.users_collection[0].children.link(output_collection)

    shirt = actor.copy()
    shirt.data = actor.data.copy()
    shirt.name = "ActorNativeTshirt_BodyComponent_v1"
    shirt.parent = None
    shirt.matrix_world = actor.matrix_world.copy()
    output_collection.objects.link(shirt)

    bm = bmesh.new()
    bm.from_mesh(shirt.data)
    bm.faces.ensure_lookup_table()
    world = actor.matrix_world
    groups = {group.name: group.index for group in actor.vertex_groups}
    torso_groups = {index for name, index in groups.items() if any(token in name for token in ("Waist", "Spine", "NeckTwist", "Clavicle"))}
    upper_groups = {index for name, index in groups.items() if "Upperarm" in name or "Clavicle" in name}
    lower_groups = {index for name, index in groups.items() if any(token in name for token in ("Forearm", "Hand", "Mid", "Index", "Ring", "Pinky", "Thumb"))}
    selected: set[int] = set()
    counts = {"torso_faces": 0, "left_sleeve_faces": 0, "right_sleeve_faces": 0}
    for face in bm.faces:
        face.tag = False

    arm_axes: dict[str, tuple[Vector, Vector, float]] = {}
    for side in ("L", "R"):
        bone = armature.data.bones.get(f"CC_Base_{side}_Upperarm")
        twist = armature.data.bones.get(f"CC_Base_{side}_UpperarmTwist02")
        if bone is None or twist is None:
            continue
        shoulder = armature.matrix_world @ bone.head_local
        elbow = armature.matrix_world @ twist.tail_local
        axis_vector = elbow - shoulder
        length = axis_vector.length
        if length > 0.001:
            arm_axes[side] = (shoulder, axis_vector.normalized(), length)

    for face in bm.faces:
        center = world @ face.calc_center_median()
        if not (options.bottom_z <= center.z <= options.top_z):
            continue
        reject = weight(face, actor, lower_groups)
        if reject > 0.20:
            continue

        upper = weight(face, actor, upper_groups)
        torso = abs(center.x) <= options.torso_half_width and upper < 0.78
        if torso:
            selected.add(face.index)
            counts["torso_faces"] += 1
            continue

        for side in ("L", "R"):
            if side not in arm_axes:
                continue
            shoulder, axis, length = arm_axes[side]
            side_ok = center.x > 0.02 if side == "L" else center.x < -0.02
            projection = (center - shoulder).dot(axis) / length
            # The negative start includes the shoulder bridge; the positive
            # cutoff is the actual short-sleeve cuff boundary.
            if side_ok and upper > 0.18 and -0.45 <= projection <= options.sleeve_fraction and abs(center.x) <= 0.78:
                selected.add(face.index)
                face.tag = True
                counts[f"{'left' if side == 'L' else 'right'}_sleeve_faces"] += 1
                break

    if not selected:
        raise RuntimeError("Actor-native clothing selection was empty")

    bmesh.ops.delete(bm, geom=[face for face in bm.faces if face.index not in selected], context="FACES")
    loose = [vertex for vertex in bm.verts if not vertex.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    boundary_stats = clean_garment_boundaries(bm, world, armature, options.bottom_z, options.sleeve_fraction)
    bm.normal_update()
    scale = max(world.to_scale().x, 1e-6)
    for vertex in bm.verts:
        if vertex.normal.length > 1e-6:
            vertex.co += vertex.normal.normalized() * (options.clearance / scale)
    bm.to_mesh(shirt.data)
    bm.free()
    shirt.data.update()

    allowed = ("Waist", "Spine", "NeckTwist", "Clavicle", "Upperarm", "UpperarmTwist")
    for group in list(shirt.vertex_groups):
        if not any(token in group.name for token in allowed):
            shirt.vertex_groups.remove(group)
    shirt.data.materials.clear()
    shirt.data.materials.append(make_material())
    armature_mod = next((mod for mod in shirt.modifiers if mod.type == "ARMATURE"), None)
    if armature_mod is None:
        armature_mod = shirt.modifiers.new("ActorArmature", "ARMATURE")
        armature_mod.object = armature
    if options.shell_thickness > 0.0:
        solidify = shirt.modifiers.new("NativeClothingThickness", "SOLIDIFY")
        solidify.thickness = options.shell_thickness
        solidify.offset = -1.0
        # Do not generate a solidify rim around the shared shoulder/armhole
        # boundary. In this Actor surface component that rim reads as a stray
        # line on the torso side and creates a back-view offset.
        solidify.use_rim = False
    for polygon in shirt.data.polygons:
        polygon.use_smooth = True
    shirt["assetslab_clothing_type"] = "actor_native_single_body_component"
    shirt["assetslab_source"] = "actor_surface_topology_only"
    shirt["assetslab_sleeve_connection"] = "same_mesh_torso_to_upperarm_surface"
    shirt["assetslab_cuff_contract"] = "upperarm_projection_cutoff"
    shirt["assetslab_fit_status"] = "review_required"
    counts.update(boundary_stats)
    return shirt, counts


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    scene = bpy.context.scene
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if actor is None or armature is None:
        raise RuntimeError("actor blend must contain Actor mesh and Armature")
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    shirt, counts = build_component(actor, armature, options)
    frames = render_review(scene, output, actor, shirt, options.resolution)
    blend_path = output / f"{output.name}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report = {
        "schema": "assetslab_actor_native_single_body_component_tshirt_v1",
        "actor_blend": str(options.actor_blend.resolve()),
        "source_garment": None,
        "construction": "single mesh extracted from Actor torso plus upper-arm surfaces; original Actor armature weights",
        "parameters": vars(options) | {"actor_blend": str(options.actor_blend), "output": str(options.output)},
        "selected_face_counts": counts,
        "final_face_count": len(shirt.data.polygons),
        "frame_count_per_direction": 8,
        "directions": ["front", "right", "back", "left"],
        "status": "review_required",
        "candidate_blend": str(blend_path),
        "frames": frames,
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    (output / "HUMAN_REVIEW.md").write_text(
        "# Human review: Actor-native single body-component short sleeve v1\n\n"
        "Status: `review_required`\n\n"
        "This candidate does not import Colin_shirt_short or GarmentCode panels. "
        "The torso and upper-arm sleeve surfaces are one mesh with the Actor's "
        "original armature weights. Review shoulder continuity, cuff opening, "
        "hand exposure, side silhouette, and four-way motion.\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
