"""Create a source/render contact sheet and inspect raw connectivity."""
import argparse
import json
from pathlib import Path

import trimesh
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--mesh', required=True)
    parser.add_argument('--render', default='render')
    parser.add_argument('--beauty-subdir', default='beauty')
    parser.add_argument('--name', default='review20')
    args = parser.parse_args()
    mesh = trimesh.load(args.root / args.mesh, force='mesh', process=False)
    parts = sorted(mesh.split(only_watertight=False), key=lambda x: len(x.faces), reverse=True)
    report = {'status': 'diagnostic_only', 'components': [{'faces': len(p.faces), 'watertight': bool(p.is_watertight), 'bounds': p.bounds.tolist()} for p in parts]}
    (args.root / (args.name + '_components.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
    canvas = Image.new('RGB', (1536, 830), '#202124')
    draw = ImageDraw.Draw(canvas)
    for i, view in enumerate(['front', 'right', 'back', 'left']):
        draw.text((i * 384 + 12, 12), view.upper() + ' SOURCE / 3D PROBE', fill='white')
        for row, path in enumerate([args.root / (view + '.png'), args.root / args.render / args.beauty_subdir / (view + '.png')]):
            im = Image.open(path).convert('RGBA').resize((384, 384))
            tile = Image.new('RGBA', im.size, '#999999')
            tile.alpha_composite(im)
            canvas.paste(tile.convert('RGB'), (i * 384, 34 + row * 384))
    draw.text((12, 805), 'EXPERIMENT ONLY - topology and visual approval pending', fill='white')
    canvas.save(args.root / (args.name + '.png'))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
