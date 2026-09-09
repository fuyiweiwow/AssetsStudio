"""Repair the diagnosed Actor's head weights with a connected head and harmonic neck patch.

Frozen source only. Changes weights, never vertex coordinates or the skeleton.
Creates an isolated candidate and compares deformation before/after and after FBX import.
"""
import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspect_accurig_head_blender import evaluated_points

SOURCE_HASH = '58435dada868a5e7f0c67ae178dd5f7118979b70a033171d149962ae8eeee825'


def weights(obj):
    names = {g.index:g.name for g in obj.vertex_groups}
    return [{names[g.group]:float(g.weight) for g in v.groups if g.weight > 0} for v in obj.data.vertices]


def pose(rig, spec):
    rig.animation_data_clear()
    rig.data.pose_position='POSE'
    for b in rig.pose.bones:
        b.matrix_basis.identity()
        b.rotation_mode='QUATERNION'
    for name,axis,angle in spec:
        v=Vector((0,0,0));v[axis]=1
        rig.pose.bones[name].rotation_quaternion=Quaternion(v,math.radians(angle))
    bpy.context.view_layer.update()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    if hashlib.sha256(args.input.read_bytes()).hexdigest()!=SOURCE_HASH:
        raise ValueError('This repair is calibrated only for the diagnosed 1.fbx')
    args.output.mkdir(parents=True,exist_ok=False)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(args.input.resolve()),use_anim=False)
    obj=[o for o in bpy.context.scene.objects if o.type=='MESH'][0]
    rig=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'][0]
    pose(rig,[])
    rest=evaluated_points(obj)
    original_weights=weights(obj)
    coordinates=[list(v.co) for v in obj.data.vertices]
    skeleton={b.name:list(sum((list(row) for row in b.matrix_local),[])) for b in rig.data.bones}
    height=max(p.z for p in rest)-min(p.z for p in rest)
    neck=rig.matrix_world@rig.data.bones['CC_Base_NeckTwist01'].head_local
    cut=neck.z-height*.006
    adj=[[] for _ in rest]
    edges=np.asarray([list(e.vertices) for e in obj.data.edges],dtype=np.int32)
    for a,b in edges:
        a,b=int(a),int(b)
        d=(rest[a]-rest[b]).length
        adj[a].append((b,d));adj[b].append((a,d))
    # Keep only the top-connected component above the neck landmark plane.
    # Arms also above that plane remain separate and retain original weights.
    allowed={i for i,p in enumerate(rest) if p.z>cut}
    seed=max(allowed,key=lambda i:rest[i].z)
    head={seed};stack=[seed]
    while stack:
        i=stack.pop()
        for j,_ in adj[i]:
            if j in allowed and j not in head:
                head.add(j);stack.append(j)
    boundary={i for i in head if any(j not in head for j,_ in adj[i])}
    # Physical surface distances avoid a horizontal seam across the jaw.
    width=height*.10
    distances={i:0. for i in boundary}
    queue=[(0.,i) for i in boundary];heapq.heapify(queue)
    while queue:
        d,i=heapq.heappop(queue)
        if d!=distances[i]:continue
        for j,length in adj[i]:
            nd=d+length
            if j not in head and nd<width and nd<distances.get(j,float('inf')):
                distances[j]=nd;heapq.heappush(queue,(nd,j))
    alpha={i:1. for i in head}
    for i,d in distances.items():
        if i not in head:
            t=d/width
            alpha[i]=1-(3*t*t-2*t*t*t)
    transition=set(alpha)-head
    protected=set(range(len(rest)))-set(alpha)
    rest_np=np.asarray(rest,dtype=np.float64)
    length0=np.linalg.norm(rest_np[edges[:,0]]-rest_np[edges[:,1]],axis=1)
    selections={
        'head':np.asarray([a in head and b in head for a,b in edges]),
        'neck_transition':np.asarray([a in transition or b in transition for a,b in edges]),
        'protected':np.asarray([a in protected and b in protected for a,b in edges]),
    }
    specs={}
    for bone in ['CC_Base_Head','CC_Base_NeckTwist01','CC_Base_NeckTwist02','CC_Base_Spine01','CC_Base_Spine02']:
        for axis in range(3):
            for angle in [-30,30]:specs[f'{bone}_{axis}_{angle}']=[(bone,axis,angle)]
    specs['combined']=[('CC_Base_Head',1,30),('CC_Base_NeckTwist01',0,-15),('CC_Base_Spine02',2,15)]
    specs['combined_reverse']=[('CC_Base_Head',1,-30),('CC_Base_NeckTwist01',0,15),('CC_Base_Spine02',2,-15)]
    original_pose_points={}
    def metrics(points):
        p=np.asarray(points)
        ratios=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1)/np.maximum(length0,1e-12)
        return {name:{'min':float(np.min(ratios[mask])), 'p01':float(np.quantile(ratios[mask],.01)),
                      'p99':float(np.quantile(ratios[mask],.99)), 'max':float(np.max(ratios[mask])),
                      'outside_10pct':int(np.count_nonzero((ratios[mask]<.9)|(ratios[mask]>1.1)))}
                for name,mask in selections.items()}
    before={}
    for label,spec in specs.items():
        pose(rig,spec);p=evaluated_points(obj)
        original_pose_points[label]=np.asarray(p)
        before[label]=metrics(p)
    pose(rig,[])
    # Harmonic weights on the neck patch, fixed to rigid Head at its top and
    # the exact original weights along its body boundary. Positive edge
    # coefficients preserve nonnegative, partition-of-unity weights.
    transition_list=sorted(transition)
    ti={v:i for i,v in enumerate(transition_list)}
    names=[g.name for g in obj.vertex_groups]
    ni={name:i for i,name in enumerate(names)}
    matrix=np.zeros((len(ti),len(ti)))
    rhs=np.zeros((len(ti),len(names)))
    for v,row in ti.items():
        for j,length in adj[v]:
            w=1/max(length,1e-8)
            matrix[row,row]+=w
            if j in ti:matrix[row,ti[j]]-=w
            elif j in head:rhs[row,ni['CC_Base_Head']]+=w
            else:
                for name,value in original_weights[j].items():rhs[row,ni[name]]+=w*value
    solution=np.linalg.solve(matrix,rhs)
    residual=float(np.max(np.abs(matrix@solution-rhs)))
    discarded_mass_max=0.
    for i in alpha:
        new={'CC_Base_Head':1.} if i in head else {name:max(0.,float(solution[ti[i],ni[name]])) for name in names}
        retained=sorted(new.items(),key=lambda item:-item[1])
        discarded_mass_max=max(discarded_mass_max,sum(w for _,w in retained[8:]))
        new=dict(retained[:8])
        total=sum(new.values())
        for group in [g.group for g in obj.data.vertices[i].groups]:obj.vertex_groups[group].remove([i])
        for name,w in new.items():
            if w>0:obj.vertex_groups[name].add([i],w/total,'REPLACE')
    after_weights=weights(obj)
    max_influences=max(len(w) for w in after_weights)
    normalization_error=max(abs(sum(w.values())-1) for w in after_weights)
    protected_weights_equal=all(original_weights[i]==after_weights[i] for i in protected)
    scene=bpy.context.scene
    scene.render.engine='BLENDER_WORKBENCH'
    scene.render.resolution_x=scene.render.resolution_y=768
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    shading=scene.display.shading
    shading.light='STUDIO';shading.color_type='SINGLE';shading.single_color=(.55,.55,.55)
    shading.show_shadows=False;shading.show_cavity=False;shading.background_type='WORLD'
    scene.world.color=(.08,.08,.08)
    for poly in obj.data.polygons:poly.use_smooth=True
    cd=bpy.data.cameras.new('RepairReview');cd.type='ORTHO';cd.ortho_scale=height*.78
    cam=bpy.data.objects.new('RepairReview',cd);scene.collection.objects.link(cam);scene.camera=cam
    review=args.output/'review';review.mkdir()
    def render(label,p):
        hp=[p[i] for i in head]
        aim=Vector([(min(q[a] for q in hp)+max(q[a] for q in hp))/2 for a in range(3)])
        for name,xyz in {'front':(0,-1,0),'right':(1,0,0),'back':(0,1,0),'left':(-1,0,0),'under':(1,-1,-.7)}.items():
            cam.location=aim+Vector(xyz).normalized()*height*3
            cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler()
            bpy.context.view_layer.update()
            scene.render.filepath=str((review/f'{label}_{name}.png').resolve())
            bpy.ops.render.render(write_still=True)
    after={};posed_errors=[];repaired_pose_points={}
    protected_indices=sorted(protected)
    for label,spec in specs.items():
        pose(rig,spec);p=evaluated_points(obj);after[label]=metrics(p)
        repaired_pose_points[label]=np.asarray(p)
        posed_errors.append(float(np.max(np.linalg.norm(np.asarray(p)[protected_indices]-original_pose_points[label][protected_indices],axis=1))))
        if label in ['CC_Base_Head_0_-30','CC_Base_NeckTwist01_1_30','combined','combined_reverse']:
            render(label,p)
    pose(rig,[]);render('rest',evaluated_points(obj))
    geometry_equal=coordinates==[list(v.co) for v in obj.data.vertices]
    skeleton_equal=skeleton=={b.name:list(sum((list(row) for row in b.matrix_local),[])) for b in rig.data.bones}
    bpy.data.objects.remove(cam,do_unlink=True)
    pose(rig,[])
    bpy.ops.wm.save_as_mainfile(filepath=str((args.output/'Actor_HeadWeights_Repaired.blend').resolve()))
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True)
    bpy.context.view_layer.objects.active=rig
    fbx=args.output/'Actor_HeadWeights_Repaired.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx.resolve()),use_selection=True,object_types={'MESH','ARMATURE'},
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Z',axis_up='Y',
        use_mesh_modifiers=False,add_leaf_bones=False,bake_anim=False)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(fbx.resolve()),use_anim=False)
    obj=[o for o in bpy.context.scene.objects if o.type=='MESH'][0]
    rig=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'][0]
    pose(rig,[])
    imported_rest=evaluated_points(obj)
    if len(imported_rest)!=len(rest):raise ValueError('FBX vertex count changed')
    # This FBX exporter/importer preserves index order; verify positions before
    # using it for weight and pose correspondence.
    rest_error=float(np.max(np.linalg.norm(np.asarray(imported_rest)-rest_np,axis=1)))
    if rest_error>height*1e-5:raise ValueError('FBX rest correspondence failed')
    imported_weights=weights(obj)
    weight_error=max(abs(w.get(n,0)-v.get(n,0)) for w,v in zip(after_weights,imported_weights) for n in set(w)|set(v))
    roundtrip={};roundtrip_error=0.
    for label,spec in specs.items():
        pose(rig,spec);p=evaluated_points(obj);roundtrip[label]=metrics(p)
        roundtrip_error=max(roundtrip_error,float(np.max(np.linalg.norm(np.asarray(p)-repaired_pose_points[label],axis=1))))
    gates={'source_unchanged':hashlib.sha256(args.input.read_bytes()).hexdigest()==SOURCE_HASH,
           'geometry_unchanged':geometry_equal,'skeleton_unchanged':skeleton_equal,
           'protected_weights_unchanged':protected_weights_equal,'protected_pose_unchanged':max(posed_errors)<height*1e-6,
           'whole_head_rigid_all_probes':all(v['head']['outside_10pct']==0 for v in after.values()),
           'fbx_whole_head_rigid_all_probes':all(v['head']['outside_10pct']==0 for v in roundtrip.values()),
           'fbx_rest_error':rest_error<height*1e-5,'fbx_pose_error':roundtrip_error<height*1e-5,
           'fbx_weight_error':weight_error<1e-5}
    gates.update({'max_eight_influences':max_influences<=8,
                  'weights_normalized':normalization_error<1e-4,
                  'pruned_mass_below_1pct':discarded_mass_max<.01})
    report={'status':'pass_local_repair_checks' if all(gates.values()) else 'fail', 'source_sha256':SOURCE_HASH,
            'output_sha256':hashlib.sha256(fbx.read_bytes()).hexdigest(),'height':height,
            'method':'Connected head above NeckTwist01.z - .006H; harmonic weights over geodesic .10H neck patch with fixed original body boundary',
            'harmonic_residual':residual,
            'max_influences':max_influences,'normalization_max_error':normalization_error,
            'top8_discarded_mass_max':discarded_mass_max,
            'cut_z':cut,'head_vertices':len(head),'transition_vertices':len(transition),'protected_vertices':len(protected),
            'boundary_bounds':[[min(rest[i][a] for i in boundary),max(rest[i][a] for i in boundary)] for a in range(3)],
            'protected_pose_max_error':max(posed_errors),'fbx_rest_max_error':rest_error,
            'fbx_pose_max_error':roundtrip_error,'fbx_weight_max_error':weight_error,
            'gates':gates,'before':before,'after':after,'roundtrip':roundtrip,
            'limitations':'Local synthetic poses; neck transition requires visual review. Not full motion or collision certification.'}
    (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['before','after','roundtrip']},indent=2))
    if not all(gates.values()):raise ValueError('Repair validation failed')


if __name__=='__main__':main()
