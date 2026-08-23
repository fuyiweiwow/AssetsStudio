"""Apply a Studio head-feature adjustment request to a prepared Actor Blend.

Studio exports relative world-space deltas in Three.js' X-right/Y-up/Z-out
coordinate system. This stage converts those deltas to Blender X-right/Z-up/
-Y-out coordinates, applies them around each object's current world pivot, and
keeps the original head-bone parenting intact. The result is still a candidate:
the caller must rerun all static, blink, contact and action gates.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector


SCHEMA = "assetsstudio_head_feature_feedback_v1"
COORDINATE_CONTRACT = "studio_world_x_right_y_up_z_out_v1"
ALIASES = {
    "HairBundle_Female_Seed04": "HairCandidate_Blend",
    "HairUnderCap_Candidate": "HairCandidate_ActorCap",
}
BASIS_THREE_TO_BLENDER = Matrix(
    (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, -1.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
)


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--feedback", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--frame", type=int, default=1)
    return parser.parse_args(argv)


def triple(value: object, label: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise RuntimeError(f"{label} must contain exactly three numbers")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise RuntimeError(f"{label} contains a non-finite number")
    return result


def resolve_object(name: str) -> bpy.types.Object:
    resolved = ALIASES.get(name, name)
    obj = bpy.data.objects.get(resolved)
    if obj is None:
        raise RuntimeError(f"Studio feedback target is missing from Blend: {name} (resolved {resolved})")
    if obj.type != "MESH":
        raise RuntimeError(f"Studio feedback target is not a mesh: {obj.name}")
    return obj


def matrix_values(matrix: Matrix) -> list[list[float]]:
    return [[round(float(value), 8) for value in row] for row in matrix]


def visible_world_bounds_center(obj: bpy.types.Object) -> Vector:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    points = [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]
    low = Vector(tuple(min(point[index] for point in points) for index in range(3)))
    high = Vector(tuple(max(point[index] for point in points) for index in range(3)))
    return (low + high) * 0.5


def apply_adjustment(obj: bpy.types.Object, adjustment: dict) -> dict:
    translation_three = Vector(triple(adjustment.get("translation_m"), "translation_m"))
    rotation_degrees = triple(adjustment.get("rotation_degrees_xyz"), "rotation_degrees_xyz")
    scale_three = triple(adjustment.get("scale_ratio_xyz"), "scale_ratio_xyz")

    if translation_three.length > 0.25:
        raise RuntimeError(f"translation exceeds the 0.25 m safety bound for {obj.name}")
    if any(abs(value) > 45.0 for value in rotation_degrees):
        raise RuntimeError(f"rotation exceeds the 45 degree safety bound for {obj.name}")
    if any(value < 0.5 or value > 1.75 for value in scale_three):
        raise RuntimeError(f"scale is outside [0.5, 1.75] for {obj.name}")

    translation_blender = BASIS_THREE_TO_BLENDER.to_3x3() @ translation_three
    rotation_three = Euler(tuple(math.radians(value) for value in rotation_degrees), "XYZ").to_matrix().to_4x4()
    rotation_blender = BASIS_THREE_TO_BLENDER @ rotation_three @ BASIS_THREE_TO_BLENDER.inverted()
    scale_blender = Matrix.Diagonal((scale_three[0], scale_three[2], scale_three[1], 1.0))

    before = obj.matrix_world.copy()
    pivot = visible_world_bounds_center(obj)
    delta = (
        Matrix.Translation(pivot + translation_blender)
        @ rotation_blender
        @ scale_blender
        @ Matrix.Translation(-pivot)
    )
    obj.matrix_world = delta @ before
    bpy.context.view_layer.update()
    obj["assetsstudio_manual_fit_feedback"] = SCHEMA
    obj["assetsstudio_manual_fit_target_id"] = str(adjustment.get("target_id", ""))
    return {
        "target_id": adjustment.get("target_id"),
        "requested_object": adjustment.get("object_name"),
        "resolved_object": obj.name,
        "parent_type": obj.parent_type,
        "parent_bone": obj.parent_bone,
        "visible_world_pivot": [round(float(value), 8) for value in pivot],
        "before_world": matrix_values(before),
        "after_world": matrix_values(obj.matrix_world),
    }


def main() -> int:
    options = cli_args()
    input_path = options.input.resolve()
    feedback_path = options.feedback.resolve()
    output_path = options.output.resolve()
    payload = json.loads(feedback_path.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA:
        raise RuntimeError(f"unsupported feedback schema: {payload.get('schema')}")
    if payload.get("coordinate_contract") != COORDINATE_CONTRACT:
        raise RuntimeError(f"unsupported coordinate contract: {payload.get('coordinate_contract')}")
    adjustments = payload.get("adjustments")
    if not isinstance(adjustments, list) or not adjustments:
        raise RuntimeError("Studio feedback contains no material adjustments")

    bpy.ops.wm.open_mainfile(filepath=str(input_path))
    bpy.context.scene.frame_set(options.frame)
    bpy.context.view_layer.update()
    applied = []
    seen = set()
    for adjustment in adjustments:
        if not isinstance(adjustment, dict):
            raise RuntimeError("each Studio feedback adjustment must be an object")
        requested_name = str(adjustment.get("object_name", ""))
        if requested_name in seen:
            raise RuntimeError(f"duplicate Studio feedback target: {requested_name}")
        seen.add(requested_name)
        applied.append(apply_adjustment(resolve_object(requested_name), adjustment))

    bpy.context.scene["assetsstudio_head_feature_feedback_schema"] = SCHEMA
    bpy.context.scene["assetsstudio_head_feature_feedback_source"] = str(feedback_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    report = {
        "schema": "assetsstudio_head_feature_feedback_apply_report_v1",
        "input": str(input_path),
        "feedback": str(feedback_path),
        "output": str(output_path),
        "frame": options.frame,
        "applied": applied,
        "status": "applied_requires_full_revalidation",
    }
    report_path = options.report.resolve() if options.report else output_path.with_suffix(".feedback-report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ASSETSSTUDIO_HEAD_FEATURE_FEEDBACK_PASS applied={len(applied)} output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
