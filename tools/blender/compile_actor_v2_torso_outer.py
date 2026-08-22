"""Compile the generated default-adventurer torso shell for Actor V2."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
LEGACY_COMPILER = ROOT / "experiments" / "generated_wearables" / "stage9_hunyuan_adapter_transfer_v1"
sys.path.insert(0, str(LEGACY_COMPILER))
import build_hunyuan_jacket_adapter_v1 as support  # noqa: E402


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE_NAME = "Armature"
GARMENT_NAME = "TorsoOuter_DefaultAdventurer_V1"
MASK_NAME = "WearableMask_ActorV2_TorsoOuter_DefaultAdventurer_V1"
NECK_SEAL_NAME = "ActorProfile_NeckSeal_ActorV2"
ALLOWED_BONES = support.ALLOWED_BONES

SOURCE_LOW = -0.683559
SOURCE_HIGH = 0.673580
SOURCE_ARM = [
    Vector((0.38, 0.0, 0.42)),
    Vector((0.66, 0.0, 0.05)),
    Vector((0.90, 0.0, -0.28)),
]

TARGET_LOW = 0.50
TARGET_HIGH = 1.04
TARGET_ARM: list[Vector] = []


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--source-glb", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--reference-dir", required=True, type=Path)
    parser.add_argument("--decimate-ratio", type=float, default=0.18)
    return parser.parse_args(argv)


def calibrate_target_arm(armature: bpy.types.Object) -> None:
    global TARGET_ARM
    upper = armature.data.bones["CC_Base_L_Upperarm"]
    forearm = armature.data.bones["CC_Base_L_Forearm"]
    shoulder = armature.matrix_world @ upper.head_local
    elbow = armature.matrix_world @ forearm.head_local
    TARGET_ARM = [
        Vector((abs(shoulder.x), shoulder.y, shoulder.z)),
        Vector((abs(shoulder.lerp(elbow, 0.30).x), shoulder.lerp(elbow, 0.30).y, shoulder.lerp(elbow, 0.30).z)),
        Vector((abs(shoulder.lerp(elbow, 0.62).x), shoulder.lerp(elbow, 0.62).y, shoulder.lerp(elbow, 0.62).z)),
    ]
    support.TARGET_ARM = TARGET_ARM


def arm_membership(point: Vector) -> float:
    z = min(0.52, max(-0.40, point.z))
    source_arm_center_x = 0.60 - 0.42 * z
    source_torso_half = 0.47 + 0.05 * ((SOURCE_HIGH - z) / (SOURCE_HIGH - SOURCE_LOW))
    threshold = 0.5 * (source_arm_center_x + source_torso_half)
    return support.smoothstep(threshold - 0.055, threshold + 0.055, abs(point.x))


def map_torso(point: Vector) -> Vector:
    t = (point.z - SOURCE_LOW) / (SOURCE_HIGH - SOURCE_LOW)
    z = TARGET_LOW + t * (TARGET_HIGH - TARGET_LOW)
    # Actor V2 is compact and round.  Keep clearance without restoring the
    # wider/taller Actor V1 torso assumptions.
    lower_flare = 1.0 - support.smoothstep(0.68, 0.90, z)
    x_scale = 0.42 + 0.025 * lower_flare
    y_scale = 0.42 + 0.02 * lower_flare
    return Vector((point.x * x_scale, point.y * y_scale - 0.012, z))


def map_arm(point: Vector, side: int) -> tuple[Vector, float]:
    source_xz = Vector((abs(point.x), point.z))
    parameter, source_center, source_tangent = support.closest_polyline_parameter(source_xz, SOURCE_ARM)
    target_center, target_tangent = support.sample_polyline(parameter, TARGET_ARM)
    source_normal = Vector((-source_tangent.y, source_tangent.x))
    target_normal = Vector((-target_tangent.y, target_tangent.x))
    radial = (source_xz - source_center).dot(source_normal)
    radial_scale = 0.88 + 0.12 * support.smoothstep(0.15, 0.85, parameter)
    mapped_xz = Vector((target_center.x, target_center.z)) + target_normal * (radial * radial_scale)
    mapped_xz.x += 0.012 * support.smoothstep(0.25, 0.90, parameter)
    return Vector((side * mapped_xz.x, point.y * 0.76 - 0.010, mapped_xz.y)), parameter


def map_point(point: Vector) -> tuple[Vector, float, float, int]:
    side = 1 if point.x >= 0.0 else -1
    torso = map_torso(point)
    membership = arm_membership(point)
    parameter, _, _ = support.closest_polyline_parameter(
        Vector((abs(point.x), point.z)), SOURCE_ARM
    )
    # Actor V2 and this generated source share a compact downward short-sleeve
    # pose.  Preserve the source silhouette globally; use the arm partition
    # only for weights instead of re-bending the visible sleeve geometry.
    return torso, membership, parameter, side


def torso_weights(point: Vector) -> dict[str, float]:
    z = point.z
    if z <= 0.64:
        return {"CC_Base_Waist": 0.75, "CC_Base_Spine01": 0.25}
    if z <= 0.78:
        t = (z - 0.64) / 0.14
        return {"CC_Base_Waist": 0.75 * (1.0 - t), "CC_Base_Spine01": 0.25 + 0.75 * t}
    if z <= 0.96:
        t = (z - 0.78) / 0.18
        return {"CC_Base_Spine01": 1.0 - 0.90 * t, "CC_Base_Spine02": 0.90 * t}
    return {"CC_Base_Spine02": 1.0}


def arm_weights(parameter: float, side: int) -> dict[str, float]:
    clavicle, upperarm, _forearm, _hand = support.SIDE_BONES[side]
    if parameter <= 0.20:
        t = parameter / 0.20
        return {clavicle: 0.70 * (1.0 - t), upperarm: 0.30 + 0.70 * t}
    return {upperarm: 1.0}


def add_body_mask(actor: bpy.types.Object) -> int:
    old = actor.vertex_groups.get(MASK_NAME)
    if old is not None:
        actor.vertex_groups.remove(old)
    group = actor.vertex_groups.new(name=MASK_NAME)
    names = {item.index: item.name for item in actor.vertex_groups}
    selected: list[int] = []
    for vertex in actor.data.vertices:
        point = actor.matrix_world @ vertex.co
        weights = {
            names.get(item.group): item.weight
            for item in vertex.groups
            if names.get(item.group) is not None
        }
        hand_weight = weights.get("CC_Base_L_Hand", 0.0) + weights.get("CC_Base_R_Hand", 0.0)
        if hand_weight >= 0.10:
            continue
        torso_weight = sum(weights.get(name, 0.0) for name in support.TORSO_BONES)
        clavicle_weight = weights.get("CC_Base_L_Clavicle", 0.0) + weights.get("CC_Base_R_Clavicle", 0.0)
        upperarm_weight = weights.get("CC_Base_L_Upperarm", 0.0) + weights.get("CC_Base_R_Upperarm", 0.0)
        torso = 0.49 <= point.z <= 1.03 and abs(point.x) <= 0.31 and torso_weight >= 0.10
        shoulder = 0.83 <= point.z <= 1.02 and abs(point.x) <= 0.34 and clavicle_weight >= 0.08
        side = 1 if point.x >= 0.0 else -1
        parameter, arm_distance = support.target_arm_coordinates(point, side)
        sleeve = upperarm_weight >= 0.08 and parameter <= 0.72 and arm_distance <= 0.145
        if torso or shoulder or sleeve:
            selected.append(vertex.index)
    if selected:
        group.add(selected, 1.0, "REPLACE")
    return len(selected)


def add_neck_seal(actor: bpy.types.Object, armature: bpy.types.Object) -> bpy.types.Object:
    old = bpy.data.objects.get(NECK_SEAL_NAME)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32,
        radius=0.068,
        depth=0.13,
        end_fill_type="NGON",
        location=(0.0, -0.006, 1.015),
    )
    seal = bpy.context.object
    seal.name = NECK_SEAL_NAME
    seal.scale.y = 0.90
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if actor.data.materials and actor.data.materials[0] is not None:
        seal.data.materials.append(actor.data.materials[0])
    spine = seal.vertex_groups.new(name="CC_Base_Spine02")
    neck = seal.vertex_groups.new(name="CC_Base_NeckTwist01")
    for vertex in seal.data.vertices:
        z = (seal.matrix_world @ vertex.co).z
        neck_weight = support.smoothstep(0.98, 1.08, z)
        spine.add([vertex.index], 1.0 - neck_weight, "REPLACE")
        neck.add([vertex.index], neck_weight, "REPLACE")
    modifier = seal.modifiers.new("ActorArmature", "ARMATURE")
    modifier.object = armature
    modifier.use_vertex_groups = True
    seal["actor_profile_component"] = "neck_occlusion_seal"
    seal["wearable_slot"] = "torso_outer"
    return seal


def make_toon_material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.78
    return material


def load_reference_rgba(path: Path) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    image = bpy.data.images.load(str(path.resolve()), check_existing=False)
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    rgba = pixels.reshape((height, width, 4))
    ys, xs = np.where(rgba[:, :, 3] > 0.10)
    if len(xs) == 0:
        raise RuntimeError(f"reference alpha is empty: {path}")
    bbox = (int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1))
    return rgba, bbox


def assign_projected_palette(
    garment: bpy.types.Object,
    reference_dir: Path,
) -> dict[str, int]:
    """Build clean, exportable color regions from the four source views.

    Directly assigning one projected image per triangle produces visible view
    seams on rounded sleeves.  Sampling the same views into a small semantic
    palette keeps the authored color layout while allowing adjacency cleanup.
    """
    views = {
        name: load_reference_rgba(reference_dir / f"{name}.png")
        for name in ("front", "right", "back", "left")
    }
    points = [vertex.co.copy() for vertex in garment.data.vertices]
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    sizes = high - low
    labels: list[str] = []
    counts = {"blue": 0, "cream": 0, "red": 0, "lining": 0}
    slot = {"blue": 0, "cream": 1, "red": 2, "lining": 3}

    def sample(view: str, horizontal: float, vertical: float) -> tuple[float, float, float, float]:
        rgba, bbox = views[view]
        u0, v0, u1, v1 = bbox
        u = min(1.0, max(0.0, horizontal))
        v = min(1.0, max(0.0, vertical))
        x = min(rgba.shape[1] - 1, max(0, round(u0 + u * max(1, u1 - u0 - 1))))
        y = min(rgba.shape[0] - 1, max(0, round(v0 + v * max(1, v1 - v0 - 1))))
        return tuple(float(value) for value in rgba[y, x])

    for polygon in garment.data.polygons:
        center = polygon.center
        normal = polygon.normal
        vertical = (center.z - low.z) / max(sizes.z, 1e-8)
        if abs(normal.y) >= abs(normal.x):
            if normal.y < 0.0:
                view = "front"
                horizontal = (center.x - low.x) / max(sizes.x, 1e-8)
            else:
                view = "back"
                horizontal = (high.x - center.x) / max(sizes.x, 1e-8)
        elif normal.x > 0.0:
            view = "right"
            horizontal = (high.y - center.y) / max(sizes.y, 1e-8)
        else:
            view = "left"
            horizontal = (center.y - low.y) / max(sizes.y, 1e-8)
        r, g, b, alpha = sample(view, horizontal, vertical)
        if alpha <= 0.10:
            label = "blue"
        elif max(r, g, b) < 0.32:
            label = "lining"
        elif r > g * 1.22 and r > b * 1.30 and r > 0.34:
            label = "red"
        elif r > 0.68 and g > 0.58 and r - b > 0.06:
            label = "cream"
        else:
            label = "blue"
        # Accents are constrained in Actor V2 target space.  These are broad
        # semantic zones, not silhouette edits: red is the wrapped front scarf;
        # cream is the collar/front insert/cuffs; dark lining belongs inside a
        # sleeve opening.  The source projection decides the final label.
        red_allowed = (
            center.z >= 0.78
            and abs(center.x) <= 0.30
            and center.y <= 0.08
            and normal.y <= 0.45
        )
        cuff_zone = abs(center.x) >= 0.27 and center.z <= 0.75
        collar_zone = center.z >= 0.94 and abs(center.x) <= 0.20
        front_insert_zone = (
            center.y <= -0.12
            and normal.y <= -0.25
            and abs(center.x) <= 0.17
            and center.z <= 0.92
        )
        cream_allowed = cuff_zone or collar_zone or front_insert_zone
        lining_allowed = cuff_zone and abs(normal.x) < 0.80
        if label == "red" and not red_allowed:
            label = "blue"
        if label == "cream" and not cream_allowed:
            label = "blue"
        if label == "lining" and not lining_allowed:
            label = "blue"
        labels.append(label)

    # Remove isolated projection fragments without erasing the intentionally
    # separate left/right cuff regions.  Generated meshes are triangulated, so
    # a two-neighbour majority is enough to collapse one-face speckle.
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for polygon in garment.data.polygons:
        for edge in polygon.edge_keys:
            edge_faces.setdefault(tuple(sorted(edge)), []).append(polygon.index)
    neighbours: list[set[int]] = [set() for _ in garment.data.polygons]
    for face_indices in edge_faces.values():
        if len(face_indices) == 2:
            a, b = face_indices
            neighbours[a].add(b)
            neighbours[b].add(a)
    minimum_component = {"cream": 36, "red": 36, "lining": 18}
    for accent, minimum in minimum_component.items():
        pending = {index for index, label in enumerate(labels) if label == accent}
        while pending:
            seed = pending.pop()
            component = {seed}
            frontier = [seed]
            while frontier:
                current = frontier.pop()
                for neighbour in neighbours[current]:
                    if neighbour in pending and labels[neighbour] == accent:
                        pending.remove(neighbour)
                        component.add(neighbour)
                        frontier.append(neighbour)
            if len(component) < minimum:
                for index in component:
                    labels[index] = "blue"
    for _ in range(3):
        updated = labels.copy()
        for index, adjacent in enumerate(neighbours):
            adjacent_labels = [labels[item] for item in adjacent]
            if len(adjacent_labels) < 2:
                continue
            winner = max(set(adjacent_labels), key=adjacent_labels.count)
            if adjacent_labels.count(winner) >= 2 and labels[index] != winner:
                updated[index] = winner
        labels = updated

    garment.data.materials.clear()
    materials = {
        "blue": make_toon_material("TorsoOuter_Blue", (0.045, 0.18, 0.46, 1.0)),
        "cream": make_toon_material("TorsoOuter_Cream", (0.82, 0.64, 0.38, 1.0)),
        "red": make_toon_material("TorsoOuter_ScarfRed", (0.58, 0.07, 0.035, 1.0)),
        "lining": make_toon_material("TorsoOuter_Lining", (0.075, 0.035, 0.018, 1.0)),
    }
    for name in ("blue", "cream", "red", "lining"):
        garment.data.materials.append(materials[name])
    for polygon, label in zip(garment.data.polygons, labels):
        polygon.material_index = slot[label]
        counts[label] += 1
    garment.data.update()
    return counts


def make_projected_material(name: str, image_path: Path) -> bpy.types.Material:
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    for node in list(nodes):
        nodes.remove(node)
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    texture = nodes.new("ShaderNodeTexImage")
    image = bpy.data.images.load(str(image_path.resolve()), check_existing=True)
    image.colorspace_settings.name = "sRGB"
    pixel_values = np.empty(image.size[0] * image.size[1] * 4, dtype=np.float32)
    image.pixels.foreach_get(pixel_values)
    pixel_values = pixel_values.reshape((-1, 4))
    opaque = pixel_values[:, 3] > 0.10
    blue_candidates = opaque & (
        (pixel_values[:, 2] > pixel_values[:, 0] * 1.20)
        & (pixel_values[:, 2] > pixel_values[:, 1] * 1.12)
    )
    if np.any(blue_candidates):
        blue_fill = np.median(pixel_values[blue_candidates, :3], axis=0)
    else:
        blue_fill = np.array((0.055, 0.19, 0.43), dtype=np.float32)
    pixel_values[~opaque, :3] = blue_fill
    pixel_values[~opaque, 3] = 1.0
    image.pixels.foreach_set(pixel_values.reshape(-1))
    image.update()
    image.pack()
    texture.image = image
    principled.inputs["Roughness"].default_value = 0.78
    links.new(texture.outputs["Color"], principled.inputs["Base Color"])
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return material


def assign_projected_uv_materials(
    garment: bpy.types.Object,
    reference_dir: Path,
) -> dict[str, int]:
    """Assign one orthographic texture material and projected UV per face."""
    view_names = ("front", "right", "back", "left")
    references = {
        name: load_reference_rgba(reference_dir / f"{name}.png")
        for name in view_names
    }
    garment.data.materials.clear()
    for view in view_names:
        garment.data.materials.append(
            make_projected_material(
                f"TorsoOuter_DefaultAdventurer_{view.title()}Projection",
                reference_dir / f"{view}.png",
            )
        )
    uv = garment.data.uv_layers.get("UV_MultiviewProjected") or garment.data.uv_layers.new(
        name="UV_MultiviewProjected"
    )
    garment.data.uv_layers.active = uv
    points = [vertex.co.copy() for vertex in garment.data.vertices]
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    sizes = high - low
    counts = {name: 0 for name in view_names}
    index_by_view = {name: index for index, name in enumerate(view_names)}

    def view_and_horizontal(normal: Vector, point: Vector) -> tuple[str, float]:
        if abs(normal.y) >= abs(normal.x):
            if normal.y < 0.0:
                return "front", (point.x - low.x) / max(sizes.x, 1e-8)
            return "back", (high.x - point.x) / max(sizes.x, 1e-8)
        if normal.x > 0.0:
            return "right", (high.y - point.y) / max(sizes.y, 1e-8)
        return "left", (point.y - low.y) / max(sizes.y, 1e-8)

    for polygon in garment.data.polygons:
        view, _ = view_and_horizontal(polygon.normal, polygon.center)
        polygon.material_index = index_by_view[view]
        counts[view] += 1
        rgba, bbox = references[view]
        u0, v0, u1, v1 = bbox
        for loop_index in polygon.loop_indices:
            point = garment.data.vertices[garment.data.loops[loop_index].vertex_index].co
            _, horizontal = view_and_horizontal(polygon.normal, point)
            vertical = (point.z - low.z) / max(sizes.z, 1e-8)
            u_px = u0 + min(1.0, max(0.0, horizontal)) * max(1, u1 - u0 - 1)
            v_px = v0 + min(1.0, max(0.0, vertical)) * max(1, v1 - v0 - 1)
            uv.data[loop_index].uv = (u_px / rgba.shape[1], v_px / rgba.shape[0])
    garment.data.update()
    return counts


def main() -> int:
    args = cli()
    bpy.ops.wm.open_mainfile(filepath=str(args.actor_blend.resolve()))
    bpy.context.scene.frame_set(1)
    actor = bpy.data.objects.get(ACTOR_NAME)
    armature = bpy.data.objects.get(ARMATURE_NAME)
    if actor is None or armature is None:
        raise RuntimeError("Actor V2 body or Armature is missing")
    for name in ALLOWED_BONES:
        if armature.data.bones.get(name) is None:
            raise RuntimeError(f"required Actor V2 bone missing: {name}")
    calibrate_target_arm(armature)
    support.TARGET_ARM = TARGET_ARM
    support.torso_weights = torso_weights
    support.arm_weights = arm_weights

    old = bpy.data.objects.get(GARMENT_NAME)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    existing = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.source_glb.resolve()))
    imported = [obj for obj in bpy.data.objects if obj not in existing and obj.type == "MESH"]
    if not imported:
        raise RuntimeError("Hunyuan torso GLB contains no mesh")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in imported:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = imported[0]
    bpy.ops.object.join()
    garment = bpy.context.object
    garment.name = GARMENT_NAME
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    source_vertices = len(garment.data.vertices)
    source_faces = len(garment.data.polygons)

    decimate = garment.modifiers.new("GeneratedAssetRetopoProxy", "DECIMATE")
    decimate.decimate_type = "COLLAPSE"
    decimate.ratio = args.decimate_ratio
    decimate.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=decimate.name)

    semantics: list[tuple[float, float, int]] = []
    for vertex in garment.data.vertices:
        mapped, membership, parameter, side = map_point(vertex.co.copy())
        vertex.co = mapped
        semantics.append((membership, parameter, side))
    garment.data.update()

    material_face_counts = assign_projected_palette(
        garment, args.reference_dir.resolve()
    )

    weight_counts = support.assign_weights(garment, semantics, armature)
    mask_count = add_body_mask(actor)
    neck_seal = add_neck_seal(actor, armature)
    old_modifier = actor.modifiers.get("PreviewBodyHide_ActorV2_TorsoOuter")
    if old_modifier is not None:
        actor.modifiers.remove(old_modifier)
    mask_modifier = actor.modifiers.new("PreviewBodyHide_ActorV2_TorsoOuter", "MASK")
    mask_modifier.mode = "VERTEX_GROUP"
    mask_modifier.vertex_group = MASK_NAME
    mask_modifier.invert_vertex_group = True

    garment["source_kind"] = "Hunyuan3D-2MV generated garment"
    garment["source_glb"] = str(args.source_glb.resolve())
    garment["actor_class"] = "ActorV2"
    garment["wearable_slot"] = "torso_outer"
    garment["body_mask"] = MASK_NAME
    bpy.context.scene["actor_class"] = "ActorV2"
    bpy.context.scene["wearable_slot"] = "torso_outer"

    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    report = {
        "schema": "assetsstudio_actor_v2_torso_outer_compile_v1",
        "status": "compiled_motion_and_visual_review_required",
        "actor_class": "ActorV2",
        "slot": "torso_outer",
        "source_glb": str(args.source_glb.resolve()),
        "source_vertices": source_vertices,
        "source_faces": source_faces,
        "compiled_vertices": len(garment.data.vertices),
        "compiled_faces": len(garment.data.polygons),
        "decimate_ratio": args.decimate_ratio,
        "bounds_frame_1": support.bounds(garment),
        "target_vertical_range": [TARGET_LOW, TARGET_HIGH],
        "target_arm": [list(point) for point in TARGET_ARM],
        "allowed_bones": ALLOWED_BONES,
        "weight_counts": weight_counts,
        "body_mask": {"name": MASK_NAME, "vertex_count": mask_count},
        "neck_seal": neck_seal.name,
        "material_stage": "four-view sampled semantic toon palette",
        "reference_dir": str(args.reference_dir.resolve()),
        "material_face_counts": material_face_counts,
    }
    args.manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"ACTOR_V2_TORSO_OUTER_COMPILE_PASS vertices={len(garment.data.vertices)} "
        f"faces={len(garment.data.polygons)} output={args.output_blend.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
