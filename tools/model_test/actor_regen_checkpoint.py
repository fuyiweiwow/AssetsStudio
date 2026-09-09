"""Verify and replay the frozen shorter-arm Actor generation milestones."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
BUNDLE=ROOT/'milestones/actor_regen_20260909'


def digest(path, mode='binary'):
    data=path.read_bytes()
    if mode=='lf_normalized':data=data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()


def verify():
    manifest=json.loads((BUNDLE/'manifest.json').read_text(encoding='utf-8'))
    for record in manifest['files']:
        path=(ROOT/record['path']).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError('Missing/invalid checkpoint path: '+record['path'])
        if digest(path,record['hash_mode'])!=record['sha256']:
            raise ValueError('Hash mismatch: '+record['path'])
    print('REGEN_CHECKPOINT_VERIFIED files='+str(len(manifest['files'])),flush=True)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['verify','prepare','generate'])
    p.add_argument('--output',type=Path)
    p.add_argument('--cpu-offload',action='store_true')
    args=p.parse_args()
    verify()
    if args.action=='verify':return
    if args.output is None:p.error('--output required')
    output=args.output.resolve()
    if output.exists():raise ValueError('Use a new replay output directory')
    from prepare_actor_regen_inputs import prepare
    inputs=output/'inputs'
    result=prepare(BUNDLE/'source/front.png',BUNDLE/'source/right.png',BUNDLE/'source/back.png',inputs)
    expected=json.loads((BUNDLE/'inputs/input_manifest.json').read_text(encoding='utf-8'))
    for role in ['front','right','back','left']:
        if result['views'][role]['sha256']!=expected['views'][role]['sha256']:
            raise ValueError('Replayed RGBA differs: '+role)
    print('REGEN_INPUT_REPLAY_PASS all four RGBA hashes match',flush=True)
    if args.action=='generate':
        recipe=json.loads((BUNDLE/'recipe.json').read_text(encoding='utf-8'))
        cmd=[sys.executable,str(ROOT/'tools/model_test/actor_core_offline.py'),'generate',
             '--inputs',str(inputs),'--output',str(output/'shape'),
             '--seed',str(recipe['shape']['seed']),'--steps',str(recipe['shape']['steps'])]
        if args.cpu_offload:cmd.append('--cpu-offload')
        subprocess.run(cmd,cwd=ROOT,check=True)
        subprocess.run([sys.executable,str(ROOT/'tools/model_test/actor_core_offline.py'),'audit',
                        '--mesh',str(output/'shape/shape.glb'),'--report',str(output/'shape/audit.json')],cwd=ROOT,check=True)


if __name__=='__main__':main()
