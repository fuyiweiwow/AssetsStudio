"""Compare independently generated AB meshes; local input is not local 3D repair."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree
import trimesh


def normalized(path):
    mesh = trimesh.load(path,force='mesh',process=False)
    lo,hi = mesh.bounds
    return (mesh.vertices - np.array([(lo[0]+hi[0])/2,lo[1],(lo[2]+hi[2])/2]))/(hi[1]-lo[1])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--before',type=Path,required=True)
    ap.add_argument('--after',type=Path,required=True)
    args = ap.parse_args()
    roots = [args.before,args.after]
    reports = [json.loads((r/'review/audit.json').read_text(encoding='utf-8')) for r in roots]
    meshes = [r/'shape_seed20260909/shape.glb' for r in roots]
    a,b = [normalized(m) for m in meshes]
    distances = []
    for source,target in [(a,b),(b,a)]:
        d = cKDTree(target).query(source)[0]
        regions = {}
        for name,mask in {'whole':np.ones(len(source),bool),'head':source[:,1]>.55,'feet':source[:,1]<.10}.items():
            values = d[mask]
            regions[name] = {'mean_over_height':float(values.mean()),'p95_over_height':float(np.quantile(values,.95)), 'max_over_height':float(values.max())}
        distances.append(regions)
    result = {'input_change':'foot-alpha only; RGB exact',
        'mesh_sha256':[hashlib.sha256(m.read_bytes()).hexdigest() for m in meshes],
        'before':reports[0], 'after':reports[1],
        'vertex_nearest_neighbor_diagnostic':distances,
        'distance_limits':'Separate height normalization and bbox centering, no ICP; vertex distances are not surface correspondence or deformation certification',
        'allow_calibration':False,'allow_production':False}
    out = args.after/'ab_comparison'
    out.mkdir(exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    sheet = Image.new('RGB',(1536,800),'#252525')
    draw = ImageDraw.Draw(sheet)
    for row,r in enumerate(roots):
        for col,v in enumerate(('front','right','oblique','bottom')):
            im = Image.open(r/'foot_review'/f'feet_{v}.png').convert('RGB')
            sheet.paste(im.resize((384,384)),(col*384,row*400+16))
            draw.text((col*384+8,row*400+2),('BASELINE / ' if row==0 else 'FOOT ALPHA AB / ')+v,fill='white')
    sheet.save(out/'feet_before_after.jpg')
    print(json.dumps({'before_flange':reports[0]['topology_diagnosis']['sole_flange'],
        'after_flange':reports[1]['topology_diagnosis']['sole_flange'],
        'after_structure':reports[1]['structural_status'],
        'after_fixed_frame':reports[1]['fixed_frame_status'],
        'distance_diagnostic':distances},indent=2))


if __name__ == '__main__':
    main()
