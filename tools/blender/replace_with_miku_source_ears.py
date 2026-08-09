"""Replace detached generic ears with the connected ear components from Miku's head.

The selected Miku head mesh contains two small, disconnected ear components.
Unlike the previous side-facing standalone ear, each source component includes
the authored skin-side root.  Placement reuses the actor's calibrated inner
ear-root positions, preserving the existing head-bone binding contract.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ACTOR_EARS = {"L": "CartoonEar_L_Downloaded", "R": "CartoonEar_R_Downloaded"}
HEAD_BONE = "CC_Base_Head"
SOURCE_HEAD = "head_org_0_0_node"


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--miku-fbx", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--size-scale", type=float, default=0.92)
    return parser.parse_args(argv)


def parent_to_head(obj: bpy.types.Object, armature: bpy.types.Object) -> None:
    # Newly-created objects have not necessarily evaluated their assigned
    # location yet.  Flush that state before preserving world space through
    # bone parenting, otherwise they jump to the armature origin.
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = HEAD_BONE
    obj.matrix_world = world


def connected_components(mesh: bpy.types.Mesh) -> list[set[int]]:
    neighbours = [set() for _ in mesh.vertices]
    for polygon in mesh.polygons:
        vertices = list(polygon.vertices)
        for index, vertex in enumerate(vertices):
            neighbours[vertex].update(vertices[:index] + vertices[index + 1 :])
    unseen = set(range(len(neighbours)))
    components = []
    while unseen:
        todo = [unseen.pop()]
        found = set()
        while todo:
            vertex = todo.pop()
            found.add(vertex)
            for other in neighbours[vertex] & unseen:
                unseen.remove(other)
                todo.append(other)
        components.append(found)
    return components


def source_ear_components(source: bpy.types.Object) -> dict[str, set[int]]:
    components = connected_components(source.data)
    details = []
    for component in components:
        center = sum((source.matrix_world @ source.data.vertices[index].co for index in component), Vector()) / len(component)
        details.append((center.x, component))
    # The two small components farthest from the head centre are the authored ears.
    candidates = sorted(details, key=lambda item: abs(item[0]), reverse=True)[:2]
    if len(candidates) != 2 or min(len(component) for _, component in candidates) < 12:
        raise RuntimeError("could not identify the two Miku ear components")
    return {"L": min(candidates, key=lambda item: item[0])[1], "R": max(candidates, key=lambda item: item[0])[1]}


def inner_root(points: list[Vector], side: str) -> Vector:
    values = [point.x for point in points]
    minimum, maximum = min(values), max(values)
    # For the left ear the inner/root side has the larger X; right is opposite.
    band = (maximum - minimum) * 0.14
    selected = [point for point in points if point.x >= maximum - band] if side == "L" else [point for point in points if point.x <= minimum + band]
    return sum(selected, Vector()) / len(selected)


def target_root_and_height(ear: bpy.types.Object, side: str) -> tuple[Vector, float, bpy.types.Material | None]:
    points = [ear.matrix_world @ Vector(corner) for corner in ear.bound_box]
    root_x = max(point.x for point in points) if side == "L" else min(point.x for point in points)
    band = (max(point.x for point in points) - min(point.x for point in points)) * 0.12
    selected = [point for point in points if point.x >= root_x - band] if side == "L" else [point for point in points if point.x <= root_x + band]
    root = sum(selected, Vector()) / len(selected)
    return root, max(point.z for point in points) - min(point.z for point in points), ear.active_material


def create_component(source: bpy.types.Object, component: set[int], source_root: Vector, target_root: Vector, target_height: float, size_scale: float, side: str, material, collection) -> bpy.types.Object:
    source_points = {index: source.matrix_world @ source.data.vertices[index].co for index in component}
    source_height = max(point.z for point in source_points.values()) - min(point.z for point in source_points.values())
    scale = target_height * size_scale / max(source_height, 1e-6)
    index_map = {old: new for new, old in enumerate(sorted(component))}
    vertices = [(source_points[old] - source_root) * scale for old in sorted(component)]
    faces = []
    for polygon in source.data.polygons:
        if all(index in component for index in polygon.vertices):
            faces.append([index_map[index] for index in polygon.vertices])
    mesh = bpy.data.meshes.new(f"MikuEar_{side}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(f"MikuEar_{side}_SourceV1", mesh)
    collection.objects.link(obj)
    obj.location = target_root
    if material:
        mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return obj


def main() -> int:
    options = parse_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    armature = bpy.data.objects.get("Armature")
    if armature is None or HEAD_BONE not in armature.pose.bones:
        raise RuntimeError("actor head bone not found")
    old = {side: bpy.data.objects.get(name) for side, name in ACTOR_EARS.items()}
    if any(ear is None for ear in old.values()):
        raise RuntimeError("expected both baseline downloaded ears")
    targets = {side: target_root_and_height(ear, side) for side, ear in old.items()}
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(options.miku_fbx.resolve()), use_anim=False)
    source = bpy.data.objects.get(SOURCE_HEAD)
    if source is None or source.type != "MESH":
        raise RuntimeError(f"Miku source head mesh not found: {SOURCE_HEAD}")
    components = source_ear_components(source)
    created = []
    for side in ("L", "R"):
        source_points = [source.matrix_world @ source.data.vertices[index].co for index in components[side]]
        root = inner_root(source_points, side)
        target_root, target_height, material = targets[side]
        ear = create_component(source, components[side], root, target_root, target_height, options.size_scale, side, material, bpy.context.scene.collection)
        parent_to_head(ear, armature)
        created.append(ear)
    for ear in old.values():
        bpy.data.objects.remove(ear, do_unlink=True)
    for obj in list(bpy.data.objects):
        if obj in before or obj in created:
            continue
        bpy.data.objects.remove(obj, do_unlink=True)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output.resolve()))
    manifest = {
        "schema": "assetslab_miku_source_ear_replacement_v1",
        "source_blend": str(options.blend.resolve()),
        "miku_fbx": str(options.miku_fbx.resolve()),
        "source_mesh": SOURCE_HEAD,
        "component_vertices": {side: len(component) for side, component in components.items()},
        "size_scale": options.size_scale,
        "created": [obj.name for obj in created],
        "binding": f"Armature/{HEAD_BONE}",
        "status": "WIP_candidate_for_visual_comparison",
    }
    options.output.with_suffix(".json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"MIKU_EAR_REPLACEMENT_PASS output={options.output.resolve()} created={[obj.name for obj in created]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
