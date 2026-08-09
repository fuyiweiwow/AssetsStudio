"""Attach BlendSwap's procedural anime eyes to the AccuRIG actor for review."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


SOURCE_URL = "https://blendswap.com/blend/23319"
EYE_NAMES = ("EyeL", "EyeR")
HEAD_BONE = "CC_Base_Head"


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--save-blend", type=Path)
    parser.add_argument("--safe-editable", action="store_true")
    parser.add_argument("--left-yaw-deg", type=float, default=0.0)
    parser.add_argument("--right-yaw-deg", type=float, default=0.0)
    parser.add_argument("--pitch-deg", type=float, default=0.0)
    parser.add_argument("--scale", type=float, default=1.4)
    parser.add_argument("--depth-scale", type=float, default=1.0, help="Compress source eye depth along its local Y axis")
    parser.add_argument("--eye-spacing", type=float, default=0.44)
    parser.add_argument("--eye-z-ratio", type=float, default=0.82)
    # Positive values move the eye center inward from the actor's front-most Y.
    parser.add_argument("--face-front-bias", type=float, default=0.22)
    parser.add_argument("--surface-depth-factor", type=float, default=0.75, help="Calibrated placement depth behind the marked face surface")
    parser.add_argument("--no-parent-head", action="store_true")
    return parser.parse_args(argv)


def load_calibration(path: Path) -> dict:
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    if payload.get("schema") not in {"assetslab_chibi_eye_calibration_v1", "assetslab_chibi_eye_calibration_v2"}:
        raise RuntimeError(f"unsupported eye calibration schema: {payload.get('schema')}")
    front = {item["key"]: item for item in payload.get("views", {}).get("front", [])}
    side = {item["key"]: item for item in payload.get("views", {}).get("side", [])}
    required_front = {"screen_left_eye_center", "screen_right_eye_center"}
    required_side = {"eye_center", "iris_forward"}
    if not required_front.issubset(front) or not required_side.issubset(side):
        raise RuntimeError("eye calibration is missing required points")
    if payload.get("schema") == "assetslab_chibi_eye_calibration_v2" and "face_front_surface" not in side:
        raise RuntimeError("eye calibration v2 is missing face_front_surface")
    return payload


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector((min(point[i] for point in points) for i in range(3))),
        Vector((max(point[i] for point in points) for i in range(3))),
    )


def group_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    return (
        Vector((min(point[i] for point in points) for i in range(3))),
        Vector((max(point[i] for point in points) for i in range(3))),
    )


def annotation_world_point(point: dict, view: str, target_z: float, ortho_scale: float) -> Vector:
    # The annotation renders use a 512x512 orthographic camera centered at X/Y=0.
    u = float(point["x"]) / 512.0
    v = float(point["y"]) / 512.0
    horizontal = (u - 0.5) * ortho_scale
    z = target_z + (0.5 - v) * ortho_scale
    if view == "front":
        return Vector((horizontal, 0.0, z))
    if view == "side":
        # The annotation side camera is on -X, so its screen-right direction
        # corresponds to the actor's visual front (-Y) in this project.
        return Vector((0.0, -horizontal, z))
    raise ValueError(view)


def append_eyes(source: Path) -> list[bpy.types.Object]:
    with bpy.data.libraries.load(str(source.resolve()), link=False) as (data_from, data_to):
        data_to.objects = [name for name in EYE_NAMES if name in data_from.objects]
    loaded: list[bpy.types.Object] = []
    for obj in data_to.objects:
        if obj is None:
            continue
        obj.name = f"ProceduralAnimeEye_{obj.name}"
        bpy.context.collection.objects.link(obj)
        loaded.append(obj)
    names = {obj.name.rsplit("_", 1)[-1] for obj in loaded}
    if names != set(EYE_NAMES):
        raise RuntimeError(f"source is missing eye objects: expected={EYE_NAMES} found={sorted(names)}")
    bpy.context.view_layer.update()
    return loaded


def parent_to_head(obj: bpy.types.Object, armature: bpy.types.Object) -> None:
    world = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = HEAD_BONE
    obj.matrix_world = world


def place_eyes(
    eyes: list[bpy.types.Object],
    target_center: Vector,
    scale: float,
    eye_spacing: float,
) -> None:
    bpy.context.view_layer.update()
    original_world = {obj: obj.matrix_world.copy() for obj in eyes}
    for obj in eyes:
        obj.parent = None
        obj.matrix_world = original_world[obj]
    low, high = group_bounds(eyes)
    source_center = (low + high) * 0.5
    left = next(obj for obj in eyes if obj.name.endswith("EyeL"))
    left_low, left_high = bounds(left)
    left_center = (left_low + left_high) * 0.5
    source_offset = max(abs(left_center.x - source_center.x), 1e-6)
    source_spacing = source_offset * 2.0
    x_scale = eye_spacing / (source_spacing * scale)
    transform = (
        Matrix.Translation(target_center)
        @ Matrix.Scale(scale, 4)
        @ Matrix.Scale(x_scale, 4, (1.0, 0.0, 0.0))
        @ Matrix.Translation(-source_center)
    )
    for obj in eyes:
        obj.matrix_world = transform @ original_world[obj]


def place_eyes_from_calibration(
    eyes: list[bpy.types.Object],
    calibration: dict,
    target_z: float,
    ortho_scale: float,
    scale: float,
    left_yaw_deg: float,
    right_yaw_deg: float,
    pitch_deg: float,
    surface_depth_factor: float,
) -> dict:
    front = {item["key"]: item for item in calibration["views"]["front"]}
    side = {item["key"]: item for item in calibration["views"]["side"]}
    screen_left = annotation_world_point(front["screen_left_eye_center"], "front", target_z, ortho_scale)
    screen_right = annotation_world_point(front["screen_right_eye_center"], "front", target_z, ortho_scale)
    side_center = annotation_world_point(side["eye_center"], "side", target_z, ortho_scale)
    side_forward = annotation_world_point(side["iris_forward"], "side", target_z, ortho_scale)
    surface_point = (
        annotation_world_point(side["face_front_surface"], "side", target_z, ortho_scale)
        if "face_front_surface" in side
        else None
    )
    target_z_average = (screen_left.z + screen_right.z + side_center.z) / 3.0
    targets = {
        "EyeL": Vector((screen_left.x, side_center.y, target_z_average)),
        "EyeR": Vector((screen_right.x, side_center.y, target_z_average)),
    }

    # The downloaded shader faces the negative-Y side in its source scene.
    # The side annotation explicitly marks the actor's forward direction.
    target_forward = Vector((0.0, side_forward.y - side_center.y, 0.0))
    if target_forward.length < 1e-5:
        raise RuntimeError("side calibration forward vector is too short")
    target_forward.normalize()
    source_forward = Vector((0.0, -1.0, 0.0))
    rotation = source_forward.rotation_difference(target_forward).to_matrix().to_4x4()

    for obj in eyes:
        source_name = obj.name.rsplit("_", 1)[-1]
        if source_name not in targets:
            raise RuntimeError(f"unexpected eye object: {obj.name}")
        source_low, source_high = bounds(obj)
        source_center = (source_low + source_high) * 0.5
        target = targets[source_name].copy()
        if surface_point is not None:
            source_radius = (source_high.y - source_low.y) * 0.5 * scale
            target.y = surface_point.y - target_forward.y * source_radius * surface_depth_factor
        yaw_deg = 0.0
        if source_name == "EyeL":
            yaw_deg = left_yaw_deg
        elif source_name == "EyeR":
            yaw_deg = right_yaw_deg
        yaw = Matrix.Rotation(math.radians(yaw_deg), 4, "Z")
        pitch = Matrix.Rotation(math.radians(pitch_deg), 4, "X")
        original_world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = (
            Matrix.Translation(target)
            @ pitch
            @ yaw
            @ rotation
            @ Matrix.Scale(scale, 4)
            @ Matrix.Translation(-source_center)
            @ original_world
        )
    return {
        "target_left": list(targets["EyeL"]),
        "target_right": list(targets["EyeR"]),
        "target_surface": list(surface_point) if surface_point is not None else None,
        "forward": list(target_forward),
        "annotation_ortho_scale": ortho_scale,
        "left_yaw_deg": left_yaw_deg,
        "right_yaw_deg": right_yaw_deg,
        "pitch_deg": pitch_deg,
    }


def make_camera(scene: bpy.types.Scene, target: Vector, name: str, location: tuple[float, float, float], scale: float) -> bpy.types.Object:
    data = bpy.data.cameras.new(name + "Data")
    data.type = "ORTHO"
    data.ortho_scale = scale
    data.clip_start = 0.01
    data.clip_end = 1000.0
    camera = bpy.data.objects.new(name, data)
    scene.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    return camera


def setup_render(scene: bpy.types.Scene, forward_sign: float = -1.0) -> None:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("ProceduralAnimeEyeWorld")
    scene.world.color = (0.055, 0.055, 0.075)
    for index, (location, energy, size) in enumerate(
        (((0.0, 4.0 * forward_sign, 5.0), 700.0, 4.0), ((-3.0, 2.0 * forward_sign, 2.0), 280.0, 3.0))
    ):
        data = bpy.data.lights.new(f"ProceduralAnimeEyeLight_{index}", "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(light)
        light.location = location


def apply_safe_edit_materials(eyes: list[bpy.types.Object]) -> None:
    """Replace procedural nodes with simple viewport-safe materials for manual placement."""
    colors = {
        "EyeL": (0.18, 0.75, 1.0, 1.0),
        "EyeR": (1.0, 0.25, 0.55, 1.0),
    }
    for obj in eyes:
        source_name = obj.name.rsplit("_", 1)[-1]
        material = bpy.data.materials.new(f"ManualEyeSafe_{source_name}")
        material.diffuse_color = colors[source_name]
        material.use_nodes = True
        shader = material.node_tree.nodes.get("Principled BSDF")
        if shader is not None:
            shader.inputs["Base Color"].default_value = colors[source_name]
            shader.inputs["Roughness"].default_value = 0.65
        obj.data.materials.clear()
        obj.data.materials.append(material)


def main() -> int:
    options = cli_args()
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(options.fbx.resolve()), use_anim=True)
    mesh = next(obj for obj in bpy.data.objects if obj.type == "MESH")
    armature = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
    if HEAD_BONE not in armature.data.bones:
        raise RuntimeError(f"actor is missing required head bone: {HEAD_BONE}")

    low, high = bounds(mesh)
    actor_center = (low + high) * 0.5
    eye_z = low.z + (high.z - low.z) * options.eye_z_ratio
    target_center = Vector((actor_center.x, low.y + options.face_front_bias, eye_z))

    eyes = append_eyes(options.source)
    calibration_meta = None
    if options.calibration:
        calibration = load_calibration(options.calibration)
        annotation_scale = max(4.0, (high.z - low.z) * 1.25)
        calibration_meta = place_eyes_from_calibration(
            eyes,
            calibration,
            actor_center.z,
            annotation_scale,
            options.scale,
            options.left_yaw_deg,
            options.right_yaw_deg,
            options.pitch_deg,
            options.surface_depth_factor,
        )
        target_center = Vector((
            (calibration_meta["target_left"][0] + calibration_meta["target_right"][0]) * 0.5,
            calibration_meta["target_left"][1],
            calibration_meta["target_left"][2],
        ))
    else:
        place_eyes(eyes, target_center, options.scale, options.eye_spacing)
    if abs(options.depth_scale - 1.0) > 1e-6:
        for eye in eyes:
            eye.scale.y *= options.depth_scale
        bpy.context.view_layer.update()
    if options.safe_editable:
        apply_safe_edit_materials(eyes)
    if not options.no_parent_head:
        for eye in eyes:
            parent_to_head(eye, armature)

    eye_low, eye_high = group_bounds(eyes)
    print(
        "EYE_DEBUG target="
        + str(tuple(round(value, 4) for value in target_center))
        + " bounds="
        + str(tuple(round(value, 4) for value in eye_low))
        + ".."
        + str(tuple(round(value, 4) for value in eye_high))
    )

    scene = bpy.context.scene
    scene.frame_set(1)
    setup_render(scene, -1.0)
    if options.safe_editable:
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.display.shading.color_type = "MATERIAL"
        scene.display.shading.show_shadows = True
        scene.display.shading.show_cavity = True
    if options.save_blend:
        manual_camera = make_camera(
            scene,
            actor_center,
            "ManualEyeAdjustmentFront",
            (0.0, -12.0, actor_center.z),
            max(4.0, high.z - low.z + 0.6),
        )
        scene.camera = manual_camera
        for eye in eyes:
            eye.select_set(True)
        bpy.context.view_layer.objects.active = eyes[0]
        if options.safe_editable:
            bpy.ops.outliner.orphans_purge(do_recursive=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(options.save_blend.resolve()))
        print(f"MANUAL_EYE_BLEND_SAVED path={options.save_blend.resolve()}")
    camera_specs = {
        "front": (0.0, -12.0, actor_center.z),
        "right": (12.0, 0.0, actor_center.z),
        "back": (0.0, 12.0, actor_center.z),
        "left": (-12.0, 0.0, actor_center.z),
    }
    for direction, location in camera_specs.items():
        camera = make_camera(scene, actor_center, direction, location, max(4.0, high.z - low.z + 0.6))
        scene.camera = camera
        scene.render.filepath = str(output / f"{direction}.png")
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(camera, do_unlink=True)

    closeup_target = Vector((actor_center.x, actor_center.y, eye_z))
    closeup_scale = max(1.15, (high.z - low.z) * 0.42)
    for direction, location in {
        "front": (0.0, -12.0, eye_z),
        "right": (12.0, 0.0, eye_z),
    }.items():
        camera = make_camera(scene, closeup_target, f"{direction}_closeup", location, closeup_scale)
        scene.camera = camera
        scene.render.filepath = str(output / f"{direction}_closeup.png")
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(camera, do_unlink=True)

    (output / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "assetslab_procedural_anime_eye_on_accurig_v1",
                "source_fbx": str(options.fbx.resolve()),
                "source_blend": str(options.source.resolve()),
                "source_url": SOURCE_URL,
                "eye_objects": EYE_NAMES,
                "parent_bone": None if options.no_parent_head else HEAD_BONE,
                "placement": {
                    "scale": options.scale,
                    "depth_scale": options.depth_scale,
                    "eye_spacing": options.eye_spacing,
                    "eye_z_ratio": options.eye_z_ratio,
                    "face_front_bias": options.face_front_bias,
                    "surface_depth_factor": options.surface_depth_factor,
                },
                "calibration": str(options.calibration.resolve()) if options.calibration else None,
                "calibration_meta": calibration_meta,
                "directions": list(camera_specs),
                "status": "static_four_direction_review_only",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"PROCEDURAL_ANIME_EYE_ON_ACCURIG_PASS output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
