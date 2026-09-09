"""Compare fixed-canvas silhouettes and assemble checkpoint review evidence."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import trimesh
from repair_actor_foot_local import flange_audit


def compare(a, b):
    if a.shape != (768, 768) or b.shape != a.shape or not a.any() or not b.any():
        raise ValueError('Nonempty 768x768 masks required')
    def bounds(m):
        y, x = np.where(m)
        return np.array([x.min(), y.min(), x.max()+1, y.max()+1])
    aa, bb = bounds(a), bounds(b)
    aspect = lambda q: (q[2]-q[0])/(q[3]-q[1])
    iou = float((a & b).sum()/(a | b).sum())
    drift = float(abs(aspect(bb)/aspect(aa)-1))
    center = float(np.linalg.norm((bb[:2]+bb[2:]-aa[:2]-aa[2:])/2))
    return {'iou': iou, 'relative_aspect_drift': drift, 'center_error_px': center,
            'source_bbox': aa.tolist(), 'render_bbox': bb.tolist(),
            'pass': iou >= .90 and drift <= .03 and center <= 12}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    args = ap.parse_args()
    root = args.root
    sheet = Image.new('RGB', (1536, 1200), '#303030')
    draw = ImageDraw.Draw(sheet)
    views = {}
    for i, name in enumerate(('front','right','back','left')):
        src = Image.open(root/'input_replay/inputs'/f'{name}.png').convert('RGBA')
        a = np.asarray(src)[:,:,3] >= 128
        b = np.asarray(Image.open(root/'review/silhouette'/f'{name}.png').convert('L')) >= 128
        stats = compare(a,b)
        views[name] = stats
        tile = Image.new('RGBA', src.size, '#999999')
        tile.alpha_composite(src)
        sheet.paste(tile.convert('RGB').resize((384,384)), (i*384,40))
        beauty = Image.open(root/'review/beauty'/f'{name}.png').convert('RGB')
        sheet.paste(beauty.resize((384,384)), (i*384,424))
        rgb = np.zeros((768,768,3), dtype=np.uint8)
        rgb[a & b] = 255
        rgb[a & ~b] = (255,64,64)
        rgb[b & ~a] = (64,224,255)
        overlay = Image.fromarray(rgb)
        overlay.save(root/'review'/f'{name}_overlay.png')
        sheet.paste(overlay.resize((384,384)), (i*384,808))
        draw.text((i*384+8,5), f"{name} IoU {stats['iou']:.4f}; aspect {stats['relative_aspect_drift']:.2%}", fill='white')
        draw.text((i*384+8,20), 'Shared frame; experimental, not approved', fill='white')
    sheet.save(root/'review/source_mesh_review.png')
    feet = Image.new('RGB', (1536,800), '#303030')
    d = ImageDraw.Draw(feet)
    for i, name in enumerate(('front','right','back','left','oblique','bottom')):
        p = root/'foot_review'/f'feet_{name}.png'
        if p.exists():
            x,y = (i%3)*512,(i//3)*400
            feet.paste(Image.open(p).convert('RGB').resize((384,384)), (x+64,y+16))
            d.text((x+8,y+2), name, fill='white')
    feet.save(root/'review/feet_review.jpg')
    shape = json.loads((root/'shape_seed20260909/shape.json').read_text(encoding='utf-8'))
    mesh = trimesh.load(root/'shape_seed20260909/shape.glb', force='mesh', process=False)
    faces = mesh.faces
    repeated = (faces[:,0] == faces[:,1]) | (faces[:,1] == faces[:,2]) | (faces[:,0] == faces[:,2])
    diagnostic = trimesh.Trimesh(vertices=mesh.vertices.copy(), faces=faces[~repeated].copy(), process=False)
    counts = np.bincount(mesh.edges_unique_inverse)
    diagnosis = {'repeated_index_face_ids': np.flatnonzero(repeated).tolist(),
        'raw_components_diagnostic': [{'vertices':len(c.vertices),'faces':len(c.faces),
            'watertight':bool(c.is_watertight),'euler':int(c.euler_number),'bounds_y_up':c.bounds.tolist()}
            for c in sorted(mesh.split(only_watertight=False),key=lambda c:len(c.faces),reverse=True)],
        'zero_area_faces': int((mesh.area_faces == 0).sum()),
        'boundary_edges': int((counts == 1).sum()), 'nonmanifold_edges': int((counts > 2).sum()),
        'diagnostic_only_excluding_repeated_indices': {'vertices_unchanged': bool(np.array_equal(mesh.vertices, diagnostic.vertices)),
            'faces': len(diagnostic.faces), 'watertight': bool(diagnostic.is_watertight),
            'euler': int(diagnostic.euler_number), 'components': len(diagnostic.split(only_watertight=False))},
        'policy': 'In-memory diagnosis only, no candidate exported or promoted'}
    try:
        diagnosis['sole_flange'] = flange_audit(diagnostic)
    except (ValueError, AttributeError, KeyError) as error:
        diagnosis['sole_flange'] = {'status': 'inapplicable', 'reason': str(error)}
    report = {'views': views, 'structural_status': shape['status'],
        'topology_diagnosis': diagnosis,
        'fixed_frame_status': 'pass' if all(v['pass'] for v in views.values()) else 'fail',
        'qualification': 'Numerical evidence only; hands, crown and soles require visual review',
        'allow_rigging': False, 'allow_asset_registration': False}
    (root/'review/audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
