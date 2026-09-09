"""Verify or replay the portable head repair without downloading AI models."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / 'milestones/actor_head_repair_20260909'


def verify():
    manifest = json.loads((BUNDLE / 'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        path = (BUNDLE / entry['path']).resolve()
        if not path.is_relative_to(BUNDLE) or not path.is_file():
            raise ValueError('Missing or invalid bundle path: ' + entry['path'])
        data = path.read_bytes()
        if entry.get('hash_mode') == 'lf_normalized':
            data = data.replace(b'\r\n', b'\n')
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Bundle hash mismatch: ' + entry['path'])
    print('HEAD_CHECKPOINT_VERIFIED files=' + str(len(manifest['files'])), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['verify', 'replay', 'walk'])
    ap.add_argument('--output', type=Path)
    ap.add_argument('--blender', type=Path)
    args = ap.parse_args()
    verify()
    if args.action in {'replay', 'walk'}:
        if args.output is None:
            ap.error('replay requires --output (a new directory)')
        from blender_environment import discover_blender
        subprocess.run([str(discover_blender(args.blender)), '-b', '--factory-startup', '-t', '4',
                        '--python-exit-code', '1', '--python',
                        str(ROOT / 'tools/model_test/repair_accurig_head_weights_blender.py'), '--',
                        '--input', str(BUNDLE / 'source_accurig.fbx'),
                        '--output', str(args.output.resolve())], cwd=ROOT, check=True)
        report = json.loads((args.output / 'report.json').read_text(encoding='utf-8'))
        if not all(report['gates'].values()) or len(report['after']) != 32:
            raise ValueError('Replay did not pass the expected head checks')
        print('HEAD_REPLAY_PASS', flush=True)
        if args.action == 'walk':
            blender = str(discover_blender(args.blender))
            output = args.output.resolve()
            def run(script, arguments):
                subprocess.run([blender, '-b', '--factory-startup', '-t', '4',
                                '--python-exit-code', '1', '--python',
                                str(ROOT / 'tools/model_test' / script), '--',
                                *map(str, arguments)], cwd=ROOT, check=True)
            run('retarget_mixamo_to_actor_core.py', [
                '--actor-blend', output/'Actor_HeadWeights_Repaired.blend',
                '--animation-fbx', BUNDLE/'walk_source.fbx', '--output-dir', output/'walk',
                '--actor-id', 'actor_offline_v2_headrepair', '--animation-asset-id', 'mixamo_standard_walk_v1'])
            run('optimize_actor_runtime_weights_blender.py', [
                '--input', output/'walk/retargeted.blend', '--output', output/'runtime4'])
            run('validate_actor_walk_runtime_blender.py', [
                '--blend', output/'walk/retargeted.blend', '--glb', output/'runtime4/runtime4.glb',
                '--output', output/'runtime_review'])
            print('WALK_RUNTIME_REPLAY_PASS (walk-specific; human review pending)', flush=True)


if __name__ == '__main__':
    main()
