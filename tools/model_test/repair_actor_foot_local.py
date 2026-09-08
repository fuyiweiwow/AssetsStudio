"""A93 foot-only alpha cleanup and topology-preserving low-sole flange repair.

Uses intact cross-sections of the SAME foot, never a primitive replacement.
All assets are versioned; frozen source files are hash checked and untouched.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw
import trimesh
from actor_core_offline import audit_mesh

MESH_SHA = 'e7e88465037df7ef3e5b018f19d36694e0d6c8ab081dced7fc17ace307a17068'
ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'workspace/local_generation/actor_offline_gate_20260908'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nearest_boundary(points, polygon):
    a, b = polygon[:-1], polygon[1:]
    segment = b - a
    denom = np.maximum((segment ** 2).sum(axis=1), 1e-20)
    result = []
    distances = []
    contour = polygon.astype(np.float32).reshape(-1, 1, 2)
    for p in points:
        t = np.clip(((p - a) * segment).sum(axis=1) / denom, 0, 1)
        q = a + t[:, None] * segment
        k = np.argmin(((q - p) ** 2).sum(axis=1))
        result.append(q[k])
        distances.append(max(0., -cv2.pointPolygonTest(contour, tuple(map(float, p)), True)))
    return np.asarray(result), np.asarray(distances)


def foot_sections(mesh, fraction=.015):
    lo, hi = mesh.bounds
    height = hi[1] - lo[1]
    section = mesh.section(plane_origin=[0, lo[1] + fraction * height, 0], plane_normal=[0, 1, 0])
    loops = section.discrete
    if len(loops) != 2:
        raise ValueError('Expected exactly two intact foot loops')
    return {int(np.sign(p[:, 0].mean())): p[:, [0, 2]] for p in loops}


def flange_audit(mesh, polygons=None):
    lo, hi = mesh.bounds
    height = hi[1] - lo[1]
    polygons = foot_sections(mesh) if polygons is None else polygons
    samples = []
    for fraction in [.002, .004, .006]:
        section = mesh.section(plane_origin=[0, lo[1] + fraction * height, 0], plane_normal=[0, 1, 0])
        for loop in section.discrete:
            side = int(np.sign(loop[:, 0].mean()))
            _, d = nearest_boundary(loop[:, [0, 2]], polygons[side])
            samples.append({'fraction': fraction, 'side': side, 'max_overhang_over_height': float(d.max() / height)})
    peak = max(s['max_overhang_over_height'] for s in samples)
    return {'samples': samples, 'max_overhang_over_height': peak,
            'threshold': .0015, 'pass': peak <= .0015,
            'scope': 'Low sole protrusion beyond intact .015H foot section. Not a universal shoe/foot style detector.'}


def repair_mesh(mesh):
    mesh = mesh.copy()
    original = mesh.vertices.copy()
    lo, hi = mesh.bounds
    height = hi[1] - lo[1]
    polygons = foot_sections(mesh)
    y = (original[:, 1] - lo[1]) / height
    editable = y < .015
    for side in [-1, 1]:
        ids = np.flatnonzero(editable & (np.sign(original[:, 0]) == side))
        points = original[ids][:, [0, 2]]
        q, d = nearest_boundary(points, polygons[side])
        # Monotonic compression rather than hard clamping: avoids collapsing
        # all outside vertices onto the exact same boundary curve.
        cap = .0007 * height
        compressed = cap * np.tanh(d / cap)
        factor = np.divide(compressed, d, out=np.ones_like(d), where=d > 1e-10)
        target = q + (points - q) * factor[:, None]
        blend = np.clip((.015 - y[ids]) / (.015 - .008), 0, 1)
        blend = blend * blend * (3 - 2 * blend)
        moved = points + (target - points) * blend[:, None]
        mesh.vertices[ids, 0] = moved[:, 0]
        mesh.vertices[ids, 2] = moved[:, 1]
    delta = np.linalg.norm(mesh.vertices - original, axis=1)
    return mesh, {'editable_vertices': int(editable.sum()), 'changed_vertices': int((delta > 1e-12).sum()),
                  'protected_vertices_exact': bool(np.array_equal(mesh.vertices[~editable], original[~editable])),
                  'vertical_positions_exact': bool(np.array_equal(mesh.vertices[:, 1], original[:, 1])),
                  'max_displacement_over_height': float(delta.max() / height),
                  'roi_height_fraction': .015, 'max_allowed_displacement_over_height': .025}


def prepare_alpha(output):
    output.mkdir()
    manifest = json.loads((BASE / 'inputs_v2/input_manifest.json').read_text())
    sheet = Image.new('RGB', (1200, 600), '#252525')
    draw = ImageDraw.Draw(sheet)
    reports = {}
    for col, role in enumerate(['front', 'right', 'back']):
        path = BASE / 'inputs_v2' / (role + '.png')
        if sha(path) != manifest['views'][role]['sha256']:
            raise ValueError('Source alpha identity mismatch')
        rgba = np.array(Image.open(path).convert('RGBA'))
        hsv = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2HSV)
        mask = rgba[:, :, 3] > 128
        # Dark, low-chroma reddish cast shadow differs from the actual orange
        # foot. Only the predeclared foot ROI may lose alpha; RGB never changes.
        allowed = np.zeros(mask.shape, dtype=bool)
        allowed[690:734, 290:480] = True
        shadow = (hsv[:, :, 1] < 145) & ((hsv[:, :, 0] < 9) | (hsv[:, :, 2] < 205))
        cleaned = mask & ~(allowed & shadow)
        opened = cv2.morphologyEx(cleaned.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
        cleaned[allowed] &= opened[allowed]
        candidate = rgba.copy()
        candidate[:, :, 3] = cleaned.astype(np.uint8) * 255
        Image.fromarray(candidate).save(output / f'{role}.png')
        removed = mask & ~cleaned
        reports[role] = {'input_sha256': sha(path), 'output_sha256': sha(output / f'{role}.png'),
                         'removed_pixels': int(removed.sum()), 'added_pixels': int((cleaned & ~mask).sum()),
                         'outside_roi_exact': bool(np.array_equal(candidate[~allowed], rgba[~allowed])),
                         'rgb_exact': bool(np.array_equal(candidate[:, :, :3], rgba[:, :, :3]))}
        for row, img in enumerate([rgba, candidate]):
            crop = Image.fromarray(img).crop((285, 674, 485, 744))
            bg = Image.new('RGBA', crop.size, '#66a0a8')
            bg.alpha_composite(crop)
            sheet.paste(bg.convert('RGB').resize((400, 140), Image.Resampling.NEAREST), (col * 400, row * 290 + 30))
            alpha = Image.fromarray(img[:, :, 3]).crop((285, 674, 485, 744))
            sheet.paste(alpha.convert('RGB').resize((400, 140), Image.Resampling.NEAREST), (col * 400, row * 290 + 170))
            draw.text((col * 400 + 5, row * 290 + 8), f'{role.upper()} / ' + ('BEFORE' if row == 0 else 'SHADOW ALPHA REPAIR'), fill='white')
    with Image.open(output / 'right.png') as right:
        right.transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(output / 'left.png')
    sheet.save(output / 'foot_alpha_review.png')
    (output / 'repair_report.json').write_text(json.dumps({'status': 'review_required_not_model_input_authorized',
        'region_xyxy_exclusive': [290, 690, 480, 734], 'views': reports}, indent=2), encoding='utf-8')
    return reports


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    source = BASE / 'static_50k_v2/actor_offline_v2_50k_rig_mesh.glb'
    if sha(source) != MESH_SHA:
        raise ValueError('Frozen source mesh changed')
    args.output.mkdir(parents=True, exist_ok=False)
    references = {'source_mesh_sha256': MESH_SHA, 'canonical_views': ['front', 'right'],
        'expected_parts': 1, 'scope': 'feet only; no source/model authority promotion',
        'thresholds': {'roi_height_fraction': .015, 'max_displacement_over_height': .025,
                       'sole_overhang_over_height_max': .0015, 'protected_vertex_change': 0}}
    (args.output / 'reference_manifest.json').write_text(json.dumps(references, indent=2), encoding='utf-8')
    alpha = prepare_alpha(args.output / 'alpha_diagnostic')
    original = trimesh.load(source, force='mesh', process=False)
    repaired, preservation = repair_mesh(original)
    before = flange_audit(original)
    after = flange_audit(repaired, foot_sections(original))
    structure = audit_mesh(repaired)
    normal_dot = np.einsum('ij,ij->i', original.face_normals, repaired.face_normals)
    gates = {'source_defect_rejected': not before['pass'], 'flange_check': after['pass'],
             'protected_exact': preservation['protected_vertices_exact'], 'height_exact': preservation['vertical_positions_exact'],
             'bounded_displacement': preservation['max_displacement_over_height'] <= .025,
             'faces_exact': bool(np.array_equal(original.faces, repaired.faces)),
             'structure': structure['status'] == 'pass',
             'no_degenerate_faces': bool(np.all(repaired.area_faces > 1e-12)),
             'no_face_normal_reversal': bool(np.all(normal_dot > 0))}
    # Diagnostic candidate is saved even if rejected; never exported as a rig input here.
    candidate_path = args.output / 'foot_candidate.glb'
    repaired.export(candidate_path)
    loaded = trimesh.load(candidate_path, force='mesh', process=False)
    gates['glb_structure'] = audit_mesh(loaded)['status'] == 'pass'
    report = {'status': 'automatic_pass_human_review_required' if all(gates.values()) else 'fail',
              'gates': gates, 'preservation': preservation, 'before': before, 'after': after,
              'face_normal_reversals': int((normal_dot <= 0).sum()), 'structure': structure,
              'source_sha256': MESH_SHA, 'candidate_sha256': sha(candidate_path),
              'alpha_diagnostic': alpha, 'allow_calibration': False, 'allow_production': False}
    (args.output / 'repair_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if all(gates.values()) else 2


if __name__ == '__main__':
    raise SystemExit(main())
