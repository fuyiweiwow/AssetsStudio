"""Seal explicitly staged foot repair files, or verify the released inventory."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'milestones/actor_foot_repair_20260909/checkpoint.json'


def digest(path):
    data = path.read_bytes()
    if path.suffix in {'.py', '.md', '.json', '.txt'}:
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build', action='store_true', help='Publisher only: seal reviewed staged files; never reset approvals')
    args = ap.parse_args()
    if args.build:
        paths = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT, text=True).splitlines()
        paths.extend(['tools/model_test/actor_core_offline.py',
            'workspace/local_generation/actor_offline_gate_20260908/static_50k_v2/actor_offline_v2_50k_rig_mesh.glb',
            'workspace/local_generation/actor_offline_gate_20260908/inputs_v2/input_manifest.json',
            *[f'workspace/local_generation/actor_offline_gate_20260908/inputs_v2/{v}.png' for v in ['front','right','back','left']]])
        paths = sorted(set(paths) - {MANIFEST.relative_to(ROOT).as_posix()})
        entries = [{'path': p, 'sha256': digest(ROOT / p)} for p in paths]
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        payload = {'schema': 'actor_foot_repair_checkpoint_v1', 'date': '2026-09-09',
                   'status': 'ready_for_experimental_manual_calibration',
                   'approval_scope': 'Assistant local foot, structure and FBX review; not user final art approval or animation certification',
                   'supersedes': 'original 50k foot-flange handoff; retained as negative control',
                   'text_hash_mode': 'LF normalized', 'model_download_required': False,
                   'files': entries}
        with MANIFEST.open('x', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2)
    payload = json.loads(MANIFEST.read_text(encoding='utf-8'))
    for entry in payload['files']:
        path = (ROOT / entry['path']).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or digest(path) != entry['sha256']:
            raise ValueError('Checkpoint mismatch: ' + entry['path'])
    print('FOOT_CHECKPOINT_VERIFIED files=' + str(len(payload['files'])))


if __name__ == '__main__':
    main()
