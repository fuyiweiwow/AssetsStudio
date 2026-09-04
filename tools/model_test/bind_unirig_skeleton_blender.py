"""Bind a normalized UniRig mesh to its predicted skeleton for diagnostics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np


SEMANTIC_NAMES = {
    0: "CC_Base_Hip",
    1: "CC_Base_Pelvis",
    2: "CC_Base_Waist",
    3: "CC_Base_Spine02",
    4: "CC_Base_NeckTwist01",
    5: "CC_Base_Head",
    6: "CC_Base_L_Clavicle",
    7: "CC_Base_L_Upperarm",
    8: "CC_Base_L_Forearm",
    9: "CC_Base_L_Hand",
    10: "CC_Base_L_Index1",
    11: "CC_Base_L_Index2",
    12: "CC_Base_L_Index3",
    13: "CC_Base_L_Mid1",
    14: "CC_Base_L_Mid2",
    15: "CC_Base_L_Mid3",
    16: "CC_Base_L_Ring1",
    17: "CC_Base_L_Ring2",
    18: "CC_Base_L_Ring3",
    19: "CC_Base_L_Pinky1",
    20: "CC_Base_L_Pinky2",
    21: "CC_Base_L_Pinky3",
    22: "CC_Base_R_Clavicle",
    23: "CC_Base_R_Upperarm",
    24: "CC_Base_R_Forearm",
    25: "CC_Base_R_Hand",
    26: "CC_Base_R_Index1",
    27: "CC_Base_R_Index2",
    28: "CC_Base_R_Index3",
    29: "CC_Base_R_Mid1",
    30: "CC_Base_R_Mid2",
    31: "CC_Base_R_Mid3",
    32: "CC_Base_R_Ring1",
    33: "CC_Base_R_Ring2",
    34: "CC_Base_R_Ring3",
    35: "CC_Base_R_Pinky1",
    36: "CC_Base_R_Pinky2",
    37: "CC_Base_R_Pinky3",
    38: "CC_Base_L_Thigh",
    39: "CC_Base_L_Calf",
    40: "CC_Base_L_Foot",
    41: "CC_Base_L_ToeBase",
    42: "CC_Base_R_Thigh",
    43: "CC_Base_R_Calf",
    44: "CC_Base_R_Foot",
    45: "CC_Base_R_ToeBase",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-npz", required=True, type=Path)
    parser.add_argument("--skeleton-fbx", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-glb", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    with np.load(args.mesh_npz.resolve(), allow_pickle=True) as payload:
        vertices = np.asarray(payload["vertices"], dtype=np.float64)
        faces = np.asarray(payload["faces"], dtype=np.int64)

    mesh_data = bpy.data.meshes.new("ActorCoreGeneratedMesh")
    mesh_data.from_pydata(vertices.tolist(), [], faces.tolist())
    mesh_data.update()
    mesh = bpy.data.objects.new("ActorCoreGeneratedMesh", mesh_data)
    bpy.context.collection.objects.link(mesh)
    bpy.ops.import_scene.fbx(filepath=str(args.skeleton_fbx.resolve()), use_image_search=False)
    armature = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
    # UniRig's diagnostic FBX can contain a copy of its inference mesh.  It is
    # evidence for the predicted joints, not part of the bound actor.  Keeping
    # it in the .blend makes later "select all meshes" exports silently contain
    # two overlapping bodies.
    imported_helper_meshes = [
        obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != mesh
    ]
    for helper in imported_helper_meshes:
        bpy.data.objects.remove(helper, do_unlink=True)
    if len(armature.data.bones) != len(SEMANTIC_NAMES):
        raise RuntimeError(
            f"Unapproved skeleton signature: expected {len(SEMANTIC_NAMES)} bones, "
            f"received {len(armature.data.bones)}"
        )
    for index, name in SEMANTIC_NAMES.items():
        bone = armature.data.bones.get(f"bone_{index}")
        if bone is None:
            raise RuntimeError(f"Missing predicted bone_{index}; semantic mapping refused")
        bone.name = name
    armature.name = "ActorCoreGeneratedRig"
    armature.data.name = "ActorCoreGeneratedRigData"

    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")

    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)

    influences = np.zeros(len(mesh.data.vertices), dtype=np.int32)
    totals = np.zeros(len(mesh.data.vertices), dtype=np.float64)
    for vertex in mesh.data.vertices:
        for assignment in vertex.groups:
            if assignment.weight > 1e-6:
                influences[vertex.index] += 1
                totals[vertex.index] += assignment.weight
    report = {
        "schema": "assetsstudio_unirig_blender_heat_bind_v1",
        "status": "diagnostic_only",
        "approved_asset": False,
        "mesh_vertices": len(mesh.data.vertices),
        "mesh_faces": len(mesh.data.polygons),
        "bones": len(armature.data.bones),
        "removed_skeleton_helper_meshes": len(imported_helper_meshes),
        "semantic_mapping": "validated_46_bone_biped_signature_v1",
        "unweighted_vertices": int(np.count_nonzero(influences == 0)),
        "maximum_influences": int(influences.max(initial=0)),
        "vertices_over_four_influences": int(np.count_nonzero(influences > 4)),
        "maximum_normalization_error": float(np.abs(totals[influences > 0] - 1.0).max(initial=0.0)),
        "next_gate": "isolated_joint_deformation_preview",
    }
    for path in (args.output_blend, args.output_glb, args.report):
        path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.gltf(
        filepath=str(args.output_glb.resolve()),
        export_format="GLB",
        export_materials="EXPORT",
        export_skins=True,
        use_selection=True,
    )
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
