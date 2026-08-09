"""Render a configurable chibi walk test from an AccuRIG actor.

This is a diagnostic motion, not a replacement for a production motion clip.
It is intentionally small so knee placement, foot behavior, and head stability
can be judged before retargeting a larger motion library.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


FACE_STYLE_COUNT = 4
EYE_OBJECT_PREFIX = "EyePackageV1_"

# These are deliberately bounded style bundles, rather than independently
# randomising every mesh axis.  The eye attachment has already passed a
# four-view fit test; this keeps every generated face in that safe envelope.
FACE_STYLES = (
    {
        "name": "classic",
        "eye_width": 1.00,
        "eye_height": 1.00,
        "eye_raise": 0.00,
        "brow_raise": 0.00,
        "brow_arch": 0.025,
        "brow_tilt": 0.000,
        "brow_colour": (0.16, 0.055, 0.035, 1.0),
    },
    {
        "name": "bright_tall",
        "eye_width": 0.96,
        "eye_height": 1.12,
        "eye_raise": 0.075,
        "brow_raise": 0.095,
        "brow_arch": 0.060,
        "brow_tilt": 0.015,
        "brow_colour": (0.20, 0.070, 0.040, 1.0),
    },
    {
        "name": "soft_round",
        "eye_width": 1.08,
        "eye_height": 1.07,
        "eye_raise": 0.040,
        "brow_raise": 0.050,
        "brow_arch": 0.080,
        "brow_tilt": 0.000,
        "brow_colour": (0.24, 0.085, 0.050, 1.0),
    },
    {
        "name": "focused",
        "eye_width": 0.92,
        "eye_height": 1.02,
        "eye_raise": 0.105,
        "brow_raise": 0.070,
        "brow_arch": 0.018,
        "brow_tilt": -0.040,
        "brow_colour": (0.12, 0.038, 0.025, 1.0),
    },
)


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fbx", type=Path)
    source.add_argument(
        "--input-blend",
        type=Path,
        help="Prepared actor Blend; preserves head-bone attachments such as eyes and ears.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--amplitude",
        type=float,
        default=1.0,
        help="motion amplitude multiplier; current project Walk baseline is 1.3",
    )
    parser.add_argument("--reverse-calf", action="store_true")
    parser.add_argument("--freestyle", action="store_true")
    parser.add_argument("--frame-count", type=int, default=8)
    parser.add_argument(
        "--appearance-seed",
        type=int,
        help="Stable seed used to choose one constrained face-style bundle.",
    )
    parser.add_argument(
        "--face-style",
        type=int,
        choices=range(FACE_STYLE_COUNT),
        help="Explicit face-style bundle. Overrides the style chosen from --appearance-seed.",
    )
    parser.add_argument(
        "--soft-toon-lighting",
        action="store_true",
        help="Use broad key/fill lighting and a soft pastel base palette for preview renders.",
    )
    return parser.parse_args(argv)


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def reset_pose(armature: bpy.types.Object) -> None:
    armature.animation_data_clear()
    for bone in armature.pose.bones:
        bone.rotation_mode = "XYZ"
        bone.location = (0.0, 0.0, 0.0)
        bone.rotation_euler = (0.0, 0.0, 0.0)
        bone.scale = (1.0, 1.0, 1.0)


def rotate(armature: bpy.types.Object, name: str, axis: int, degrees: float) -> None:
    armature.pose.bones[name].rotation_euler[axis] = math.radians(degrees)


def apply_walk_pose(
    armature: bpy.types.Object,
    phase: float,
    amplitude: float = 1.0,
    reverse_calf: bool = False,
) -> None:
    """Apply a visible in-place walk cycle using the FBX local X swing axis."""
    swing = math.sin(phase)
    left_forward = swing
    right_forward = -swing

    # Legs: clear contact, passing, and swing phases for a short-legged actor.
    rotate(armature, "CC_Base_L_Thigh", 0, amplitude * 24.0 * left_forward)
    rotate(armature, "CC_Base_R_Thigh", 0, amplitude * 24.0 * right_forward)
    left_calf = amplitude * (8.0 + 26.0 * max(0.0, -left_forward))
    right_calf = amplitude * (8.0 + 26.0 * max(0.0, -right_forward))
    if reverse_calf:
        left_calf = -left_calf
        right_calf = -right_calf
    rotate(armature, "CC_Base_L_Calf", 0, left_calf)
    rotate(armature, "CC_Base_R_Calf", 0, right_calf)
    rotate(armature, "CC_Base_L_Foot", 0, amplitude * -10.0 * left_forward)
    rotate(armature, "CC_Base_R_Foot", 0, amplitude * -10.0 * right_forward)

    # Arms counter-swing; head and torso remain fixed for deformation inspection.
    rotate(armature, "CC_Base_L_Upperarm", 0, amplitude * -18.0 * left_forward)
    rotate(armature, "CC_Base_R_Upperarm", 0, amplitude * -18.0 * right_forward)
    rotate(armature, "CC_Base_L_Forearm", 0, amplitude * -6.0 * left_forward)
    rotate(armature, "CC_Base_R_Forearm", 0, amplitude * -6.0 * right_forward)


def make_camera(scene: bpy.types.Scene, target: Vector, low: Vector, high: Vector, name: str, location: tuple[float, float, float]):
    camera_data = bpy.data.cameras.new(name + "Data")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(4.0, (high.z - low.z) * 1.25)
    camera = bpy.data.objects.new(name, camera_data)
    scene.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    return camera


def configure_freestyle(scene: bpy.types.Scene) -> None:
    """Enable Blender's native visible-edge outline for comparison renders."""
    scene.render.use_freestyle = True
    view_layer = scene.view_layers[0]
    settings = view_layer.freestyle_settings
    line_set = settings.linesets[0]
    line_style = line_set.linestyle or bpy.data.linestyles.new("PixelOutline")
    line_set.linestyle = line_style
    line_style.color = (0.06, 0.05, 0.10)
    line_style.thickness = 2.0
    for property_name in ("select_silhouette", "select_border", "select_crease"):
        if hasattr(line_set, property_name):
            setattr(line_set, property_name, True)


