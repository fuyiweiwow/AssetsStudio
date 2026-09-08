"""Experimental waist-only slot measured from a Y-up, separated-leg T-pose.

No bone mapping or old Actor slot coordinates are transferred. Requires review.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh
from actor_core_offline import audit_mesh, sha256


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--actor',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--actor-id',required=True)
    args=p.parse_args()
    if args.output.exists():
        raise ValueError('Do not overwrite slot evidence')
    mesh=trimesh.load(args.actor,force='mesh',process=False)
    if audit_mesh(mesh)['status']!='pass':
        raise ValueError('Actor structural gate failed')
    lo,hi=mesh.bounds
    height=hi[1]-lo[1]
    center=(lo+hi)/2
    rows=[]
    for fraction in np.linspace(.12,.65,107):
        section=mesh.section(plane_origin=[0,lo[1]+fraction*height,0],plane_normal=[0,1,0])
        loops=[] if section is None else [x for x in section.discrete if np.ptp(x[:,0])>.025*height]
        if loops:
            points=np.concatenate(loops)
            rows.append(dict(height=float(fraction),loops=len(loops),width=float(np.ptp(points[:,0])/height)))
    arm=max(rows,key=lambda row:row['width'])
    crotch_candidates=[row for row in rows if row['height']<arm['height']-.06 and row['loops']==2]
    if not crotch_candidates:
        raise ValueError('Cannot identify legs below the arm span')
    crotch=max(crotch_candidates,key=lambda row:row['height'])
    torso_span=arm['height']-crotch['height']
    if not .08<torso_span<.35:
        raise ValueError('Ambiguous torso span; manual landmark review needed')
    waist=crotch['height']+.45*torso_span
    half_band=min(.025,.12*torso_span)
    band=mesh.vertices[np.abs((mesh.vertices[:,1]-lo[1])/height-waist)<half_band]
    xlo,xhi=(band[:,0].min()-center[0])/height,(band[:,0].max()-center[0])/height
    # Blender imports glTF Y-up as Z-up, with depth -Z.
    dlo,dhi=-(band[:,2].max()-center[2])/height,-(band[:,2].min()-center[2])/height
    padding=.03
    profile={'schema':'assetsstudio_actor_slot_profile_v2','id':args.actor_id+'_waist_measured_v1',
             'actor_asset_id':args.actor_id,'status':'experimental_manual_review_required',
             'actor_model':{'path':str(args.actor.resolve()),'sha256':sha256(args.actor)},
             'coordinate_contract':{'rig_state':'unbound_tpose','frame':'actor_normalized_rest'},
             'measurement':{'method':'lower-body two-loop transition and maximum arm span; waist at 45 percent of torso interval',
                            'crotch_h':crotch['height'],'arm_h':arm['height'],'waist_h':waist,'slices':rows},
             'slots':[{'slot_id':'waist_accessory','status':'static_tpose_only',
                        'attachment':{'mode':'rest_surface','rig_dependency':'none_until_rig_intake',
                                      'anchors':[{'id':'Waist','position_h':[0,0,waist],'future_parent_bone':'Hips'}]},
                        'fit_envelope':{'frame':'actor_normalized_rest','kind':'surface','clearance_h':.006,
                                        'bounds_h':{'min':[xlo-padding,dlo-padding,waist-.045],
                                                    'max':[xhi+padding,dhi+padding,waist+.045]}}}]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(profile,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:profile['measurement'][k] for k in ['crotch_h','arm_h','waist_h']}))


if __name__=='__main__':
    main()
