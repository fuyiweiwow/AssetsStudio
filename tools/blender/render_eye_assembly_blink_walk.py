"""Render the Actor eye assembly over the unchanged eight-frame walk sample.

The body keeps the source action sample frames. Only the active material slot on
the two head-parented EyeAssemblyV1 surfaces changes according to a fixed,
deterministic blink schedule.
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

from render_procedural_anime_eye_on_accurig import make_camera  # noqa: E402


DIRECTIONS = {
    "front": (0.0, -12.0),
    "right": (12.0, 0.0),
    "back": (0.0, 12.0),
    "left": (-12.0, 0.0),
}
EYE_OBJECTS = ("EyeAssemblyV1_Front_L", "EyeAssemblyV1_Front_R")
BLINK_STATES = ("open", "half", "closed", "half", "open", "open", "open", "open")
BLINK_AMOUNTS = (0.0, 0.5, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0)


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--resolution", type=int, default=256)
    parser.add_argument("--lighting-profile", choices=("current", "soft_flat"), default="current")
    return parser.parse_args(argv)


def visible_bounds() -> tuple[Vector, Vector]:
    points = [
        obj.matrix_world @ Vector(corner)
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and not obj.hide_render
        for corner in obj.bound_box
    ]
    if not points:
        raise RuntimeError("no visible meshes in eye assembly blend")
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def set_eye_state(state: str) -> None:
    title = state.title()
    for side, object_name in (("L", EYE_OBJECTS[0]), ("R", EYE_OBJECTS[1])):
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise RuntimeError(f"missing eye assembly object: {object_name}")
        material_name = f"EyeAssemblyV1_{title}_{side}"
        material = bpy.data.materials.get(material_name)
        if material is None:
            raise RuntimeError(f"missing eye state material: {material_name}")
        slot_index = next(
            (index for index, slot in enumerate(obj.material_slots) if slot.material == material),
            None,
        )
        if slot_index is None:
            raise RuntimeError(f"eye object has no material slot: {material_name}")
        obj.active_material_index = slot_index
        for polygon in obj.data.polygons:
            polygon.material_index = slot_index


def _look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    if direction.length <= 1e-6:
        return
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def configure_lighting(scene: bpy.types.Scene, target: Vector, profile: str) -> None:
    """Apply a named render-only lighting profile without saving the source blend."""

    if profile == "current":
        scene["assetslab_lighting_profile"] = "current_source_scene"
        return

    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)

    world = scene.world or bpy.data.worlds.new("AssetsLabSoftFlatWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.14, 0.16, 0.20, 1.0)
        background.inputs["Strength"].default_value = 0.42
    world.color = (0.14, 0.16, 0.20)

    def add_area(name: str, location: tuple[float, float, float], energy: float, size: float, use_shadow: bool) -> None:
        data = bpy.data.lights.new(name, type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        if hasattr(data, "use_shadow"):
            data.use_shadow = use_shadow
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        _look_at(light, target)

    # Large sources keep the actor readable while preserving only a gentle key.
    add_area("AssetsLabSoftFlatKey", (target.x - 4.5, target.y - 6.0, target.z + 7.5), 430.0, 6.5, True)
    add_area("AssetsLabSoftFlatFill", (target.x + 5.0, target.y - 3.5, target.z + 4.5), 300.0, 8.0, False)

    try:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
    except (AttributeError, TypeError, ValueError):
        pass
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene["assetslab_lighting_profile"] = "soft_flat_v1"


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    scene = bpy.context.scene
    scene.render.resolution_x = options.resolution
    scene.render.resolution_y = options.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False

    if tuple(scene.get("assetslab_eye_assembly_blink_states", [])) != ("Open", "Half", "Closed"):
        raise RuntimeError("blend does not contain the three validated eye states")
    if any(bpy.data.objects.get(name) is None for name in EYE_OBJECTS):
        raise RuntimeError("blend does not contain both EyeAssemblyV1 surfaces")

    action = None
    armature = bpy.data.objects.get("Armature")
    if armature is not None and armature.animation_data is not None:
        action = armature.animation_data.action
    if action is None:
        raise RuntimeError("Armature has no active walk action")
    start, end = int(action.frame_range[0]), int(action.frame_range[1])
    body_sample_frames = [round(start + (end - start) * index / 7.0) for index in range(8)]

    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    low, high = visible_bounds()
    center = (low + high) * 0.5
    configure_lighting(scene, center, options.lighting_profile)
    ortho_scale = max(high.z - low.z, high.x - low.x, high.y - low.y) * 1.16
    if ortho_scale <= 0.0:
        raise RuntimeError("invalid actor bounds")

    frames = []
    for direction, (x, y) in DIRECTIONS.items():
        for index, source_frame in enumerate(body_sample_frames):
            scene.frame_set(source_frame)
            bpy.context.view_layer.update()
            state = BLINK_STATES[index]
            set_eye_state(state)
            scene["assetslab_eye_assembly_blink_amount"] = BLINK_AMOUNTS[index]
            camera = make_camera(scene, center, f"EyeBlinkWalk_{direction}_{index}", (x, y, center.z), ortho_scale)
            scene.camera = camera
            path = output / f"{direction}_{index:02d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            bpy.data.objects.remove(camera, do_unlink=True)
            frames.append(
                {
                    "direction": direction,
                    "frame": index,
                    "source_frame": source_frame,
                    "eye_state": state,
                    "blink_amount": BLINK_AMOUNTS[index],
                    "path": str(path.relative_to(output)),
                }
            )

    manifest = {
        "schema": "assetslab_eye_assembly_blink_walk_v1",
        "blend": str(options.blend.resolve()),
        "action": action.name,
        "source_frame_range": [start, end],
        "body_sample_frames": body_sample_frames,
        "eye_state_by_frame": list(BLINK_STATES),
        "blink_amount_by_frame": list(BLINK_AMOUNTS),
        "directions": list(DIRECTIONS),
        "resolution": options.resolution,
        "lighting_profile": scene.get("assetslab_lighting_profile", options.lighting_profile),
        "frame_count_per_direction": 8,
        "body_sampling_contract": "unchanged_source_action_sample_8_frames",
        "blink_contract": "deterministic_single_blink_no_random_scheduler",
        "frames": frames,
        "status": "deterministic_blink_walk_review_only",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"EYE_ASSEMBLY_BLINK_WALK_PASS directions=4 frames=8 output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