def configure_soft_toon_lighting(scene: bpy.types.Scene) -> None:
    """Make side views readable before a final character palette is authored."""
    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)

    world = scene.world or bpy.data.worlds.new("ChibiSoftWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.52, 0.34, 0.28, 1.0)
        background.inputs["Strength"].default_value = 0.85

    for name, location, energy, size, colour in (
        ("SoftKey", (4.5, -5.5, 7.0), 700.0, 5.0, (1.0, 0.76, 0.62)),
        ("SoftFill", (-5.0, -2.0, 4.0), 800.0, 7.0, (1.0, 0.62, 0.50)),
        ("SoftRim", (0.0, 4.0, 6.0), 280.0, 5.0, (1.0, 0.76, 0.60)),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        data.color = colour
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (0.0, 0.0, 0.0)

    for material in bpy.data.materials:
        if material.name == "Default":
            material.diffuse_color = (0.82, 0.43, 0.30, 1.0)
        elif material.name == "CartoonEarActorSkin":
            material.diffuse_color = (0.98, 0.69, 0.66, 1.0)
        if material.use_nodes:
            principled = material.node_tree.nodes.get("Principled BSDF")
            if principled is not None:
                if material.name == "Default":
                    principled.inputs["Base Color"].default_value = (0.82, 0.43, 0.30, 1.0)
                elif material.name == "CartoonEarActorSkin":
                    principled.inputs["Base Color"].default_value = (0.98, 0.69, 0.66, 1.0)
                principled.inputs["Roughness"].default_value = 0.88
                # A small same-colour emission floor keeps the untextured
                # prototype readable in side view without erasing form.
                if material.name in {"Default", "CartoonEarActorSkin"}:
                    principled.inputs["Emission Color"].default_value = principled.inputs["Base Color"].default_value
                    principled.inputs["Emission Strength"].default_value = 0.28


def stable_face_style(seed: int) -> int:
    """Return a cross-platform stable style index without Python RNG state."""
    digest = hashlib.blake2b(str(seed).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % FACE_STYLE_COUNT


def mesh_world_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    bpy.context.view_layer.update()
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def transform_eye_mesh(obj: bpy.types.Object, width: float, height: float, raise_z: float) -> None:
    """Scale one attached eye object in world X/Z, retaining its head-bone fit."""
    low, high = mesh_world_bounds(obj)
    center = Vector(((low.x + high.x) * 0.5, (low.y + high.y) * 0.5, (low.z + high.z) * 0.5))
    world_to_local = obj.matrix_world.inverted()
    obj.data = obj.data.copy()
    for vertex in obj.data.vertices:
        point = obj.matrix_world @ vertex.co
        point.x = center.x + (point.x - center.x) * width
        point.z = center.z + (point.z - center.z) * height + raise_z
        vertex.co = world_to_local @ point


def brow_material(colour: tuple[float, float, float, float]) -> bpy.types.Material:
    material = bpy.data.materials.new("FaceVariantBrowMaterial")
    material.diffuse_color = colour
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is not None:
        principled.inputs["Base Color"].default_value = colour
        principled.inputs["Roughness"].default_value = 0.72
        principled.inputs["Emission Color"].default_value = colour
        principled.inputs["Emission Strength"].default_value = 0.18
    return material


def add_brow(
    armature: bpy.types.Object,
    name: str,
    points: tuple[Vector, Vector, Vector],
    material: bpy.types.Material,
) -> None:
    curve = bpy.data.curves.new(name + "Curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = 0.022
    curve.bevel_resolution = 2
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(2)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = "CC_Base_Head"
    bpy.context.view_layer.update()
    to_local = obj.matrix_world.inverted()
    for point, world in zip(spline.bezier_points, points):
        point.co = to_local @ world
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj.data.materials.append(material)


def add_style_brows(armature: bpy.types.Object, style: dict[str, object]) -> None:
    """Add a small, deliberately separate brow layer above the eye package."""
    eye_objects = [obj for obj in bpy.data.objects if obj.name.startswith(EYE_OBJECT_PREFIX)]
    eye_low = Vector((min(mesh_world_bounds(obj)[0].x for obj in eye_objects), 0.0, min(mesh_world_bounds(obj)[0].z for obj in eye_objects)))
    eye_high = Vector((max(mesh_world_bounds(obj)[1].x for obj in eye_objects), 0.0, max(mesh_world_bounds(obj)[1].z for obj in eye_objects)))
    brow_y = -0.775
    brow_z = eye_high.z + 0.115 + float(style["brow_raise"])
    half_width = max(0.18, (eye_high.x - eye_low.x) * 0.135)
    x_centers = (-0.405, 0.405)
    material = brow_material(style["brow_colour"])
    arch = float(style["brow_arch"])
    tilt = float(style["brow_tilt"])
    for side, x_center in ((-1.0, x_centers[0]), (1.0, x_centers[1])):
        outer_z = brow_z + side * tilt
        inner_z = brow_z - side * tilt
        add_brow(
            armature,
            "FaceVariantBrowL" if side < 0 else "FaceVariantBrowR",
            (
                Vector((x_center - half_width, brow_y, outer_z)),
                Vector((x_center, brow_y, brow_z + arch)),
                Vector((x_center + half_width, brow_y, inner_z)),
            ),
            material,
        )


def apply_face_style(armature: bpy.types.Object, style_id: int) -> dict[str, object]:
    style = FACE_STYLES[style_id]
    eye_objects = [obj for obj in bpy.data.objects if obj.name.startswith(EYE_OBJECT_PREFIX)]
    if len(eye_objects) != 4:
        raise RuntimeError(f"expected four eye-package meshes, found {len(eye_objects)}")
    for obj in eye_objects:
        transform_eye_mesh(
            obj,
            float(style["eye_width"]),
            float(style["eye_height"]),
            float(style["eye_raise"]),
        )
    add_style_brows(armature, style)
    return {"id": style_id, "name": style["name"], "parameters": dict(style)}


def main() -> int:
    options = cli_args()
    if options.frame_count < 2:
        raise RuntimeError("frame count must be at least two")
    project_root = Path(__file__).resolve().parents[2]
    output_dir = options.output if options.output.is_absolute() else project_root / options.output
    output_dir = output_dir.resolve()
    if options.input_blend:
        bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(options.fbx.resolve()), use_anim=True)
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        raise RuntimeError("expected exactly one armature")
    mesh = next((obj for obj in meshes if obj.name.startswith("ChibiBase")), None)
    if mesh is None:
        if len(meshes) != 1:
            raise RuntimeError("could not identify the actor mesh")
        mesh = meshes[0]
    armature = armatures[0]
    low, high = bounds(mesh)
    target = Vector(((low.x + high.x) * 0.5, (low.y + high.y) * 0.5, (low.z + high.z) * 0.5))

    scene = bpy.context.scene
    # EEVEE preserves the packed image textures used by the verified eye
    # package.  Workbench only displays a material's viewport colour, which
    # made the eye layer disappear from the 3D-to-pixel walk output.
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = True
    if options.soft_toon_lighting:
        configure_soft_toon_lighting(scene)
    if options.freestyle:
        configure_freestyle(scene)
    output_dir.mkdir(parents=True, exist_ok=True)

    selected_style: dict[str, object] | None = None
    style_id = options.face_style
    if style_id is None and options.appearance_seed is not None:
        style_id = stable_face_style(options.appearance_seed)
    if style_id is not None:
        selected_style = apply_face_style(armature, style_id)
        (output_dir / "face_variant.json").write_text(
            json.dumps(
                {
                    "schema": "assetslab_chibi_face_variant_v1",
                    "appearance_seed": options.appearance_seed,
                    "style": selected_style,
                    "ear_policy": "locked_verified_attachment",
                    "brow_policy": "generated_head_bone_layer",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    camera_specs = {
        "front": (0.0, -12.0, target.z),
        "right": (12.0, 0.0, target.z),
        "back": (0.0, 12.0, target.z),
        "left": (-12.0, 0.0, target.z),
    }
    cameras = {
        name: make_camera(scene, target, low, high, name, location)
        for name, location in camera_specs.items()
    }
    for direction, camera in cameras.items():
        scene.camera = camera
        for frame in range(options.frame_count):
            reset_pose(armature)
            apply_walk_pose(
                armature,
                (2.0 * math.pi * frame) / options.frame_count,
                options.amplitude,
                options.reverse_calf,
            )
            scene.render.filepath = str(output_dir / f"{direction}_{frame:02d}.png")
            bpy.ops.render.render(write_still=True)

    print(
        "ACCURIG_CHIBI_WALK_TEST_PASS "
        f"directions=4 frames={options.frame_count} style={selected_style['name'] if selected_style else 'base'} "
        f"output={output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
