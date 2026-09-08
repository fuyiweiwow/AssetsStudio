"""Deterministic preprocessing and structural checks for isolated biped Actor Cores.

Supported image contract: a colored, featureless body on a neutral background,
orthographic front/back with separated legs. Other families must be rejected or
given their own profile; this is not a general-purpose background remover.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


VERSION = 'biped_colored_neutral_v2'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def runs(row):
    changes = np.diff(np.pad(row.astype(np.int8), (1, 1)))
    return list(zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)))


def bbox(mask):
    y, x = np.where(mask)
    if not len(x):
        raise ValueError('No foreground')
    return [int(x.min()), int(y.min()), int(x.max())+1, int(y.max())+1]


def largest(mask):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    if count < 2:
        raise ValueError('No foreground component')
    return labels == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))


def leg_gap(mask):
    """Locate a corridor supported by two substantial leg runs, in relative units."""
    x0, y0, x1, y1 = bbox(mask)
    height = y1-y0
    width = x1-x0
    center = (x0+x1)/2
    evidence = []
    for y in range(round(y0+.68*height), round(y0+.94*height)):
        spans = [(a,b) for a,b in runs(mask[y]) if b-a >= .055*width]
        for (a,b),(c,d) in zip(spans, spans[1:]):
            if b < center < c and .01*width <= c-b <= .38*width:
                evidence.append((y,b,c))
    if len(evidence) < max(6, .08*height):
        raise ValueError('Insufficient separated-leg evidence; manual review required')
    # Stable intersection of the observed gap; excludes outlying rows and shadows.
    left = int(np.ceil(np.quantile([e[1] for e in evidence], .85)))
    right = int(np.floor(np.quantile([e[2] for e in evidence], .15)))
    if right-left < max(2, .008*width):
        raise ValueError('No stable leg-gap corridor; do not cut blindly')
    return {'left':left, 'right':right, 'start_y':min(e[0] for e in evidence),
            'floor_y':y1, 'evidence_rows':len(evidence), 'bbox': [x0,y0,x1,y1]}


def prepare_image(image, role):
    rgb = np.array(image.convert('RGB'))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    border = np.concatenate([hsv[0],hsv[-1],hsv[:,0],hsv[:,-1]])
    if np.quantile(border[:,1], .90) > 30:
        raise ValueError('Background is not neutral; unsupported image contract')
    threshold, _ = cv2.threshold(hsv[:,:,1],0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    threshold = max(30,float(threshold))
    mask = largest((hsv[:,:,1] > threshold) & (hsv[:,:,2] > 100))
    if mask.mean() < .06 or mask.mean() > .75:
        raise ValueError('Unexpected foreground coverage')
    baseline = mask.copy()
    gap = None
    if role in ('front','back'):
        gap = leg_gap(mask)
        # Clear only the supported corridor, not whole rows or foot surfaces.
        mask[gap['start_y']:gap['floor_y'],gap['left']:gap['right']] = False
    # Enclosed pale highlights are not background. Fill only small, non-neutral
    # holes AFTER opening the leg corridor, never the external contour.
    flooded = np.pad(mask.astype(np.uint8)*255, 1)
    cv2.floodFill(flooded, None, (0,0), 255)
    holes = flooded[1:-1,1:-1] == 0
    eligible = holes & (hsv[:,:,1] > 20) & (hsv[:,:,2] > 100)
    # Isolated raster noise gets a separately bounded allowance; a neutral
    # region of meaningful size remains ambiguous and must be rejected.
    count,labels,stats,_=cv2.connectedComponentsWithStats(holes.astype(np.uint8))
    noise=np.zeros_like(mask)
    for label in range(1,count):
        if stats[label,cv2.CC_STAT_AREA] <= 4:
            noise |= labels==label
    if noise.sum() <= .0001*baseline.sum():
        eligible |= noise
    if np.count_nonzero(holes) > .05*baseline.sum() or np.any(holes & ~eligible):
        raise ValueError(f'Ambiguous interior holes; manual review required: role={role}, holes={holes.sum()}, foreground={baseline.sum()}, neutral_or_dark={(holes & ~eligible).sum()}')
    mask |= eligible
    mask = largest(mask)
    removed_fraction = float(np.count_nonzero(baseline & ~mask) / baseline.sum())
    if removed_fraction > .02:
        raise ValueError('Repair exceeds 2% foreground budget; manual review required')
    # Never fill external contours: the open leg corridor is negative space.
    neutral = (hsv[:,:,1] <= 20) & (hsv[:,:,2] > 100)
    if np.any(mask & neutral & ~noise):
        raise ValueError('Neutral background pixels promoted to foreground')
    if gap and mask[gap['start_y']:,gap['left']:gap['right']].any():
        raise ValueError('Leg corridor was refilled')
    result = Image.fromarray(np.dstack([rgb,mask.astype(np.uint8)*255]))
    report = {'role':role, 'threshold_saturation':threshold, 'bbox':bbox(mask),
              'removed_fraction':removed_fraction, 'added_foreground_pixels':int(eligible.sum()),
              'leg_gap':gap, 'status':'pass', 'rgb_unchanged':True}
    return result, report


def prepare(front, right, back, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output directory already exists; use a new revision directory')
    sources = {'front':Path(front), 'right':Path(right), 'back':Path(back)}
    pending = {}
    records = {}
    # Validate every view before writing any generation-ready file.
    for role,path in sources.items():
        with Image.open(path) as image:
            pending[role], records[role] = prepare_image(image,role)
        records[role]['source'] = str(path.resolve())
        records[role]['source_sha256'] = sha256(path)
    if len({im.size for im in pending.values()}) != 1:
        raise ValueError('All orthographic views must share the same canvas')
    height0 = records['front']['bbox'][3]-records['front']['bbox'][1]
    for record in records.values():
        height = record['bbox'][3]-record['bbox'][1]
        if abs(height/height0-1) > .025:
            raise ValueError('Multiview height drift exceeds 2.5%')
    pending['left'] = ImageOps.mirror(pending['right'])
    records['left'] = {'derived_from':'right', 'method':'horizontal_mirror_including_lighting'}
    output.mkdir(parents=True)
    for role,image in pending.items():
        image.save(output / (role+'.png'))
        records[role]['file'] = role+'.png'
        records[role]['sha256'] = sha256(output/(role+'.png'))
    manifest = {'schema':'actor_core_offline_inputs_v1', 'profile':VERSION,
                'implementation_sha256':sha256(__file__),
                'status':'pass', 'qualification':'input_structure_only_not_art_approval',
                'views':records}
    (output/'input_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


def validate_inputs(manifest_path, paths):
    manifest_path = Path(manifest_path)
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (data.get('schema') != 'actor_core_offline_inputs_v1' or data.get('status') != 'pass'
            or data.get('profile') != VERSION):
        raise ValueError('Missing successful offline input gate')
    for role,path in paths.items():
        entry = data['views'][role]
        if Path(path).resolve() != (manifest_path.parent/entry['file']).resolve() or sha256(path) != entry['sha256']:
            raise ValueError('Input does not match gate manifest: '+role)
        if role in ('front','back'):
            mask = np.array(Image.open(path).getchannel('A')) > 128
            gap = leg_gap(mask)
            if mask[gap['start_y']:,gap['left']:gap['right']].any():
                raise ValueError('Input contains an obstructed foot corridor: '+role)
    return data


def audit_mesh(mesh):
    """Y-up biped foot-slice test; slicing the lower body avoids torso connectivity."""
    lo,hi = mesh.bounds
    height = hi[1]-lo[1]
    if not np.isfinite(mesh.vertices).all() or height <= 0:
        raise ValueError('Invalid or zero-height mesh')
    center = (lo[0]+hi[0])/2
    slices=[]
    for fraction in [.002,.005,.01,.02,.04,.08,.12]:
        section = mesh.section(plane_origin=[0,lo[1]+height*fraction,0],plane_normal=[0,1,0])
        loops = section.discrete if section is not None else []
        widths = [float(np.ptp(p[:,0])) for p in loops]
        significant=[p for p,w in zip(loops,widths) if w > .01*height]
        crosses = any(p[:,0].min() < center-.003*height and p[:,0].max() > center+.003*height for p in significant)
        slices.append({'height_fraction':fraction,'significant_loops':len(significant),'crosses_center':bool(crosses)})
    bridge = any(s['crosses_center'] for s in slices)
    legs_established = sum(s['significant_loops']==2 and not s['crosses_center'] for s in slices[2:]) >= 3
    components=list(mesh.split(only_watertight=False))
    gates={'single_component':len(components)==1,'watertight':bool(mesh.is_watertight),
           'euler_two':mesh.euler_number==2,'separated_feet':legs_established and not bridge,
           'winding_consistent':bool(mesh.is_winding_consistent)}
    return {'schema':'actor_core_offline_mesh_v1','status':'pass' if all(gates.values()) else 'fail',
            'qualification':'structural_only_not_rig_approval', 'axis':'Y-up', 'gates':gates,
            'foot_slices':slices,'euler_number':int(mesh.euler_number),'components':len(components),
            'repair_policy':'revisit input first; no unbounded mesh cutting or whole-body smoothing'}


def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    for name in ['front','right','back','output']:
        p.add_argument('--'+name,type=Path,required=True)
    p=sub.add_parser('audit')
    p.add_argument('--mesh',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p=sub.add_parser('generate', help='Gated generation using the active local Hunyuan Python environment')
    p.add_argument('--inputs',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True,help='New experiment directory')
    p.add_argument('--seed',type=int,default=20260908)
    p.add_argument('--steps',type=int,default=40)
    p.add_argument('--cpu-offload',action='store_true')
    args=parser.parse_args()
    if args.command=='prepare':
        result=prepare(args.front,args.right,args.back,args.output)
    elif args.command=='generate':
        manifest=args.inputs/'input_manifest.json'
        paths={role:args.inputs/(role+'.png') for role in ('front','left','back')}
        validate_inputs(manifest,paths)
        if args.output.exists():
            raise ValueError('Output directory already exists; use a new revision directory')
        command=[sys.executable,str(Path(__file__).with_name('run_hunyuan3d_mv_shape.py')),
                 '--input-manifest',str(manifest), '--output',str(args.output/'shape.glb'),
                 '--manifest',str(args.output/'shape.json'),'--seed',str(args.seed),
                 '--steps',str(args.steps),'--guidance-scale','5','--octree-resolution','256']
        command.extend(['--subfolder','hunyuan3d-dit-v2-mv'])
        for role,path in paths.items():
            command.extend(['--'+role,str(path)])
        if args.cpu_offload:
            command.append('--cpu-offload')
        return subprocess.run(command,check=False).returncode
    else:
        import trimesh
        result=audit_mesh(trimesh.load(args.mesh,force='mesh',process=False))
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    return 0 if result['status']=='pass' else 2


if __name__=='__main__':
    raise SystemExit(main())
