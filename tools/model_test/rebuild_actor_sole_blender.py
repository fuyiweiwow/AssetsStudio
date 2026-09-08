"""Rebuild only the lowest .015H sole from each foot's intact boundary loop.

The body and upper foot are frozen. No whole-body remesh, scaling or cut-short
foot: new rounded sole rings return to the original floor. Experimental only.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

EXPECTED = 'e7e88465037df7ef3e5b018f19d36694e0d6c8ab081dced7fc17ace307a17068'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if hashlib.sha256(args.input.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('Unexpected source: preserve frozen 50k v2')
    args.output.mkdir(parents=True, exist_ok=False)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(args.input.resolve()))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if len(meshes) != 1:
        raise ValueError('Expected one actor mesh')
    obj = meshes[0]
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    original = [v.co.copy() for v in obj.data.vertices]
    floor = min(p.z for p in original)
    height = max(p.z for p in original) - floor
    cut = floor + .015 * height
    protected = [p for p in original if p.z > cut + 1e-6]
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
        plane_co=(0, 0, cut), plane_no=(0, 0, 1), dist=1e-8,
        clear_inner=True, clear_outer=False)
    if any(v.co.z < cut - 1e-6 for v in bm.verts):
        raise ValueError('Bisect did not isolate the lowest sole')
    boundaries = [e for e in bm.edges if e.is_boundary]
    if any(abs(v.co.z - cut) > 1e-5 for e in boundaries for v in e.verts):
        raise ValueError('Unexpected non-sole boundary')
    remaining = set(boundaries)
    loops = []
    while remaining:
        edge = next(iter(remaining))
        start, current = edge.verts
        loop = [start]
        remaining.remove(edge)
        while current != start:
            loop.append(current)
            options = [e for e in current.link_edges if e in remaining]
            if len(options) != 1:
                raise ValueError('Sole boundary is not a simple loop')
            edge = options[0]
            remaining.remove(edge)
            current = edge.other_vert(current)
        loops.append(loop)
    if len(loops) != 2:
        raise ValueError('Expected exactly two sole boundary loops')
    curves = []
    for loop in loops:
        # Polygon centroid, not vertex mean: intersection tessellation is uneven.
        points = [v.co.copy() for v in loop]
        cross = [p.x * q.y - q.x * p.y for p, q in zip(points, points[1:] + points[:1])]
        area6 = 3 * sum(cross)
        cx = sum((p.x + q.x) * c for p, q, c in zip(points, points[1:] + points[:1], cross)) / area6
        cy = sum((p.y + q.y) * c for p, q, c in zip(points, points[1:] + points[:1], cross)) / area6
        center = Vector((cx, cy, cut))
        curves.append({'boundary_vertices': len(points), 'center_blender': list(center),
                       'boundary_xyz': [list(p) for p in points]})
        previous = loop
        for degrees in [10, 25, 40, 55, 70, 82, 90]:
            angle = math.radians(degrees)
            scale = 1 - .12 * (1 - math.cos(angle))
            z = floor + (cut - floor) * (1 - math.sin(angle))
            ring = [bm.verts.new((cx + (p.x - cx) * scale, cy + (p.y - cy) * scale, z)) for p in points]
            for i in range(len(ring)):
                j = (i + 1) % len(ring)
                bm.faces.new((previous[i], previous[j], ring[j], ring[i]))
            previous = ring
        bm.faces.new(tuple(reversed(previous)))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method='BEAUTY', ngon_method='EAR_CLIP')
    if not all(e.is_manifold for e in bm.edges) or len(bm.verts) - len(bm.edges) + len(bm.faces) != 2:
        raise ValueError('Rebuilt sole failed manifold/Euler checks')
    bm.to_mesh(obj.data)
    bm.free()
    for p in obj.data.polygons:
        p.use_smooth = True
    obj.data.update()
    tree = KDTree(len(obj.data.vertices))
    for i, v in enumerate(obj.data.vertices):
        tree.insert(v.co, i)
    tree.balance()
    protected_error = max(tree.find(p)[2] for p in protected)
    if protected_error > 1e-7:
        raise ValueError('Protected body/upper foot vertices moved')
    report = {'status': 'candidate_requires_external_audit_and_visual_review',
        'method': 'local bottom-sole topology rebuild from the same foot boundary; no primitive body replacement',
        'source_sha256': EXPECTED, 'roi_height_fraction': .015,
        'floor_original': floor, 'floor_candidate': min(v.co.z for v in obj.data.vertices),
        'protected_vertex_count': len(protected), 'protected_vertex_error_max': protected_error,
        'vertices': len(obj.data.vertices), 'faces': len(obj.data.polygons),
        'sole_ring_angles_degrees': [10, 25, 40, 55, 70, 82, 90],
        'lower_ring_scale': .88, 'curves': curves,
        'allow_calibration': False, 'allow_production': False}
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.name = 'Actor_Offline_v2_FootRepair_Candidate'
    bpy.ops.wm.save_as_mainfile(filepath=str((args.output / 'foot_candidate.blend').resolve()))
    bpy.ops.export_scene.gltf(filepath=str((args.output / 'foot_candidate.glb').resolve()),
        export_format='GLB', use_selection=True)
    report['candidate_sha256'] = hashlib.sha256((args.output / 'foot_candidate.glb').read_bytes()).hexdigest()
    (args.output / 'repair_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'curves'}, indent=2))


if __name__ == '__main__':
    main()
