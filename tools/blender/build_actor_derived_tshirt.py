"""Build a first fitted T-shirt directly from the Actor surface.

This is intentionally an actor-derived acceptance garment, not a general
clothing generator.  It keeps the Actor topology and weights, extracts a
torso/upper-arm band, offsets it by a measured clearance, and then renders
the same four-direction/action review used by the rest of AssetsLab.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from fit_clothing_to_actor_cage import DIRECTIONS  # noqa: E402
from render_eye_assembly_blink_walk import configure_lighting, visible_bounds  # noqa: E402
from render_procedural_anime_eye_on_accurig import make_camera  # noqa: E402


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bottom-z", type=float, default=0.70)
    parser.add_argument("--top-z", type=float, default=1.48)
    parser.add_argument("--max-abs-x", type=float, default=0.82)
    # The generated turnaround reference places the cuff around one third of
    # the shoulder-to-elbow distance. Keep this narrow so a casual T-shirt
    # cannot silently become an arm guard.
    parser.add_argument("--sleeve-fraction", type=float, default=0.45)
    parser.add_argument("--sleeve-mode", choices=("surface", "geometric_surface", "geometric_armhole", "curved_tube", "pattern_panel", "hybrid_panel", "seamed_panel"), default="curved_tube")
    parser.add_argument("--clearance", type=float, default=0.025)
    parser.add_argument("--resolution", type=int, default=256)
    return parser.parse_args(argv)


def make_material() -> bpy.types.Material:
    material = bpy.data.materials.new("ActorDerivedTshirt_Material")
    material.diffuse_color = (0.12, 0.38, 0.82, 1.0)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    if shader:
        shader.inputs["Base Color"].default_value = (0.12, 0.38, 0.82, 1.0)
        shader.inputs["Roughness"].default_value = 0.86
    return material


def create_bone_sleeves(
    actor: bpy.types.Object,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    armature: bpy.types.Object,
    sleeve_fraction: float,
    clearance: float,
) -> None:
    """Create two curved, open sleeves with an explicit armhole bridge.

    GarmentCode's default T-shirt connects two front/back sleeve panels to a
    curved armhole edge.  This is not a full sewing-pattern reconstruction,
    but four rings along clavicle -> upperarm -> cuff preserve the same
    structural idea and remove the single-ring shoulder-cap failure.
    """
    inverse = actor.matrix_world.inverted()
    fraction = max(0.36, min(sleeve_fraction, 0.80))
    sides = ("L", "R")
    for side in sides:
        clavicle = armature.data.bones.get(f"CC_Base_{side}_Clavicle")
        upper = armature.data.bones.get(f"CC_Base_{side}_Upperarm")
        twist01 = armature.data.bones.get(f"CC_Base_{side}_UpperarmTwist01")
        twist = armature.data.bones.get(f"CC_Base_{side}_UpperarmTwist02")
        if not clavicle or not upper or not twist01 or not twist:
            continue
        clavicle_head = armature.matrix_world @ clavicle.head_local
        shoulder = armature.matrix_world @ upper.head_local
        elbow = armature.matrix_world @ twist.tail_local
        arm_axis = elbow - shoulder
        if arm_axis.length < 0.001:
            continue
        arm_axis.normalize()
        cuff = shoulder + (elbow - shoulder) * fraction
        # The Actor's upper-arm bone head sits well inside the torso
        # silhouette.  Start the garment armhole slightly outward, then
        # taper back onto the bone; otherwise a physically centered sleeve is
        # hidden by the torso in front/back orthographic renders.
        outward = Vector((0.11 if side == "L" else -0.11, 0.0, 0.0))
        # The first two rings follow the shoulder/clavicle curve; the last two
        # follow the upper arm.  This is the explicit native counterpart of
        # GarmentCode's front/back sleeve panels joined to an armhole edge.
        # Keep the sleeve centreline on the actual upper-arm bone.  Earlier
        # probes pushed the whole tube toward the camera to make it visible;
        # that produced a floating shoulder pad and back-view misalignment.
        # The arm surface itself is the depth reference here, so only a tiny
        # armhole bridge offset is allowed.
        front_bridge = Vector((0.0, -0.025, 0.0))
        centers = [
            shoulder - arm_axis * 0.055 + outward * 0.75 + front_bridge,
            shoulder + arm_axis * 0.10 + outward * 0.55 + front_bridge,
            shoulder + (cuff - shoulder) * 0.42 + outward * 0.20 + front_bridge,
            cuff + front_bridge,
        ]
        # A short sleeve is a tube around the upper arm, not a broad cap.
        # These rings leave a small fabric clearance over the Actor surface
        # while keeping the armhole/cuff silhouette readable in front/back.
        radii = [0.175 + clearance, 0.160 + clearance, 0.145 + clearance, 0.125 + clearance]
        segments = 16
        world_vertices = []
        for ring_index, (center, radius) in enumerate(zip(centers, radii)):
            if ring_index == 0:
                tangent = centers[1] - centers[0]
            elif ring_index == len(centers) - 1:
                tangent = centers[-1] - centers[-2]
            else:
                tangent = centers[ring_index + 1] - centers[ring_index - 1]
            tangent.normalize()
            reference = Vector((0.0, 1.0, 0.0))
            if abs(tangent.dot(reference)) > 0.95:
                reference = Vector((1.0, 0.0, 0.0))
            radial_a = tangent.cross(reference).normalized()
            radial_b = tangent.cross(radial_a).normalized()
            for index in range(segments):
                angle = 2.0 * math.pi * index / segments
                offset = radial_a * math.cos(angle) * radius + radial_b * math.sin(angle) * radius
                world_vertices.append(center + offset)
        vertices = [tuple(inverse @ vertex) for vertex in world_vertices]
        faces = []
        for index in range(segments):
            next_index = (index + 1) % segments
            faces.append((index, next_index, segments + next_index, segments + index))

        mesh = bpy.data.meshes.new(f"ActorDerivedSleeve_{side}_Mesh")
        mesh.from_pydata(vertices, [], faces)
        mesh.materials.append(material)
        mesh.update()
        sleeve = bpy.data.objects.new(f"ActorDerivedSleeve_{side}", mesh)
        sleeve.matrix_world = actor.matrix_world.copy()
        collection.objects.link(sleeve)
        groups = {
            "clavicle": sleeve.vertex_groups.new(name=clavicle.name),
            "upperarm": sleeve.vertex_groups.new(name=upper.name),
            "twist01": sleeve.vertex_groups.new(name=twist01.name),
            "twist02": sleeve.vertex_groups.new(name=twist.name),
        }
        ring_weights = (
            {"clavicle": 1.0},
            {"clavicle": 0.65, "upperarm": 0.35},
            {"upperarm": 0.70, "twist01": 0.30},
            {"twist01": 0.55, "twist02": 0.45},
        )
        for ring_index, weights in enumerate(ring_weights):
            vertex_indices = list(range(ring_index * segments, (ring_index + 1) * segments))
            for name, weight in weights.items():
                groups[name].add(vertex_indices, weight, "REPLACE")
        solidify = sleeve.modifiers.new("SleeveHemThickness", "SOLIDIFY")
        solidify.thickness = 0.006
        solidify.offset = -1.0
        modifier = sleeve.modifiers.new("Armature", "ARMATURE")
        modifier.object = armature
        sleeve["assetslab_clothing_type"] = "complete_bone_sleeve"
        sleeve["assetslab_sleeve_fraction"] = fraction
        sleeve["assetslab_armhole_reference"] = "GarmentCode_front_back_sleeve_panels_to_curved_armhole"
        sleeve["assetslab_ring_count"] = len(centers)
        sleeve["assetslab_panel_semantics"] = "front_sleeve_panel_plus_back_sleeve_panel"
        sleeve["assetslab_front_panel_edge"] = "shoulder_armhole_to_cuff_front"
        sleeve["assetslab_back_panel_edge"] = "shoulder_armhole_to_cuff_back"
        sleeve["assetslab_armhole_bridge"] = True



def create_seamed_panel_sleeves(
    actor: bpy.types.Object,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    armature: bpy.types.Object,
    sleeve_fraction: float,
    clearance: float,
) -> None:
    """Create explicit front/back sleeve panels around each upper arm.

    This is a compact native reconstruction of the official T-shirt contract:
    each sleeve has a front panel and a back panel, a sleeve-cap armhole
    boundary, and an open cuff. The panels are bone-driven and intentionally
    remain separate from the torso until a welded-seam implementation is
    justified by visual review.
    """
    inverse = actor.matrix_world.inverted()
    fraction = max(0.36, min(sleeve_fraction, 0.72))
    for side in ("L", "R"):
        clavicle = armature.data.bones.get(f"CC_Base_{side}_Clavicle")
        upper = armature.data.bones.get(f"CC_Base_{side}_Upperarm")
        twist01 = armature.data.bones.get(f"CC_Base_{side}_UpperarmTwist01")
        twist = armature.data.bones.get(f"CC_Base_{side}_UpperarmTwist02")
        if not clavicle or not upper or not twist01 or not twist:
            continue
        shoulder = armature.matrix_world @ upper.head_local
        elbow = armature.matrix_world @ twist.tail_local
        axis = elbow - shoulder
        if axis.length < 0.001:
            continue
        axis.normalize()
        cuff = shoulder + (elbow - shoulder) * fraction
        centers = [
            shoulder - axis * 0.16 + Vector((0.0, 0.0, 0.025)),
            shoulder + axis * 0.03,
            shoulder + (cuff - shoulder) * 0.42,
            cuff,
        ]
        # A deeper Y radius keeps the sleeve visible in both orthographic
        # front and back views instead of hiding the back half inside the
        # Actor torso.
        depth_radii = [0.285 + clearance, 0.255 + clearance, 0.205 + clearance, 0.165 + clearance]
        vertical_radii = [0.195 + clearance, 0.178 + clearance, 0.145 + clearance, 0.115 + clearance]
        ring_weights = (
            {"clavicle": 1.0},
            {"clavicle": 0.60, "upperarm": 0.40},
            {"upperarm": 0.72, "twist01": 0.28},
            {"twist01": 0.55, "twist02": 0.45},
        )
        bone_groups = {
            "clavicle": clavicle.name,
            "upperarm": upper.name,
            "twist01": twist01.name,
            "twist02": twist.name,
        }
        axis_vertical = Vector((0.0, 1.0, 0.0)).cross(axis)
        if axis_vertical.length < 0.001:
            axis_vertical = Vector((0.0, 0.0, 1.0))
        axis_vertical.normalize()
        depth_axis = Vector((0.0, 1.0, 0.0))
        # Duplicate seam endpoints by design: these are explicit panel
        # boundaries, not a falsely claimed welded topology.
        # Split by the Y/depth plane, not by the vertical plane.  The previous
        # ranges (pi..2pi and 0..pi) accidentally produced lower/upper panels,
        # which rendered as shoulder straps in the front view.
        panel_specs = (("Front", 0.5 * math.pi, 1.5 * math.pi), ("Back", -0.5 * math.pi, 0.5 * math.pi))
        segments = 8
        for panel_name, angle_start, angle_end in panel_specs:
            world_vertices = []
            for ring_index, center in enumerate(centers):
                for step in range(segments + 1):
                    angle = angle_start + (angle_end - angle_start) * step / segments
                    offset = (
                        depth_axis * math.cos(angle) * depth_radii[ring_index]
                        + axis_vertical * math.sin(angle) * vertical_radii[ring_index]
                    )
                    world_vertices.append(center + offset)
            vertices = [tuple(inverse @ vertex) for vertex in world_vertices]
            faces = []
            width = segments + 1
            for ring_index in range(len(centers) - 1):
                for step in range(segments):
                    current = ring_index * width + step
                    next_ring = (ring_index + 1) * width
                    faces.append((current, current + 1, next_ring + step + 1, next_ring + step))
            mesh = bpy.data.meshes.new(f"ActorDerivedSleeve_{side}_{panel_name}_Mesh")
            mesh.from_pydata(vertices, [], faces)
            mesh.materials.append(material)
            mesh.update()
            panel = bpy.data.objects.new(f"ActorDerivedSleeve_{side}_{panel_name}Panel", mesh)
            panel.matrix_world = actor.matrix_world.copy()
            collection.objects.link(panel)
            groups = {key: panel.vertex_groups.new(name=value) for key, value in bone_groups.items()}
            for ring_index, weights in enumerate(ring_weights):
                vertex_indices = list(range(ring_index * width, (ring_index + 1) * width))
                for key, weight in weights.items():
                    groups[key].add(vertex_indices, weight, "REPLACE")
            solidify = panel.modifiers.new("SleevePanelThickness", "SOLIDIFY")
            solidify.thickness = 0.006
            solidify.offset = -1.0
            modifier = panel.modifiers.new("Armature", "ARMATURE")
            modifier.object = armature
            panel["assetslab_clothing_type"] = "explicit_sewn_sleeve_panel"
            panel["assetslab_sleeve_fraction"] = fraction
            panel["assetslab_panel_role"] = f"{panel_name.lower()}_sleeve_panel"
            panel["assetslab_armhole_reference"] = "GarmentCode_explicit_armhole_edge"
            panel["assetslab_explicit_armhole_edge"] = True
            panel["assetslab_sleeve_body_stitch"] = f"{panel_name.lower()}_sleeve_to_{panel_name.lower()}_torso"
            panel["assetslab_front_back_panel_contract"] = True


def create_surface_sleeves(
    actor: bpy.types.Object,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    armature: bpy.types.Object,
    sleeve_fraction: float,
    clearance: float,
    name_prefix: str = "ActorDerivedSurfaceSleeve",
    fraction_override: float | None = None,
    selection_mode: str = "weights",
) -> None:
    """Extract upper-arm surface faces as sleeves with an explicit cuff cut.

    This is the native counterpart of a sewn armhole in the current Actor:
    the sleeve and the torso are both offset from the same rest-pose surface,
    so the shoulder connection cannot be displaced by an unrelated cylinder.
    """
    fraction = max(0.10, min(fraction_override if fraction_override is not None else sleeve_fraction, 0.65))
    # Extend the shoulder-side boundary far enough to include the clavicle
    # bridge.  This is the native geometric counterpart of GarmentCode's
    # armhole edge; the previous -0.20 cutoff left only a small shoulder cap
    # visible in the front view.
    armhole_start_fraction = -0.45
    group_indices = {group.name: group.index for group in actor.vertex_groups}
    deps_matrix = actor.matrix_world
    body_bmesh = bmesh.new()
    body_bmesh.from_mesh(actor.data)
    body_bmesh.faces.ensure_lookup_table()

    def average_weight(face: bmesh.types.BMFace, group_ids: set[int]) -> float:
        if not group_ids:
            return 0.0
        return sum(
            sum(assignment.weight for assignment in actor.data.vertices[vertex.index].groups if assignment.group in group_ids)
            for vertex in face.verts
        ) / max(len(face.verts), 1)

    for side in ("L", "R"):
        arm_groups = {
            index
            for name, index in group_indices.items()
            if f"_{side}_" in name and any(token in name for token in ("Clavicle", "Upperarm"))
        }
        reject_groups = {
            index
            for name, index in group_indices.items()
            if f"_{side}_" in name and any(token in name for token in ("Forearm", "Hand", "Mid", "Index", "Ring", "Pinky", "Thumb"))
        }
        upper = armature.data.bones.get(f"CC_Base_{side}_Upperarm")
        twist = armature.data.bones.get(f"CC_Base_{side}_UpperarmTwist02")
        if not upper or not twist:
            continue
        shoulder = armature.matrix_world @ upper.head_local
        elbow = armature.matrix_world @ twist.tail_local
        axis = elbow - shoulder
        length = axis.length
        if length < 0.001:
            continue
        axis.normalize()
        keep: set[int] = set()
        for face in body_bmesh.faces:
            center = deps_matrix @ face.calc_center_median()
            upper_weight = average_weight(face, arm_groups)
            reject_weight = average_weight(face, reject_groups)
            projection = (center - shoulder).dot(axis) / length
            side_ok = center.x > 0.02 if side == "L" else center.x < -0.02
            if selection_mode in ("geometric", "geometric_armhole"):
                centerline = shoulder + axis * (projection * length)
                radial_distance = (center - centerline).length
                armhole_mode = selection_mode == "geometric_armhole"
                geometric_side_ok = (center.x > 0.12 if side == "L" else center.x < -0.12) if armhole_mode else (center.x > 0.16 if side == "L" else center.x < -0.16)
                radial_limit = 0.31 if armhole_mode and projection < 0.08 else 0.27
                projection_start = -0.42 if armhole_mode else -0.22
                if (
                    geometric_side_ok
                    and abs(center.x) < 0.68
                    and reject_weight < 0.08
                    and radial_distance <= radial_limit
                    and projection_start <= projection <= fraction
                ):
                    keep.add(face.index)
            elif side_ok and upper_weight > 0.18 and reject_weight < 0.08 and armhole_start_fraction <= projection <= fraction:
                keep.add(face.index)
        if not keep:
            continue

        sleeve = actor.copy()
        sleeve.data = actor.data.copy()
        sleeve.name = f"{name_prefix}_{side}"
        sleeve.parent = None
        sleeve.matrix_world = actor.matrix_world.copy()
        collection.objects.link(sleeve)
        sleeve_bmesh = bmesh.new()
        sleeve_bmesh.from_mesh(sleeve.data)
        sleeve_bmesh.faces.ensure_lookup_table()
        delete_faces = [face for face in sleeve_bmesh.faces if face.index not in keep]
        bmesh.ops.delete(sleeve_bmesh, geom=delete_faces, context="FACES")
        loose = [vertex for vertex in sleeve_bmesh.verts if not vertex.link_faces]
        if loose:
            bmesh.ops.delete(sleeve_bmesh, geom=loose, context="VERTS")
        sleeve_bmesh.normal_update()
        local_clearance = clearance / max(deps_matrix.to_scale().x, 0.000001)
        for vertex in sleeve_bmesh.verts:
            vertex.co += vertex.normal.normalized() * local_clearance
        sleeve_bmesh.to_mesh(sleeve.data)
        sleeve_bmesh.free()
        sleeve.data.update()

        allowed_tokens = ("Clavicle", "Upperarm")
        for group in list(sleeve.vertex_groups):
            if not any(token in group.name for token in allowed_tokens):
                sleeve.vertex_groups.remove(group)
        sleeve.data.materials.clear()
        sleeve.data.materials.append(material)
        solidify = sleeve.modifiers.new("SurfaceSleeveThickness", "SOLIDIFY")
        solidify.thickness = 0.006
        solidify.offset = -1.0
        modifier = sleeve.modifiers.new("Armature", "ARMATURE")
        modifier.object = armature
        sleeve["assetslab_clothing_type"] = "actor_surface_sleeve"
        sleeve["assetslab_sleeve_fraction"] = fraction
        sleeve["assetslab_armhole_reference"] = "GarmentCode_front_back_sleeve_panels_to_curved_armhole"
        sleeve["assetslab_surface_connection"] = True
        sleeve["assetslab_armhole_start_fraction"] = armhole_start_fraction
        sleeve["assetslab_panel_semantics"] = "front_panel_and_back_panel_share_actor_armhole_boundary"
    body_bmesh.free()


def extract_surface_shirt(
    actor: bpy.types.Object,
    collection: bpy.types.Collection,
    bottom_z: float,
    top_z: float,
    max_abs_x: float,
    sleeve_fraction: float,
    clearance: float,
    sleeve_mode: str,
) -> tuple[bpy.types.Object, int, int]:
    shirt = actor.copy()
    shirt.data = actor.data.copy()
    shirt.name = "ActorReferenceTshirt_short_sleeve_v1"
    shirt.parent = None
    shirt.matrix_world = actor.matrix_world.copy()
    collection.objects.link(shirt)

    mesh = shirt.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    matrix = actor.matrix_world
    group_indices = {group.name: group.index for group in actor.vertex_groups}
    # Keep clavicle faces in the torso shell so the shirt reaches the
    # shoulder naturally.  Only upper-arm/twist faces belong to the separate
    # sleeve tubes.
    upper_groups = {
        index
        for name, index in group_indices.items()
        if any(token in name for token in ("Upperarm",))
    }
    lower_groups = {
        index
        for name, index in group_indices.items()
        if any(token in name for token in ("Forearm", "Hand", "Mid", "Index", "Ring", "Pinky", "Thumb"))
    }

    def group_weight(face: bmesh.types.BMFace, groups: set[int]) -> float:
        if not groups:
            return 0.0
        return sum(
            sum(assignment.weight for assignment in actor.data.vertices[vertex.index].groups if assignment.group in groups)
            for vertex in face.verts
        ) / max(len(face.verts), 1)

    selected = []
    for face in bm.faces:
        center = matrix @ face.calc_center_median()
        # Include the shoulder cap in the torso garment so the independent
        # sleeve tube can overlap it cleanly instead of exposing an opening.
        # The Actor's upper arms occupy the same z band as the chest.  The
        # previous broad x/z filter copied those arm faces into the shirt
        # body, making even a short independent sleeve read as long-sleeved.
        # Keep the torso surface here; the upper-arm volume is supplied by
        # create_bone_sleeves() below.
        shoulder_band = (
            abs(center.x) <= 0.48
            and 1.30 <= center.z <= 1.56
            and group_weight(face, upper_groups) < 0.72
            and group_weight(face, lower_groups) < 0.20
        )
        torso_face = (
            abs(center.x) <= 0.72
            and group_weight(face, lower_groups) < 0.20
            and (group_weight(face, upper_groups) < 0.20 or shoulder_band)
        )
        upper_arm_face = (
            abs(center.x) <= max_abs_x
            and group_weight(face, upper_groups) >= group_weight(face, lower_groups)
            and group_weight(face, upper_groups) > 0.20
        )
        if bottom_z <= center.z <= top_z and torso_face:
            selected.append(face)
    selected_count = len(selected)
    bmesh.ops.delete(bm, geom=[face for face in bm.faces if face not in selected], context="FACES")
    loose = [vertex for vertex in bm.verts if not vertex.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")

    # Cut the hem and shoulder line with planes after the region selection so
    # the boundary is a clean ring instead of an irregular source topology.
    scale = max(matrix.to_scale().x, 0.000001)
    for plane_z in (bottom_z, top_z):
        bmesh.ops.bisect_plane(
            bm,
            geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
            plane_co=Vector((0.0, 0.0, plane_z / scale)),
            plane_no=Vector((0.0, 0.0, 1.0)),
            clear_inner=False,
            clear_outer=False,
        )
        outside = [
            face
            for face in bm.faces
            if ((matrix @ face.calc_center_median()).z < bottom_z - 0.00001)
            or ((matrix @ face.calc_center_median()).z > top_z + 0.00001)
        ]
        if outside:
            bmesh.ops.delete(bm, geom=outside, context="FACES")
        loose = [vertex for vertex in bm.verts if not vertex.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")

    armature_modifier = next((modifier for modifier in shirt.modifiers if modifier.type == "ARMATURE"), None)
    armature_object = armature_modifier.object if armature_modifier else None
    bm.normal_update()
    local_clearance = clearance / scale
    for vertex in bm.verts:
        normal = vertex.normal.normalized()
        vertex.co += normal * local_clearance
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    # A copied Actor mesh contains many finger/forearm groups.  Leaving those
    # groups on a garment is unsafe even if most offending faces were removed:
    # shared boundary vertices can still receive hand motion.  Keep only the
    # garment region contract and normalize the remaining inherited weights.
    allowed_tokens = ("Waist", "Spine", "NeckTwist", "Clavicle", "Upperarm")
    for group in list(shirt.vertex_groups):
        if not any(token in group.name for token in allowed_tokens):
            shirt.vertex_groups.remove(group)
    for vertex in mesh.vertices:
        assignments = [assignment for assignment in vertex.groups if assignment.weight > 0.0]
        total = sum(assignment.weight for assignment in assignments)
        if total > 0.0:
            for assignment in assignments:
                # The group index remains valid after the removals above.
                shirt.vertex_groups[assignment.group].add([vertex.index], assignment.weight / total, "REPLACE")

    # The duplicate already owns Actor vertex groups and its Armature modifier.
    # Replace the body material with a visible review material.
    mesh.materials.clear()
    mesh.materials.append(make_material())
    if armature_modifier:
        shirt.modifiers.remove(armature_modifier)
    solidify = shirt.modifiers.new("GarmentThickness", "SOLIDIFY")
    solidify.thickness = 0.8
    solidify.offset = -1.0
    solidify.use_rim = True
    if armature_object:
        armature = shirt.modifiers.new("Armature", "ARMATURE")
        armature.object = armature_object
        if sleeve_mode == "surface":
            create_surface_sleeves(actor, collection, mesh.materials[0], armature_object, sleeve_fraction, clearance)
        elif sleeve_mode == "geometric_surface":
            create_surface_sleeves(
                actor,
                collection,
                mesh.materials[0],
                armature_object,
                sleeve_fraction,
                clearance,
                name_prefix="ActorDerivedGeometricSurfaceSleeve",
                selection_mode="geometric",
            )
        elif sleeve_mode == "geometric_armhole":
            create_surface_sleeves(
                actor,
                collection,
                mesh.materials[0],
                armature_object,
                sleeve_fraction,
                clearance,
                name_prefix="ActorDerivedGeometricArmholeSleeve",
                selection_mode="geometric_armhole",
            )
        elif sleeve_mode == "seamed_panel":
            create_seamed_panel_sleeves(actor, collection, mesh.materials[0], armature_object, sleeve_fraction, clearance)
        elif sleeve_mode == "hybrid_panel":
            # Use a conforming Actor-surface armhole patch only at the
            # shoulder, then use the larger bone-driven panel tube for the
            # visible sleeve length.  This avoids the planar bridge wing
            # failure while preserving the official front/back connection
            # concept.
            create_surface_sleeves(
                actor,
                collection,
                mesh.materials[0],
                armature_object,
                sleeve_fraction,
                clearance,
                name_prefix="ActorDerivedArmholeSurface",
                fraction_override=0.24,
            )
            create_bone_sleeves(actor, collection, mesh.materials[0], armature_object, sleeve_fraction, clearance)
        else:
            create_bone_sleeves(actor, collection, mesh.materials[0], armature_object, sleeve_fraction, clearance)
    shirt["assetslab_clothing_type"] = "ordinary_short_sleeve_tshirt"
    shirt["assetslab_clothing_source"] = "actor_surface_extraction"
    shirt["assetslab_fit_status"] = "review_required"
    shirt["assetslab_clearance_world"] = clearance
    shirt["assetslab_region_contract"] = "reference_turnaround_torso_plus_upper_arm_band"
    shirt["assetslab_sleeve_mode"] = sleeve_mode
    shirt["assetslab_reference"] = "prototype/assets/references/clothing/short_sleeve_turnaround_ref_v0.png"
    return shirt, selected_count, len(mesh.polygons)


def render_review(scene: bpy.types.Scene, output: Path, actor: bpy.types.Object, shirt: bpy.types.Object, resolution: int) -> list[dict[str, object]]:
    low, high = visible_bounds()
    center = (low + high) * 0.5
    configure_lighting(scene, center, "soft_flat")
    scene.view_settings.exposure = 0.35
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    action = bpy.data.objects["Armature"].animation_data.action
    start, end = int(action.frame_range[0]), int(action.frame_range[1])
    sample_frames = [round(start + (end - start) * index / 7.0) for index in range(8)]
    ortho_scale = max(high.z - low.z, high.x - low.x, high.y - low.y) * 1.16
    frames = []
    for direction, (x, y) in DIRECTIONS.items():
        camera = make_camera(scene, center, f"ActorDerivedTshirt_{direction}", (x, y, center.z), ortho_scale)
        scene.camera = camera
        for index, source_frame in enumerate(sample_frames):
            scene.frame_set(source_frame)
            bpy.context.view_layer.update()
            path = output / f"{direction}_{index:02d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            frames.append({"direction": direction, "sample_index": index, "source_frame": source_frame, "path": path.name})
        bpy.data.objects.remove(camera, do_unlink=True)
    return frames


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
    collection = bpy.data.collections.new("ActorDerivedClothing")
    scene.collection.children.link(collection)
    shirt, selected_faces, final_faces = extract_surface_shirt(
        actor, collection, options.bottom_z, options.top_z, options.max_abs_x, options.sleeve_fraction, options.clearance, options.sleeve_mode
    )
    frames = render_review(scene, output, actor, shirt, options.resolution)
    candidate_blend = output / "actor_derived_tshirt_candidate.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(candidate_blend))
    report = {
        "schema": "assetslab_actor_derived_tshirt_review_v1",
        "actor_blend": str(options.actor_blend.resolve()),
        "candidate": "ActorReferenceTshirt_short_sleeve_v1",
        "source_method": (
            "garmentcode_front_back_sleeve_panel_contract_plus_bone_driven_actor_adaptation"
            if options.sleeve_mode in ("pattern_panel", "hybrid_panel", "seamed_panel")
            else "garmentcode_armhole_analysis_plus_actor_surface_extraction"
        ),
        "region": {
            "bottom_z": options.bottom_z,
            "top_z": options.top_z,
            "max_abs_x": options.max_abs_x,
            "sleeve_fraction": options.sleeve_fraction,
            "sleeve_mode": options.sleeve_mode,
        },
        "connection_contract": {
            "reference": "GarmentCode armhole edges plus front/back sleeve-to-body stitches",
            "native_implementation": (
                "explicit front/back sleeve panels with sleeve-cap armhole boundaries"
                if options.sleeve_mode == "seamed_panel"
                else "GarmentCode-inspired front/back sleeve panel tube with clavicle armhole bridge and upperarm cuff boundary"
                if options.sleeve_mode == "pattern_panel"
                else "same-Actor surface sleeve with clavicle bridge and upperarm cuff boundary"
            ),
            "armhole_start_fraction": -0.45 if options.sleeve_mode == "surface" else None,
            "explicit_welded_armhole_topology": False,
            "front_back_panel_semantics": options.sleeve_mode in ("surface", "pattern_panel", "hybrid_panel", "seamed_panel"),
        },
        "clearance": options.clearance,
        "selected_faces_before_cleanup": selected_faces,
        "final_faces": final_faces,
        "rig_status": "actor_vertex_groups_and_armature_modifier_inherited",
        "direction_count": 4,
        "frame_count_per_direction": 8,
        "lighting_profile": "soft_flat_v1",
        "status": "review_required",
        "frames": frames,
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
