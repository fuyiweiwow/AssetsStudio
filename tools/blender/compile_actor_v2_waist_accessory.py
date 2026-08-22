"""Compile the generated Actor V2 default belt/pouch into a rigged slot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE_NAME = "Armature"
ACCESSORY_NAME = "WaistAccessory_DefaultAdventurer_V1"
WAIST_BONE = "CC_Base_Waist"

TARGET_X_RADIUS = 0.295
TARGET_Y_RADIUS = 0.205
TARGET_Z_LOW = 0.37
TARGET_Z_HIGH = 0.59
TARGET_Y_CENTER = 0.005


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--source-glb", required=True, type=Path)
    parser.add_argument("--reference-dir", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--decimate-ratio", type=float, default=0.14)
    return parser.parse_args(argv)


def make_toon_material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.76
        principled.inputs["Metallic"].default_value = 0.0
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
    return rgba, (int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1))


def assign_source_sampled_materials(
    accessory: bpy.types.Object,
    reference_dir: Path,
) -> dict[str, int]:
    views = {
        name: load_reference_rgba(reference_dir / f"{name}.png")
        for name in ("front", "right", "back", "left")
    }
    points = [vertex.co.copy() for vertex in accessory.data.vertices]
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    sizes = high - low
    labels: list[str] = []

    def sample(view: str, horizontal: float, vertical: float) -> tuple[float, float, float, float]:
        rgba, bbox = views[view]
        u0, v0, u1, v1 = bbox
        u = min(1.0, max(0.0, horizontal))
        v = min(1.0, max(0.0, vertical))
        x = min(rgba.shape[1] - 1, max(0, round(u0 + u * max(1, u1 - u0 - 1))))
        y = min(rgba.shape[0] - 1, max(0, round(v0 + v * max(1, v1 - v0 - 1))))
        return tuple(float(value) for value in rgba[y, x])

    for polygon in accessory.data.polygons:
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
        # Brass is lighter and substantially less red-dominant than the leather.
        brass_color = alpha > 0.10 and r > 0.30 and g > r * 0.70 and b > r * 0.43
        buckle_zone = view == "front" and 0.34 <= horizontal <= 0.66 and 0.22 <= vertical <= 0.88
        pouch_stud_zone = view == "front" and horizontal >= 0.76 and 0.24 <= vertical <= 0.72
        brass = brass_color and (buckle_zone or pouch_stud_zone)
        labels.append("brass" if brass else "leather")

    edge_faces: dict[tuple[int, int], list[int]] = {}
    for polygon in accessory.data.polygons:
        for edge in polygon.edge_keys:
            edge_faces.setdefault(tuple(sorted(edge)), []).append(polygon.index)
    neighbours: list[set[int]] = [set() for _ in accessory.data.polygons]
    for face_indices in edge_faces.values():
        if len(face_indices) == 2:
            a, b = face_indices
            neighbours[a].add(b)
            neighbours[b].add(a)
    pending = {index for index, label in enumerate(labels) if label == "brass"}
    while pending:
        seed = pending.pop()
        component = {seed}
        frontier = [seed]
        while frontier:
            current = frontier.pop()
            for neighbour in neighbours[current]:
                if neighbour in pending and labels[neighbour] == "brass":
                    pending.remove(neighbour)
                    component.add(neighbour)
                    frontier.append(neighbour)
        if len(component) < 12:
            for index in component:
                labels[index] = "leather"
    for _ in range(2):
        updated = labels.copy()
        for index, adjacent in enumerate(neighbours):
            adjacent_labels = [labels[item] for item in adjacent]
            if adjacent_labels.count("brass") >= 2:
                updated[index] = "brass"
            elif adjacent_labels.count("leather") >= 2:
                updated[index] = "leather"
        labels = updated

    accessory.data.materials.clear()
    accessory.data.materials.append(
        make_toon_material("WaistAccessory_LeatherBrown", (0.24, 0.105, 0.035, 1.0))
    )
    accessory.data.materials.append(
        make_toon_material("WaistAccessory_Brass", (0.58, 0.39, 0.16, 1.0))
    )
    counts = {"leather": 0, "brass": 0}
    for polygon, label in zip(accessory.data.polygons, labels):
        polygon.material_index = 1 if label == "brass" else 0
        counts[label] += 1
    accessory.data.update()
    return counts


def mesh_bounds(obj: bpy.types.Object) -> dict[str, list[float]]:
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    low = [min(point[axis] for point in points) for axis in range(3)]
    high = [max(point[axis] for point in points) for axis in range(3)]
    return {
        "low": [round(value, 6) for value in low],
        "high": [round(value, 6) for value in high],
        "size": [round(high[i] - low[i], 6) for i in range(3)],
    }


def main() -> int:
    args = cli()
    bpy.ops.wm.open_mainfile(filepath=str(args.actor_blend.resolve()))
    bpy.context.scene.frame_set(1)
    actor = bpy.data.objects.get(ACTOR_NAME)
    armature = bpy.data.objects.get(ARMATURE_NAME)
    if actor is None or armature is None:
        raise RuntimeError("Actor V2 body or armature is missing")
    if armature.data.bones.get(WAIST_BONE) is None:
        raise RuntimeError(f"required bone missing: {WAIST_BONE}")

    old = bpy.data.objects.get(ACCESSORY_NAME)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    existing = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.source_glb.resolve()))
    imported = [obj for obj in bpy.data.objects if obj not in existing and obj.type == "MESH"]
    if not imported:
        raise RuntimeError("Hunyuan waist accessory GLB contains no mesh")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in imported:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = imported[0]
    bpy.ops.object.join()
    accessory = bpy.context.object
    accessory.name = ACCESSORY_NAME
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    source_vertices = len(accessory.data.vertices)
    source_faces = len(accessory.data.polygons)

    decimate = accessory.modifiers.new("GeneratedAssetRetopoProxy", "DECIMATE")
    decimate.decimate_type = "COLLAPSE"
    decimate.ratio = args.decimate_ratio
    decimate.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = accessory
    bpy.ops.object.modifier_apply(modifier=decimate.name)

    material_face_counts = assign_source_sampled_materials(accessory, args.reference_dir.resolve())
    points = [vertex.co.copy() for vertex in accessory.data.vertices]
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    center = (low + high) * 0.5
    half = (high - low) * 0.5
    for vertex in accessory.data.vertices:
        point = vertex.co.copy()
        x = (point.x - center.x) / max(half.x, 1e-8) * TARGET_X_RADIUS
        y = (point.y - center.y) / max(half.y, 1e-8) * TARGET_Y_RADIUS + TARGET_Y_CENTER
        z_unit = (point.z - low.z) / max(high.z - low.z, 1e-8)
        vertex.co = Vector((x, y, TARGET_Z_LOW + z_unit * (TARGET_Z_HIGH - TARGET_Z_LOW)))
    accessory.data.update()

    for group in list(accessory.vertex_groups):
        accessory.vertex_groups.remove(group)
    waist_group = accessory.vertex_groups.new(name=WAIST_BONE)
    waist_group.add([vertex.index for vertex in accessory.data.vertices], 1.0, "REPLACE")
    modifier = accessory.modifiers.new("ActorArmature", "ARMATURE")
    modifier.object = armature
    modifier.use_vertex_groups = True
    accessory["source_kind"] = "Hunyuan3D-2MV generated waist accessory"
    accessory["source_glb"] = str(args.source_glb.resolve())
    accessory["actor_class"] = "ActorV2"
    accessory["wearable_slot"] = "waist_accessory"
    accessory["parent_bone_contract"] = WAIST_BONE

    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    report = {
        "schema": "assetsstudio_actor_v2_waist_accessory_compile_v1",
        "status": "compiled_motion_and_visual_review_required",
        "actor_class": "ActorV2",
        "slot": "waist_accessory",
        "source_glb": str(args.source_glb.resolve()),
        "source_vertices": source_vertices,
        "source_faces": source_faces,
        "compiled_vertices": len(accessory.data.vertices),
        "compiled_faces": len(accessory.data.polygons),
        "decimate_ratio": args.decimate_ratio,
        "bounds_frame_1": mesh_bounds(accessory),
        "target_radii": [TARGET_X_RADIUS, TARGET_Y_RADIUS],
        "target_vertical_range": [TARGET_Z_LOW, TARGET_Z_HIGH],
        "weight_bone": WAIST_BONE,
        "material_stage": "four-view sampled leather/brass toon palette",
        "material_face_counts": material_face_counts,
    }
    args.manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"ACTOR_V2_WAIST_ACCESSORY_COMPILE_PASS vertices={len(accessory.data.vertices)} "
        f"faces={len(accessory.data.polygons)} output={args.output_blend.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
