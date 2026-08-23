"""Open calibrated detachable-ear windows in fitted hair and undercap meshes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--radius-x", type=float, default=0.105)
    parser.add_argument("--radius-y", type=float, default=0.120)
    parser.add_argument("--radius-z", type=float, default=0.125)
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    return parser.parse_args(raw)


def object_center(obj: bpy.types.Object) -> Vector:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    return (low + high) * 0.5


def remove_faces_in_ear_windows(
    obj: bpy.types.Object,
    centers: list[Vector],
    radii: tuple[float, float, float],
) -> dict[str, int]:
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    removed = []
    for face in bm.faces:
        center = obj.matrix_world @ face.calc_center_median()
        for ear_center in centers:
            value = sum(((center[axis] - ear_center[axis]) / radii[axis]) ** 2 for axis in range(3))
            if value <= 1.0:
                removed.append(face)
                break
    before_faces = len(mesh.polygons)
    if removed:
        bmesh.ops.delete(bm, geom=removed, context="FACES")
        bm.to_mesh(mesh)
        mesh.update()
    bm.free()
    return {
        "faces_before": before_faces,
        "faces_removed": before_faces - len(mesh.polygons),
        "faces_after": len(mesh.polygons),
    }


def main() -> int:
    options = parse_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.input.resolve()))
    scene = bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    hair_objects = [
        obj
        for name in ("HairCandidate_Blend", "HairCandidate_ActorCap")
        if (obj := bpy.data.objects.get(name)) is not None
    ]
    ears = []
    for side in ("L", "R"):
        candidates = [
            obj
            for obj in scene.objects
            if obj.type == "MESH"
            and (
                obj.name.startswith(f"MikuEar_{side}_SourceV1")
                or obj.name.startswith(f"EarPair_HunyuanV2_{side}")
            )
        ]
        ears.append(candidates[0] if candidates else None)
    if not hair_objects or any(ear is None for ear in ears):
        raise RuntimeError("fitted hair and both calibrated EarPair objects are required")
    centers = [object_center(ear) for ear in ears if ear is not None]
    radii = (options.radius_x, options.radius_y, options.radius_z)
    mesh_results = {}
    for hair in hair_objects:
        mesh_results[hair.name] = remove_faces_in_ear_windows(hair, centers, radii)
        hair["assetsstudio_ear_clearance_adapter"] = "calibrated_ellipsoid_face_removal_v2"
        hair["assetsstudio_ear_clearance_radii_m"] = list(radii)
    total_removed = sum(result["faces_removed"] for result in mesh_results.values())
    if total_removed == 0:
        raise RuntimeError("ear clearance selected no fitted hair faces")

    options.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output.resolve()))
    report = {
        "schema": "assetsstudio_hair_ear_clearance_v2",
        "status": "pass",
        "input": str(options.input.resolve()),
        "output": str(options.output.resolve()),
        "hair_objects": [obj.name for obj in hair_objects],
        "ear_centers": [list(center) for center in centers],
        "radii_m": list(radii),
        "mesh_results": mesh_results,
        "policy": "interface cleanup only; no authored replacement locks or cap geometry",
    }
    options.output.with_suffix(".ear_clearance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"HAIR_EAR_CLEARANCE_PASS removed={total_removed} "
        f"output={options.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
