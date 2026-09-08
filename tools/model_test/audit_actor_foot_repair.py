"""Independent post-export checks for the published bounded sole repair."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree
import trimesh
from actor_core_offline import audit_mesh
from repair_actor_foot_local import flange_audit, foot_sections, sha, MESH_SHA


def audit(source, candidate):
    lo, hi = source.bounds
    height = hi[1] - lo[1]
    cut = lo[1] + .015 * height
    protected = source.vertices[source.vertices[:, 1] > cut + 1e-6]
    error = float(cKDTree(candidate.vertices).query(protected)[0].max())
    reverse = candidate.vertices[candidate.vertices[:, 1] > cut + 1e-6]
    reverse_error = float(cKDTree(protected).query(reverse)[0].max())
    before = flange_audit(source)
    after = flange_audit(candidate, foot_sections(source))
    structure = audit_mesh(candidate)
    gates = {'original_defect_rejected': not before['pass'], 'sole_overhang': after['pass'],
             'structure': structure['status'] == 'pass',
             'protected_geometry_preserved': bool(max(error, reverse_error) < 1e-6 * height),
             'height_and_floor_preserved': bool(np.max(np.abs(source.bounds[:, 1] - candidate.bounds[:, 1])) < 1e-6 * height),
             'no_degenerate_triangles': bool(np.all(candidate.area_faces > 1e-12)),
             'positive_volume': bool(candidate.volume > 0)}
    return {'status': 'pass_foot_and_structure_only' if all(gates.values()) else 'fail',
            'gates': gates, 'before': before, 'after': after, 'structure': structure,
            'protected_vertex_error_max': error, 'protected_reverse_error_max': reverse_error,
            'export_coordinate_tolerance': 1e-6 * height,
            'limits': ['No full-body self-intersection certification', 'No skinning/motion validation',
                       'Face/hand artistic issues remain outside this foot-only repair']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--before-review', type=Path)
    ap.add_argument('--after-review', type=Path)
    args = ap.parse_args()
    if sha(args.source) != MESH_SHA:
        raise ValueError('Frozen source changed')
    report = audit(trimesh.load(args.source, force='mesh', process=False),
                   trimesh.load(args.candidate, force='mesh', process=False))
    report.update({'source_sha256': sha(args.source), 'candidate_sha256': sha(args.candidate)})
    serialized = json.dumps(report, indent=2)
    with args.output.open('x', encoding='utf-8') as handle:
        handle.write(serialized)
    if args.before_review and args.after_review:
        sheet = Image.new('RGB', (1536, 820), '#202124')
        draw = ImageDraw.Draw(sheet)
        for row, (root, label) in enumerate([(args.before_review, 'BEFORE / REJECTED'), (args.after_review, 'SOLE REPAIR / CALIBRATION EXPERIMENT')]):
            for col, view in enumerate(['front', 'right', 'oblique', 'bottom']):
                with Image.open(root / f'feet_{view}.png') as im:
                    sheet.paste(im.convert('RGB').resize((384, 384)), (col * 384, row * 410 + 25))
                draw.text((col * 384 + 5, row * 410 + 6), label + ' / ' + view.upper(), fill='white')
        sheet.save(args.output.parent / 'foot_before_after.png')
    print(json.dumps(report, indent=2))
    return 0 if all(report['gates'].values()) else 2


if __name__ == '__main__':
    raise SystemExit(main())
