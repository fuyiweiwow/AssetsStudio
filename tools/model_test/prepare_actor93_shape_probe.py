"""Prepare isolated RGBA inputs from the recorded Actor93 views, without rescaling."""
import argparse
import json
from pathlib import Path

from actor_core_offline import prepare

ROOT = Path(__file__).resolve().parents[2]


def main():
    source_dir = ROOT / 'workspace/local_generation/actor_core_multiview_gate_20260907'
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True, help='New revision directory')
    output = parser.parse_args().output
    sources = {
        'front': ROOT / 'workspace/local_generation/actor_core_tpose_shoulder_gate_20260907/tpose93_shoulders_seed1002_blankface_v1.png',
        'right': source_dir / 'right_b_seed1005_refined.png',
        'back': source_dir / 'back_b_seed1008_refined_v2.png',
    }
    report = prepare(sources['front'], sources['right'], sources['back'], output)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
