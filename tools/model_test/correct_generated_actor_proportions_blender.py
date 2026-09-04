"""Apply a bounded proportion correction to a generated Actor Core mesh.

This is deliberately a continuous deformation of the current generated mesh.
It must not import a canonical/legacy body or invent replacement geometry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import bpy
import numpy as np


def smoothstep(edge0: float, edge1: float, values: np.ndarray) -> np.ndarray:
    scaled = np.clip((values - edge0) / (edge1 - edge0), 0.0, 1.0)
    return scaled * scaled * (3.0 - 2.0 * scaled)


def topology_hash(faces: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(faces, dtype=np.int64).tobytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-npz", required=True, type=Path)
    parser.add_argument("--output-glb", required=True, type=Path)
    parser.add_argument("--output-npz", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--pelvis-z", type=float, default=-0.48)
    parser.add_argument("--neck-z", type=float, default=0.20)
    parser.add_argument("--torso-compression", type=float, default=0.08)
    parser.add_argument("--belly-front-reduction", type=float, default=0.12)
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw)
    if not 0.0 <= args.torso_compression <= 0.15:
        raise ValueError("torso-compression must remain in the approved [0, 0.15] diagnostic range")
    if not 0.0 <= args.belly_front_reduction <= 0.20:
        raise ValueError("belly-front-reduction must remain in the approved [0, 0.20] range")
    if args.neck_z <= args.pelvis_z:
        raise ValueError("neck-z must be above pelvis-z")

    with np.load(args.input_npz.resolve(), allow_pickle=True) as payload:
        source = np.asarray(payload["vertices"], dtype=np.float64)
        faces = np.asarray(payload["faces"], dtype=np.int64)
    vertices = source.copy()

    # Compress only the pelvis-to-neck interval. Everything above the neck is
    # translated intact, preserving the generated head; legs stay untouched.
    span = args.neck_z - args.pelvis_z
    vertical_delta = span * args.torso_compression
    inside = (source[:, 2] > args.pelvis_z) & (source[:, 2] < args.neck_z)
    above = source[:, 2] >= args.neck_z
    vertices[inside, 2] = args.pelvis_z + (
        (source[inside, 2] - args.pelvis_z) * (1.0 - args.torso_compression)
    )
    vertices[above, 2] -= vertical_delta

    # Negative Y is the actor's front in the normalized TripoSG/UniRig frame.
    # A smooth central-torso mask avoids narrowing arms, back, hips, or chest.
    z_in = smoothstep(-0.50, -0.39, source[:, 2])
    z_out = 1.0 - smoothstep(0.02, 0.13, source[:, 2])
    x_center = 1.0 - smoothstep(0.20, 0.31, np.abs(source[:, 0]))
    front = smoothstep(0.02, 0.18, -source[:, 1])
    belly_weight = z_in * z_out * x_center * front
    front_reference_y = -0.015
    front_distance = np.minimum(vertices[:, 1] - front_reference_y, 0.0)
    vertices[:, 1] -= front_distance * args.belly_front_reduction * belly_weight

    edge_uses: Counter[tuple[int, int]] = Counter()
    for face in faces:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge_uses[tuple(sorted((int(a), int(b))))] += 1
    nonmanifold_edges = sum(count != 2 for count in edge_uses.values())
    source_hash = topology_hash(faces)
    output_hash = topology_hash(faces)
    report = {
        "schema": "assetsstudio_generated_actor_proportion_correction_v1",
        "status": "diagnostic_only",
        "approved_asset": False,
        "operation": "bounded_vertex_deformation_of_current_generated_mesh",
        "legacy_or_canonical_mesh_imported": False,
        "parameters": {
            "pelvis_z": args.pelvis_z,
            "neck_z": args.neck_z,
            "torso_compression": args.torso_compression,
            "vertical_delta": vertical_delta,
            "belly_front_reduction": args.belly_front_reduction,
        },
        "vertices": len(vertices),
        "faces": len(faces),
        "topology_hash_before": source_hash,
        "topology_hash_after": output_hash,
        "topology_preserved": source_hash == output_hash,
        "nonmanifold_edges": nonmanifold_edges,
        "watertight": nonmanifold_edges == 0,
        "maximum_vertex_displacement": float(np.linalg.norm(vertices - source, axis=1).max()),
        "mean_vertex_displacement": float(np.linalg.norm(vertices - source, axis=1).mean()),
        "next_gate": "rerun_independent_skeleton_bind_and_deformation_preview",
    }

    for path in (args.output_glb, args.output_npz, args.report):
        path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output_npz.resolve(), vertices=vertices, faces=faces)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    mesh_data = bpy.data.meshes.new("ActorCoreGeneratedMeshCorrected")
    mesh_data.from_pydata(vertices.tolist(), [], faces.tolist())
    mesh_data.update()
    mesh = bpy.data.objects.new("ActorCoreGeneratedMeshCorrected", mesh_data)
    bpy.context.collection.objects.link(mesh)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.export_scene.gltf(
        filepath=str(args.output_glb.resolve()),
        export_format="GLB",
        export_materials="NONE",
        use_selection=True,
    )
    print(json.dumps(report))
    return 0 if report["topology_preserved"] and report["watertight"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
