"""Validate the static EyeAssemblyV1 contract in a saved Blender file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector


HEAD_BONE = "CC_Base_Head"


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path, required=True)
    return parser.parse_args(argv)


def object_corner(obj: bpy.types.Object) -> Vector:
    return obj.matrix_world @ Vector(obj.bound_box[0])


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    scene = bpy.context.scene
    eyes = sorted(
        (obj for obj in bpy.data.objects if obj.name.startswith("EyeAssemblyV1_Front_")),
        key=lambda obj: obj.name,
    )
    if [obj.name for obj in eyes] != ["EyeAssemblyV1_Front_L", "EyeAssemblyV1_Front_R"]:
        raise RuntimeError(f"unexpected eye assembly objects: {[obj.name for obj in eyes]}")
    if any(obj.parent_type != "BONE" or obj.parent_bone != HEAD_BONE for obj in eyes):
        raise RuntimeError("EyeAssemblyV1 surfaces are not bone-parented to CC_Base_Head")
    if any(obj.parent is None or obj.parent.name != "Armature" for obj in eyes):
        raise RuntimeError("EyeAssemblyV1 surfaces do not use Armature as parent")
    old = [obj.name for obj in bpy.data.objects if obj.name.startswith(("EyePackageV1_", "EyePackageV2_", "EyeBlinkV1_"))]
    if old:
        raise RuntimeError(f"old eye objects remain: {old}")
    if scene.get("assetslab_eye_assembly_stage") != "static_multiview_review_only":
        raise RuntimeError("unexpected EyeAssemblyV1 stage")
    if scene.get("assetslab_eye_assembly_parent_bone") != HEAD_BONE:
        raise RuntimeError("unexpected EyeAssemblyV1 parent contract")
    blink_states = scene.get("assetslab_eye_assembly_blink_states", ["Open"])
    expected_states = ["Open", "Half", "Closed"]
    if blink_states == expected_states:
        for state in expected_states:
            for side in ("L", "R"):
                material_name = f"EyeAssemblyV1_{state}_{side}"
                material = bpy.data.materials.get(material_name)
                if material is None:
                    raise RuntimeError(f"missing blink state material: {material_name}")
                if not any(node.type == "TEX_IMAGE" and node.image for node in material.node_tree.nodes):
                    raise RuntimeError(f"blink state material has no image texture: {material_name}")
    elif blink_states != ["Open"]:
        raise RuntimeError(f"unexpected blink state contract: {blink_states}")
    if scene.frame_end < 71:
        raise RuntimeError(f"body animation frame range was shortened: {scene.frame_end}")

    scene.frame_set(1)
    bpy.context.view_layer.update()
    first = {obj.name: object_corner(obj) for obj in eyes}
    scene.frame_set(31)
    bpy.context.view_layer.update()
    moved = any((object_corner(obj) - first[obj.name]).length > 0.0001 for obj in eyes)
    if not moved:
        raise RuntimeError("EyeAssemblyV1 did not follow the animated head")

    print("EYE_ASSEMBLY_V1_VALIDATION_PASS")
    print(f"EYE_ASSEMBLY_OBJECTS={','.join(obj.name for obj in eyes)}")
    print("EYE_ASSEMBLY_PARENT=Armature/CC_Base_Head")
    print("EYE_ASSEMBLY_BACK_POLICY=transparent_no_eye_geometry")
    print("EYE_ASSEMBLY_HEAD_FOLLOW=frame1_to_frame31")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
