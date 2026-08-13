"""Render an Actor clothing candidate with the project's face and walk action."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(TOOLS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR.parent))

import render_accurig_chibi_walk_test as actor_render  # noqa: E402
from garment_material_recipe import hex_to_linear_rgba, load_material_library, resolve_recipe  # noqa: E402


DIRECTIONS = ("front", "right", "back", "left")


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--frames", type=int, default=8)
    parser.add_argument("--resolution", type=int, default=256)
    parser.add_argument("--appearance-seed", type=int, default=20260808)
    parser.add_argument("--face-style", type=int, choices=range(actor_render.FACE_STYLE_COUNT))
    parser.add_argument("--highlight-object", default="GarmentCodePantsContinuousSequence")
    parser.add_argument("--highlight-color", default="0.08,0.30,0.85,1.0")
    parser.add_argument("--actor-color", help="optional RGBA override used to match the web preview body contrast")
    parser.add_argument(
        "--actor-unlit",
        action="store_true",
        help="render Actor materials as flat emission colours for pixel-space occlusion diagnostics",
    )
    parser.add_argument(
        "--directions",
        default=",".join(DIRECTIONS),
        help="comma-separated subset of front,right,back,left",
    )
    parser.add_argument(
        "--sample-frames",
        help="optional comma-separated action frames; overrides --frames",
    )
    parser.add_argument(
        "--garment-unlit",
        action="store_true",
        help="render the highlighted garment as a flat emission colour to separate geometry from lighting seams",
    )
    parser.add_argument(
        "--garment-only",
        action="store_true",
        help="hide visible Actor/face meshes while retaining the armature-deformed garment",
    )
    parser.add_argument("--material-library", type=Path, help="shared AssetsStudio garment material library JSON")
    parser.add_argument("--material-recipe", help="recipe id from --material-library")
    return parser.parse_args(argv)


def parse_color(value: str) -> tuple[float, float, float, float]:
    parts = tuple(float(item.strip()) for item in value.split(","))
    if len(parts) != 4:
        raise RuntimeError("highlight color must have four comma-separated values")
    return parts


def prepare_scene(scene: bpy.types.Scene, resolution: int) -> None:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    actor_render.configure_soft_toon_lighting(scene)


def apply_highlight(object_name: str, color_text: str) -> None:
    if not object_name:
        return
    target = bpy.data.objects.get(object_name)
    if target is None or target.type != "MESH":
        raise RuntimeError(f"highlight object is missing or not a mesh: {object_name}")
    color = parse_color(color_text)
    material = bpy.data.materials.get("AssetsLabActorClothingHighlight")
    if material is None:
        material = bpy.data.materials.new("AssetsLabActorClothingHighlight")
    material.diffuse_color = color
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is not None:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.86
    target.data.materials.clear()
    target.data.materials.append(material)


def make_garment_unlit(object_name: str, color_text: str) -> None:
    target = bpy.data.objects.get(object_name)
    if target is None or target.type != "MESH":
        raise RuntimeError(f"unlit garment object is missing: {object_name}")
    color = parse_color(color_text)
    material = bpy.data.materials.new("AssetsLabActorClothingUnlitDiagnostic")
    material.diffuse_color = color
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = 1.0
    material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    target.data.materials.clear()
    target.data.materials.append(material)


def apply_actor_color(actor: bpy.types.Object, color_text: str | None, unlit: bool = False) -> None:
    if not color_text:
        return
    color = parse_color(color_text)
    for material in actor.data.materials:
        if material is None:
            continue
        material.diffuse_color = color
        if not material.use_nodes:
            continue
        if unlit:
            nodes = material.node_tree.nodes
            nodes.clear()
            output = nodes.new("ShaderNodeOutputMaterial")
            emission = nodes.new("ShaderNodeEmission")
            emission.inputs["Color"].default_value = color
            emission.inputs["Strength"].default_value = 1.0
            material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
            continue
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is not None:
            principled.inputs["Base Color"].default_value = color
            principled.inputs["Emission Color"].default_value = color
            principled.inputs["Emission Strength"].default_value = 0.12


def apply_material_recipe(object_name: str, library_path: Path, recipe_id: str | None) -> dict:
    library = load_material_library(library_path)
    recipe = resolve_recipe(library, recipe_id or library["default_recipe_id"])
    target = bpy.data.objects.get(object_name)
    if target is None or target.type != "MESH":
        raise RuntimeError(f"material target is missing or not a mesh: {object_name}")
    material = bpy.data.materials.get(f"AssetsStudio_{recipe['id']}")
    if material is None:
        material = bpy.data.materials.new(f"AssetsStudio_{recipe['id']}")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    base = hex_to_linear_rgba(recipe["base_color"])
    accent = hex_to_linear_rgba(recipe["accent_color"])
    principled.inputs["Base Color"].default_value = base
    principled.inputs["Roughness"].default_value = recipe["roughness"]
    principled.inputs["Metallic"].default_value = recipe["metalness"]
    if "Sheen Weight" in principled.inputs:
        principled.inputs["Sheen Weight"].default_value = recipe["sheen"]
    elif "Sheen" in principled.inputs:
        principled.inputs["Sheen"].default_value = recipe["sheen"]
    links.new(principled.outputs[0], output.inputs[0])
    if recipe["pattern"] != "none" and recipe["pattern_strength"] > 0:
        coordinates = nodes.new("ShaderNodeTexCoord")
        texture = nodes.new("ShaderNodeTexNoise" if recipe["pattern"] == "weave" else "ShaderNodeTexWave")
        texture.inputs["Scale"].default_value = recipe["pattern_scale"]
        if recipe["pattern"] == "weave":
            texture.inputs["Detail"].default_value = 3.0
            texture.inputs["Roughness"].default_value = 0.65
        else:
            texture.wave_type = "BANDS"
            texture.bands_direction = "X"
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = base
        ramp.color_ramp.elements[1].color = tuple(base[i] + (accent[i] - base[i]) * recipe["pattern_strength"] for i in range(3)) + (1.0,)
        links.new(coordinates.outputs["Generated"], texture.inputs["Vector"])
        links.new(texture.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], principled.inputs["Base Color"])
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = min(recipe["pattern_strength"] * 0.2, 0.08)
        bump.inputs["Distance"].default_value = 0.015
        links.new(texture.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], principled.inputs["Normal"])
    material["assetsstudio_material_recipe_id"] = recipe["id"]
    material["assetsstudio_geometry_immutable"] = True
    target.data.materials.clear()
    target.data.materials.append(material)
    return {"library": str(library_path.resolve()), "recipe": recipe}


def main() -> int:
    options = cli_args()
    if options.frames < 2:
        raise RuntimeError("frames must be at least two")
    if options.resolution < 128:
        raise RuntimeError("resolution must be at least 128")
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    scene = bpy.context.scene
    armatures = [obj for obj in scene.objects if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        raise RuntimeError(f"expected one Actor armature, found {len(armatures)}")
    armature = armatures[0]
    action = armature.animation_data.action if armature.animation_data else None
    if action is None:
        raise RuntimeError("Actor armature has no active walk action")
    # Some transferred candidates retain REST display mode even though the
    # action and pose bones are animated.  In REST mode the Armature modifier
    # leaves the rendered mesh static, so the GIF would falsely look frozen.
    armature.data.pose_position = "POSE"
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    if actor is None:
        raise RuntimeError("Actor mesh is missing")

    prepare_scene(scene, options.resolution)
    style_id = options.face_style
    if style_id is None:
        style_id = actor_render.stable_face_style(options.appearance_seed)
    face_style = actor_render.apply_face_style(armature, style_id)
    apply_actor_color(actor, options.actor_color, options.actor_unlit)
    material_record = None
    if options.material_library:
        material_record = apply_material_recipe(options.highlight_object, options.material_library, options.material_recipe)
    else:
        apply_highlight(options.highlight_object, options.highlight_color)
    if options.garment_unlit:
        make_garment_unlit(options.highlight_object, options.highlight_color)
    if options.garment_only:
        garment = bpy.data.objects.get(options.highlight_object)
        if garment is None:
            raise RuntimeError(f"garment-only object is missing: {options.highlight_object}")
        for obj in scene.objects:
            if obj is garment or obj.type in {"ARMATURE", "LIGHT", "CAMERA"}:
                continue
            if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
                obj.hide_render = True

    low, high = actor_render.bounds(actor)
    target = Vector(((low.x + high.x) * 0.5, (low.y + high.y) * 0.5, (low.z + high.z) * 0.5))
    camera_specs = {
        "front": (0.0, -12.0, target.z),
        "right": (12.0, 0.0, target.z),
        "back": (0.0, 12.0, target.z),
        "left": (-12.0, 0.0, target.z),
    }
    directions = tuple(item.strip() for item in options.directions.split(",") if item.strip())
    if not directions or any(item not in DIRECTIONS for item in directions):
        raise RuntimeError(f"--directions must be a comma-separated subset of {DIRECTIONS}")
    cameras = {
        direction: actor_render.make_camera(
            scene,
            target,
            low,
            high,
            direction,
            location,
        )
        for direction, location in camera_specs.items()
        if direction in directions
    }
    start, end = int(action.frame_range[0]), int(action.frame_range[1])
    if options.sample_frames:
        sample_frames = [int(value.strip()) for value in options.sample_frames.split(",") if value.strip()]
        if not sample_frames or any(frame < start or frame > end for frame in sample_frames):
            raise RuntimeError(f"--sample-frames must stay within {start}..{end}")
    else:
        sample_frames = [round(start + (end - start) * index / max(options.frames - 1, 1)) for index in range(options.frames)]
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for direction, camera in cameras.items():
        scene.camera = camera
        for frame_index, frame in enumerate(sample_frames):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            scene.render.filepath = str(output / f"{direction}_{frame_index:02d}.png")
            bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(camera, do_unlink=True)

    manifest = {
        "schema": "assetslab_actor_clothing_eevee_render_v1",
        "blend": str(options.blend.resolve()),
        "action": action.name,
        "sample_frames": sample_frames,
        "directions": list(directions),
        "resolution": options.resolution,
        "engine": "BLENDER_EEVEE_NEXT",
        "face_style": face_style,
        "highlight_object": options.highlight_object,
        "highlight_color": options.highlight_color,
        "actor_color": options.actor_color,
        "actor_unlit": options.actor_unlit,
        "garment_unlit": options.garment_unlit,
        "garment_only": options.garment_only,
        "material_library": str(options.material_library.resolve()) if options.material_library else None,
        "material_recipe": material_record["recipe"]["id"] if material_record else None,
        "geometry_immutable": bool(material_record),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"ACTOR_CLOTHING_EEVEE_RENDER_PASS frames={len(sample_frames)} directions=4 output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
