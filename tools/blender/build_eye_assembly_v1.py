"""Build the first single-assembly 3D eye structure on Actor V1.

This stage creates one eyebrow+eye texture surface per eye, parented to
CC_Base_Head. Open is Actor-native; optional half/closed state materials are
available for a separate deterministic blink render. It does not create side
planes, random states, or gallery output.
"""

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

from render_procedural_anime_eye_on_accurig import bounds, make_camera, setup_render  # noqa: E402


HEAD_BONE = "CC_Base_Head"
OLD_EYE_PREFIXES = ("EyePackageV1_", "EyePackageV2_", "EyeBlinkV1_")


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-blend", type=Path, required=True)
    parser.add_argument("--left-texture", type=Path, required=True)
    parser.add_argument("--right-texture", type=Path, required=True)
    parser.add_argument("--half-left-texture", type=Path)
    parser.add_argument("--half-right-texture", type=Path)
    parser.add_argument("--closed-left-texture", type=Path)
    parser.add_argument("--closed-right-texture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--save-blend", type=Path, required=True)
    parser.add_argument("--frame", type=int, default=1)
    parser.add_argument("--width-scale", type=float, default=0.68)
    parser.add_argument("--height-scale", type=float, default=0.68)
    parser.add_argument("--clearance", type=float, default=0.008)
    parser.add_argument("--curvature", type=float, default=0.018)
    return parser.parse_args(argv)


def validate_blink_texture_args(options: argparse.Namespace) -> bool:
    values = (
        options.half_left_texture,
        options.half_right_texture,
        options.closed_left_texture,
        options.closed_right_texture,
    )
    if any(value is not None for value in values) and not all(value is not None for value in values):
        raise RuntimeError("half/closed blink textures must be supplied for both eyes")
    return all(value is not None for value in values)


def remove_old_eye_objects() -> None:
    for obj in list(bpy.data.objects):
        if obj.name.startswith(OLD_EYE_PREFIXES):
            bpy.data.objects.remove(obj, do_unlink=True)


def configure_alpha(material: bpy.types.Material) -> None:
    if hasattr(material, "surface_render_method"):
        for method in ("BLENDED", "BLEND"):
            try:
                material.surface_render_method = method
                break
            except Exception:
                continue
    if hasattr(material, "blend_method"):
        try:
            material.blend_method = "BLEND"
        except Exception:
            pass
    if hasattr(material, "use_transparency_overlap"):
        material.use_transparency_overlap = False


