"""Prepare exact multiview Hunyuan hair inputs from a fitted 3D prototype.

The fitted source hair is only an image-authoring scaffold. The script closes
small crown gaps with an Actor-derived under-cap, optionally cuts openings
around the detachable ears, and renders matching on-Actor and isolated
orthographic views. The scaffold is not a runtime hair asset.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


VIEWS = {
    "front": Vector((0.0, -1.0, 0.0)),
    "right": Vector((1.0, 0.0, 0.0)),
    "back": Vector((0.0, 1.0, 0.0)),
    "left": Vector((-1.0, 0.0, 0.0)),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", type=Path, required=True)
    parser.add_argument("--output-blend", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=1024)
    parser.add_argument("--cap-front-z", type=float, default=1.535)
    parser.add_argument("--cap-rear-z", type=float, default=1.340)
    parser.add_argument("--cap-front-y", type=float, default=-0.060)
    parser.add_argument("--cap-offset", type=float, default=0.010)
    parser.add_argument("--ear-radius-x", type=float, default=0.145)
    parser.add_argument("--ear-radius-y", type=float, default=0.165)
    parser.add_argument("--ear-radius-z", type=float, default=0.145)
    parser.add_argument(
        "--ear-opening-mode",
        choices=("cut", "closed"),
        default="cut",
        help="Use 'closed' when the detachable ears should overlap a continuous hair shell.",
    )
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    return parser.parse_args(raw)


def material() -> bpy.types.Material:
    value = bpy.data.materials.get("HairPrototypeBrown") or bpy.data.materials.new("HairPrototypeBrown")
    value.use_nodes = True
    bsdf = value.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.12, 0.045, 0.025, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.78
    return value


def world_mesh_copy(obj: bpy.types.Object, name: str) -> bpy.types.Object:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
    mesh.transform(evaluated.matrix_world)
    result = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(result)
    return result


def ear_centers() -> list[Vector]:
    centers = []
    for name in ("EarPair_HunyuanV2_L", "EarPair_HunyuanV2_R"):
        ear = bpy.data.objects.get(name)
        if ear is None:
            raise RuntimeError(f"missing detachable ear: {name}")
        points = [ear.matrix_world @ Vector(corner) for corner in ear.bound_box]
        low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
        high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
        centers.append((low + high) * 0.5)
    return centers


def in_ear_opening(point: Vector, centers: list[Vector], options: argparse.Namespace) -> bool:
    for center in centers:
        value = (
            ((point.x - center.x) / options.ear_radius_x) ** 2
            + ((point.y - center.y) / options.ear_radius_y) ** 2
            + ((point.z - center.z) / options.ear_radius_z) ** 2
        )
        if value <= 1.0:
            return True
    return False


def cut_ear_openings(obj: bpy.types.Object, centers: list[Vector], options: argparse.Namespace) -> int:
    mesh = obj.data
    kept_faces = []
    removed = 0
    for polygon in mesh.polygons:
        center = sum((mesh.vertices[index].co for index in polygon.vertices), Vector()) / len(polygon.vertices)
        if in_ear_opening(center, centers, options):
            removed += 1
        else:
            kept_faces.append(tuple(polygon.vertices))
    vertices = [tuple(vertex.co) for vertex in mesh.vertices]
    replacement = bpy.data.meshes.new(mesh.name + "_EarOpenings")
    replacement.from_pydata(vertices, [], kept_faces)
    replacement.update()
    old = obj.data
    obj.data = replacement
    bpy.data.meshes.remove(old)
    return removed


def create_under_cap(
    body: bpy.types.Object,
    centers: list[Vector],
    options: argparse.Namespace,
) -> bpy.types.Object:
    source = world_mesh_copy(body, "HairPrototypeBodyCopy")
    mesh = source.data
    head_center = Vector((0.0, 0.03, 1.56))
    selected = []
    for polygon in mesh.polygons:
        center = sum((mesh.vertices[index].co for index in polygon.vertices), Vector()) / len(polygon.vertices)
        keep = center.z >= options.cap_front_z or (
            center.z >= options.cap_rear_z and center.y >= options.cap_front_y
        )
        if keep and not in_ear_opening(center, centers, options):
            selected.append(polygon)
    used = sorted({index for polygon in selected for index in polygon.vertices})
    remap = {old: new for new, old in enumerate(used)}
    vertices = []
    for index in used:
        point = mesh.vertices[index].co.copy()
        radial = point - head_center
        if radial.length > 1e-8:
            point += radial.normalized() * options.cap_offset
        vertices.append(tuple(point))
    faces = [tuple(remap[index] for index in polygon.vertices) for polygon in selected]
    cap_mesh = bpy.data.meshes.new("HairPrototypeUnderCapMesh")
    cap_mesh.from_pydata(vertices, [], faces)
    cap_mesh.update()
    cap = bpy.data.objects.new("HairPrototype_UnderCap", cap_mesh)
    bpy.context.scene.collection.objects.link(cap)
    cap.data.materials.append(material())
    for polygon in cap.data.polygons:
        polygon.use_smooth = True
    bpy.data.objects.remove(source, do_unlink=True)
    return cap


def bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    return (
        Vector(tuple(min(point[axis] for point in points) for axis in range(3))),
        Vector(tuple(max(point[axis] for point in points) for axis in range(3))),
    )


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def configure_scene(scene: bpy.types.Scene, resolution: int) -> None:
    for obj in list(scene.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    world = scene.world or bpy.data.worlds.new("HairPrototypeWorld")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.94, 0.94, 0.94, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    for name, location, energy, size in (
        ("HairPrototypeKey", (-3.0, -4.0, 4.0), 650.0, 3.0),
        ("HairPrototypeFill", (3.0, -2.0, 3.0), 380.0, 3.0),
        ("HairPrototypeRim", (0.0, 3.0, 3.0), 420.0, 2.5),
    ):
        data = bpy.data.lights.new(name + "Data", "AREA")
        data.energy = energy
        data.size = size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        look_at(light, Vector((0.0, 0.0, 1.55)))


def render_set(
    scene: bpy.types.Scene,
    output: Path,
    target: Vector,
    scale: float,
) -> dict[str, str]:
    output.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, direction in VIEWS.items():
        data = bpy.data.cameras.new("HairPrototypeCameraData_" + name)
        data.type = "ORTHO"
        data.ortho_scale = scale
        camera = bpy.data.objects.new("HairPrototypeCamera_" + name, data)
        scene.collection.objects.link(camera)
        camera.location = target + direction * 6.0
        look_at(camera, target)
        scene.camera = camera
        path = output / f"{name}.png"
        scene.render.filepath = str(path.resolve())
        bpy.ops.render.render(write_still=True)
        paths[name] = str(path.resolve())
        bpy.data.objects.remove(camera, do_unlink=True)
    return paths


def main() -> int:
    options = parse_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    scene = bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    body = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    source_hair = bpy.data.objects.get("HairCandidate_Blend")
    if body is None or source_hair is None:
        raise RuntimeError("input blend requires Actor body and HairCandidate_Blend")
    centers = ear_centers()
    hair = world_mesh_copy(source_hair, "HairPrototype_SourceLocks")
    opening_centers = centers if options.ear_opening_mode == "cut" else []
    removed_faces = cut_ear_openings(hair, opening_centers, options)
    hair.data.materials.clear()
    hair.data.materials.append(material())
    for polygon in hair.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    cap = create_under_cap(body, opening_centers, options)
    source_hair.hide_render = True
    source_hair.hide_viewport = True
    configure_scene(scene, options.resolution)

    hair_low, hair_high = bounds([hair, cap])
    target = (hair_low + hair_high) * 0.5
    isolated_scale = max(hair_high.x - hair_low.x, hair_high.y - hair_low.y, hair_high.z - hair_low.z) * 1.18
    output = options.output_dir.resolve()
    on_actor = render_set(scene, output / "on_actor", target, isolated_scale)

    actor_objects = [
        obj for obj in scene.objects
        if obj not in {hair, cap, source_hair} and obj.type == "MESH"
    ]
    previous_holdout = {obj.name: obj.is_holdout for obj in actor_objects}
    for obj in actor_objects:
        obj.hide_render = False
        obj.is_holdout = True
    scene.render.film_transparent = True
    isolated = render_set(scene, output / "rgba", target, isolated_scale)
    for obj in actor_objects:
        obj.is_holdout = previous_holdout[obj.name]
    scene.render.film_transparent = False

    options.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output_blend.resolve()))
    report = {
        "schema": "assetsstudio_hunyuan_hair_prototype_v1",
        "status": "prototype_review_required",
        "input_blend": str(options.input_blend.resolve()),
        "output_blend": str(options.output_blend.resolve()),
        "source_hair": source_hair.name,
        "prototype_objects": [hair.name, cap.name],
        "ear_centers": [list(center) for center in centers],
        "ear_opening_mode": options.ear_opening_mode,
        "ear_opening_radii": [options.ear_radius_x, options.ear_radius_y, options.ear_radius_z],
        "removed_hair_faces": removed_faces,
        "cap_faces": len(cap.data.polygons),
        "bounds": {"min": list(hair_low), "max": list(hair_high)},
        "on_actor": on_actor,
        "hunyuan_rgba": isolated,
        "policy": "3D scaffold is image-authoring evidence only; runtime hair must be reconstructed by Hunyuan",
    }
    (output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"HUNYUAN_HAIR_PROTOTYPE_PASS output={output} removed_faces={removed_faces}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
