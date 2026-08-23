"""Run low-VRAM P3-SAM point prompts and export candidate mesh masks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import trimesh
from scipy.spatial import cKDTree


P3SAM_DEMO = Path(r"E:\env\Hunyuan3D-Part\P3-SAM\demo")
sys.path.insert(0, str(P3SAM_DEMO))
sys.path.insert(0, str(P3SAM_DEMO.parent))
from app import P3SAM, get_feat, get_mask, normalize_pc  # noqa: E402


def choose_prompt(vertices: np.ndarray, name: str) -> tuple[int, np.ndarray]:
    lo = vertices.min(axis=0)
    hi = vertices.max(axis=0)
    yn = (vertices[:, 1] - lo[1]) / max(hi[1] - lo[1], 1e-8)

    if name == "hair_wig":
        candidates = np.where(yn > 0.78)[0]
        score = vertices[candidates, 1]
    elif name == "adventurer_jacket":
        candidates = np.where((yn > 0.38) & (yn < 0.62))[0]
        score = vertices[candidates, 2] - 0.15 * np.abs(vertices[candidates, 0])
    elif name == "trousers":
        candidates = np.where((yn > 0.18) & (yn < 0.40))[0]
        score = vertices[candidates, 2] - 0.10 * np.abs(vertices[candidates, 0])
    elif name == "boots":
        candidates = np.where(yn < 0.18)[0]
        score = -np.abs(vertices[candidates, 0])
    else:
        raise ValueError(name)

    if len(candidates) == 0:
        raise RuntimeError(f"No candidate vertices found for {name}")
    index = int(candidates[int(np.argmax(score))])
    return index, vertices[index]


def normalize_point(point: np.ndarray, vertices: np.ndarray) -> np.ndarray:
    lo = vertices.min(axis=0)
    hi = vertices.max(axis=0)
    center = (hi + lo) / 2
    scale = np.max(np.abs((hi - lo) / 2))
    return (point - center) / max(scale, 1e-8)


def export_candidate(mesh: trimesh.Trimesh, face_mask: np.ndarray, point_mask: np.ndarray,
                      points_raw: np.ndarray, out_dir: Path, name: str) -> dict:
    face_colors = np.tile(np.array([[125, 125, 125, 255]], dtype=np.uint8), (len(mesh.faces), 1))
    face_colors[face_mask] = np.array([40, 150, 255, 255], dtype=np.uint8)
    preview = mesh.copy()
    preview.visual.face_colors = face_colors
    preview_path = out_dir / f"{name}_mask_preview.glb"
    preview.export(preview_path)

    selected = np.flatnonzero(face_mask)
    part_path = out_dir / f"{name}_candidate.glb"
    if len(selected):
        part = mesh.submesh([selected], append=True, repair=False)
        part.export(part_path)

    point_colors = np.tile(np.array([[125, 125, 125, 255]], dtype=np.uint8), (len(points_raw), 1))
    point_colors[point_mask] = np.array([40, 150, 255, 255], dtype=np.uint8)
    points_path = out_dir / f"{name}_points.glb"
    trimesh.points.PointCloud(points_raw, colors=point_colors).export(points_path)

    return {
        "preview": str(preview_path),
        "candidate": str(part_path),
        "points": str(points_path),
        "point_count": int(point_mask.sum()),
        "face_count": int(face_mask.sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--point_num", type=int, default=10000)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    mesh = trimesh.load(args.mesh, force="mesh", process=False)
    points_raw, face_idx = trimesh.sample.sample_surface(mesh, args.point_num, seed=42)
    points = normalize_pc(points_raw)
    normals = mesh.face_normals[face_idx]

    model = P3SAM()
    model.load_state_dict(args.ckpt)
    model.eval().cuda()
    feats = get_feat(model, points, normals)

    face_centers = mesh.triangles_center
    nearest = cKDTree(points_raw).query(face_centers, workers=-1)[1]
    records = {}
    for name in ("hair_wig", "adventurer_jacket", "trousers", "boots"):
        vertex_index, prompt_raw = choose_prompt(mesh.vertices, name)
        prompt = normalize_point(prompt_raw, mesh.vertices)
        masks = get_mask(model, feats, points, prompt)
        mask_list = masks[:3]
        ious = [float(masks[3]), float(masks[4]), float(masks[5])]
        best = int(np.argmax(ious))
        point_mask = mask_list[best]
        face_mask = point_mask[nearest]
        records[name] = {
            "vertex_index": vertex_index,
            "prompt_raw": prompt_raw.tolist(),
            "prompt_normalized": prompt.tolist(),
            "best_mask": best + 1,
            "ious": ious,
            "artifacts": export_candidate(mesh, face_mask, point_mask, points_raw, out_dir, name),
        }
        torch.cuda.empty_cache()
        print(name, records[name]["best_mask"], records[name]["ious"], records[name]["artifacts"])

    (out_dir / "manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
