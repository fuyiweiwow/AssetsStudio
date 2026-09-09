"""Fit at most four existing influences to the full sampled action; keep source untouched.

The result is action-specific and must be validated on additional motions before
being treated as general-purpose skin weights.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspect_accurig_head_blender import evaluated_points


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output.mkdir(parents=True,exist_ok=False)
    digest=hashlib.sha256(args.input.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))
    obj=[o for o in bpy.context.scene.objects if o.type=='MESH'][0]
    rig=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'][0]
    scene=bpy.context.scene
    rig.data.pose_position='REST';bpy.context.view_layer.update()
    rest=np.asarray(evaluated_points(obj),dtype=np.float64)
    height=float(np.ptp(rest[:,2]))
    groups={g.index:g.name for g in obj.vertex_groups}
    assignments=[[(g.group,g.weight) for g in v.groups if g.weight>1e-8] for v in obj.data.vertices]
    used=sorted(set(g for row in assignments for g,_ in row))
    transforms=[];expected=[]
    rig.data.pose_position='POSE'
    for frame in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        expected.append(np.asarray(evaluated_points(obj)))
        transforms.append([np.asarray(rig.matrix_world @ rig.pose.bones[groups[g]].matrix
                            @ rig.data.bones[groups[g]].matrix_local.inverted()
                            @ rig.matrix_world.inverted()) for g in used])
    transforms=np.asarray(transforms);expected=np.asarray(expected)
    gi={g:i for i,g in enumerate(used)}
    fit_error=0.;reconstruction_error=0.;changed=0
    source_coordinates=[list(v.co) for v in obj.data.vertices]
    for i,row in enumerate(assignments):
        if len(row)<=4:continue
        ids=[g for g,_ in row]
        original=np.asarray([w for _,w in row]);original/=original.sum()
        position=np.append(rest[i],1)
        contributions=np.einsum('fgab,b->fga',transforms[:,[gi[g] for g in ids]],position)[:,:,:3]
        reconstructed=np.einsum('fgc,g->fc',contributions,original)
        reconstruction_error=max(reconstruction_error,float(np.max(np.linalg.norm(reconstructed-expected[:,i],axis=1)))/height)
        # Fit relative offsets; translation cancels under the sum-to-one constraint.
        target=(expected[:,i]/height).reshape(-1)
        points=(contributions/height).transpose(0,2,1).reshape(-1,len(ids))
        top=np.argsort(-original)[:4]
        best_ids=top;best_weights=original[top]/original[top].sum()
        best_error=float(np.sum((points[:,top]@best_weights-target)**2))
        for count in range(1,5):
            for support in itertools.combinations(range(len(ids)),count):
                values=points[:,support]
                if count==1:fit=np.ones(1)
                else:
                    delta=values[:,:-1]-values[:,-1:]
                    y=target-values[:,-1]
                    fit3=np.linalg.lstsq(delta,y,rcond=1e-8)[0]
                    fit=np.append(fit3,1-fit3.sum())
                if fit.min() < -1e-7:continue
                fit=np.maximum(fit,0);fit/=fit.sum()
                error=float(np.sum((values@fit-target)**2))
                if error<best_error:
                    best_error=error;best_ids=support;best_weights=fit
        fit_error=max(fit_error,float(np.max(np.linalg.norm((points[:,best_ids]@best_weights-target).reshape(-1,3),axis=1))))
        for g,_ in row:obj.vertex_groups[g].remove([i])
        for j,w in zip(best_ids,best_weights):
            if w>1e-8:obj.vertex_groups[ids[j]].add([i],float(w),'REPLACE')
        changed+=1
    actual_errors=[]
    for offset,frame in enumerate(range(scene.frame_start,scene.frame_end+1)):
        scene.frame_set(frame);bpy.context.view_layer.update()
        actual=np.asarray(evaluated_points(obj))
        actual_errors.append(float(np.max(np.linalg.norm(actual-expected[offset],axis=1)))/height)
    report={'source_unchanged':hashlib.sha256(args.input.read_bytes()).hexdigest()==digest,
            'source_sha256':digest,'changed_vertices':changed,'frames':len(expected),
            'skin_formula_error_H':reconstruction_error,'fit_max_error_H':fit_error,
            'actual_max_error_H':max(actual_errors),'geometry_unchanged':source_coordinates==[list(v.co) for v in obj.data.vertices],
            'max_influences':max(sum(g.weight>1e-8 for g in v.groups) for v in obj.data.vertices),
            'scope':'71-frame walk-specific fit; additional motions require fresh validation'}
    gates={'source_unchanged':report['source_unchanged'],'geometry_unchanged':report['geometry_unchanged'],
           'skin_formula_matches':reconstruction_error<1e-5,'four_weights':report['max_influences']<=4,
           'max_error_below_005H':max(actual_errors)<.005}
    report['gates']=gates
    report['status']='pass_walk_specific_fit' if all(gates.values()) else 'fail'
    (args.output/'fit_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    if not all(gates.values()):raise ValueError('Four-weight fit failed')
    scene.frame_set(scene.frame_start)
    bpy.ops.wm.save_as_mainfile(filepath=str((args.output/'runtime4.blend').resolve()))
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.gltf(filepath=str((args.output/'runtime4.glb').resolve()),export_format='GLB',
        use_selection=True,export_skins=True,export_animations=True,export_materials='EXPORT')


if __name__=='__main__':main()
