"""Export the exact d0f92ac 50k checkpoint for experimental manual calibration.

No geometry cleanup, smoothing, rescaling or pose edits. This is interchange
validation, not artistic approval or proof of animation topology.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix
from mathutils.kdtree import KDTree

EXPECTED = 'e7e88465037df7ef3e5b018f19d36694e0d6c8ab081dced7fc17ace307a17068'
REPAIRED = 'f20120e0a0d6708516d6c66d01aec111bc5a6559e84db1f0082925b281498f6d'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if len(meshes) != 1 or any(o.type == 'ARMATURE' for o in bpy.context.scene.objects):
        raise ValueError('Expected one unbound mesh')
    obj = meshes[0]
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    manifold = all(e.is_manifold for e in bm.edges)
    euler = len(bm.verts) - len(bm.edges) + len(bm.faces)
    bm.free()
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    return obj, points, {'vertices': len(points), 'faces': len(obj.data.polygons),
                         'manifold': manifold, 'euler': euler}


def max_distance(a, b):
    tree = KDTree(len(b))
    for i, p in enumerate(b):
        tree.insert(p, i)
    tree.balance()
    return max(tree.find(p)[2] for p in a)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--foot-repaired', action='store_true', help='Use the separately frozen sole-repair v2 checkpoint')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
    expected = REPAIRED if args.foot_repaired else EXPECTED
    if digest(args.input) != expected:
        raise ValueError('Not the frozen 50k v2 checkpoint')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(args.input.resolve()))
    obj, _, _ = snapshot()
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    obj.name = 'Actor_Offline_v2_50k_Calibration'
    bpy.context.view_layer.update()
    obj, before, before_stats = snapshot()
    vertices, faces = (26115, 52226) if args.foot_repaired else (25002, 50000)
    if before_stats != {'vertices': vertices, 'faces': faces, 'manifold': True, 'euler': 2}:
        raise ValueError('Unexpected source topology')
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    output = args.output_dir / ('Actor_Offline_v2_FootRepair_AccuRIG.fbx' if args.foot_repaired else 'Actor_Offline_v2_50k_AccuRIG.fbx')
    bpy.ops.export_scene.fbx(filepath=str(output.resolve()), use_selection=True,
        object_types={'MESH'}, apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Z', axis_up='Y', bake_space_transform=False,
        use_mesh_modifiers=False, mesh_smooth_type='OFF', add_leaf_bones=False, bake_anim=False)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(output.resolve()))
    _, after, after_stats = snapshot()
    error = max(max_distance(before, after), max_distance(after, before))
    height = max(p.z for p in before) - min(p.z for p in before)
    passed = before_stats == after_stats and error <= height * 1e-5
    report = {'status': 'pass_interchange_only' if passed else 'fail',
              'purpose': 'User manual calibration then motion diagnostics; not final art approval',
              'source_sha256': expected, 'output_sha256': digest(output),
              'source': str(args.input), 'output': output.name,
              'before': before_stats, 'after': after_stats,
              'bidirectional_world_vertex_error_max': error, 'error_tolerance': height * 1e-5,
              'source_unchanged': digest(args.input) == expected,
              'finger_count': 0, 'accessory_included': False,
              'allow_production': False}
    (args.output_dir / 'handoff.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if not passed:
        raise RuntimeError('Interchange failed; do not calibrate this FBX')


if __name__ == '__main__':
    main()
