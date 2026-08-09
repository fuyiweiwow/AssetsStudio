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
        "EyePackageV1_AlmondFrame_L",
        "EyePackageV1_AlmondFrame_R",
        "EyePackageV1_Lens_L",
        "EyePackageV1_Lens_R",
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


def retarget_armature_modifier(obj: bpy.types.Object, armature: bpy.types.Object) -> None:
    modifiers = [modifier for modifier in obj.modifiers if modifier.type == "ARMATURE"]
    if not modifiers:
        raise RuntimeError(f"preview component has no armature modifier: {obj.name}")
    for modifier in modifiers:
        modifier.object = armature


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
    top_blend = options.top_blend.resolve()
    pants_blend = options.pants_blend.resolve()
    output = options.output.resolve()
    for source in (base_blend, top_blend, pants_blend):
        if not source.is_file():
            raise FileNotFoundError(source)

    bpy.ops.wm.open_mainfile(filepath=str(base_blend))
    scene = bpy.context.scene
    armature = bpy.data.objects.get("Armature")
    if armature is None or armature.type != "ARMATURE":
        raise RuntimeError("base preview scene has no authoritative Armature")

    remove_reference_shoe_meshes()
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
    component_names = {**COMPONENT_OBJECTS, "shoes": shoe_names, "hair": []}

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
