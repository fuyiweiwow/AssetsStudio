"""Portable input-only checkpoint; never packages rejected model candidates."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT/'milestones/actor_regen_input_research_20260909'
SCRIPTS = ['run_regen_fixed_crop.py','prepare_regen_foot_ab.py','audit_regen_conditioning_ab.py',
    'audit_actor_regen_review.py','compare_regen_foot_ab.py','review_actor_regen_blender.py',
    'test_regen_foot_ab.py','test_actor_regen_review.py','regen_research_checkpoint.py',
    'actor_core_offline.py','repair_actor_foot_local.py','run_hunyuan3d_mv_shape.py','hunyuan_environment.py',
    'render_actor_foot_review_blender.py']


def digest(path):
    data = path.read_bytes()
    if path.suffix in ('.py','.json','.md'):
        data = data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()


def seal():
    paths = [p for p in BUNDLE.rglob('*') if p.is_file() and p.name != 'manifest.json']
    paths += [ROOT/'tools/model_test'/s for s in SCRIPTS]
    if any(p.suffix.lower() in ('.glb','.fbx','.blend','.pt','.safetensors') for p in paths):
        raise ValueError('Input-only bundle cannot contain model candidates or weights')
    report = {'version':'1.0.0','status':'validated_input_method_not_actor_approval',
        'files':[{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p)} for p in sorted(paths)],
        'hash_policy':'LF normalized py/json/md; all others binary','allow_calibration':False}
    (BUNDLE/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


def verify():
    data = json.loads((BUNDLE/'manifest.json').read_text(encoding='utf-8'))
    for entry in data['files']:
        path = (ROOT/entry['path']).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or digest(path) != entry['sha256']:
            raise ValueError('Checkpoint mismatch: '+entry['path'])
    print('INPUT_RESEARCH_CHECKPOINT_VERIFIED',len(data['files']))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['seal','verify','prepare'])
    ap.add_argument('--output',type=Path)
    args = ap.parse_args()
    if args.action == 'seal':
        seal()
    verify()
    if args.action == 'prepare':
        if args.output is None or args.output.exists():
            raise ValueError('New --output required')
        subprocess.run([sys.executable,str(ROOT/'tools/model_test/prepare_regen_foot_ab.py'),
            '--baseline',str(BUNDLE/'baseline'),'--output',str(args.output)],check=True,cwd=ROOT)
        for role in ('front','right','back','left'):
            if digest(args.output/'input_replay/inputs'/f'{role}.png') != digest(BUNDLE/'cleaned_inputs'/f'{role}.png'):
                raise ValueError('Cleaned input replay mismatch: '+role)
        shutil.copy2(BUNDLE/'fixed_crop_contract.json',args.output/'preflight.json')
        print('INPUT_RESEARCH_REPLAY_PASS all four cleaned RGBA hashes match')


if __name__ == '__main__':
    main()
