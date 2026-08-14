"""Export Actor walk-pose bone points for the pure-2D garment preview.

Blender is used only as the source of the existing Actor walk pose. The
consumer intentionally draws the garment in Pillow and never renders a 3D
garment mesh.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import render_accurig_chibi_walk_test as actor_render  # noqa: E402


POINT_BONES = (
    "CC_Base_Pelvis",
    "CC_Base_Spine02",
    "CC_Base_Head",
    "CC_Base_L_Upperarm",
    "CC_Base_L_Forearm",
    "CC_Base_L_Hand",
    "CC_Base_R_Upperarm",
    "CC_Base_R_Forearm",
    "CC_Base_R_Hand",
    "CC_Base_L_Thigh",
    "CC_Base_L_Calf",
    "CC_Base_L_Foot",
    "CC_Base_R_Thigh",
    "CC_Base_R_Calf",
    "CC_Base_R_Foot",
)


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--frames", type=int, default=8)
    return parser.parse_args(argv)


def bone_point(armature: bpy.types.Object, bone_name: str, point_name: str) -> list[float]:
    pose_bone = armature.pose.bones.get(bone_name)
    if pose_bone is None:
        raise RuntimeError(f"missing Actor pose bone: {bone_name}")
    point = getattr(pose_bone, point_name)
    world = armature.matrix_world @ point
    return [round(float(world.x), 6), round(float(world.y), 6), round(float(world.z), 6)]


def main() -> int:
    options = cli_args()
    if options.frames < 2:
        raise RuntimeError("frames must be at least two")
    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    scene = bpy.context.scene
    armature = bpy.data.objects.get("Armature")
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    if armature is None or actor is None:
        raise RuntimeError("Actor blend must contain Armature and ChibiBaseMesh_AccuRIG_InputMesh")
    armature.data.pose_position = "POSE"
    rest_low, rest_high = actor_render.bounds(actor)
    frames: list[dict] = []
    for frame_index in range(options.frames):
        actor_render.reset_pose(armature)
        actor_render.apply_walk_pose(armature, 2.0 * 3.141592653589793 * frame_index / options.frames)
        scene.frame_set(0)
        bpy.context.view_layer.update()
        frames.append(
            {
                "index": frame_index,
                "phase": round(2.0 * 3.141592653589793 * frame_index / options.frames, 6),
                "bones": {
                    bone_name: {
                        "head": bone_point(armature, bone_name, "head"),
                        "tail": bone_point(armature, bone_name, "tail"),
                    }
                    for bone_name in POINT_BONES
                },
            }
        )
    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "assetsstudio_actor_walk_poses_2d_v1",
        "actor_blend": str(options.actor_blend.resolve()),
        "source": "render_accurig_chibi_walk_test.apply_walk_pose",
        "frames": frames,
        "rest_bounds": {
            "low": [float(rest_low.x), float(rest_low.y), float(rest_low.z)],
            "high": [float(rest_high.x), float(rest_high.y), float(rest_high.z)],
        },
    }
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ACTOR_WALK_POSES_2D_PASS frames={len(frames)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
