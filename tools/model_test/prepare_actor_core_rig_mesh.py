"""Build a non-destructive, lighter Actor Core mesh for rigging handoff.

The accepted Hunyuan mesh remains the source asset.  This script imports that
mesh, canonicalizes it, applies one deterministic collapse decimation, checks
basic topology/bounds gates, and writes a separate GLB/BLEND candidate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector(tuple(min(point[index] for point in points) for index in range(3))),
        Vector(tuple(max(point[index] for point in points) for index in range(3))),
    )


def bounds_payload(minimum: Vector, maximum: Vector) -> dict[str, list[float]]:
    return {
        "min": list(minimum),
        "max": list(maximum),
        "dimensions": list(maximum - minimum),
        "center": list((minimum + maximum) / 2.0),
    }


def topology(obj: bpy.types.Object) -> dict[str, int]:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    boundary_edges = sum(1 for edge in bm.edges if len(edge.link_faces) == 1)
    non_manifold_edges = sum(1 for edge in bm.edges if len(edge.link_faces) != 2)

    unseen = set(range(len(bm.verts)))
    components = 0
    while unseen:
        components += 1
        stack = [unseen.pop()]
        while stack:
            vertex = bm.verts[stack.pop()]
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex).index
                if other in unseen:
                    unseen.remove(other)
                    stack.append(other)

    result = {
        "vertices": len(bm.verts),
        "edges": len(bm.edges),
        "faces": len(bm.faces),
        "boundary_edges": boundary_edges,
        "non_manifold_edges": non_manifold_edges,
        "connected_components": components,
    }
    bm.free()
    return result


def weld_coincident_vertices(obj: bpy.types.Object, distance: float) -> tuple[int, int]:
    """Undo GLB normal-split vertex duplication on the untextured rig copy."""
    before = len(obj.data.vertices)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=distance)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.validate(clean_customdata=False)
    obj.data.update()
    return before, len(obj.data.vertices)


def relative_dimension_drift(before: Vector, after: Vector) -> float:
    values = []
    for source, candidate in zip(before, after):
        values.append(abs(candidate - source) / max(abs(source), 1e-8))
    return max(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--target-faces", type=int, default=122_000)
    parser.add_argument("--max-bounds-drift", type=float, default=0.005)
    parser.add_argument("--weld-distance", type=float, default=1e-6)
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(raw_args)
    if args.target_faces < 1_000:
        raise ValueError("--target-faces must be at least 1000")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(args.input.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(meshes) != 1:
        raise RuntimeError(f"Rig mesh preparation requires one mesh; found {len(meshes)}")
    if armatures:
        raise RuntimeError("Rig mesh preparation requires an unrigged source")

    actor = meshes[0]
    source_minimum, source_maximum = bounds(actor)
    source_center = (source_minimum + source_maximum) / 2.0
    canonical_offset = Vector((-source_center.x, -source_center.y, -source_minimum.z))
    actor.data.transform(Matrix.Translation(canonical_offset) @ actor.matrix_world)
    actor.matrix_world = Matrix.Identity(4)
    actor.data.validate(clean_customdata=False)
    actor.data.update()
    bpy.context.view_layer.update()

    canonical_minimum, canonical_maximum = bounds(actor)
    imported_vertices, welded_vertices = weld_coincident_vertices(actor, args.weld_distance)
    source_topology = topology(actor)
    if source_topology["faces"] <= args.target_faces:
        raise RuntimeError(
            f"Source already has {source_topology['faces']} faces, not above target {args.target_faces}"
        )

    actor.name = f"{args.asset_id}_RigMesh"
    actor.data.name = f"{args.asset_id}_RigMeshData"
    bpy.context.view_layer.objects.active = actor
    actor.select_set(True)
    modifier = actor.modifiers.new(name="RigMesh_Decimate", type="DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = args.target_faces / source_topology["faces"]
    modifier.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    actor.data.validate(clean_customdata=False)
    actor.data.update()
    bpy.context.view_layer.update()

    candidate_minimum, candidate_maximum = bounds(actor)
    candidate_topology = topology(actor)
    source_dimensions = canonical_maximum - canonical_minimum
    candidate_dimensions = candidate_maximum - candidate_minimum
    bounds_drift = relative_dimension_drift(source_dimensions, candidate_dimensions)
    face_error = abs(candidate_topology["faces"] - args.target_faces) / args.target_faces
    gates = {
        "one_mesh": len(meshes) == 1,
        "no_armature": not armatures,
        "single_component": candidate_topology["connected_components"] == 1,
        "watertight": candidate_topology["boundary_edges"] == 0,
        "manifold_edges": candidate_topology["non_manifold_edges"] == 0,
        "target_faces_within_1_percent": face_error <= 0.01,
        "bounds_drift_within_limit": bounds_drift <= args.max_bounds_drift,
    }

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0
    blend_path = args.output_dir / f"{args.asset_id}_rig_mesh.blend"
    glb_path = args.output_dir / f"{args.asset_id}_rig_mesh.glb"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path.resolve()))
    bpy.ops.object.select_all(action="DESELECT")
    actor.select_set(True)
    bpy.context.view_layer.objects.active = actor
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path.resolve()),
        export_format="GLB",
        export_materials="EXPORT",
        use_selection=True,
    )

    report = {
        "schema": "assetsstudio_actor_core_rig_mesh_v1",
        "asset_id": args.asset_id,
        "status": "pass" if all(gates.values()) else "fail",
        "source": str(args.input.resolve()),
        "outputs": {
            "blend": str(blend_path.resolve()),
            "glb": str(glb_path.resolve()),
        },
        "strategy": {
            "name": "blender_collapse_decimation",
            "target_faces": args.target_faces,
            "ratio": args.target_faces / source_topology["faces"],
            "preprocess": {
                "name": "weld_coincident_glb_normal_splits",
                "distance_m": args.weld_distance,
                "imported_vertices": imported_vertices,
                "welded_vertices": welded_vertices,
            },
            "source_asset_preserved": True,
            "purpose": "rigging_handoff_candidate",
        },
        "source_topology": source_topology,
        "candidate_topology": candidate_topology,
        "source_canonical_bounds": bounds_payload(canonical_minimum, canonical_maximum),
        "candidate_bounds": bounds_payload(candidate_minimum, candidate_maximum),
        "max_relative_dimension_drift": bounds_drift,
        "gates": gates,
    }
    report_path = args.output_dir / "rig_mesh_manifest.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["status"] != "pass":
        raise RuntimeError(f"Rig mesh gates failed: {gates}")
    print(
        "ACTOR_CORE_RIG_MESH_PASS "
        f"faces={candidate_topology['faces']} vertices={candidate_topology['vertices']} "
        f"output={glb_path.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
