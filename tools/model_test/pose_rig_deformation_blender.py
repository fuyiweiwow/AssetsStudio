"""Apply a deterministic diagnostic pose to an Actor Core rig."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Quaternion, Vector


# Axes are expressed in the armature's object space and converted to each
# bone's rest-local basis. This tests actual flexion instead of accidentally
# twisting long bones around their own local X axis.
POSE_AXIS_ANGLE = {
    "CC_Base_Head": ((1.0, 0.0, 0.0), 10.0),
    "CC_Base_L_Upperarm": ((0.0, 1.0, 0.0), 16.0),
    "CC_Base_R_Upperarm": ((0.0, 1.0, 0.0), -16.0),
    "CC_Base_L_Forearm": ((0.0, 0.0, 1.0), 58.0),
    "CC_Base_R_Forearm": ((0.0, 0.0, 1.0), -58.0),
    "CC_Base_L_Thigh": ((1.0, 0.0, 0.0), -28.0),
    "CC_Base_L_Calf": ((1.0, 0.0, 0.0), 46.0),
    "CC_Base_R_Thigh": ((1.0, 0.0, 0.0), 18.0),
    "CC_Base_R_Calf": ((1.0, 0.0, 0.0), -32.0),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-glb", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw)
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    armature = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
    meshes = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        and (
            obj.parent == armature
            or any(
                modifier.type == "ARMATURE" and modifier.object == armature
                for modifier in obj.modifiers
            )
        )
    ]
    if len(meshes) != 1:
        raise RuntimeError(f"Expected exactly one skinned actor mesh, received {len(meshes)}")
    rest_vertices = np.asarray([vertex.co[:] for vertex in meshes[0].data.vertices], dtype=np.float64)
    joint_positions_before = {
        name: {
            "head": list(armature.pose.bones[name].head),
            "tail": list(armature.pose.bones[name].tail),
        }
        for name in POSE_AXIS_ANGLE
    }
    for name, (axis, degrees) in POSE_AXIS_ANGLE.items():
        bone = armature.pose.bones.get(name)
        if bone is None:
            raise RuntimeError(f"Required semantic bone missing: {name}")
        axis_local = bone.bone.matrix_local.to_3x3().inverted() @ Vector(axis)
        axis_local.normalize()
        bone.rotation_mode = "QUATERNION"
        bone.rotation_quaternion = Quaternion(axis_local, math.radians(degrees))
    bpy.context.view_layer.update()
    evaluated_mesh = meshes[0].evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    posed_vertices = np.asarray([vertex.co[:] for vertex in evaluated_mesh.vertices], dtype=np.float64)
    if posed_vertices.shape != rest_vertices.shape:
        raise RuntimeError("Evaluated pose changed the actor vertex count")
    vertex_displacement = np.linalg.norm(posed_vertices - rest_vertices, axis=1)
    joint_positions_after = {
        name: {
            "head": list(armature.pose.bones[name].head),
            "tail": list(armature.pose.bones[name].tail),
        }
        for name in POSE_AXIS_ANGLE
    }

    for path in (args.output_blend, args.output_glb, args.report):
        path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.gltf(
        filepath=str(args.output_glb.resolve()),
        export_format="GLB",
        export_materials="EXPORT",
        export_skins=True,
        export_current_frame=True,
        use_selection=True,
    )
    report = {
        "schema": "assetsstudio_actor_core_deformation_pose_v1",
        "status": "diagnostic_only",
        "approved_asset": False,
        "exported_skinned_meshes": [mesh.name for mesh in meshes],
        "pose_axis_angle_armature_space": {
            name: {"axis": list(axis), "degrees": degrees}
            for name, (axis, degrees) in POSE_AXIS_ANGLE.items()
        },
        "maximum_evaluated_vertex_displacement": float(vertex_displacement.max(initial=0.0)),
        "mean_evaluated_vertex_displacement": float(vertex_displacement.mean()),
        "joint_positions_before": joint_positions_before,
        "joint_positions_after": joint_positions_after,
        "next_gate": "four_view_visual_deformation_review",
    }
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
