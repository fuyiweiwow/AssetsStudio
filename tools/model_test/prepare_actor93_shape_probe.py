"""Prepare isolated RGBA inputs from the recorded Actor93 views, without rescaling."""
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]


def main():
    source_dir = ROOT / 'workspace/local_generation/actor_core_multiview_gate_20260907'
    output = ROOT / 'workspace/local_generation/actor93_shape_probe_20260908'
    output.mkdir(parents=True, exist_ok=True)
    sources = {
        'front': ROOT / 'workspace/local_generation/actor_core_tpose_shoulder_gate_20260907/tpose93_shoulders_seed1002_blankface_v1.png',
        'right': source_dir / 'right_b_seed1005_refined.png',
        'back': source_dir / 'back_b_seed1008_refined_v2.png',
    }
    records = {}
    for name, path in sources.items():
        rgb = np.array(Image.open(path).convert('RGB'))
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        mask = ((hsv[:, :, 1] > 30) & (hsv[:, :, 2] > 125)).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        if count < 2:
            raise ValueError('No foreground: ' + str(path))
        mask = (labels == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(mask, contours, -1, 255, cv2.FILLED)
        rgba = Image.fromarray(np.dstack([rgb, mask]))
        rgba.save(output / (name + '.png'))
        if name == 'right':
            ImageOps.mirror(rgba).save(output / 'left.png')
        records[name] = {'source': path.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bbox': rgba.getchannel('A').getbbox()}
    report = {'status': 'experimental_input_not_production_approval', 'method': 'largest skin-color component; fill internal holes; preserve original canvas and scale', 'left': 'horizontal mirror of right, including illumination; geometry probe only', 'sources': records}
    (output / 'input_manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
