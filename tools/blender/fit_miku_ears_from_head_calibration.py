"""Fit the retained Miku ear meshes to calibrated Actor V2 head-root anchors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


HEAD_BONE = "CC_Base_Head"
SOURCE_EARS = ("MikuEar_L_SourceV1", "MikuEar_R_SourceV1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-blend", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frame", type=int, default=1)
    parser.add_argument(
        "--outward-scale",
        type=float,
        default=1.0,
        help="extend the ear silhouette away from its projected root without moving the root band",
    )
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    return parser.parse_args(raw)


def actor_mesh() -> bpy.types.Object:
    result = next(
        (
            obj
            for obj in bpy.context.scene.objects
            if obj.type == "MESH" and obj.name.startswith("ChibiBaseMesh")
        ),
        None,
    )
    if result is None:
        raise RuntimeError("Actor mesh was not found")
    return result


def world_bvh(obj: bpy.types.Object) -> tuple[BVHTree, bpy.types.Object]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
    return BVHTree.FromPolygons(points, polygons, all_triangles=False), evaluated


def append_source_ears(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    with bpy.data.libraries.load(str(path.resolve()), link=False) as (data_from, data_to):
        missing = [name for name in SOURCE_EARS if name not in data_from.objects]
        if missing:
            raise RuntimeError(f"source Blend is missing Miku ear objects: {missing}")
        data_to.objects = list(SOURCE_EARS)
    result = []
    for obj in data_to.objects:
        if obj is None:
            continue
        if not obj.users_collection:
            bpy.context.scene.collection.objects.link(obj)
        result.append(obj)
    bpy.context.view_layer.update()
    if len(result) != 2:
        raise RuntimeError(f"expected two appended source ears, found {len(result)}")
    # Library dependency objects are not selected explicitly; keep the set so
    # temporary source rigs can be removed after the world mesh is copied.
    for obj in set(bpy.data.objects) - before:
        obj["assetsstudio_temporary_miku_source"] = True
    return result


def world_points(obj: bpy.types.Object) -> list[Vector]:
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]


def root_indices(points: list[Vector], sign: float) -> list[int]:
    values = [point.x for point in points]
    low, high = min(values), max(values)
    band = (high - low) * 0.16
    if sign > 0.0:
        # Positive-X ear meets the head on its minimum-X edge.
        return [index for index, point in enumerate(points) if point.x <= low + band]
    return [index for index, point in enumerate(points) if point.x >= high - band]


def root_center(points: list[Vector], indices: list[int]) -> Vector:
    return sum((points[index] for index in indices), Vector()) / len(indices)


def side_surface_hit(
    bvh: BVHTree,
    head_low: Vector,
    head_high: Vector,
    sign: float,
    y: float,
    z: float,
):
    margin = max(head_high.x - head_low.x, 0.25)
    origin_x = head_high.x + margin if sign > 0.0 else head_low.x - margin
    return bvh.ray_cast(Vector((origin_x, y, z)), Vector((-sign, 0.0, 0.0)), margin * 3.0)


def create_fitted_ear(
    source: bpy.types.Object,
    side: str,
    target_root: Vector,
    target_height: float,
    clearance: float,
    bvh: BVHTree,
    head_low: Vector,
    head_high: Vector,
    outward_scale: float,
) -> tuple[bpy.types.Object, list[int], list[float]]:
    sign = 1.0 if side == "L" else -1.0
    points = world_points(source)
    source_root_indices = root_indices(points, sign)
    source_root = root_center(points, source_root_indices)
    source_height = max(point.z for point in points) - min(point.z for point in points)
    scale = target_height / max(source_height, 1e-8)
    fitted = []
    for point in points:
        delta = (point - source_root) * scale
        delta.x *= outward_scale
        fitted.append(target_root + delta)

    contact_distances = []
    for index in source_root_indices:
        point = fitted[index]
        hit, normal, _, _ = side_surface_hit(bvh, head_low, head_high, sign, point.y, point.z)
        if hit is None:
            continue
        fitted[index] = hit + normal * clearance
        contact_distances.append((fitted[index] - hit).length)

    faces = [tuple(polygon.vertices) for polygon in source.data.polygons]
    mesh = bpy.data.meshes.new(f"MikuEar_{side}_CalibratedMesh")
    mesh.from_pydata([tuple(point) for point in fitted], [], faces)
    mesh.update()
    for material in source.data.materials:
        mesh.materials.append(material)
    for source_polygon, target_polygon in zip(source.data.polygons, mesh.polygons):
        target_polygon.material_index = min(source_polygon.material_index, max(len(mesh.materials) - 1, 0))
        target_polygon.use_smooth = True
    ear = bpy.data.objects.new(f"MikuEar_{side}_SourceV1", mesh)
    bpy.context.scene.collection.objects.link(ear)
    ear["assetsstudio_slot_id"] = "EarPair"
    ear["assetsstudio_bundle_id"] = "earpair_miku_source_v1"
    ear["assetsstudio_side"] = side
    ear["assetsstudio_parent_bone"] = HEAD_BONE
    ear["assetsstudio_calibration_mode"] = "head_surface_root_projection_v1"
    ear["assetsstudio_target_root"] = list(target_root)
    ear["assetsstudio_target_height"] = target_height
    ear["assetsstudio_root_clearance"] = clearance
    ear["assetsstudio_outward_scale"] = outward_scale
    return ear, source_root_indices, contact_distances


def parent_to_head(obj: bpy.types.Object, armature: bpy.types.Object) -> None:
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = HEAD_BONE
    obj.matrix_world = world


def relative_translation(armature: bpy.types.Object, obj: bpy.types.Object) -> Vector:
    head_world = armature.matrix_world @ armature.pose.bones[HEAD_BONE].matrix
    return (head_world.inverted() @ obj.matrix_world).translation


def main() -> int:
    options = parse_args()
    if options.outward_scale < 1.0:
        raise RuntimeError("--outward-scale must be at least 1.0 so the calibrated root stays authoritative")
    calibration = json.loads(options.calibration.read_text(encoding="utf-8"))
    if calibration.get("schema") != "assetsstudio_actor_v2_head_feature_calibration_v1":
        raise RuntimeError("unsupported head-feature calibration schema")
    bpy.ops.wm.open_mainfile(filepath=str(options.input.resolve()))
    scene = bpy.context.scene
    scene.frame_set(options.frame)
    bpy.context.view_layer.update()
    actor = actor_mesh()
    armature = bpy.data.objects.get("Armature")
    if armature is None or armature.pose.bones.get(HEAD_BONE) is None:
        raise RuntimeError("Actor Armature/CC_Base_Head was not found")

    for obj in list(bpy.data.objects):
        if obj.name.startswith(("MikuEar_", "EarPair_HunyuanV2_", "EarPair_DefaultHuman_")):
            bpy.data.objects.remove(obj, do_unlink=True)

    bvh, evaluated = world_bvh(actor)
    head_low = Vector(calibration["head_bounds"]["min"])
    head_high = Vector(calibration["head_bounds"]["max"])
    ear_contract = calibration["ear"]
    sources = append_source_ears(options.source_blend)
    by_sign = {
        1.0: max(sources, key=lambda obj: sum(point.x for point in world_points(obj)) / len(obj.data.vertices)),
        -1.0: min(sources, key=lambda obj: sum(point.x for point in world_points(obj)) / len(obj.data.vertices)),
    }
    source_mapping = {"L": by_sign[1.0].name, "R": by_sign[-1.0].name}
    created = []
    contacts = {}
    root_counts = {}
    for side, sign in (("L", 1.0), ("R", -1.0)):
        target_root = Vector(ear_contract["root_anchors"][side])
        ear, indices, distances = create_fitted_ear(
            by_sign[sign],
            side,
            target_root,
            float(ear_contract["target_height"]),
            float(ear_contract["root_clearance"]),
            bvh,
            head_low,
            head_high,
            options.outward_scale,
        )
        parent_to_head(ear, armature)
        created.append(ear)
        contacts[side] = distances
        root_counts[side] = len(indices)

    for obj in list(bpy.data.objects):
        if obj.get("assetsstudio_temporary_miku_source"):
            bpy.data.objects.remove(obj, do_unlink=True)
    evaluated.to_mesh_clear()

    sample_frames = sorted({int(scene.frame_start), 31, int(scene.frame_end)})
    base_relative = {}
    max_drift = 0.0
    for frame in sample_frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        for ear in created:
            current = relative_translation(armature, ear)
            if ear.name not in base_relative:
                base_relative[ear.name] = current.copy()
            max_drift = max(max_drift, (current - base_relative[ear.name]).length)
    scene.frame_set(options.frame)
    bpy.context.view_layer.update()

    all_contact = [distance for distances in contacts.values() for distance in distances]
    maximum_contact = max(all_contact) if all_contact else float("inf")
    gates = {
        "two_separate_mesh_objects": len(created) == 2,
        "head_bone_parent": all(
            ear.parent == armature and ear.parent_type == "BONE" and ear.parent_bone == HEAD_BONE
            for ear in created
        ),
        "root_vertices_projected": all(contacts[side] for side in ("L", "R")),
        "root_clearance_within_contract": maximum_contact <= float(ear_contract["root_clearance"]) + 1e-5,
        "head_relative_motion_drift": max_drift <= calibration["validation_thresholds"]["head_relative_motion_drift_max_m"],
    }
    scene["assetsstudio_earpair_slot_id"] = "EarPair"
    scene["assetsstudio_earpair_bundle_id"] = "earpair_miku_source_v1"
    scene["assetsstudio_earpair_objects"] = [ear.name for ear in created]
    options.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output.resolve()))
    report = {
        "schema": "assetsstudio_actor_v2_miku_ear_calibrated_fit_v1",
        "status": "pass" if all(gates.values()) else "fail",
        "input": str(options.input.resolve()),
        "source_blend": str(options.source_blend.resolve()),
        "calibration": str(options.calibration.resolve()),
        "output": str(options.output.resolve()),
        "objects": [ear.name for ear in created],
        "source_mapping": source_mapping,
        "root_vertex_counts": root_counts,
        "contact_distance_max_m": maximum_contact,
        "sample_frames": sample_frames,
        "head_relative_motion_drift_m": max_drift,
        "outward_scale": options.outward_scale,
        "gates": gates,
    }
    options.output.with_suffix(".miku_ear_fit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if report["status"] != "pass":
        raise RuntimeError(f"Miku ear calibrated fit failed: {gates}")
    print(
        "ACTOR_V2_MIKU_EAR_CALIBRATED_FIT_PASS "
        f"contact_max={maximum_contact:.6f} drift={max_drift:.8f} output={options.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
