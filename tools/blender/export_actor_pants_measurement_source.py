"""Export the Actor REST mesh and lower-body landmarks for pants authoring.

The output OBJ is in GarmentCode coordinates and metres: Blender
``(x, y, z)`` becomes ``(x, z, -y)``.  The companion JSON records only
Actor-derived landmarks; no demo body or existing garment is consulted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--mesh-output", required=True, type=Path)
    parser.add_argument("--landmarks-output", required=True, type=Path)
    parser.add_argument("--object", default="ChibiBaseMesh_AccuRIG_InputMesh")
    parser.add_argument("--armature", default="Armature")
    return parser.parse_args(argv)


def bone_point(armature: bpy.types.Object, name: str, tail: bool = False):
    bone = armature.data.bones.get(name)
    if bone is None:
        raise RuntimeError(f"missing Actor bone: {name}")
    return armature.matrix_world @ (bone.tail_local if tail else bone.head_local)


def gc_point(point) -> list[float]:
    return [float(point.x), float(point.z), float(-point.y)]


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.actor.resolve()))
    actor = bpy.data.objects.get(options.object)
    armature = bpy.data.objects.get(options.armature)
    if actor is None or actor.type != "MESH" or armature is None:
        raise RuntimeError("Actor blend is missing the expected mesh or armature")

    armature.data.pose_position = "REST"
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    evaluated = actor.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        world = evaluated.matrix_world
        vertices = [gc_point(world @ vertex.co) for vertex in mesh.vertices]
        lines = [
            "# AssetsStudio Actor REST mesh for GarmentCode pants measurements\n",
            *[f"v {x:.9f} {y:.9f} {z:.9f}\n" for x, y, z in vertices],
        ]
        # This axis mapping is a proper rotation (determinant +1), so winding
        # must remain unchanged for outward normals.
        face_count = len(mesh.polygons)
        for polygon in mesh.polygons:
            lines.append(
                "f " + " ".join(str(index + 1) for index in polygon.vertices) + "\n"
            )
    finally:
        evaluated.to_mesh_clear()

    waist = bone_point(armature, "CC_Base_Waist", tail=True)
    pelvis = bone_point(armature, "CC_Base_Pelvis")
    left_thigh_head = bone_point(armature, "CC_Base_L_Thigh")
    right_thigh_head = bone_point(armature, "CC_Base_R_Thigh")
    left_thigh_tail = bone_point(armature, "CC_Base_L_Thigh", tail=True)
    right_thigh_tail = bone_point(armature, "CC_Base_R_Thigh", tail=True)
    neck = bone_point(armature, "CC_Base_NeckTwist01")

    thigh_section_left = left_thigh_head.lerp(left_thigh_tail, 0.32)
    thigh_section_right = right_thigh_head.lerp(right_thigh_tail, 0.32)
    mesh_output = options.mesh_output.resolve()
    landmarks_output = options.landmarks_output.resolve()
    mesh_output.parent.mkdir(parents=True, exist_ok=True)
    landmarks_output.parent.mkdir(parents=True, exist_ok=True)
    mesh_output.write_text("".join(lines), encoding="utf-8")

    bounds = {
        "min": [min(vertex[index] for vertex in vertices) for index in range(3)],
        "max": [max(vertex[index] for vertex in vertices) for index in range(3)],
    }
    payload = {
        "schema": "assetsstudio_actor_pants_landmarks_v1",
        "source_actor": str(options.actor.resolve()),
        "source_object": actor.name,
        "pose": "REST",
        "units": "metres",
        "coordinate_mapping": "Blender (x,y,z) -> GarmentCode (x,z,-y)",
        "mesh": str(mesh_output),
        "mesh_vertex_count": len(vertices),
        "mesh_face_count": face_count,
        "mesh_bounds_m": bounds,
        "landmarks_gc_m": {
            "neck": gc_point(neck),
            "waist": gc_point(waist),
            "hips": gc_point(pelvis),
            "left_thigh_head": gc_point(left_thigh_head),
            "right_thigh_head": gc_point(right_thigh_head),
            "left_thigh_section": gc_point(thigh_section_left),
            "right_thigh_section": gc_point(thigh_section_right),
            "left_thigh_tail": gc_point(left_thigh_tail),
            "right_thigh_tail": gc_point(right_thigh_tail),
        },
        "authoring_policy": "Actor REST mesh and Actor skeleton only",
    }
    landmarks_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
