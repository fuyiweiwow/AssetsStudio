"""Transfer an Actor-specific GarmentCode simulation OBJ into the Actor blend.

This is a coordinate/rig transfer diagnostic only.  It does not shrinkwrap,
push, or repair the garment surface.  The GarmentCode simulation remains the
source geometry; only coordinates and Actor armature weights are added.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import closest_point_on_tri


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--sim-obj", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--garment-name", default="GarmentCodeShirt_ActorTransfer")
    parser.add_argument("--arm-region-x", type=float, default=0.18)
    parser.add_argument("--arm-region-z-min", type=float, default=1.05)
    parser.add_argument("--arm-region-z-max", type=float, default=1.43)
    parser.add_argument("--armhole-blend-width", type=float, default=0.0)
    parser.add_argument(
        "--panel-membership",
        type=Path,
        help="exact GarmentCode global-vertex panel membership JSON",
    )
    parser.add_argument(
        "--armhole-arm-weight",
        type=float,
        default=0.5,
        help="arm contribution for vertices shared by a sleeve and torso panel",
    )
    parser.add_argument(
        "--skinning-mode",
        choices=("actor", "preserve-volume", "linear"),
        default="preserve-volume",
        help="garment armature skinning mode; actor copies the Actor modifier",
    )
    parser.add_argument(
        "--weight-interpolation",
        choices=("inverse-distance", "barycentric"),
        default="inverse-distance",
        help="interpolation of Actor weights at the nearest source face",
    )
    parser.add_argument(
        "--include-forearm-weights",
        action="store_true",
        help="allow short-sleeve vertices near the Actor forearm to inherit forearm/twist weights",
    )
    parser.add_argument(
        "--forearm-fade-width",
        type=float,
        default=0.0,
        help=(
            "distance in metres from the GarmentCode armhole seam over which "
            "forearm weights fade in; keeps the sleeve root on upper-arm/clavicle motion"
        ),
    )
    parser.add_argument(
        "--armhole-upperarm-min-weight",
        type=float,
        default=0.0,
        help="minimum main upper-arm weight at the armhole seam, fading to zero by the configured width",
    )
    parser.add_argument(
        "--armhole-upperarm-width",
        type=float,
        default=0.0,
        help="distance in metres over which the armhole upper-arm minimum fades out",
    )
    parser.add_argument(
        "--posterior-armhole-torso-blend-width",
        type=float,
        default=0.0,
        help=(
            "distance in metres over which sleeve_b vertices blend from the "
            "shared-seam arm contribution to full arm-surface weights"
        ),
    )
    parser.add_argument(
        "--posterior-armhole-arm-weight",
        type=float,
        default=0.5,
        help="arm contribution at the sleeve_b side of the armhole transition",
    )
    return parser.parse_args(argv)


def remove_existing(name: str) -> None:
    obj = bpy.data.objects.get(name)
    if obj is not None:
        bpy.data.objects.remove(obj, do_unlink=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def transfer_weights(
    garment: bpy.types.Object,
    actor: bpy.types.Object,
    options: argparse.Namespace,
    panel_memberships: list[list[str]] | None,
) -> dict[str, object]:
    group_names = {group.index: group.name for group in actor.vertex_groups}
    torso_groups = {
        name for name in group_names.values()
        if name in {
            "CC_Base_Hip", "CC_Base_Waist", "CC_Base_Spine01", "CC_Base_Spine02",
            # Shoulder vertices on the Actor are driven substantially by the
            # clavicles.  Excluding these groups normalizes the transferred
            # shoulder cloth to Spine02 and makes the Actor shoulder move
            # through the garment as soon as the walk action starts.
            "CC_Base_L_Clavicle", "CC_Base_R_Clavicle",
        }
    }
    left_arm_groups = {
        name for name in group_names.values()
        if name in {
            "CC_Base_L_Clavicle", "CC_Base_L_Upperarm",
            "CC_Base_L_UpperarmTwist01", "CC_Base_L_UpperarmTwist02",
        }
    }
    right_arm_groups = {
        name for name in group_names.values()
        if name in {
            "CC_Base_R_Clavicle", "CC_Base_R_Upperarm",
            "CC_Base_R_UpperarmTwist01", "CC_Base_R_UpperarmTwist02",
        }
    }
    if options.include_forearm_weights:
        left_arm_groups.update(
            name for name in group_names.values()
            if name in {
                "CC_Base_L_Forearm", "CC_Base_L_ForearmTwist01", "CC_Base_L_ForearmTwist02",
            }
        )
        right_arm_groups.update(
            name for name in group_names.values()
            if name in {
                "CC_Base_R_Forearm", "CC_Base_R_ForearmTwist01", "CC_Base_R_ForearmTwist02",
            }
        )
    upper_groups = torso_groups | left_arm_groups | right_arm_groups

    def group_weight(source_index: int, allowed: set[str]) -> float:
        return sum(
            assignment.weight
            for assignment in actor.data.vertices[source_index].groups
            if group_names.get(assignment.group) in allowed
        )

    def make_surface(selector_groups: set[str], transfer_groups: set[str]) -> dict[str, object]:
        faces: list[tuple[int, ...]] = []
        source_indices: set[int] = set()
        for polygon in actor.data.polygons:
            face = tuple(polygon.vertices)
            if max((group_weight(index, selector_groups) for index in face), default=0.0) < 0.20:
                continue
            faces.append(face)
            source_indices.update(face)
        if not faces:
            raise RuntimeError("Actor transfer surface is empty")
        source_order = sorted(source_indices)
        source_to_local = {source: index for index, source in enumerate(source_order)}
        points = [actor.matrix_world @ actor.data.vertices[index].co for index in source_order]
        local_faces = [tuple(source_to_local[index] for index in face) for face in faces]
        return {
            "selector_groups": selector_groups,
            "transfer_groups": transfer_groups,
            "faces": faces,
            "source_indices": source_indices,
            "source_to_local": source_to_local,
            "points": points,
            "bvh": BVHTree.FromPolygons(points, local_faces, all_triangles=False),
        }

    surfaces = {
        "torso": make_surface(
            torso_groups,
            torso_groups | left_arm_groups | right_arm_groups,
        ),
        # Select the matching upper-arm surface with arm weights, but preserve
        # the Actor's native clavicle/spine contribution at the shoulder.  The
        # previous implementation discarded these source weights and then
        # normalized the remainder, making each sleeve almost rigidly follow a
        # single upper-arm chain.
        "left_arm": make_surface(left_arm_groups, torso_groups | left_arm_groups),
        "right_arm": make_surface(right_arm_groups, torso_groups | right_arm_groups),
    }

    def face_weight_factors(
        surface: dict[str, object], face_index: int, nearest_point: Vector
    ) -> list[tuple[int, float]]:
        face = surface["faces"][face_index]
        points = surface["points"]
        source_to_local = surface["source_to_local"]
        if options.weight_interpolation == "inverse-distance":
            distances = [
                max((nearest_point - points[source_to_local[index]]).length, 1e-5)
                for index in face
            ]
            inverse = [1.0 / distance for distance in distances]
            denominator = sum(inverse)
            return [(index, factor / denominator) for index, factor in zip(face, inverse)]

        # BVHTree triangulates Actor quads internally.  Reconstruct the two
        # fan triangles and interpolate at the closest point on the matching
        # triangle, avoiding weights from the opposite half of the quad.
        best: tuple[float, tuple[int, int, int], Vector] | None = None
        for offset in range(1, len(face) - 1):
            triangle = (face[0], face[offset], face[offset + 1])
            a, b, c = (points[source_to_local[index]] for index in triangle)
            projected = closest_point_on_tri(nearest_point, a, b, c)
            candidate = ((projected - nearest_point).length_squared, triangle, projected)
            if best is None or candidate[0] < best[0]:
                best = candidate
        if best is None:
            raise RuntimeError(f"cannot triangulate Actor source face {face_index}")
        _distance_squared, triangle, projected = best
        a, b, c = (points[source_to_local[index]] for index in triangle)
        edge0 = b - a
        edge1 = c - a
        relative = projected - a
        d00 = edge0.dot(edge0)
        d01 = edge0.dot(edge1)
        d11 = edge1.dot(edge1)
        d20 = relative.dot(edge0)
        d21 = relative.dot(edge1)
        denominator = d00 * d11 - d01 * d01
        if abs(denominator) <= 1e-12:
            return [(triangle[0], 1.0)]
        weight_b = (d11 * d20 - d01 * d21) / denominator
        weight_c = (d00 * d21 - d01 * d20) / denominator
        weights = [max(0.0, 1.0 - weight_b - weight_c), max(0.0, weight_b), max(0.0, weight_c)]
        total = sum(weights)
        return [(index, weight / total) for index, weight in zip(triangle, weights)]
    garment_groups = {
        name: garment.vertex_groups.new(name=name)
        for name in group_names.values()
    }
    nearest_counts: dict[str, int] = {}
    face_counts: dict[str, int] = {}
    region_counts: dict[str, int] = {name: 0 for name in surfaces}
    assignment_policy_counts = {
        "torso_panel": 0,
        "left_sleeve_panel": 0,
        "right_sleeve_panel": 0,
        "left_armhole_shared": 0,
        "right_armhole_shared": 0,
        "left_armhole_blend_ring": 0,
        "right_armhole_blend_ring": 0,
        "spatial_fallback": 0,
    }
    armhole_points: dict[str, list[Vector]] = {"left_arm": [], "right_arm": []}
    if panel_memberships is not None:
        for vertex in garment.data.vertices:
            panels = set(panel_memberships[vertex.index])
            is_torso = any("torso" in name for name in panels)
            if not is_torso:
                continue
            if any(name.startswith("left_sleeve_") or name.startswith("sl_left_cuff_") for name in panels):
                armhole_points["left_arm"].append(garment.matrix_world @ vertex.co)
            if any(name.startswith("right_sleeve_") or name.startswith("sl_right_cuff_") for name in panels):
                armhole_points["right_arm"].append(garment.matrix_world @ vertex.co)
    for vertex in garment.data.vertices:
        point = garment.matrix_world @ vertex.co
        forearm_factor = 1.0
        seam_distance = float("inf")
        upperarm_group_name: str | None = None
        if panel_memberships is not None:
            panels = set(panel_memberships[vertex.index])
            is_left_sleeve = any(
                name.startswith("left_sleeve_") or name.startswith("sl_left_cuff_")
                for name in panels
            )
            is_right_sleeve = any(
                name.startswith("right_sleeve_") or name.startswith("sl_right_cuff_")
                for name in panels
            )
            is_torso = any("torso" in name for name in panels)
            is_posterior_sleeve = any(name.endswith("_sleeve_b") for name in panels)
            if is_left_sleeve and is_right_sleeve:
                raise RuntimeError(f"vertex {vertex.index} belongs to both left and right sleeves")
            if is_left_sleeve or is_right_sleeve:
                region = "left_arm" if is_left_sleeve else "right_arm"
                upperarm_group_name = (
                    "CC_Base_L_Upperarm" if is_left_sleeve else "CC_Base_R_Upperarm"
                )
                seam_points = armhole_points[region]
                seam_distance = min(
                    ((point - seam_point).length for seam_point in seam_points),
                    default=float("inf"),
                )
                if options.forearm_fade_width > 0.0:
                    forearm_factor = min(1.0, seam_distance / options.forearm_fade_width)
                if is_torso:
                    arm_weight = options.armhole_arm_weight
                    key = "left_armhole_shared" if is_left_sleeve else "right_armhole_shared"
                else:
                    effective_blend_width = options.armhole_blend_width
                    blend_start_arm_weight = options.armhole_arm_weight
                    if is_posterior_sleeve and options.posterior_armhole_torso_blend_width > 0.0:
                        effective_blend_width = options.posterior_armhole_torso_blend_width
                        blend_start_arm_weight = options.posterior_armhole_arm_weight
                    if seam_distance < effective_blend_width:
                        blend = seam_distance / max(effective_blend_width, 1e-6)
                        arm_weight = blend_start_arm_weight + (1.0 - blend_start_arm_weight) * blend
                        ring_key = "left_armhole_blend_ring" if is_left_sleeve else "right_armhole_blend_ring"
                        assignment_policy_counts[ring_key] += 1
                    else:
                        arm_weight = 1.0
                    key = "left_sleeve_panel" if is_left_sleeve else "right_sleeve_panel"
                assignment_policy_counts[key] += 1
            else:
                region = "torso"
                arm_weight = 0.0
                assignment_policy_counts["torso_panel"] += 1
        else:
            # Compatibility path for older candidates without exact panel
            # membership.  New Actor-specific candidates must use labels.
            arm_weight = 0.0
            arm_region = None
            if options.arm_region_z_min <= point.z <= options.arm_region_z_max:
                if point.x >= options.arm_region_x:
                    arm_region = "left_arm"
                elif point.x <= -options.arm_region_x:
                    arm_region = "right_arm"
            if arm_region is not None:
                arm_weight = min(
                    1.0,
                    (abs(point.x) - options.arm_region_x) / max(options.armhole_blend_width, 1e-6),
                )
                region = arm_region
            else:
                region = "torso"
            assignment_policy_counts["spatial_fallback"] += 1
        surface = surfaces[region]
        region_counts[region] += 1
        nearest = surface["bvh"].find_nearest(point)
        if nearest is None:
            continue
        nearest_point, _normal, face_index, _distance = nearest
        transfer_groups = surface["transfer_groups"]
        blended: dict[int, float] = {}
        for source_index, vertex_factor in face_weight_factors(surface, face_index, nearest_point):
            nearest_counts[str(source_index)] = nearest_counts.get(str(source_index), 0) + 1
            for assignment in actor.data.vertices[source_index].groups:
                assignment_name = group_names.get(assignment.group)
                if assignment_name not in transfer_groups:
                    continue
                weight = assignment.weight * vertex_factor
                if "Forearm" in assignment_name:
                    weight *= forearm_factor
                blended[assignment.group] = blended.get(assignment.group, 0.0) + weight
        total = sum(blended.values())
        if total <= 1e-8:
            continue
        combined: dict[int, float] = {}
        if region != "torso" and arm_weight < 1.0:
            # Keep the arm and torso contributions in one map and normalize
            # once.  Writing the arm weights first and then adding torso
            # weights leaves sums above 1.0 at the armhole, which causes a
            # second deformation error rather than a smooth transition.
            for group_index, weight in blended.items():
                combined[group_index] = combined.get(group_index, 0.0) + weight * arm_weight / total
        else:
            for group_index, weight in blended.items():
                combined[group_index] = combined.get(group_index, 0.0) + weight / total
        if region != "torso" and arm_weight < 1.0:
            torso_surface = surfaces["torso"]
            torso_nearest = torso_surface["bvh"].find_nearest(point)
            if torso_nearest is not None:
                torso_point, _normal, torso_face_index, _distance = torso_nearest
                for source_index, factor in face_weight_factors(
                    torso_surface, torso_face_index, torso_point
                ):
                    for assignment in actor.data.vertices[source_index].groups:
                        name = group_names.get(assignment.group)
                        if name not in torso_groups:
                            continue
                        combined[assignment.group] = combined.get(assignment.group, 0.0) + (
                            (1.0 - arm_weight) * assignment.weight * factor
                        )
        combined_total = sum(combined.values())
        if combined_total <= 1e-8:
            continue
        combined = {
            group_index: weight / combined_total
            for group_index, weight in combined.items()
        }
        if (
            upperarm_group_name is not None
            and options.armhole_upperarm_min_weight > 0.0
            and options.armhole_upperarm_width > 0.0
            and seam_distance < options.armhole_upperarm_width
        ):
            upperarm_index = next(
                (
                    group_index
                    for group_index, name in group_names.items()
                    if name == upperarm_group_name
                ),
                None,
            )
            if upperarm_index is not None:
                fade = 1.0 - seam_distance / options.armhole_upperarm_width
                target = options.armhole_upperarm_min_weight * fade
                current = combined.get(upperarm_index, 0.0)
                if current < target and current < 1.0 - 1e-8:
                    other_scale = (1.0 - target) / (1.0 - current)
                    combined = {
                        group_index: (
                            target if group_index == upperarm_index else weight * other_scale
                        )
                        for group_index, weight in combined.items()
                    }
                    combined[upperarm_index] = target
        for group_index, weight in combined.items():
            name = group_names.get(group_index)
            if name is not None and weight > 1e-8:
                garment_groups[name].add([vertex.index], weight, "REPLACE")
        face_counts[f"{region}:{face_index}"] = face_counts.get(f"{region}:{face_index}", 0) + 1
    return {
        "actor_vertices": len(actor.data.vertices),
        "garment_vertices": len(garment.data.vertices),
        "garment_vertex_groups": len(garment_groups),
        "torso_source_faces": len(surfaces["torso"]["faces"]),
        "left_arm_source_faces": len(surfaces["left_arm"]["faces"]),
        "right_arm_source_faces": len(surfaces["right_arm"]["faces"]),
        "torso_source_vertices": len(surfaces["torso"]["source_indices"]),
        "left_arm_source_vertices": len(surfaces["left_arm"]["source_indices"]),
        "right_arm_source_vertices": len(surfaces["right_arm"]["source_indices"]),
        "region_assignment_counts": region_counts,
        "assignment_policy": (
            "garmentcode_panel_membership" if panel_memberships is not None else "spatial_fallback"
        ),
        "assignment_policy_counts": assignment_policy_counts,
        "armhole_arm_weight": options.armhole_arm_weight if panel_memberships is not None else None,
        "armhole_blend_width": options.armhole_blend_width if panel_memberships is not None else None,
        "weight_interpolation": options.weight_interpolation,
        "include_forearm_weights": options.include_forearm_weights,
        "forearm_fade_width": options.forearm_fade_width,
        "armhole_upperarm_min_weight": options.armhole_upperarm_min_weight,
        "armhole_upperarm_width": options.armhole_upperarm_width,
        "posterior_armhole_torso_blend_width": options.posterior_armhole_torso_blend_width,
        "posterior_armhole_arm_weight": options.posterior_armhole_arm_weight,
        "unique_nearest_actor_vertices": len(nearest_counts),
        "unique_nearest_actor_faces": len(face_counts),
    }


def main() -> int:
    options = cli_args()
    if not 0.0 <= options.armhole_arm_weight <= 1.0:
        raise ValueError("--armhole-arm-weight must be between 0 and 1")
    if options.armhole_blend_width < 0.0:
        raise ValueError("--armhole-blend-width must be non-negative")
    if options.forearm_fade_width < 0.0:
        raise ValueError("--forearm-fade-width must be non-negative")
    if not 0.0 <= options.armhole_upperarm_min_weight <= 1.0:
        raise ValueError("--armhole-upperarm-min-weight must be between 0 and 1")
    if options.armhole_upperarm_width < 0.0:
        raise ValueError("--armhole-upperarm-width must be non-negative")
    if options.posterior_armhole_torso_blend_width < 0.0:
        raise ValueError("--posterior-armhole-torso-blend-width must be non-negative")
    if not 0.0 <= options.posterior_armhole_arm_weight <= 1.0:
        raise ValueError("--posterior-armhole-arm-weight must be between 0 and 1")
    panel_memberships = None
    membership_source = None
    if options.panel_membership is not None:
        membership_source = options.panel_membership.resolve()
        if not membership_source.is_file():
            raise FileNotFoundError(membership_source)
        membership_report = json.loads(membership_source.read_text(encoding="utf-8"))
        if membership_report.get("schema") != "assetsstudio_garmentcode_panel_membership_v1":
            raise RuntimeError(f"unsupported panel-membership schema: {membership_source}")
        expected_sim_hash = membership_report.get("sim_obj", {}).get("sha256")
        actual_sim_hash = sha256(options.sim_obj.resolve())
        if expected_sim_hash != actual_sim_hash:
            raise RuntimeError(
                "panel-membership/simulation hash mismatch: "
                f"{expected_sim_hash} != {actual_sim_hash}"
            )
        panel_memberships = membership_report["vertex_panels"]
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if actor is None or armature is None:
        raise RuntimeError("Actor blend is missing the expected mesh or Armature")

    remove_existing(options.garment_name)
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(options.sim_obj.resolve()))
    imported = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    if len(imported) != 1:
        raise RuntimeError(f"expected one imported simulation mesh, got {len(imported)}")
    garment = imported[0]
    garment.name = options.garment_name
    # GarmentCode OBJ is centimetres in (x, y-up, z-depth).
    for vertex in garment.data.vertices:
        gc = vertex.co.copy() * 0.01
        vertex.co = Vector((gc.x, -gc.z, gc.y))
    garment.location = (0.0, 0.0, 0.0)
    garment.rotation_euler = (0.0, 0.0, 0.0)
    garment.scale = (1.0, 1.0, 1.0)
    # Force the imported OBJ transform reset before using world-space points
    # for Actor-surface weight transfer.  Without this update Blender can
    # still expose the OBJ importer's stale matrix to the diagnostic mapper.
    bpy.context.view_layer.update()
    if panel_memberships is not None and len(panel_memberships) != len(garment.data.vertices):
        raise RuntimeError(
            "panel-membership/garment vertex count mismatch: "
            f"{len(panel_memberships)} != {len(garment.data.vertices)}"
        )

    material = bpy.data.materials.new("GarmentCodeActorTransfer_Material")
    material.diffuse_color = (0.36, 0.10, 0.58, 1.0)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    if shader is not None:
        shader.inputs["Base Color"].default_value = (0.36, 0.10, 0.58, 1.0)
        shader.inputs["Roughness"].default_value = 0.86
    garment.data.materials.clear()
    garment.data.materials.append(material)

    weight_report = transfer_weights(garment, actor, options, panel_memberships)
    modifier = garment.modifiers.new("ActorArmature_GarmentCodeTransfer", "ARMATURE")
    modifier.object = armature
    actor_armature_modifiers = [item for item in actor.modifiers if item.type == "ARMATURE"]
    if len(actor_armature_modifiers) != 1:
        raise RuntimeError(
            "expected exactly one Actor armature modifier, got "
            f"{len(actor_armature_modifiers)}"
        )
    actor_armature_modifier = actor_armature_modifiers[0]
    # The garment and Actor must use the same skinning algorithm.  Forcing
    # preserve-volume (dual-quaternion) here while the Actor uses linear blend
    # skinning makes otherwise matching weights diverge around the shoulders,
    # armholes and neckline as soon as the action starts.
    if options.skinning_mode == "actor":
        modifier.use_deform_preserve_volume = actor_armature_modifier.use_deform_preserve_volume
    else:
        modifier.use_deform_preserve_volume = options.skinning_mode == "preserve-volume"
    garment["assetsstudio_transfer_schema"] = "assetsstudio_garmentcode_sim_actor_transfer_v1"
    garment["assetsstudio_source_sim_obj"] = str(options.sim_obj.resolve())
    garment["assetsstudio_surface_policy"] = "GarmentCode simulation geometry; no shrinkwrap or repair"

    bpy.context.view_layer.objects.active = garment
    garment.select_set(True)
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    blend_path = output / "garmentcode_actor_transfer.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    points = [garment.matrix_world @ vertex.co for vertex in garment.data.vertices]
    report = {
        "schema": "assetsstudio_garmentcode_sim_actor_transfer_v1",
        "actor_blend": str(options.actor_blend.resolve()),
        "sim_obj": str(options.sim_obj.resolve()),
        "output_blend": str(blend_path),
        "garment_name": garment.name,
        "coordinate_mapping": "GarmentCode centimetres (x,y-up,z-depth) -> Blender metres (x,-z-depth,y-up)",
        "geometry_policy": "direct simulation geometry; no shrinkwrap, scale fit, surface push, or seam repair",
        "panel_membership": str(membership_source) if membership_source else None,
        "mesh": {
            "vertices": len(garment.data.vertices),
            "polygons": len(garment.data.polygons),
            "bounds_m": [
                [min(point[index] for point in points) for index in range(3)],
                [max(point[index] for point in points) for index in range(3)],
            ],
        },
        "weight_transfer": weight_report,
        "skinning": {
            "actor_modifier": actor_armature_modifier.name,
            "actor_preserve_volume": actor_armature_modifier.use_deform_preserve_volume,
            "garment_preserve_volume": modifier.use_deform_preserve_volume,
            "policy": options.skinning_mode,
        },
        "status": "review_required",
    }
    (output / "transfer_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
