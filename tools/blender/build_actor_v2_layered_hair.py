"""Build a clean, source-locked layered hairstyle for Actor V2.

The first Actor V2 hair candidate came from Hunyuan3D-2MV.  Its input masks
contained connected skin/eyebrow pixels and the generated mesh consequently
contained melted bridges and noisy fragments.  This compiler intentionally
does not repair that mesh.  It rebuilds the approved chunky hairstyle as a
deterministic scalp shell plus named tapered locks, using the approved four
view sheet as the silhouette contract.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hair_fit_support as fit_tools


HEAD_BONE = "CC_Base_Head"
HAIR_OBJECT = "HeadHair_DefaultAdventurer_V2_Layered"


@dataclass(frozen=True)
class LockRecipe:
    name: str
    root: tuple[float, float, float]
    tip: tuple[float, float, float]
    width: float
    thickness: float
    outward: tuple[float, float, float]
    across: tuple[float, float, float]
    bulge: float
    layer: str


LOCKS = (
    # Front silhouette: five broad, readable pieces instead of dozens of
    # generated crumbs.  Front is -Y in the Actor coordinate contract.
    LockRecipe("front_outer_L", (-0.27, -0.27, 1.96), (-0.40, -0.36, 1.47), 0.18, 0.075, (0, -1, 0), (1, 0, 0), 0.055, "front"),
    LockRecipe("front_sweep_L", (-0.15, -0.31, 2.03), (-0.23, -0.43, 1.58), 0.25, 0.085, (0, -1, 0), (1, 0, 0), 0.075, "front"),
    LockRecipe("front_center", (0.08, -0.32, 2.04), (-0.02, -0.44, 1.55), 0.29, 0.090, (0, -1, 0), (1, 0, 0), 0.085, "front"),
    LockRecipe("front_sweep_R", (0.24, -0.27, 1.99), (0.27, -0.40, 1.57), 0.21, 0.080, (0, -1, 0), (1, 0, 0), 0.065, "front"),
    LockRecipe("front_outer_R", (0.34, -0.20, 1.91), (0.40, -0.31, 1.45), 0.15, 0.070, (0, -1, 0), (1, 0, 0), 0.050, "front"),
    # Left and right temple/rear transitions.  These locks own the side-view
    # outline and leave the detachable EarPair readable.
    LockRecipe("side_L_front", (-0.43, -0.22, 1.91), (-0.49, -0.18, 1.49), 0.18, 0.075, (-1, 0, 0), (0, 1, 0), 0.050, "side"),
    LockRecipe("side_L_mid", (-0.44, -0.01, 1.93), (-0.50, 0.04, 1.40), 0.20, 0.080, (-1, 0, 0), (0, 1, 0), 0.055, "side"),
    LockRecipe("side_L_back", (-0.42, 0.20, 1.91), (-0.47, 0.32, 1.31), 0.20, 0.080, (-1, 0, 0), (0, 1, 0), 0.050, "side"),
    LockRecipe("side_R_front", (0.43, -0.22, 1.91), (0.49, -0.18, 1.49), 0.18, 0.075, (1, 0, 0), (0, 1, 0), 0.050, "side"),
    LockRecipe("side_R_mid", (0.44, -0.01, 1.93), (0.50, 0.04, 1.40), 0.20, 0.080, (1, 0, 0), (0, 1, 0), 0.055, "side"),
    LockRecipe("side_R_back", (0.42, 0.20, 1.91), (0.47, 0.32, 1.31), 0.20, 0.080, (1, 0, 0), (0, 1, 0), 0.050, "side"),
    # Back view: a restrained two-row rhythm matching the approved master.
    LockRecipe("back_outer_L", (-0.31, 0.28, 1.94), (-0.37, 0.48, 1.42), 0.20, 0.080, (0, 1, 0), (1, 0, 0), 0.060, "back"),
    LockRecipe("back_center_L", (-0.14, 0.34, 2.01), (-0.16, 0.54, 1.34), 0.24, 0.090, (0, 1, 0), (1, 0, 0), 0.075, "back"),
    LockRecipe("back_center_R", (0.10, 0.34, 2.02), (0.12, 0.54, 1.34), 0.24, 0.090, (0, 1, 0), (1, 0, 0), 0.075, "back"),
    LockRecipe("back_outer_R", (0.30, 0.28, 1.94), (0.36, 0.48, 1.42), 0.20, 0.080, (0, 1, 0), (1, 0, 0), 0.060, "back"),
    LockRecipe("back_lower_L", (-0.23, 0.39, 1.75), (-0.25, 0.50, 1.30), 0.19, 0.070, (0, 1, 0), (1, 0, 0), 0.050, "back_lower"),
    LockRecipe("back_lower_C", (0.00, 0.43, 1.76), (0.00, 0.55, 1.26), 0.20, 0.075, (0, 1, 0), (1, 0, 0), 0.055, "back_lower"),
    LockRecipe("back_lower_R", (0.23, 0.39, 1.75), (0.25, 0.50, 1.30), 0.19, 0.070, (0, 1, 0), (1, 0, 0), 0.050, "back_lower"),
    # Two clean crown accents reproduce the source cowlick without a noisy
    # generated spike field.
    LockRecipe("crown_main", (-0.18, -0.09, 2.04), (0.10, -0.12, 2.18), 0.20, 0.070, (0, -1, 0), (1, 0, 0), 0.060, "crown"),
    LockRecipe("crown_small", (0.12, -0.07, 2.03), (-0.04, -0.13, 2.13), 0.14, 0.055, (0, -1, 0), (1, 0, 0), 0.045, "crown"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(raw)


def append_mesh(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    new_vertices: list[Vector],
    new_faces: list[tuple[int, ...]],
) -> None:
    offset = len(vertices)
    vertices.extend(tuple(point) for point in new_vertices)
    faces.extend(tuple(offset + index for index in face) for face in new_faces)


def scalp_shell() -> tuple[list[Vector], list[tuple[int, ...]]]:
    """Return a smooth hollow cap with a higher front hairline."""
    center = Vector((0.0, 0.055, 1.59))
    radii = Vector((0.485, 0.495, 0.535))
    lon_steps = 40
    ring_steps = 13
    outer: list[Vector] = [center + Vector((0.0, 0.0, radii.z))]
    inner: list[Vector] = [center + Vector((0.0, 0.0, radii.z - 0.035))]
    for ring in range(1, ring_steps + 1):
        ratio = ring / ring_steps
        for longitude in range(lon_steps):
            phi = 2.0 * math.pi * longitude / lon_steps
            front_weight = max(0.0, -math.sin(phi))
            back_weight = max(0.0, math.sin(phi))
            side_weight = abs(math.cos(phi))
            # Keep the front shell above the brows.  The visible hairline is
            # authored by the tapered fringe locks, not by a helmet-like cap
            # edge crossing the forehead.
            theta_limit = math.radians(122.0 - 60.0 * front_weight + 23.0 * back_weight - 5.0 * side_weight)
            theta = ratio * theta_limit
            direction = Vector((math.sin(theta) * math.cos(phi), math.sin(theta) * math.sin(phi), math.cos(theta)))
            outer.append(center + Vector((radii.x * direction.x, radii.y * direction.y, radii.z * direction.z)))
            inner_radii = radii - Vector((0.035, 0.035, 0.035))
            inner.append(center + Vector((inner_radii.x * direction.x, inner_radii.y * direction.y, inner_radii.z * direction.z)))

    vertices = outer + inner
    faces: list[tuple[int, ...]] = []
    outer_count = len(outer)
    for longitude in range(lon_steps):
        next_lon = (longitude + 1) % lon_steps
        faces.append((0, 1 + longitude, 1 + next_lon))
        faces.append((outer_count, outer_count + 1 + next_lon, outer_count + 1 + longitude))
    for ring in range(1, ring_steps):
        previous = 1 + (ring - 1) * lon_steps
        current = 1 + ring * lon_steps
        for longitude in range(lon_steps):
            next_lon = (longitude + 1) % lon_steps
            faces.append((previous + longitude, current + longitude, current + next_lon, previous + next_lon))
            faces.append((outer_count + previous + next_lon, outer_count + current + next_lon, outer_count + current + longitude, outer_count + previous + longitude))
    last = 1 + (ring_steps - 1) * lon_steps
    for longitude in range(lon_steps):
        next_lon = (longitude + 1) % lon_steps
        faces.append((last + longitude, outer_count + last + longitude, outer_count + last + next_lon, last + next_lon))
    return vertices, faces


def tapered_lock(recipe: LockRecipe, segments: int = 10, sides: int = 8) -> tuple[list[Vector], list[tuple[int, ...]]]:
    root = Vector(recipe.root)
    tip = Vector(recipe.tip)
    outward = Vector(recipe.outward).normalized()
    across = Vector(recipe.across).normalized()
    # Keep both cross-section axes orthogonal so broad locks remain flat and
    # readable rather than turning into tubes.
    outward = (outward - across * outward.dot(across)).normalized()
    vertices: list[Vector] = []
    ring_count = segments
    for segment in range(ring_count):
        t = segment / ring_count
        center = root.lerp(tip, t) + outward * (recipe.bulge * math.sin(math.pi * t))
        # Roots begin narrow inside the cap, broaden into one coherent lobe,
        # then converge to the explicit tip.  This removes the straight,
        # cut-off root faces visible in the first deterministic draft.
        fullness = 0.16 + 0.84 * (math.sin(math.pi * t) ** 0.72)
        half_width = recipe.width * 0.5 * fullness
        half_thickness = recipe.thickness * 0.5 * (0.22 + 0.78 * math.sin(math.pi * t))
        for side in range(sides):
            angle = 2.0 * math.pi * side / sides
            vertices.append(center + across * (half_width * math.cos(angle)) + outward * (half_thickness * math.sin(angle)))
    tip_index = len(vertices)
    vertices.append(tip)
    faces: list[tuple[int, ...]] = []
    faces.append(tuple(reversed(tuple(range(sides)))))
    for ring in range(ring_count - 1):
        current = ring * sides
        following = (ring + 1) * sides
        for side in range(sides):
            next_side = (side + 1) % sides
            faces.append((current + side, following + side, following + next_side, current + next_side))
    final_ring = (ring_count - 1) * sides
    for side in range(sides):
        faces.append((final_ring + side, tip_index, final_ring + (side + 1) % sides))
    return vertices, faces


def remove_old_hair() -> list[str]:
    removed: list[str] = []
    for obj in list(bpy.data.objects):
        is_hair = obj.get("assetsstudio_slot_id") == "head_hair" or obj.name in {
            "HairCandidate_Blend",
            "HeadHair_DefaultAdventurer_V1_Source",
            HAIR_OBJECT,
        }
        if is_hair:
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    return removed


def make_material() -> bpy.types.Material:
    material = bpy.data.materials.get("MAT_HeadHair_Chestnut_V2") or bpy.data.materials.new("MAT_HeadHair_Chestnut_V2")
    material.diffuse_color = (0.24, 0.105, 0.055, 1.0)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.24, 0.105, 0.055, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.72
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.16
    return material


def build_hair(armature: bpy.types.Object) -> bpy.types.Object:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    cap_vertices, cap_faces = scalp_shell()
    append_mesh(vertices, faces, cap_vertices, cap_faces)
    for recipe in LOCKS:
        lock_vertices, lock_faces = tapered_lock(recipe)
        append_mesh(vertices, faces, lock_vertices, lock_faces)
    mesh = bpy.data.meshes.new(HAIR_OBJECT + "Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    hair = bpy.data.objects.new(HAIR_OBJECT, mesh)
    bpy.context.scene.collection.objects.link(hair)
    hair.data.materials.append(make_material())
    for polygon in hair.data.polygons:
        polygon.use_smooth = True
        polygon.material_index = 0
    hair["assetsstudio_slot_id"] = "head_hair"
    hair["assetsstudio_asset_id"] = "head_hair/default_adventurer_v2_layered"
    hair["assetsstudio_source_kind"] = "deterministic_source_locked_layered_mesh"
    hair["assetsstudio_reference_contract"] = "approved Actor V2 four-view master"
    world = hair.matrix_world.copy()
    hair.parent = armature
    hair.parent_type = "BONE"
    hair.parent_bone = HEAD_BONE
    hair.matrix_world = world
    return hair


def configure_closeup_render(scene: bpy.types.Scene) -> None:
    fit_tools.configure_render(scene)
    scene.render.resolution_x = 768
    scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    rim_data = bpy.data.lights.new("HairV2RimData", "AREA")
    rim_data.energy = 500.0
    rim_data.shape = "DISK"
    rim_data.size = 3.0
    rim = bpy.data.objects.new("HairV2Rim", rim_data)
    scene.collection.objects.link(rim)
    rim.location = Vector((0.0, 4.0, 4.0))
    rim.rotation_euler = (Vector((0.0, 0.1, 1.65)) - rim.location).to_track_quat("-Z", "Y").to_euler()


def render_closeups(scene: bpy.types.Scene, output_dir: Path) -> dict[str, str]:
    target = Vector((0.0, 0.055, 1.68))
    views = {
        "front": Vector((0.0, -8.0, target.z)),
        "right": Vector((8.0, target.y, target.z)),
        "back": Vector((0.0, 8.0, target.z)),
        "left": Vector((-8.0, target.y, target.z)),
    }
    outputs: dict[str, str] = {}
    for direction, location in views.items():
        camera_data = bpy.data.cameras.new(f"ActorV2HairV2CameraData_{direction}")
        camera_data.type = "ORTHO"
        camera_data.ortho_scale = 1.55
        camera = bpy.data.objects.new(f"ActorV2HairV2Camera_{direction}", camera_data)
        scene.collection.objects.link(camera)
        camera.location = location
        camera.rotation_euler = (target - location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = camera
        output = output_dir / f"{direction}_closeup.png"
        scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)
        outputs[direction] = str(output)
    return outputs


def main() -> int:
    args = parse_args()
    bpy.ops.wm.open_mainfile(filepath=str(args.actor_blend.resolve()))
    armature = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
    removed = remove_old_hair()
    hair = build_hair(armature)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_closeup_render(bpy.context.scene)
    renders = render_closeups(bpy.context.scene, output_dir)
    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    report = {
        "schema": "assetsstudio_actor_v2_layered_hair_compile_v1",
        "status": "review",
        "source_reference": str(args.reference.resolve()),
        "source_policy": "approved four-view silhouette; Hunyuan v1 geometry explicitly rejected",
        "actor_blend": str(args.actor_blend.resolve()),
        "output_blend": str(args.output_blend.resolve()),
        "object": hair.name,
        "parent": {"object": armature.name, "bone": HEAD_BONE, "mode": "rigid_bone_parent"},
        "removed_previous_hair_objects": removed,
        "geometry": {
            "vertices": len(hair.data.vertices),
            "faces": len(hair.data.polygons),
            "scalp_shell": "hollow ellipsoid with raised front hairline",
            "lock_count": len(LOCKS),
            "locks": [asdict(recipe) for recipe in LOCKS],
        },
        "renders": renders,
        "gates": {
            "no_hunyuan_geometry": True,
            "one_runtime_object": True,
            "no_skin_or_eyebrow_source_pixels": True,
            "static_multiview_review": "pending",
            "walk_review": "pending",
        },
    }
    (output_dir / "compile.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ACTOR_V2_LAYERED_HAIR_REVIEW vertices={len(hair.data.vertices)} faces={len(hair.data.polygons)} output={args.output_blend.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
