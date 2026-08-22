"""Remove loose Hunyuan fragments and decimate a hair source for Actor fitting."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-faces", type=int, default=48000)
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw_args)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(f"Expected one source mesh, found {len(meshes)}")
    source = meshes[0]
    initial_vertices = len(source.data.vertices)
    initial_faces = len(source.data.polygons)

    bpy.context.view_layer.objects.active = source
    source.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    components = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    if not components:
        raise RuntimeError("Loose-component separation produced no mesh")
    components.sort(key=lambda obj: len(obj.data.polygons), reverse=True)
    source = components[0]
    removed = [
        {"name": obj.name, "vertices": len(obj.data.vertices), "faces": len(obj.data.polygons)}
        for obj in components[1:]
    ]
    for obj in components[1:]:
        bpy.data.objects.remove(obj, do_unlink=True)

    largest_faces = len(source.data.polygons)
    ratio = min(1.0, args.target_faces / max(largest_faces, 1))
    if ratio < 1.0:
        bpy.context.view_layer.objects.active = source
        source.select_set(True)
        modifier = source.modifiers.new("ActorV2_HairSilhouetteDecimate", "DECIMATE")
        modifier.decimate_type = "COLLAPSE"
        modifier.ratio = ratio
        modifier.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    source.name = "HeadHair_DefaultAdventurer_V1_Source"
    source.data.name = "HeadHair_DefaultAdventurer_V1_SourceMesh"
    source["assetsstudio_slot_id"] = "head_hair"
    source["assetsstudio_source"] = "Hunyuan3D-2mv"
    source["assetsstudio_removed_loose_components"] = len(removed)
    source["assetsstudio_decimation_target_faces"] = args.target_faces

    final_vertices = len(source.data.vertices)
    final_faces = len(source.data.polygons)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    report = {
        "schema": "assetsstudio_actor_v2_hunyuan_hair_cleanup_v1",
        "status": "pass",
        "input": str(args.input.resolve()),
        "output": str(args.output.resolve()),
        "object": source.name,
        "initial": {"vertices": initial_vertices, "faces": initial_faces},
        "loose_components": len(components),
        "removed_components": len(removed),
        "largest_component_faces": largest_faces,
        "decimation_ratio": ratio,
        "final": {"vertices": final_vertices, "faces": final_faces},
        "policy": "largest connected component only; silhouette-preserving collapse decimation",
    }
    args.output.with_suffix(".cleanup.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"ACTOR_V2_HAIR_CLEANUP_PASS components={len(components)} removed={len(removed)} "
        f"faces={initial_faces}->{final_faces} output={args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
