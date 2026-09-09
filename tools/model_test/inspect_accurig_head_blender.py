"""Read-only AccuRIG head weight and deformation diagnostics (background Blender)."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector, Quaternion
from mathutils.kdtree import KDTree


def evaluated_points(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return points


def nearest_error(a, b):
    tree = KDTree(len(b))
    for i, p in enumerate(b):
        tree.insert(p, i)
    tree.balance()
    return max(tree.find(p)[2] for p in a)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--reference', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output.mkdir(parents=True, exist_ok=False)
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.input, args.reference]}
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(args.reference.resolve()), use_anim=False)
    reference = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
    ref_points = [reference.matrix_world @ v.co for v in reference.data.vertices]
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(args.input.resolve()), use_anim=True)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    if len(meshes) != 1 or len(rigs) != 1:
        raise ValueError(f'Expected one mesh and armature: {len(meshes)}, {len(rigs)}')
    obj, rig = meshes[0], rigs[0]
    actions = [{'name': a.name, 'frame_range': list(a.frame_range)} for a in bpy.data.actions]
    rig.animation_data_clear()
    obj.animation_data_clear()
    rig.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    rest = evaluated_points(obj)
    lo = Vector([min(p[i] for p in rest) for i in range(3)])
    hi = Vector([max(p[i] for p in rest) for i in range(3)])
    height = hi.z-lo.z
    indices = [i for i,p in enumerate(rest) if p.z > lo.z+height*.80]
    groups = {g.index:g.name for g in obj.vertex_groups}
    totals = defaultdict(float)
    low_head = []
    sums = []
    dominant_counts = defaultdict(int)
    for i in indices:
        weights = [(groups[g.group],g.weight) for g in obj.data.vertices[i].groups if g.weight > 1e-8]
        total = sum(w for _,w in weights)
        sums.append(total)
        for name,w in weights:
            totals[name] += w
        hw = sum(w for n,w in weights if 'head' in n.lower())
        if hw < .95:
            low_head.append({'vertex':i,'position':list(rest[i]),'head_weight':hw,'weights':dict(weights)})
        if weights:
            dominant_counts[max(weights,key=lambda x:x[1])[0]]+=1
    bones = [{'name': b.name, 'parent': b.parent.name if b.parent else None,
              'head_world': list(rig.matrix_world @ b.head_local),
              'tail_world': list(rig.matrix_world @ b.tail_local), 'deform': b.use_deform} for b in rig.data.bones]
    index_set = set(indices)
    edges = [(e.vertices[0],e.vertices[1]) for e in obj.data.edges
             if e.vertices[0] in index_set and e.vertices[1] in index_set]
    lengths = [(rest[a]-rest[b]).length for a,b in edges]
    def metrics(points):
        ratios = sorted((points[a]-points[b]).length/length for (a,b),length in zip(edges,lengths) if length>1e-10)
        return {'edge_ratio_min':ratios[0], 'edge_ratio_p01':ratios[int(.01*(len(ratios)-1))],
                'edge_ratio_max':ratios[-1], 'edges_compressed_over_10pct':sum(r<.9 for r in ratios),
                'edges_stretched_over_10pct':sum(r>1.1 for r in ratios)}
    scene=bpy.context.scene
    scene.render.engine='BLENDER_WORKBENCH'
    scene.render.resolution_x=scene.render.resolution_y=768
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    shading=scene.display.shading
    shading.light='STUDIO'
    shading.color_type='SINGLE'
    shading.single_color=(.55,.55,.55)
    shading.show_shadows=False
    shading.show_cavity=False
    shading.background_type='WORLD'
    scene.world.color=(.08,.08,.08)
    for p in obj.data.polygons:
        p.use_smooth=True
    rig.hide_render=True
    cd=bpy.data.cameras.new('HeadDiagnosticCamera')
    cd.type='ORTHO'
    cd.ortho_scale=height*.80
    cam=bpy.data.objects.new('HeadDiagnosticCamera',cd)
    scene.collection.objects.link(cam)
    scene.camera=cam
    def render(label, points):
        aim=sum((points[i] for i in indices),Vector())/len(indices)
        aim.z-=height*.09
        for name,direction in {'front':(0,-1,.15),'right':(1,0,.15),'back':(0,1,.15),'left':(-1,0,.15),'top':(0,0,1)}.items():
            cam.location=aim+Vector(direction).normalized()*height*3
            cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler()
            bpy.context.view_layer.update()
            scene.render.filepath=str((args.output/f'{label}_{name}.png').resolve())
            bpy.ops.render.render(write_still=True)
    render('rest',rest)
    rig.data.pose_position='POSE'
    def reset():
        for b in rig.pose.bones:
            b.matrix_basis.identity()
            b.rotation_mode='QUATERNION'
        bpy.context.view_layer.update()
    reset()
    neutral=evaluated_points(obj)
    probes=[]
    candidates=[b.name for b in rig.pose.bones if b.name.lower().endswith(('head','necktwist01','necktwist02','spine02','spine01'))]
    worst=None
    for name in candidates:
        for axis in range(3):
            for degrees in [-30,30]:
                reset()
                vector=Vector((0,0,0)); vector[axis]=1
                rig.pose.bones[name].rotation_quaternion=Quaternion(vector,math.radians(degrees))
                bpy.context.view_layer.update()
                points=evaluated_points(obj)
                result={'bone':name,'local_axis':axis,'degrees':degrees,**metrics(points)}
                probes.append(result)
                if worst is None or result['edge_ratio_min']<worst['edge_ratio_min']:
                    worst=result
    if worst:
        reset()
        vector=Vector((0,0,0));vector[worst['local_axis']]=1
        rig.pose.bones[worst['bone']].rotation_quaternion=Quaternion(vector,math.radians(worst['degrees']))
        bpy.context.view_layer.update()
        render('worst_probe',evaluated_points(obj))
    # Causal ablation only, in memory: rigid upper-head assignment under the
    # exact same pose. No repaired mesh/FBX is saved; the neck transition is
    # intentionally outside the scope of this diagnostic.
    control = None
    if worst and obj.vertex_groups.get('CC_Base_Head'):
        region = [i for i,p in enumerate(rest) if p.z > lo.z+height*.60]
        assignments = {i:[(g.group,g.weight) for g in obj.data.vertices[i].groups] for i in region}
        for group in obj.vertex_groups:
            group.remove(region)
        obj.vertex_groups['CC_Base_Head'].add(region,1.0,'REPLACE')
        bpy.context.view_layer.update()
        controlled = evaluated_points(obj)
        control = {'method':'In-memory z>0.60H assigned to Head at weight 1; same worst pose; no asset export',
                   'changed_weight_vertices':len(region), **metrics(controlled)}
        render('weight_control',controlled)
        for group in obj.vertex_groups:
            group.remove(region)
        for i,weights in assignments.items():
            for group,weight in weights:
                obj.vertex_groups[group].add([i],weight,'REPLACE')
        bpy.context.view_layer.update()
    unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    report={'input_hashes':hashes,'sources_unchanged':unchanged,'mesh':{'vertices':len(rest),'faces':len(obj.data.polygons)},
      'reference_bidirectional_max_distance':max(nearest_error(rest,ref_points),nearest_error(ref_points,rest)),
      'height':height,'actions':actions,'bones':bones,'cranium_region':'world z > min_z + 0.80H (upper skull only)',
      'cranium_vertices':len(indices),'cranium_edges':len(edges),'weight_sum_range':[min(sums),max(sums)],
      'mean_bone_weights':{n:w/len(indices) for n,w in sorted(totals.items(),key=lambda x:-x[1])},
      'dominant_bone_counts':dict(dominant_counts),'head_weight_below_095_count':len(low_head),
      'head_weight_below_095_vertices':low_head,
      'neutral_pose_max_displacement':max((a-b).length for a,b in zip(rest,neutral)),
      'neutral_metrics':metrics(neutral),'synthetic_probes':probes,'worst_probe':worst,'weight_control':control,
      'limitations':'Synthetic local single-bone rotations are diagnostics, not the original AccuRIG preview or animation approval.'}
    (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert unchanged
    print(json.dumps({k:v for k,v in report.items() if k not in ['bones','head_weight_below_095_vertices','synthetic_probes']},indent=2))


if __name__=='__main__':
    main()
