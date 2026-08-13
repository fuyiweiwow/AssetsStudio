"""Diagnose which GarmentCode cloth springs cross the Actor body proxy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--garmentcode-root", type=Path, required=True)
    parser.add_argument("--pattern-spec", type=Path, required=True)
    parser.add_argument("--body-obj", type=Path, required=True)
    parser.add_argument("--body-measurements", type=Path, required=True)
    parser.add_argument("--body-segmentation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attachment-frames", type=int, default=100)
    parser.add_argument("--final-sim-obj", type=Path)
    parser.add_argument("--initial-boxmesh", action="store_true")
    parser.add_argument("--panel-membership", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for label, path in (
        ("GarmentCode root", args.garmentcode_root),
        ("pattern spec", args.pattern_spec),
        ("body obj", args.body_obj),
        ("body measurements", args.body_measurements),
        ("body segmentation", args.body_segmentation),
    ):
        if not (path.is_dir() if label == "GarmentCode root" else path.is_file()):
            raise FileNotFoundError(f"missing {label}: {path}")

    pattern_spec_path = args.pattern_spec.resolve()
    body_obj_path = args.body_obj.resolve()
    body_measurements_path = args.body_measurements.resolve()
    body_segmentation_path = args.body_segmentation.resolve()
    final_sim_path = args.final_sim_obj.resolve() if args.final_sim_obj else None
    panel_membership_path = args.panel_membership.resolve()
    output_path = args.output.resolve()

    root = args.garmentcode_root.resolve()
    sys.path.insert(0, str(root))
    import numpy as np
    import warp as wp
    import pygarment.data_config as data_config
    from pygarment.meshgen.boxmeshgen import BoxMesh
    from pygarment.meshgen.garment import Cloth
    from pygarment.meshgen.sim_config import PathCofig, SimConfig
    from pygarment.meshgen.simulation import sim_frame_sequence

    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    membership = json.loads(panel_membership_path.read_text(encoding="utf-8"))
    if membership.get("schema") != "assetsstudio_garmentcode_panel_membership_v1":
        raise RuntimeError(f"unsupported panel-membership schema: {panel_membership_path}")
    if membership.get("pattern_spec", {}).get("sha256") != sha256(pattern_spec_path):
        raise RuntimeError("panel-membership/pattern hash mismatch")
    vertex_panels = membership["vertex_panels"]

    def families(panel_names: set[str]) -> str:
        result = []
        if any(name.startswith("left_sleeve_") or name.startswith("sl_left_cuff_") for name in panel_names):
            result.append("left_sleeve")
        if any(name.startswith("right_sleeve_") or name.startswith("sl_right_cuff_") for name in panel_names):
            result.append("right_sleeve")
        if any("torso" in name for name in panel_names):
            result.append("torso")
        return "+".join(result) if result else "unknown"

    sim_config = root / "assets/Sim_props/default_sim_props.yaml"
    system = root / "system.json"
    props = data_config.Properties(str(sim_config))
    props["sim"]["config"]["max_frame_time"] = None
    props["sim"]["config"]["attachment_frames"] = args.attachment_frames
    props.set_section_stats(
        "sim", fails={}, sim_time={}, spf={}, fin_frame={},
        body_collisions={}, self_collisions={}
    )
    props.set_section_stats("render", render_time={})

    original_cwd = Path.cwd()
    os.chdir(root)
    try:
        system_props = data_config.Properties(str(system))
        # Keep the absolute path resolved before chdir; otherwise the relative
        # CLI path is incorrectly relocated under GarmentCode/workspace.
        pattern_spec = pattern_spec_path
        garment_name = pattern_spec.stem.rpartition("_specification")[0]
        paths = PathCofig(
            in_element_path=pattern_spec.parent,
            out_path=str(output_path),
            in_name=garment_name,
            body_name="mean_all",
            smpl_body=False,
            add_timestamp=True,
        )
        paths.in_body_obj = body_obj_path
        paths.in_body_mes = body_measurements_path
        paths.body_seg = body_segmentation_path

        box = BoxMesh(paths.in_g_spec, props["sim"]["config"]["resolution_scale"])
        box.load()
        box.serialize(paths, store_panels=False, uv_config=props["render"]["config"]["uv_texture"])
        props.serialize(paths.element_sim_props)

        config = SimConfig(props["sim"]["config"])
        garment = Cloth(box.name, config, paths, caching=False)
        if args.final_sim_obj and args.initial_boxmesh:
            raise ValueError("use either --final-sim-obj or --initial-boxmesh, not both")
        if args.final_sim_obj:
            if not final_sim_path.is_file():
                raise FileNotFoundError(f"missing final sim obj: {final_sim_path}")
            final_vertices, _, _ = garment.load_obj(final_sim_path)
            if len(final_vertices) != garment.model.particle_count:
                raise RuntimeError(
                    f"final sim vertex count {len(final_vertices)} does not match particles "
                    f"{garment.model.particle_count}"
                )
            cloth_positions = np.asarray(final_vertices, dtype=np.float32)
            sim_frames = None
            position_source = "final_sim_obj"
        elif args.initial_boxmesh:
            cloth_positions = np.asarray(garment.v_cloth_init, dtype=np.float32)
            sim_frames = 0
            position_source = "initial_boxmesh"
        else:
            sim_frame_sequence(garment, config, store_usd=False, verbose=False)
            cloth_positions = np.asarray(wp.array.numpy(garment.state_0.particle_q), dtype=np.float32)
            sim_frames = garment.frame + 1
            position_source = "fresh_simulation"

        model = garment.model
        spring_indices = np.asarray(wp.array.numpy(model.spring_indices), dtype=np.int32).reshape(-1, 2)
        edge_origins = cloth_positions[spring_indices[:, 0]]
        edge_ends = cloth_positions[spring_indices[:, 1]]
        edge_delta = edge_ends - edge_origins
        edge_lengths = np.linalg.norm(edge_delta, axis=1)
        valid = edge_lengths > 1.0e-8
        edge_directions = np.zeros_like(edge_delta)
        edge_directions[valid] = edge_delta[valid] / edge_lengths[valid, None]
        mark_values = np.zeros(model.spring_count, dtype=int)
        hit_face_values = np.full(model.spring_count, -1, dtype=int)
        hit_distance_values = np.full(model.spring_count, np.nan, dtype=np.float32)
        body_faces = np.asarray(garment.f_body, dtype=np.int64)
        body_triangles = np.asarray(garment.v_body, dtype=np.float32)[
            body_faces
        ]
        tri_v0 = body_triangles[:, 0]
        tri_e1 = body_triangles[:, 1] - tri_v0
        tri_e2 = body_triangles[:, 2] - tri_v0
        valid_indices = np.flatnonzero(valid)
        ray_origins = edge_origins[valid]
        ray_directions = edge_directions[valid]
        ray_lengths = edge_lengths[valid]
        for start in range(0, len(ray_origins), 128):
            stop = min(start + 128, len(ray_origins))
            origins = ray_origins[start:stop]
            directions = ray_directions[start:stop]
            h = np.cross(directions[:, None, :], tri_e2[None, :, :])
            a = np.einsum("bti,ti->bt", h, tri_e1)
            non_parallel = np.abs(a) > 1.0e-8
            inv_a = np.zeros_like(a)
            inv_a[non_parallel] = 1.0 / a[non_parallel]
            s = origins[:, None, :] - tri_v0[None, :, :]
            u = inv_a * np.einsum("bti,bti->bt", s, h)
            q = np.cross(s, tri_e1[None, :, :])
            v = inv_a * np.einsum("bti,bti->bt", directions[:, None, :], q)
            t = inv_a * np.einsum("bti,bti->bt", tri_e2[None, :, :], q)
            hit = (
                non_parallel
                & (u >= 0.0)
                & (u <= 1.0)
                & (v >= 0.0)
                & (u + v <= 1.0)
                & (t >= 0.0)
                & (t <= ray_lengths[start:stop, None] + 1.0e-5)
            )
            batch_has_hit = np.any(hit, axis=1)
            batch_indices = valid_indices[start:stop]
            mark_values[batch_indices] = batch_has_hit.astype(int)
            if np.any(batch_has_hit):
                masked_t = np.where(hit, t, np.inf)
                nearest_faces = np.argmin(masked_t, axis=1)
                hit_rows = np.flatnonzero(batch_has_hit)
                hit_springs = batch_indices[hit_rows]
                hit_face_values[hit_springs] = nearest_faces[hit_rows]
                hit_distance_values[hit_springs] = masked_t[hit_rows, nearest_faces[hit_rows]]

        body_segmentation = json.loads(body_segmentation_path.read_text(encoding="utf-8"))
        body_vertex_regions: dict[int, list[str]] = {}
        for region, vertex_indices in body_segmentation.items():
            for vertex_index in vertex_indices:
                body_vertex_regions.setdefault(int(vertex_index), []).append(region)

        def body_face_region(face_index: int) -> str:
            region_counts: Counter[str] = Counter()
            for vertex_index in body_faces[face_index]:
                for region in body_vertex_regions.get(int(vertex_index), ["unsegmented"]):
                    region_counts[region] += 1
            if not region_counts:
                return "unsegmented"
            top_count = max(region_counts.values())
            return "+".join(sorted(region for region, count in region_counts.items() if count == top_count))
        labels = paths.g_mesh_segmentation.read_text(encoding="utf-8").splitlines()
        if len(labels) != model.particle_count:
            raise RuntimeError(
                f"segmentation count {len(labels)} does not match particles {model.particle_count}"
            )
        if len(vertex_panels) != model.particle_count:
            raise RuntimeError("panel membership count does not match particles")

        all_pair_counts: Counter[str] = Counter()
        all_endpoint_counts: Counter[str] = Counter()
        for e0, e1 in spring_indices:
            l0, l1 = labels[int(e0)], labels[int(e1)]
            all_pair_counts["|".join(sorted((l0, l1)))] += 1
            all_endpoint_counts[l0] += 1
            all_endpoint_counts[l1] += 1

        pair_counts: Counter[str] = Counter()
        endpoint_counts: Counter[str] = Counter()
        family_counts: Counter[str] = Counter()
        panel_counts: Counter[str] = Counter()
        body_region_counts: Counter[str] = Counter()
        family_body_region_counts: Counter[str] = Counter()
        height_bin_counts: Counter[str] = Counter()
        x_bin_counts: Counter[str] = Counter()
        crossing_records = []
        for index, mark in enumerate(mark_values):
            if not mark:
                continue
            e0, e1 = spring_indices[index]
            l0, l1 = labels[int(e0)], labels[int(e1)]
            pair = "|".join(sorted((l0, l1)))
            pair_counts[pair] += 1
            endpoint_counts[l0] += 1
            endpoint_counts[l1] += 1
            panels = set(vertex_panels[int(e0)]) | set(vertex_panels[int(e1)])
            family = families(panels)
            family_counts[family] += 1
            panel_counts["+".join(sorted(panels))] += 1
            midpoint = (cloth_positions[int(e0)] + cloth_positions[int(e1)]) * 0.5
            midpoint_y = float(midpoint[1])
            height_bin = f"{int(midpoint_y // 10) * 10:03d}-{int(midpoint_y // 10) * 10 + 10:03d}cm"
            height_bin_counts[height_bin] += 1
            midpoint_x = float(midpoint[0])
            x_bin_start = int(midpoint_x // 10) * 10
            x_bin = f"{x_bin_start:+04d}-{x_bin_start + 10:+04d}cm"
            x_bin_counts[x_bin] += 1
            face_index = int(hit_face_values[index])
            hit_distance = float(hit_distance_values[index])
            intersection_point = edge_origins[index] + edge_directions[index] * hit_distance
            body_region = body_face_region(face_index)
            body_region_counts[body_region] += 1
            family_body_region_counts[f"{family}|{body_region}"] += 1
            crossing_records.append({
                "spring": int(index),
                "vertices": [int(e0), int(e1)],
                "labels": [l0, l1],
                "panels": sorted(panels),
                "family": family,
                "body_face": face_index,
                "body_face_vertices": [int(value) for value in body_faces[face_index]],
                "body_region": body_region,
                "spring_midpoint_cm": [float(value) for value in midpoint],
                "spring_midpoint_y_cm": midpoint_y,
                "intersection_point_cm": [float(value) for value in intersection_point],
            })

        crossing_points = np.asarray(
            [record["intersection_point_cm"] for record in crossing_records], dtype=np.float32
        )
        spatial_clusters = []
        if len(crossing_points):
            threshold_cm = 4.0
            parent = np.arange(len(crossing_points), dtype=np.int32)

            def find(value: int) -> int:
                while parent[value] != value:
                    parent[value] = parent[parent[value]]
                    value = int(parent[value])
                return value

            def union(left: int, right: int) -> None:
                root_left, root_right = find(left), find(right)
                if root_left != root_right:
                    parent[root_right] = root_left

            for left in range(len(crossing_points)):
                distances = np.linalg.norm(crossing_points[left + 1:] - crossing_points[left], axis=1)
                for relative_right in np.flatnonzero(distances <= threshold_cm):
                    union(left, left + 1 + int(relative_right))
            cluster_members: dict[int, list[int]] = {}
            for point_index in range(len(crossing_points)):
                cluster_members.setdefault(find(point_index), []).append(point_index)
            for members in sorted(cluster_members.values(), key=len, reverse=True):
                member_records = [crossing_records[index] for index in members]
                spatial_clusters.append({
                    "count": len(members),
                    "centroid_cm": [float(value) for value in crossing_points[members].mean(axis=0)],
                    "body_region_counts": Counter(record["body_region"] for record in member_records),
                    "family_counts": Counter(record["family"] for record in member_records),
                    "panel_counts": Counter(
                        "+".join(record["panels"]) for record in member_records
                    ),
                })

        report = {
            "schema": "assetsstudio_actor_garmentcode_collision_spring_diagnostic_v1",
            "pattern_spec": str(pattern_spec),
            "body_obj": str(body_obj_path),
            "body_measurements": str(body_measurements_path),
            "body_segmentation": str(body_segmentation_path),
            "attachment_frames": args.attachment_frames,
            "sim_frames": sim_frames,
            "position_source": position_source,
            "final_sim_obj": str(final_sim_path) if final_sim_path else None,
            "particle_count": int(model.particle_count),
            "spring_count": int(model.spring_count),
            "body_collision_count": int(mark_values.sum()),
            "all_spring_endpoint_label_counts": all_endpoint_counts,
            "all_spring_label_pair_counts": all_pair_counts,
            "crossing_endpoint_label_counts": endpoint_counts,
            "crossing_label_pair_counts": pair_counts,
            "crossing_family_counts": family_counts,
            "crossing_panel_counts": panel_counts,
            "crossing_body_region_counts": body_region_counts,
            "crossing_family_body_region_counts": family_body_region_counts,
            "crossing_height_bin_counts": height_bin_counts,
            "crossing_x_bin_counts": x_bin_counts,
            "spatial_cluster_threshold_cm": 4.0,
            "spatial_clusters": spatial_clusters,
            "crossing_springs": crossing_records,
            "note": "CPU finite-segment triangle intersection fallback equivalent to GarmentCode's mesh_query_ray spring criterion; Warp source/API mismatch prevented compiling a standalone diagnostic kernel.",
        }
        output = output_path
        output.mkdir(parents=True, exist_ok=True)
        report_path = output / "collision_spring_diagnostic.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k != "crossing_springs"}, indent=2))
        return 0
    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    raise SystemExit(main())