def make_texture_material(name: str, texture_path: Path) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    configure_alpha(material)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(str(texture_path.resolve()), check_existing=True)
    texture.interpolation = "Linear"
    texture.extension = "CLIP"
    shader.inputs["Roughness"].default_value = 0.78
    if "Specular IOR Level" in shader.inputs:
        shader.inputs["Specular IOR Level"].default_value = 0.10
    links.new(texture.outputs["Color"], shader.inputs["Base Color"])
    links.new(texture.outputs["Alpha"], shader.inputs["Alpha"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def set_surface_material(surface: bpy.types.Object, material: bpy.types.Material) -> None:
    slot_index = next(
        (index for index, slot in enumerate(surface.material_slots) if slot.material == material),
        None,
    )
    if slot_index is None:
        surface.data.materials.append(material)
        slot_index = len(surface.material_slots) - 1
    surface.active_material_index = slot_index


def parent_to_head(obj: bpy.types.Object, armature: bpy.types.Object) -> None:
    world = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = HEAD_BONE
    obj.matrix_world = world


def add_surface_fit(obj: bpy.types.Object, actor_mesh: bpy.types.Object, offset: float = 0.002) -> None:
    shrink = obj.modifiers.new("EyeAssemblyV1_FitToHeadSurface", "SHRINKWRAP")
    shrink.target = actor_mesh
    shrink.wrap_method = "PROJECT"
    shrink.wrap_mode = "ON_SURFACE"
    shrink.use_project_y = True
    shrink.use_positive_direction = True
    shrink.use_negative_direction = False
    shrink.offset = offset


def create_curved_surface(
    name: str,
    center: Vector,
    width: float,
    height: float,
    curvature: float,
    material: bpy.types.Material,
    armature: bpy.types.Object,
    actor_mesh: bpy.types.Object,
) -> bpy.types.Object:
    cols, rows = 24, 18
    vertices = []
    faces = []
    uvs = []
    for row in range(rows + 1):
        v = row / rows
        z = (v - 0.5) * height
        for col in range(cols + 1):
            u = col / cols
            x = (u - 0.5) * width
            nx = x / (width * 0.5) if width else 0.0
            nz = z / (height * 0.5) if height else 0.0
            radius = min(1.0, nx * nx + nz * nz)
            y = center.y - curvature * (1.0 - radius)
            vertices.append((center.x + x, y, center.z + z))
            uvs.append((u, v))
    for row in range(rows):
        for col in range(cols):
            a = row * (cols + 1) + col
            b = a + 1
            d = (row + 1) * (cols + 1) + col
            c = d + 1
            faces.append((a, b, c, d))

    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            uv_layer.data[loop_index].uv = uvs[mesh.loops[loop_index].vertex_index]
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    obj["assetslab_role"] = "eye_assembly_v1_front_texture_surface"
    obj["assetslab_parent_bone"] = HEAD_BONE
    obj["assetslab_side_policy"] = "same_3d_assembly_projection"
    add_surface_fit(obj, actor_mesh)
    parent_to_head(obj, armature)
    return obj


def eye_world_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    return bounds(obj)


def main() -> int:
    options = cli_args()
    has_blink_states = validate_blink_texture_args(options)
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(options.source_blend.resolve()))
    scene = bpy.context.scene
    scene.frame_set(options.frame)
    bpy.context.view_layer.update()

    armature = bpy.data.objects.get("Armature")
    actor_mesh = next((obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("ChibiBaseMesh")), None)
    left_source = bpy.data.objects.get("EyePackageV1_Lens_L")
    right_source = bpy.data.objects.get("EyePackageV1_Lens_R")
    if armature is None or actor_mesh is None or left_source is None or right_source is None:
        raise RuntimeError("Actor V1 blend must contain Armature, ChibiBaseMesh, and native eye lens anchors")
    if armature.data.bones.get(HEAD_BONE) is None:
        raise RuntimeError(f"Actor V1 blend is missing {HEAD_BONE}")

    source_bounds = {"L": eye_world_bounds(left_source), "R": eye_world_bounds(right_source)}
    remove_old_eye_objects()
    collection = bpy.data.collections.get("EyeAssemblyV1") or bpy.data.collections.new("EyeAssemblyV1")
    if collection.name not in scene.collection.children:
        scene.collection.children.link(collection)
    state_texture_paths = {
        "open": {"L": options.left_texture, "R": options.right_texture},
    }
    if has_blink_states:
        state_texture_paths["half"] = {"L": options.half_left_texture, "R": options.half_right_texture}
        state_texture_paths["closed"] = {"L": options.closed_left_texture, "R": options.closed_right_texture}
    state_materials = {
        state: {
            side: make_texture_material(f"EyeAssemblyV1_{state.title()}_{side}", path)
            for side, path in paths.items()
        }
        for state, paths in state_texture_paths.items()
    }

    surfaces = []
    surfaces_by_side = {}
    for side in ("L", "R"):
        material = state_materials["open"][side]
        low, high = source_bounds[side]
        eye_center = (low + high) * 0.5
        eye_width = high.x - low.x
        eye_height = high.z - low.z
        width = eye_width * 1.42 * options.width_scale
        height = eye_height * 1.52 * options.height_scale
        # The generated canvas contains the eyebrow above the eye; shift the
        # assembly center upward so the actual eye remains on the native anchor.
        group_center = Vector((eye_center.x, low.y - options.clearance, eye_center.z + height * 0.10))
        surface = create_curved_surface(
            f"EyeAssemblyV1_Front_{side}", group_center, width, height, options.curvature, material, armature, actor_mesh
        )
        surface["assetslab_native_eye_anchor"] = list(eye_center)
        surface["assetslab_texture"] = str((options.left_texture if side == "L" else options.right_texture).resolve())
        collection.objects.link(surface)
        for linked_collection in list(surface.users_collection):
            if linked_collection != collection:
                linked_collection.objects.unlink(surface)
        surfaces.append(surface)
        surfaces_by_side[side] = surface

    scene["assetslab_eye_assembly_id"] = "EyeAssemblyV1"
    scene["assetslab_eye_assembly_stage"] = "static_multiview_review_only"
    scene["assetslab_eye_assembly_parent_bone"] = HEAD_BONE
    scene["assetslab_eye_assembly_side_policy"] = "same_3d_assembly_projection"
    scene["assetslab_eye_assembly_back_policy"] = "transparent_no_eye_geometry"
    scene["assetslab_eye_assembly_blink_amount"] = 0.0
    scene["assetslab_eye_assembly_blink_states"] = ["Open", "Half", "Closed"] if has_blink_states else ["Open"]

    low, high = bounds(actor_mesh)
    actor_center = (low + high) * 0.5
    setup_render(scene, -1.0)
    scene.render.resolution_x = scene.render.resolution_y = 384
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    eye_target = (source_bounds["L"][0] + source_bounds["L"][1] + source_bounds["R"][0] + source_bounds["R"][1]) * 0.25
    camera_specs = {
        "front": (0.0, -12.0, eye_target.z),
        "threequarter": (8.5, -8.5, eye_target.z),
        "right": (12.0, 0.0, eye_target.z),
        "back": (0.0, 12.0, eye_target.z),
    }
    for direction, location in camera_specs.items():
        camera = make_camera(scene, eye_target, direction, location, 1.55)
        scene.camera = camera
        scene.render.filepath = str(output / f"{direction}.png")
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(camera, do_unlink=True)

    state_outputs = {}
    if has_blink_states:
        for state in ("open", "half", "closed"):
            for side, surface in surfaces_by_side.items():
                set_surface_material(surface, state_materials[state][side])
            state_dir = output / "states" / state
            state_dir.mkdir(parents=True, exist_ok=True)
            state_outputs[state] = []
            for direction, location in {
                "front": (0.0, -12.0, eye_target.z),
                "threequarter": (8.5, -8.5, eye_target.z),
            }.items():
                camera = make_camera(scene, eye_target, f"{state}_{direction}", location, 1.55)
                scene.camera = camera
                state_path = state_dir / f"{direction}.png"
                scene.render.filepath = str(state_path)
                bpy.ops.render.render(write_still=True)
                bpy.data.objects.remove(camera, do_unlink=True)
                state_outputs[state].append(str(state_path.relative_to(output)))
        for side, surface in surfaces_by_side.items():
            set_surface_material(surface, state_materials["open"][side])

    bpy.ops.wm.save_as_mainfile(filepath=str(options.save_blend.resolve()))
    manifest = {
        "schema": "assetslab_eye_assembly_v1",
        "source_blend": str(options.source_blend.resolve()),
        "textures": {
            state: {side: str(path.resolve()) for side, path in paths.items()}
            for state, paths in state_texture_paths.items()
        },
        "parent_bone": HEAD_BONE,
        "objects": [obj.name for obj in surfaces],
        "frame": options.frame,
        "static_only": not has_blink_states,
        "blink_texture_states": has_blink_states,
        "side_policy": "same_3d_assembly_projection",
        "back_policy": "transparent_no_eye_geometry",
        "blink_amount": 0.0,
        "placement": {
            "width_scale": options.width_scale,
            "height_scale": options.height_scale,
            "clearance": options.clearance,
            "curvature": options.curvature,
        },
        "directions": list(camera_specs),
        "state_outputs": state_outputs,
        "status": "static_multiview_review_only",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"EYE_ASSEMBLY_V1_PASS output={output} blend={options.save_blend}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
