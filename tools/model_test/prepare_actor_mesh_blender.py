"""Create a closed, animation-sized mesh from a generated teacher GLB."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import bpy
import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-glb", required=True, type=Path)
    parser.add_argument("--output-npz", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--target-faces", type=int, default=50000)
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(args.input.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh imported")
    mesh = max(meshes, key=lambda obj: len(obj.data.polygons))
    for other in meshes:
        if other != mesh:
            bpy.data.objects.remove(other, do_unlink=True)
    before_faces = len(mesh.data.polygons)
    if before_faces > args.target_faces:
        modifier = mesh.modifiers.new("ActorCoreAnimationDecimate", type="DECIMATE")
        modifier.decimate_type = "COLLAPSE"
        modifier.ratio = args.target_faces / before_faces
        modifier.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = mesh
        mesh.select_set(True)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    removed_invalid = mesh.data.validate(verbose=True, clean_customdata=True)
    mesh.data.update(calc_edges=True)

    vertices = np.asarray([vertex.co[:] for vertex in mesh.data.vertices], dtype=np.float64)
    faces = np.asarray([polygon.vertices[:] for polygon in mesh.data.polygons], dtype=np.int64)
    if faces.ndim != 2 or faces.shape[1] != 3:
        raise RuntimeError("Prepared mesh is not fully triangulated")
    edge_uses = Counter()
    for face in faces:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge_uses[tuple(sorted((int(a), int(b))))] += 1
    nonmanifold_edges = sum(count != 2 for count in edge_uses.values())
    duplicate_faces = len(faces) - len(np.unique(np.sort(faces, axis=1), axis=0))
    report = {
        "schema": "assetsstudio_generated_actor_mesh_prepare_v1",
        "status": "diagnostic_only",
        "approved_asset": False,
        "source_faces": before_faces,
        "vertices": len(vertices),
        "faces": len(faces),
        "invalid_geometry_removed": bool(removed_invalid),
        "duplicate_faces": int(duplicate_faces),
        "nonmanifold_edges": int(nonmanifold_edges),
        "watertight": nonmanifold_edges == 0,
        "next_gate": "independent_skeleton_bind_and_deformation",
    }
    for path in (args.output_glb, args.output_npz, args.report):
        path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output_npz.resolve(),
        vertices=vertices,
        faces=faces,
        object_name=np.asarray(mesh.name),
    )
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.export_scene.gltf(
        filepath=str(args.output_glb.resolve()),
        export_format="GLB",
        export_materials="EXPORT",
        use_selection=True,
    )
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    if not report["watertight"] or duplicate_faces:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
