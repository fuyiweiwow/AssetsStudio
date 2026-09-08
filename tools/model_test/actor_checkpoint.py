"""Portable frozen artifact inventory and no-model static replay checkpoint."""
import argparse
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'milestones/actor_offline_20260908/checkpoint.json'
BASE='workspace/local_generation/actor_offline_gate_20260908'
ACCESSORY='workspace/accessory_fit/chibi3_v9b/waist_accessory'
CODE=['actor_checkpoint.py','actor_core_offline.py','test_actor_core_offline.py',
      'prepare_actor93_shape_probe.py','run_hunyuan3d_mv_shape.py','hunyuan_environment.py',
      'blender_environment.py','split_hunyuan_checkpoint.py','prepare_actor_core_rig_mesh.py',
      'validate_hunyuan_mv_blender.py','render_actor93_shadowless.py',
      'compare_hunyuan_source_silhouettes.py','review_mesh_stage.py','review_offline_actor_inputs.py',
      'measure_unbound_waist.py','fit_tpose_accessory_blender.py','waist_contact_fit.py',
      'test_waist_contact_blender.py','audit_accessory_export.py']


def digest(path):
    data=path.read_bytes()
    mode='raw'
    if path.suffix in {'.py','.json','.md','.ps1','.txt'}:
        data=data.replace(b'\r\n',b'\n')
        mode='lf_normalized'
    return hashlib.sha256(data).hexdigest(),mode


def inventory():
    tracked=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
    prefixes=[BASE+'/'+name+'/' for name in ['inputs_v2','run_v2','static_50k_v2','waist_contact_v5']]
    explicit={f'tools/model_test/{name}' for name in CODE}
    explicit.update(['requirements-actor-static.txt','docs/ACTOR_HOME_CHECKPOINT_20260908.md'])
    explicit.update([ACCESSORY+'/hunyuan/waist_accessory_seed20260831_accessory.glb',
                     ACCESSORY+'/hunyuan/shape_manifest_accessory.json',ACCESSORY+'/source_preparation.json',
                     'workspace/local_generation/actor_core_tpose_shoulder_gate_20260907/tpose93_shoulders_seed1002_blankface_v1.png',
                     'workspace/local_generation/actor_core_multiview_gate_20260907/right_b_seed1005_refined.png',
                     'workspace/local_generation/actor_core_multiview_gate_20260907/back_b_seed1008_refined_v2.png'])
    paths=sorted(set(p for p in tracked if any(p.startswith(prefix) for prefix in prefixes))|explicit)
    return [{'path':p,'sha256':digest(ROOT/p)[0],'hash_mode':digest(ROOT/p)[1]} for p in paths]


def verify():
    data=json.loads(MANIFEST.read_text(encoding='utf-8'))
    for entry in data['files']:
        path=(ROOT/entry['path']).resolve()
        if ROOT not in path.parents or not path.is_file():
            raise ValueError('Missing/invalid checkpoint path: '+entry['path'])
        actual,mode=digest(path)
        if actual!=entry['sha256'] or mode!=entry['hash_mode']:
            raise ValueError('Checkpoint differs: '+entry['path'])
    print('CHECKPOINT_VERIFIED files='+str(len(data['files'])),flush=True)
    return data


def run(command):
    subprocess.run([str(x) for x in command],cwd=ROOT,check=True)


def replay(output,blender):
    verify()
    for name in ['numpy','PIL','cv2','trimesh','scipy','networkx']:
        importlib.import_module(name)
    from blender_environment import discover_blender
    blender=discover_blender(blender)
    output=output.resolve()
    if output.exists():
        raise ValueError('Replay output must be a new directory')
    output.mkdir(parents=True)
    body=ROOT/BASE/'static_50k_v2/actor_offline_v2_50k_rig_mesh.glb'
    original=ROOT/ACCESSORY/'hunyuan/waist_accessory_seed20260831_accessory.glb'
    tool=ROOT/'tools/model_test'
    run([sys.executable,tool/'actor_core_offline.py','audit','--mesh',body,'--report',output/'body_audit.json'])
    run([blender,'--background','--factory-startup','--python-exit-code','1','--python',tool/'test_waist_contact_blender.py'])
    run([blender,'--background','--factory-startup','--python-exit-code','1','--python',tool/'fit_tpose_accessory_blender.py','--',
         '--actor',body,'--accessory',original,'--profile',ROOT/BASE/'static_50k_v2/waist_profile.json',
         '--slot-id','waist_accessory','--source-preparation',ROOT/ACCESSORY/'source_preparation.json',
         '--shape-manifest',ROOT/ACCESSORY/'hunyuan/shape_manifest_accessory.json',
         '--output-dir',output/'fit','--asset-id','actor_offline_v2_waist_contact','--radial-contact-fit',
         '--width-factor','.85','--depth-factor','.85','--resolution','768'])
    report=json.loads((output/'fit/fit_report.json').read_text(encoding='utf-8'))
    if report['status']!='pass_static_tpose':
        raise ValueError('Static fit report failed')
    run([sys.executable,tool/'audit_accessory_export.py','--source',original,
         '--candidate',output/'fit/actor_offline_v2_waist_contact.glb','--report',output/'export_audit.json'])
    print('STATIC_REPLAY_PASS preview='+str(output/'fit/preview/front.png'),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['build','verify','replay'])
    p.add_argument('--output',type=Path)
    p.add_argument('--blender',type=Path)
    args=p.parse_args()
    if args.action=='build':
        data={'schema':'assetsstudio_actor_offline_checkpoint_v1','date':'2026-09-08',
              'status':'static_candidate_human_review_required','model_download_required_for_static_replay':False,
              'files':inventory()}
        MANIFEST.parent.mkdir(parents=True,exist_ok=True)
        MANIFEST.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
        verify()
    elif args.action=='verify':
        verify()
    else:
        if args.output is None:
            p.error('replay requires --output pointing to a new directory')
        replay(args.output,args.blender)


if __name__=='__main__':
    main()
