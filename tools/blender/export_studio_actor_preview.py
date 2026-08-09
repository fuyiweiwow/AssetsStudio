"""Export the current Actor + top + pants + shoes as an F001 local GLB preview."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bpy


COMPONENT_OBJECTS = {
    "body": ["ChibiBaseMesh_AccuRIG_InputMesh"],
    "face": [
        "EyeAssemblyV1_Front_L",
        "EyeAssemblyV1_Front_R",
        "MikuEar_L_SourceV1",
        "MikuEar_R_SourceV1",
    ],
    "top": ["ActorNativeTshirt_BodyComponent_v1"],
    "pants": ["NativeControlShorts"],
}


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-blend", required=True, type=Path)
    parser.add_argument("--face-blend", required=True, type=Path)
    parser.add_argument("--top-blend", required=True, type=Path)
    parser.add_argument("--pants-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            encoding="utf-8",
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def git_is_dirty(root: Path) -> bool:
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=root,
            text=True,
            encoding="utf-8",
        )
        return bool(status.strip())
    except (OSError, subprocess.CalledProcessError):
        return True


def append_object(blend_path: Path, object_name: str) -> bpy.types.Object:
    with bpy.data.libraries.load(str(blend_path), link=False) as (source, target):
        if object_name not in source.objects:
            raise RuntimeError(f"missing object {object_name} in {blend_path}")
        target.objects = [object_name]
    appended = target.objects[0]
    if appended is None:
        raise RuntimeError(f"failed to append {object_name} from {blend_path}")
    if appended.name not in bpy.context.scene.objects:
        bpy.context.scene.collection.objects.link(appended)
    return appended


def remove_reference_shoe_meshes() -> None:
    for obj in list(bpy.data.objects):
        if obj.type == "MESH" and obj.name.startswith("shoes"):
            bpy.data.objects.remove(obj, do_unlink=True)


def remove_legacy_eye_objects() -> None:
    for obj in list(bpy.data.objects):
        if obj.name.startswith(("EyePackageV1_", "EyePackageV2_", "EyeBlinkV1_")):
            bpy.data.objects.remove(obj, do_unlink=True)


def retarget_armature_modifier(obj: bpy.types.Object, armature: bpy.types.Object) -> None:
    modifiers = [modifier for modifier in obj.modifiers if modifier.type == "ARMATURE"]
    if not modifiers:
        raise RuntimeError(f"preview component has no armature modifier: {obj.name}")
    for modifier in modifiers:
        modifier.object = armature


def retarget_eye_assembly(
    obj: bpy.types.Object,
    armature: bpy.types.Object,
    actor_mesh: bpy.types.Object,
) -> None:
    world = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = "CC_Base_Head"
    obj.matrix_world = world
    for modifier in obj.modifiers:
        if modifier.type == "SHRINKWRAP":
            modifier.target = actor_mesh


def create_blink_state_objects(eye: bpy.types.Object) -> list[bpy.types.Object]:
    side = "L" if eye.name.endswith("_L") else "R"
    eye["assetsstudio_blink_state"] = "open"
    eye.pop("assetslab_texture", None)
    exported = [eye]
    for state in ("half", "closed"):
        material = bpy.data.materials.get(f"EyeAssemblyV1_{state.title()}_{side}")
        if material is None:
            raise RuntimeError(f"missing eye blink material for {state}/{side}")
        state_object = eye.copy()
        state_object.data = eye.data.copy()
        state_object.name = f"EyeAssemblyV1_{state.title()}_{side}_PreviewState"
        state_object.data.name = state_object.name + "Mesh"
        state_object.data.materials.clear()
        state_object.data.materials.append(material)
        for polygon in state_object.data.polygons:
            polygon.material_index = 0
        state_object["assetsstudio_blink_state"] = state
        state_object.pop("assetslab_texture", None)
        bpy.context.scene.collection.objects.link(state_object)
        exported.append(state_object)
    return exported


def tag_component(component: str, object_names: list[str]) -> list[bpy.types.Object]:
    objects = []
    for name in object_names:
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise RuntimeError(f"required preview object is missing: {name}")
        obj["assetsstudio_component"] = component
        obj["assetsstudio_visibility_contract"] = "f001_v1"
        obj.hide_viewport = False
        obj.hide_render = False
        objects.append(obj)
    return objects


def main() -> int:
    options = cli_args()
    base_blend = options.base_blend.resolve()
    face_blend = options.face_blend.resolve()
    top_blend = options.top_blend.resolve()
    pants_blend = options.pants_blend.resolve()
    output = options.output.resolve()
    for source in (base_blend, face_blend, top_blend, pants_blend):
        if not source.is_file():
            raise FileNotFoundError(source)

    bpy.ops.wm.open_mainfile(filepath=str(base_blend))
    scene = bpy.context.scene
    armature = bpy.data.objects.get("Armature")
    if armature is None or armature.type != "ARMATURE":
        raise RuntimeError("base preview scene has no authoritative Armature")
    actor_mesh = bpy.data.objects.get(COMPONENT_OBJECTS["body"][0])
    if actor_mesh is None or actor_mesh.type != "MESH":
        raise RuntimeError("base preview scene has no authoritative Actor mesh")

    remove_reference_shoe_meshes()
    remove_legacy_eye_objects()
    eye_sources = [append_object(face_blend, name) for name in COMPONENT_OBJECTS["face"][:2]]
    eye_objects: list[bpy.types.Object] = []
    for eye in eye_sources:
        retarget_eye_assembly(eye, armature, actor_mesh)
        eye_objects.extend(create_blink_state_objects(eye))
    top = append_object(top_blend, COMPONENT_OBJECTS["top"][0])
    pants = append_object(pants_blend, COMPONENT_OBJECTS["pants"][0])
    retarget_armature_modifier(top, armature)
    retarget_armature_modifier(pants, armature)

    shoe_names = sorted(
        obj.name
        for obj in bpy.data.objects
        if obj.type == "MESH" and obj.name.startswith("ActorCartoonSneaker_")
    )
    if len(shoe_names) != 16:
        raise RuntimeError(f"expected 16 fitted shoe parts, found {len(shoe_names)}")
    component_names = {
        **COMPONENT_OBJECTS,
        "face": [obj.name for obj in eye_objects] + COMPONENT_OBJECTS["face"][2:],
        "shoes": shoe_names,
        "hair": [],
    }

    selected: list[bpy.types.Object] = [armature]
    for component, names in component_names.items():
        selected.extend(tag_component(component, names))

    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in selected:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = armature

    scene.frame_start = 1
    scene.frame_end = 71
    scene.render.fps = 24
    if armature.animation_data is None or armature.animation_data.action is None:
        raise RuntimeError("Actor Armature has no active Walk action")
    action = armature.animation_data.action

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(output),
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
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"GLB export did not produce a file: {output}")

    repository_root = Path(__file__).resolve().parents[2]
    manifest = {
        "schema": "assetsstudio_actor_preview_export_v1",
        "run_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "storage_policy": "local",
        "git_commit": git_commit(repository_root),
        "git_dirty": git_is_dirty(repository_root),
        "generator": {
            "id": "export_studio_actor_preview",
            "version": "1.0.0",
            "script_sha256": sha256(Path(__file__).resolve()),
        },
        "sources": [
            {"path": str(base_blend.relative_to(repository_root)), "sha256": sha256(base_blend)},
            {"path": str(face_blend.relative_to(repository_root)), "sha256": sha256(face_blend)},
            {"path": str(top_blend.relative_to(repository_root)), "sha256": sha256(top_blend)},
            {"path": str(pants_blend.relative_to(repository_root)), "sha256": sha256(pants_blend)},
        ],
        "output": {"path": output.name, "bytes": output.stat().st_size, "sha256": sha256(output)},
        "components": component_names,
        "animations": [
            {
                "name": action.name,
                "frame_start": int(scene.frame_start),
                "frame_end": int(scene.frame_end),
                "fps": int(scene.render.fps),
            }
        ],
        "model": {"id": "body_actor_v1", "object": COMPONENT_OBJECTS["body"][0]},
        "rig": {"id": "accurig_actor_v1", "object": armature.name, "head_bone": "CC_Base_Head"},
        "face": {
            "assembly": "EyeAssemblyV1",
            "blink_states": ["open", "half", "closed"],
            "blink_schedule": ["open", "half", "closed", "half", "open", "open", "open", "open"],
        },
        "known_limitations": {
            "hair": "No validated Actor hair bundle is included in the first composite GLB.",
            "top": "The provisional right shoulder/sleeve issue remains visible by design.",
            "pants": "The provisional visual-review status remains unchanged.",
        },
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "ASSETSSTUDIO_ACTOR_PREVIEW_PASS "
        f"bytes={output.stat().st_size} animation={action.name} output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
