"""Fill only open boundary loops of an Actor proxy in Blender."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import bmesh


def args_from_blender():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--scale", type=float, default=0.01)
    parser.add_argument(
        "--fill-loop-max-coordinate",
        type=float,
        default=None,
        help="Only fill boundary loops whose maximum source coordinate is <= this value",
    )
    parser.add_argument(
        "--fill-loop-coordinate-index",
        type=int,
        default=1,
        choices=(0, 1, 2),
        help="Coordinate axis used with --fill-loop-max-coordinate",
    )
    parser.add_argument(
        "--allow-remaining-boundaries",
        action="store_true",
        help="Permit intentionally skipped boundary loops for an open-body diagnostic",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = args_from_blender()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=str(args.input.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(f"expected one imported mesh, got {len(meshes)}")
    obj = meshes[0]
    obj.scale = (args.scale, args.scale, args.scale)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.context.view_layer.update()
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    boundary = [edge for edge in bm.edges if not edge.is_manifold]
    before = {"vertices": len(bm.verts), "faces": len(bm.faces), "boundary_edges": len(boundary)}
    selected_boundary = boundary
    skipped_boundary_components = 0
    if boundary and args.fill_loop_max_coordinate is not None:
        # Boundary edges form disjoint loops for the exported Actor surface.
        # Select loops by their source-space height so a shoulder/neck cut is
        # not mistaken for a planar collar opening.
        bm.verts.ensure_lookup_table()
        adjacency = {}
        for edge in boundary:
            a, b = edge.verts
            adjacency.setdefault(a.index, []).append((b.index, edge))
            adjacency.setdefault(b.index, []).append((a.index, edge))
        visited = set()
        selected_boundary = []
        for start in adjacency:
            if start in visited:
                continue
            stack = [start]
            component_vertices = set()
            component_edges = []
            while stack:
                vertex = stack.pop()
                if vertex in visited:
                    continue
                visited.add(vertex)
                component_vertices.add(vertex)
                for neighbor, edge in adjacency.get(vertex, []):
                    component_edges.append(edge)
                    if neighbor not in visited:
                        stack.append(neighbor)
            maximum = max(
                bm.verts[index].co[args.fill_loop_coordinate_index]
                for index in component_vertices
            )
            if maximum <= args.fill_loop_max_coordinate:
                selected_boundary.extend(dict.fromkeys(component_edges))
            else:
                skipped_boundary_components += 1
    if selected_boundary:
        bmesh.ops.holes_fill(bm, edges=selected_boundary, sides=0)
    bm.normal_update()
    bm.to_mesh(mesh)
    mesh.update()
    after_bm = bmesh.new()
    after_bm.from_mesh(mesh)
    after_bm.edges.ensure_lookup_table()
    after = {"vertices": len(after_bm.verts), "faces": len(after_bm.faces), "boundary_edges": sum(1 for edge in after_bm.edges if not edge.is_manifold)}
    after_bm.free()
    if after["boundary_edges"] and not args.allow_remaining_boundaries:
        raise RuntimeError(f"boundary fill incomplete: {after}")
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    # Export normals can split shared vertices by smoothing state in Blender's
    # OBJ writer.  Collision topology must survive the round trip, so normals
    # are deliberately omitted; GarmentCode rebuilds its own collision mesh
    # data from positions and triangle indices.
    bpy.ops.wm.obj_export(filepath=str(args.output.resolve()), export_materials=False, export_normals=False, export_uv=False)
    report = {
        "schema": "assetsstudio_actor_proxy_blender_boundary_fill_v1",
        "source": str(args.input.resolve()),
        "output": str(args.output.resolve()),
        "scale": args.scale,
        "before": before,
        "after": after,
        "selected_boundary_edges": len(selected_boundary),
        "skipped_boundary_components": skipped_boundary_components,
        "fill_loop_max_coordinate": args.fill_loop_max_coordinate,
        "fill_loop_coordinate_index": args.fill_loop_coordinate_index,
        "allow_remaining_boundaries": args.allow_remaining_boundaries,
        "note": "Only existing non-manifold boundary loops were filled; no voxel dilation, smoothing, or post-generation garment edit was used.",
    }
    args.report.resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
