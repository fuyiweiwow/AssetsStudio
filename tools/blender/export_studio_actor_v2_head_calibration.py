"""Export the current Actor V2 head assembly as a Studio calibration GLB."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_studio_actor_preview import (  # noqa: E402
    convert_eye_to_head_skinned_mesh,
    convert_hair_to_head_skinned_mesh,
    create_blink_state_objects,
)


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_object(name: str, object_type: str) -> bpy.types.Object:
    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != object_type:
        raise RuntimeError(f"required {object_type} object is missing: {name}")
    return obj


def canonical_ear(side: str) -> bpy.types.Object:
    prefix = f"MikuEar_{side}_SourceV1"
    candidates = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.name.startswith(prefix)]
    if len(candidates) != 1:
        raise RuntimeError(f"expected one current {prefix} object, found {len(candidates)}")
    candidates[0].name = prefix
    return candidates[0]


def tag(obj: bpy.types.Object, component: str) -> None:
    obj["assetsstudio_component"] = component
    obj["assetsstudio_visibility_contract"] = "actor_v2_head_calibration_v1"
    obj.hide_viewport = False
    obj.hide_render = False


def main() -> int:
    options = cli_args()
    input_path = options.input.resolve()
    output_path = options.output.resolve()
    bpy.ops.wm.open_mainfile(filepath=str(input_path))
    scene = bpy.context.scene
    scene.frame_set(1)
    armature = require_object("Armature", "ARMATURE")
    body = require_object("ChibiBaseMesh_AccuRIG_InputMesh", "MESH")

    eyes = [require_object(f"EyeAssemblyV1_Front_{side}", "MESH") for side in ("L", "R")]
    eye_states: list[bpy.types.Object] = []
    for eye in eyes:
        convert_eye_to_head_skinned_mesh(eye, armature)
        eye_states.extend(create_blink_state_objects(eye))

    ears = [canonical_ear(side) for side in ("L", "R")]
    for ear in ears:
        convert_eye_to_head_skinned_mesh(ear, armature)

    hair = require_object("HairCandidate_Blend", "MESH")
    cap = require_object("HairCandidate_ActorCap", "MESH")
    convert_hair_to_head_skinned_mesh(hair, armature, "actor_v2_default_adventurer_source_locked")
    convert_hair_to_head_skinned_mesh(cap, armature, "actor_v2_default_adventurer_source_locked")

    tag(body, "body")
    for obj in eye_states + ears:
        tag(obj, "face")
    for obj in (hair, cap):
        tag(obj, "hair")

    selected = [armature, body, *eye_states, *ears, hair, cap]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in selected:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = armature
    scene.frame_start = 1
    scene.frame_end = 71
    scene.render.fps = 24
    if armature.animation_data is None or armature.animation_data.action is None:
        raise RuntimeError("Actor V2 armature has no active action")
    action = armature.animation_data.action

    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format="GLB",
        use_selection=True,
        export_extras=True,
        export_animations=True,
        export_animation_mode="ACTIVE_ACTIONS",
        export_frame_range=True,
        export_force_sampling=True,
        export_def_bones=True,
        export_optimize_animation_size=True,
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )
    components = {
        "body": [body.name],
        "face": [obj.name for obj in eye_states + ears],
        "hair": [hair.name, cap.name],
    }
    manifest = {
        "schema": "assetsstudio_actor_v2_head_calibration_preview_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {"path": str(input_path), "sha256": sha256(input_path)},
        "output": {"path": output_path.name, "bytes": output_path.stat().st_size, "sha256": sha256(output_path)},
        "components": components,
        "animations": [{"name": action.name, "frame_start": 1, "frame_end": 71}],
        "model": {"id": "actor_v2", "object": body.name},
        "rig": {"id": "accurig_actor_v2", "object": armature.name, "head_bone": "CC_Base_Head"},
        "calibration_targets": {
            "eye_l": "EyeAssemblyV1_Front_L",
            "eye_r": "EyeAssemblyV1_Front_R",
            "ear_l": "MikuEar_L_SourceV1",
            "ear_r": "MikuEar_R_SourceV1",
            "hair": "HairCandidate_Blend",
        },
        "status": "manual_feedback_requires_blender_revalidation",
    }
    output_path.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"ASSETSSTUDIO_ACTOR_V2_HEAD_PREVIEW_PASS bytes={output_path.stat().st_size} output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
