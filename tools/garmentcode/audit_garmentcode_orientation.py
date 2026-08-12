"""Audit panel winding and collision-proxy normal orientation."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boxmesh-obj", required=True, type=Path)
    parser.add_argument("--sim-obj", required=True, type=Path)
    parser.add_argument("--panel-membership", required=True, type=Path)
    parser.add_argument("--body-obj", required=True, type=Path)
    parser.add_argument("--body-segmentation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def load_obj(path: Path) -> tuple[np.ndarray, np.ndarray]:
    vertices = []
    faces = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            vertices.append([float(value) for value in line.split()[1:4]])
        elif line.startswith("f "):
            face = [int(value.split("/")[0]) - 1 for value in line.split()[1:]]
            for index in range(1, len(face) - 1):
                faces.append([face[0], face[index], face[index + 1]])
    return np.asarray(vertices, dtype=np.float64), np.asarray(faces, dtype=np.int64)


def normals(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    raw = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])
    lengths = np.linalg.norm(raw, axis=1)
    unit = np.zeros_like(raw)
    valid = lengths > 1.0e-12
    unit[valid] = raw[valid] / lengths[valid, None]
    return unit, lengths


def main() -> int:
    options = arguments()
    box_vertices, box_faces = load_obj(options.boxmesh_obj.resolve())
    sim_vertices, sim_faces = load_obj(options.sim_obj.resolve())
    body_vertices, body_faces = load_obj(options.body_obj.resolve())
    if len(box_vertices) != len(sim_vertices) or not np.array_equal(box_faces, sim_faces):
        raise RuntimeError("BoxMesh and simulation topology/order differ")
    membership = json.loads(options.panel_membership.read_text(encoding="utf-8"))
    vertex_panels = [set(names) for names in membership["vertex_panels"]]
    if len(vertex_panels) != len(sim_vertices):
        raise RuntimeError("membership/simulation vertex count mismatch")

    box_normals, box_areas2 = normals(box_vertices, box_faces)
    sim_normals, sim_areas2 = normals(sim_vertices, sim_faces)
    normal_dots = np.einsum("ij,ij->i", box_normals, sim_normals)
    panel_stats: dict[str, dict[str, float | int]] = {}
    panel_face_indices: dict[str, list[int]] = defaultdict(list)
    for face_index, face in enumerate(sim_faces):
        common = vertex_panels[int(face[0])] & vertex_panels[int(face[1])] & vertex_panels[int(face[2])]
        for panel in common:
            panel_face_indices[panel].append(face_index)
    for panel, indices_list in sorted(panel_face_indices.items()):
        indices = np.asarray(indices_list, dtype=np.int64)
        z_normals = sim_normals[indices, 2]
        expected_z = 1.0 if "_f" in panel or "ftorso" in panel else -1.0
        expected_z_fraction = float(np.mean(z_normals * expected_z > 0.0))
        panel_stats[panel] = {
            "faces": int(len(indices)),
            "degenerate_faces": int(np.sum(sim_areas2[indices] <= 1.0e-12)),
            "box_to_sim_normal_dot_negative": int(np.sum(normal_dots[indices] < 0.0)),
            "box_to_sim_normal_dot_mean": float(np.mean(normal_dots[indices])),
            "expected_front_back_z_fraction": expected_z_fraction,
            "mean_normal": np.mean(sim_normals[indices], axis=0).tolist(),
        }

    # The partial Actor proxy is open, so volume cannot determine orientation.
    # Torso faces should nevertheless point away from the body's x/z centre.
    body_normals, body_areas2 = normals(body_vertices, body_faces)
    centroids = body_vertices[body_faces].mean(axis=1)
    body_center = body_vertices.mean(axis=0)
    radial = centroids - body_center
    radial[:, 1] = 0.0
    radial_lengths = np.linalg.norm(radial, axis=1)
    valid = (radial_lengths > 1.0e-8) & (body_areas2 > 1.0e-12)
    radial[valid] /= radial_lengths[valid, None]
    body_radial_dots = np.einsum("ij,ij->i", body_normals[valid], radial[valid])
    body_edge_counts = Counter()
    for face in body_faces:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            body_edge_counts[tuple(sorted((int(a), int(b))))] += 1

    body_segmentation = json.loads(options.body_segmentation.read_text(encoding="utf-8"))
    body_region_stats = {}
    for region in ("body", "left_arm", "right_arm"):
        region_vertices = np.asarray(body_segmentation[region], dtype=np.int64)
        region_set = set(int(value) for value in region_vertices)
        region_face_indices = np.asarray(
            [index for index, face in enumerate(body_faces) if all(int(value) in region_set for value in face)],
            dtype=np.int64,
        )
        points = body_vertices[region_vertices]
        centre = points.mean(axis=0)
        centered = points - centre
        _u, _s, vh = np.linalg.svd(centered, full_matrices=False)
        axis = vh[0]
        region_centroids = centroids[region_face_indices]
        from_centre = region_centroids - centre
        radial_region = from_centre - np.outer(from_centre @ axis, axis)
        radial_region_lengths = np.linalg.norm(radial_region, axis=1)
        valid_region = (radial_region_lengths > 1.0e-8) & (body_areas2[region_face_indices] > 1.0e-12)
        radial_region[valid_region] /= radial_region_lengths[valid_region, None]
        dots = np.einsum(
            "ij,ij->i",
            body_normals[region_face_indices][valid_region],
            radial_region[valid_region],
        )
        body_region_stats[region] = {
            "vertices": int(len(region_vertices)),
            "faces_wholly_in_region": int(len(region_face_indices)),
            "pca_axis": axis.tolist(),
            "outward_fraction": float(np.mean(dots > 0.0)),
            "radial_dot_mean": float(np.mean(dots)),
        }

    report = {
        "schema": "assetsstudio_garmentcode_orientation_audit_v1",
        "boxmesh_obj": str(options.boxmesh_obj.resolve()),
        "sim_obj": str(options.sim_obj.resolve()),
        "body_obj": str(options.body_obj.resolve()),
        "garment": {
            "vertices": int(len(sim_vertices)),
            "faces": int(len(sim_faces)),
            "degenerate_faces": int(np.sum(sim_areas2 <= 1.0e-12)),
            "box_to_sim_normal_dot_negative": int(np.sum(normal_dots < 0.0)),
            "box_to_sim_normal_dot_mean": float(np.mean(normal_dots)),
            "panels": panel_stats,
        },
        "body_proxy": {
            "vertices": int(len(body_vertices)),
            "faces": int(len(body_faces)),
            "boundary_edges": int(sum(value == 1 for value in body_edge_counts.values())),
            "nonmanifold_edges": int(sum(value > 2 for value in body_edge_counts.values())),
            "radial_outward_fraction": float(np.mean(body_radial_dots > 0.0)),
            "radial_dot_mean": float(np.mean(body_radial_dots)),
            "regions": body_region_stats,
            "note": "partial proxy is open; radial test audits torso-side winding, not watertight volume",
        },
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
