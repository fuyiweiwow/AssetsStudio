"""Build a recipe-driven, rest-pose 2D robe silhouette prototype.

This is deliberately a diagnostic Blender layer. It does not replace the
GarmentCode pattern or its simulation OBJ, and it is not eligible for formal
garment promotion. Its purpose is to validate the 2D silhouette, long sleeves,
and four-direction readability when physical simulation is too expensive for
the current CPU path.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import render_accurig_chibi_walk_test as actor_render  # noqa: E402


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--resolution", type=int, default=256)
    return parser.parse_args(argv)


def fail(message: str) -> None:
    raise RuntimeError(f"ROBE_2D_PROTOTYPE_FAIL: {message}")


def load_recipe(path: Path) -> dict:
    recipe = json.loads(path.read_text(encoding="utf-8"))
    if recipe.get("schema") != "assetsstudio_garment_recipe_v1":
        fail("unexpected recipe schema")
    if recipe.get("archetype") not in {"mage_robe_body_v2", "mage_robe_body_v3"}:
        fail("2D prototype requires mage_robe_body_v2 or mage_robe_body_v3")
    params = recipe.get("parameters", {})
    for key in (
        "length_factor",
        "body_width_factor",
        "robe_lower_flare",
        "sleeve_length_factor",
    ):
        if float(params.get(key, 0)) <= 0:
            fail(f"recipe parameter must be positive: {key}")
    return recipe


def srgb_channel(value: int) -> float:
    value = value / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def hex_rgba(value: str) -> tuple[float, float, float, float]:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        fail(f"invalid material color: {value}")
    return tuple(srgb_channel(int(value[index : index + 2], 16)) for index in (1, 3, 5)) + (1.0,)


def make_material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is not None:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.9
        principled.inputs["Emission Color"].default_value = color
        principled.inputs["Emission Strength"].default_value = 0.12
    return material


def create_mesh(name: str, vertices: list[Vector], faces: list[tuple[int, ...]], material: bpy.types.Material) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata([tuple(vertex) for vertex in vertices], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = False
    return obj


def create_robe_shell(actor: bpy.types.Object, recipe: dict, material: bpy.types.Material) -> bpy.types.Object:
    low, high = actor_render.bounds(actor)
    height = high.z - low.z
    armature = bpy.data.objects.get("Armature")
    left_upperarm = armature.data.bones.get("CC_Base_L_Upperarm") if armature else None
    right_upperarm = armature.data.bones.get("CC_Base_R_Upperarm") if armature else None
    if left_upperarm is None or right_upperarm is None:
        fail("missing Actor shoulder bones for robe shell")
    left_shoulder = armature.matrix_world @ left_upperarm.head_local
    right_shoulder = armature.matrix_world @ right_upperarm.head_local
    shoulder_z = (left_shoulder.z + right_shoulder.z) * 0.5
    # These anchors are intentionally tied to the current Actor shoulders and
    # feet. They are a silhouette prototype, not a replacement for GarmentCode
    # measurements.
    top_z = shoulder_z + height * 0.045
    robe_span = height * 0.46 * float(recipe["parameters"]["length_factor"])
    hem_z = max(low.z + height * 0.035, top_z - robe_span)
    waist_z = top_z - robe_span * 0.43
    actor_width = high.x - low.x
    actor_depth = high.y - low.y
    shoulder_half = abs(left_shoulder.x - right_shoulder.x) * 0.5
    top_half = (shoulder_half + actor_width * 0.035) * float(recipe["parameters"]["body_width_factor"])
    waist_half = top_half * 0.96
    hem_half = waist_half * (
        1.15
        + 0.20 * float(recipe["parameters"]["hem_flare"])
        + 0.25 * float(recipe["parameters"]["robe_lower_flare"])
    )
    top_depth = max(actor_depth * 0.11, 0.22)
    hem_depth = top_depth * 1.08
    center_y = (low.y + high.y) * 0.5

    vertices = [
        Vector((-top_half, center_y - top_depth, top_z)),
        Vector((top_half, center_y - top_depth, top_z)),
        Vector((top_half, center_y + top_depth, top_z)),
        Vector((-top_half, center_y + top_depth, top_z)),
        Vector((-waist_half, center_y - top_depth * 1.03, waist_z)),
        Vector((waist_half, center_y - top_depth * 1.03, waist_z)),
        Vector((waist_half, center_y + top_depth * 1.03, waist_z)),
        Vector((-waist_half, center_y + top_depth * 1.03, waist_z)),
        Vector((-hem_half, center_y - hem_depth, hem_z)),
        Vector((hem_half, center_y - hem_depth, hem_z)),
        Vector((hem_half, center_y + hem_depth, hem_z)),
        Vector((-hem_half, center_y + hem_depth, hem_z)),
    ]
    faces = [
        (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),
        (4, 5, 9, 8), (5, 6, 10, 9), (6, 7, 11, 10), (7, 4, 8, 11),
        (8, 9, 10, 11),
    ]
    obj = create_mesh("RobeBody_2DPrototype", vertices, faces, material)
    obj["assetsstudio_prototype_kind"] = "2d_silhouette_only"
    obj["assetsstudio_source_recipe"] = recipe["recipe_id"]
    obj["assetsstudio_physical_status"] = "not_simulated"
    return obj


def create_sleeve(
    actor: bpy.types.Object,
    armature: bpy.types.Object,
    side: str,
    recipe: dict,
    material: bpy.types.Material,
) -> bpy.types.Object:
    upper = armature.data.bones.get(f"CC_Base_{side}_Upperarm")
    hand = armature.data.bones.get(f"CC_Base_{side}_Hand")
    if upper is None or hand is None:
        fail(f"missing Actor arm bones for {side}")
    shoulder = armature.matrix_world @ upper.head_local
    hand_end = armature.matrix_world @ hand.tail_local
    fraction = min(float(recipe["parameters"]["sleeve_length_factor"]), 1.0)
    end = shoulder.lerp(hand_end, fraction)
    axis = (end - shoulder).normalized()
    reference = Vector((0.0, 1.0, 0.0))
    if abs(axis.dot(reference)) > 0.92:
        reference = Vector((1.0, 0.0, 0.0))
    basis_a = axis.cross(reference).normalized()
    basis_b = axis.cross(basis_a).normalized()
    actor_low, actor_high = actor_render.bounds(actor)
    actor_width = actor_high.x - actor_low.x
    start_radius = actor_width * 0.105
    end_radius = actor_width * 0.085
    vertices: list[Vector] = []
    for center, radius in ((shoulder, start_radius), (end, end_radius)):
        for index in range(8):
            angle = math.tau * index / 8.0
            vertices.append(center + radius * (math.cos(angle) * basis_a + math.sin(angle) * basis_b))
    faces = []
    for index in range(8):
        next_index = (index + 1) % 8
        faces.append((index, next_index, 8 + next_index, 8 + index))
    faces.append(tuple(range(7, -1, -1)))
    faces.append(tuple(range(8, 16)))
    obj = create_mesh(f"RobeLongSleeve_2DPrototype_{side}", vertices, faces, material)
    obj["assetsstudio_prototype_kind"] = "2d_silhouette_only"
    obj["assetsstudio_sleeve_fraction"] = fraction
    obj["assetsstudio_physical_status"] = "not_simulated"
    return obj


def render_views(scene: bpy.types.Scene, actor: bpy.types.Object, robe_objects: list[bpy.types.Object], output: Path, resolution: int) -> list[str]:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    actor_render.configure_soft_toon_lighting(scene)
    low, high = actor_render.bounds(actor)
    robe_low = min((min((obj.matrix_world @ Vector(corner)).z for corner in obj.bound_box) for obj in robe_objects), default=low.z)
    low = Vector((min(low.x, -0.8), min(low.y, -0.8), min(low.z, robe_low)))
    high = Vector((max(high.x, 0.8), max(high.y, 0.8), max(high.z, 1.0)))
    target = Vector(((low.x + high.x) * 0.5, (low.y + high.y) * 0.5, (low.z + high.z) * 0.5))
    cameras = {
        direction: actor_render.make_camera(scene, target, low, high, direction, location)
        for direction, location in {
            "front": (0.0, -12.0, target.z),
            "right": (12.0, 0.0, target.z),
            "back": (0.0, 12.0, target.z),
            "left": (-12.0, 0.0, target.z),
        }.items()
    }
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for direction, camera in cameras.items():
        scene.camera = camera
        scene.frame_set(0)
        scene.render.filepath = str(output / f"{direction}.png")
        bpy.ops.render.render(write_still=True)
        paths.append(str((output / f"{direction}.png").resolve()))
        bpy.data.objects.remove(camera, do_unlink=True)
    return paths


def main() -> int:
    options = cli_args()
    recipe = load_recipe(options.recipe.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    scene = bpy.context.scene
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if actor is None or armature is None:
        fail("Actor blend must contain ChibiBaseMesh_AccuRIG_InputMesh and Armature")
    actor_render.reset_pose(armature)
    main_material = make_material("AssetsStudio_Robe2DPrototype", hex_rgba(recipe["materials"]["main_color"]))
    robe = create_robe_shell(actor, recipe, main_material)
    sleeves = [create_sleeve(actor, armature, side, recipe, main_material) for side in ("L", "R")]
    robe_objects = [robe, *sleeves]
    output = options.output.resolve()
    frames = render_views(scene, actor, robe_objects, output / "review", options.resolution)
    blend_path = output / "mage_robe_body_2d_prototype.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    manifest = {
        "schema": "assetsstudio_garment_2d_prototype_v1",
        "prototype_kind": "2d_silhouette_only",
        "status": "review_required",
        "recipe": str(options.recipe.resolve()),
        "actor_blend": str(options.actor_blend.resolve()),
        "construction": "Recipe-driven Blender diagnostic shell using current Actor bounds and rest-pose arm bones",
        "physical_status": "not_simulated; do_not_promote_to_formal_garment",
        "components": [obj.name for obj in robe_objects],
        "candidate_blend": str(blend_path.resolve()),
        "review_frames": frames,
        "parameters": recipe["parameters"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
