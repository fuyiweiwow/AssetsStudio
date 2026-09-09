"""Compare the actual exported four-weight GLB against its animated Blend, frame by frame."""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspect_accurig_head_blender import evaluated_points


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--blend', type=Path, required=True)
    ap.add_argument('--glb', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
    args.output.mkdir(parents=True, exist_ok=False)
    bpy.ops.wm.open_mainfile(filepath=str(args.blend.resolve()))
    obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
    rig = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE'][0]
    scene = bpy.context.scene
    start, end, fps = scene.frame_start, scene.frame_end, scene.render.fps
    rig.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    rest = np.asarray(evaluated_points(obj))
    height = float(np.ptp(rest[:, 2]))
    neck = rig.matrix_world @ rig.data.bones['CC_Base_NeckTwist01'].head_local
    cut = neck.z - height * .006
    source_samples = []
    rig.data.pose_position = 'POSE'
    for frame in range(start, end + 1):
        scene.frame_set(frame)
        source_samples.append(np.asarray(evaluated_points(obj)))
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(args.glb.resolve()))
    obj = [o for o in scene.objects if o.type == 'MESH'][0]
    rig = [o for o in scene.objects if o.type == 'ARMATURE'][0]
    action = rig.animation_data.action
    runtime_start, runtime_end = action.frame_range
    rig.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    runtime_rest = np.asarray(evaluated_points(obj))
    tree = KDTree(len(rest))
    for i, p in enumerate(rest):
        tree.insert(Vector(p), i)
    tree.balance()
    mapping = [tree.find(Vector(p)) for p in runtime_rest]
    index = np.asarray([item[1] for item in mapping])
    rest_error = max(item[2] for item in mapping)
    if rest_error > height * 1e-5:
        raise ValueError('Runtime rest positions do not match source')
    edges = np.asarray([list(e.vertices) for e in obj.data.edges])
    head_mask = (runtime_rest[:, 2] > cut)
    # Rigid-head membership is further restricted by the actual Head weight.
    head_group = obj.vertex_groups['CC_Base_Head'].index
    head_mask &= np.asarray([sum(g.weight for g in v.groups if g.group == head_group) > .99999
                             for v in obj.data.vertices])
    head_edges = head_mask[edges[:, 0]] & head_mask[edges[:, 1]]
    rest_lengths = np.linalg.norm(runtime_rest[edges[:, 0]] - runtime_rest[edges[:, 1]], axis=1)
    valid = head_edges & (rest_lengths > 1e-8)
    max_influences = max(sum(g.weight > 1e-8 for g in v.groups) for v in obj.data.vertices)
    normalization_error = max(abs(sum(g.weight for g in v.groups) - 1) for v in obj.data.vertices)
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'SINGLE'
    scene.display.shading.single_color = (.55, .55, .55)
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = False
    scene.display.shading.show_specular_highlight = False
    for poly in obj.data.polygons:
        poly.use_smooth = True
    cd = bpy.data.cameras.new('RuntimeReview')
    cd.type = 'ORTHO'
    cd.ortho_scale = height / .85
    cam = bpy.data.objects.new('RuntimeReview', cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    aim = Vector((0, 0, float(rest[:, 2].min()) + height / 2))
    rig.data.pose_position = 'POSE'
    records = []
    first_runtime = None
    sample_frames = set(np.linspace(0, end-start, 16).round().astype(int).tolist())
    for offset, expected in enumerate(source_samples):
        frame = runtime_start + offset
        scene.frame_set(int(frame), subframe=frame-int(frame))
        actual = np.asarray(evaluated_points(obj))
        if first_runtime is None:
            first_runtime = actual.copy()
        errors = np.linalg.norm(actual - expected[index], axis=1)
        ratios = np.linalg.norm(actual[edges[:, 0]] - actual[edges[:, 1]], axis=1)[valid] / rest_lengths[valid]
        records.append({'source_frame': start+offset, 'runtime_frame': frame,
                        'max_position_error_H': float(errors.max()/height),
                        'p99_position_error_H': float(np.quantile(errors, .99)/height),
                        'head_edge_min': float(ratios.min()), 'head_edge_max': float(ratios.max())})
        if offset in sample_frames:
            for name, xyz in {'front': (0,-1,0), 'right': (1,0,0), 'back': (0,1,0), 'left': (-1,0,0)}.items():
                cam.location = aim + Vector(xyz)*height*3
                cam.rotation_euler = (aim-cam.location).to_track_quat('-Z','Y').to_euler()
                scene.render.filepath = str((args.output / f'{name}_{offset:03}.png').resolve())
                bpy.ops.render.render(write_still=True)
    loop_error = float(np.max(np.linalg.norm(actual-first_runtime, axis=1))/height)
    gates = {'four_weights': max_influences <= 4, 'normalized': normalization_error < 1e-4,
             'matching_duration': abs((runtime_end-runtime_start)-(end-start)) < .01,
             'all_source_vertices_mapped': len(set(index.tolist())) == len(rest),
             'head_rigid_all_frames': all(r['head_edge_min']>.99 and r['head_edge_max']<1.01 for r in records),
             'runtime_error_below_005H': max(r['max_position_error_H'] for r in records) < .005,
             'loop_endpoint_below_001H': loop_error < .001}
    report = {'status': 'pass_runtime_checks' if all(gates.values()) else 'fail', 'gates': gates,
              'frames': len(records), 'fps': fps, 'runtime_frame_range': [runtime_start,runtime_end],
              'max_influences': max_influences, 'normalization_error': normalization_error,
              'loop_endpoint_error_H': loop_error,
              'rest_mapping_error': rest_error, 'samples': records,
              'limitations': 'Numerical skin/export validation, not collision or human appearance approval.'}
    (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='samples'},indent=2))
    if not all(gates.values()):
        raise ValueError('Runtime validation failed')


if __name__ == '__main__':
    main()
