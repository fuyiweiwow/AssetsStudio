"""Remove tiny disconnected debris and relax the frozen probe's left cheek spike locally."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import scipy.sparse
import trimesh


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    source_sha = hashlib.sha256(args.source.read_bytes()).hexdigest()
    if source_sha != '557217b3719e9ff8b35f8054c053cac86d434de24cfe824d6df46ccc9e8ade6f':
        raise ValueError('Source is not the frozen actor93 40-step probe')
    raw = trimesh.load(args.source, force='mesh', process=False)
    parts = sorted(raw.split(only_watertight=False), key=lambda p: len(p.faces), reverse=True)
    mesh = parts[0].copy()
    removed_faces = sum(len(p.faces) for p in parts[1:])
    if removed_faces / len(raw.faces) > 0.001:
        raise ValueError('Refusing to discard substantial components')
    source = mesh.vertices.copy()
    # Coordinates refer to the raw Hunyuan Y-up seed20260908_s40 geometry.
    distance = ((source[:, 1] - .0825) / .070) ** 2 + ((source[:, 2] - .160) / .095) ** 2
    weights = np.clip(1-distance, 0, 1) ** 2 * np.clip((-.400-source[:, 0])/.035, 0, 1)
    affected = weights > 0
    if not 30 < affected.sum() < 2000:
        raise ValueError('Unexpected local patch size')
    edges = mesh.edges_unique
    a, b = edges.T
    adjacency = scipy.sparse.csr_matrix((np.ones(len(a)*2), (np.r_[a,b], np.r_[b,a])), shape=(len(source),len(source)))
    degree = np.asarray(adjacency.sum(axis=1)).ravel()
    vertices = source.copy()
    for _ in range(600):
        average = adjacency @ vertices / np.maximum(degree[:,None],1)
        vertices += .5 * weights[:,None] * (average-vertices)
    mesh.vertices = vertices
    assert np.array_equal(vertices[~affected], source[~affected])
    assert np.array_equal(mesh.faces, parts[0].faces)
    if not mesh.is_watertight or mesh.euler_number != parts[0].euler_number:
        raise ValueError('Local edit altered closure or topology')
    displacement = np.linalg.norm(vertices-source, axis=1)
    report = {
        'status': 'human_review_required_not_rig_ready',
        'source_sha256': source_sha,
        'method': 'local weighted neighbor relaxation; existing principal-component topology retained',
        'patch': {'center_yz': [.0825,.160], 'radii_yz': [.070,.095], 'x_gate': [-.400,-.435], 'iterations':600, 'step':.5},
        'removed_tiny_components':len(parts)-1, 'removed_faces':removed_faces,
        'changed_vertices':int(affected.sum()), 'main_vertices':len(source),
        'max_displacement':float(displacement.max()),
        'outside_patch_changed_vertices':int(np.any(vertices[~affected]!=source[~affected],axis=1).sum()),
        'single_component':len(mesh.split(only_watertight=False))==1,
        'watertight':bool(mesh.is_watertight), 'euler_number':int(mesh.euler_number),
        'remaining': 'Euler is -2 (genus 2); topology gate remains unresolved; no rig approval',
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    mesh.export(args.output)
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
