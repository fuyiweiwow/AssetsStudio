"""Break down GarmentCode self-intersections by cloth panel/spring labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--garmentcode-root", type=Path, required=True)
    parser.add_argument("--pattern-spec", type=Path, required=True)
    parser.add_argument("--body-obj", type=Path, required=True)
    parser.add_argument("--body-measurements", type=Path, required=True)
    parser.add_argument("--body-segmentation", type=Path, required=True)
    parser.add_argument("--final-sim-obj", type=Path, required=True)
    parser.add_argument("--panel-membership", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.garmentcode_root.resolve()
    pattern_spec_path = args.pattern_spec.resolve()
    body_obj_path = args.body_obj.resolve()
    body_measurements_path = args.body_measurements.resolve()
    body_segmentation_path = args.body_segmentation.resolve()
    final_sim_path = args.final_sim_obj.resolve()
    panel_membership_path = args.panel_membership.resolve()
    output_path = args.output.resolve()
    sys.path.insert(0, str(root))
    import numpy as np
    import warp as wp
    import pygarment.data_config as data_config
    from pygarment.meshgen.garment import Cloth
    from pygarment.meshgen.boxmeshgen import BoxMesh
    from pygarment.meshgen.sim_config import PathCofig, SimConfig
    wp.init()

    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    membership = json.loads(panel_membership_path.read_text(encoding="utf-8"))
    if membership.get("schema") != "assetsstudio_garmentcode_panel_membership_v1":
        raise RuntimeError(f"unsupported panel-membership schema: {panel_membership_path}")
    if membership.get("sim_obj", {}).get("sha256") != sha256(final_sim_path):
        raise RuntimeError("panel-membership/simulation hash mismatch")
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

    sim_config_path = root / "assets/Sim_props/default_sim_props.yaml"
    props = data_config.Properties(str(sim_config_path))
    props["sim"]["config"]["max_frame_time"] = None
    original_cwd = Path.cwd()
    os.chdir(root)
    try:
        garment_name = args.pattern_spec.stem.rpartition("_specification")[0]
        paths = PathCofig(
            in_element_path=pattern_spec_path.parent,
            out_path=str(output_path),
            in_name=garment_name,
            body_name="mean_all",
            smpl_body=False,
            add_timestamp=True,
        )
        paths.in_body_obj = body_obj_path
        paths.in_body_mes = body_measurements_path
        paths.body_seg = body_segmentation_path
        # PathCofig derives in_g_spec from the post-chdir cwd.  Restore the
        # project-owned absolute specification before constructing BoxMesh.
        paths.in_g_spec = pattern_spec_path
        box = BoxMesh(paths.in_g_spec, props["sim"]["config"]["resolution_scale"])
        box.load()
        box.serialize(paths, store_panels=False, uv_config=props["render"]["config"]["uv_texture"])
        props.serialize(paths.element_sim_props)
        config = SimConfig(props["sim"]["config"])
        garment = Cloth(box.name, config, paths, caching=False)
        final_vertices, _, _ = garment.load_obj(final_sim_path)
        if len(final_vertices) != garment.model.particle_count:
            raise RuntimeError("final OBJ vertex count does not match Cloth particle count")

        points = np.asarray(final_vertices, dtype=np.float32)
        indices = np.asarray(garment.f_cloth, dtype=np.int32).reshape(-1, 3)
        springs = np.asarray(wp.array.numpy(garment.model.spring_indices), dtype=np.int32).reshape(-1, 2)
        labels = paths.g_mesh_segmentation.read_text(encoding="utf-8").splitlines()
        if len(labels) != len(points):
            raise RuntimeError("cloth segmentation count does not match final OBJ")
        if len(vertex_panels) != len(points):
            raise RuntimeError("panel membership count does not match final OBJ")

        # CPU equivalent of the GarmentCode/Warp mesh_query_edge test.  The
        # bundled Warp is old enough that its custom-kernel array indexing
        # cannot be compiled from an external script, so keep the official
        # spring criterion but evaluate it here.
        tri = points[indices]
        tri_v0 = tri[:, 0]
        tri_e1 = tri[:, 1] - tri_v0
        tri_e2 = tri[:, 2] - tri_v0
        hit_values = np.zeros(len(springs), dtype=np.int32)
        face_values = np.full(len(springs), -1, dtype=np.int32)
        hit_distances = np.full(len(springs), np.nan, dtype=np.float32)
        edge_origins = points[springs[:, 0]]
        edge_ends = points[springs[:, 1]]
        edge_delta = edge_ends - edge_origins
        edge_lengths = np.linalg.norm(edge_delta, axis=1)
        valid = edge_lengths > 1.0e-8
        edge_dirs = np.zeros_like(edge_delta)
        edge_dirs[valid] = edge_delta[valid] / edge_lengths[valid, None]
        for start in range(0, len(springs), 128):
            stop = min(start + 128, len(springs))
            origins = edge_origins[start:stop]
            directions = edge_dirs[start:stop]
            lengths = edge_lengths[start:stop]
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
            endpoint_a = springs[start:stop, 0, None, None]
            endpoint_b = springs[start:stop, 1, None, None]
            tri_indices = indices[None, :, :]
            adjacent = (tri_indices == endpoint_a) | (tri_indices == endpoint_b)
            crossed = (
                non_parallel & ~np.any(adjacent, axis=2)
                & (u >= 0.0) & (u <= 1.0) & (v >= 0.0) & (u + v <= 1.0)
                & (t >= 0.0) & (t <= lengths[:, None] + 1.0e-5)
            )
            any_crossed = np.any(crossed, axis=1)
            hit_values[start:stop] = any_crossed.astype(np.int32)
            if np.any(any_crossed):
                first = np.argmax(crossed, axis=1)
                face_values[start:stop][any_crossed] = first[any_crossed]
                batch_rows = np.arange(stop - start)
                local_distances = hit_distances[start:stop]
                local_distances[any_crossed] = t[batch_rows, first][any_crossed]

        endpoint_counts = Counter()
        pair_counts = Counter()
        crossing_family_pair_counts = Counter()
        crossing_height_bin_counts = Counter()
        crossing_panel_pair_counts = Counter()
        crossing_region_counts = Counter()
        same_panel_overlap_count = 0
        records = []
        for spring_index, value in enumerate(hit_values):
            if not value:
                continue
            e0, e1 = springs[spring_index]
            l0, l1 = labels[int(e0)], labels[int(e1)]
            pair = "|".join(sorted((l0, l1)))
            endpoint_counts[l0] += 1
            endpoint_counts[l1] += 1
            pair_counts[pair] += 1
            face_index = int(face_values[spring_index])
            face_vertices = [int(value) for value in indices[face_index]]
            spring_panels = set(vertex_panels[int(e0)]) | set(vertex_panels[int(e1)])
            face_panels = set()
            for face_vertex in face_vertices:
                face_panels.update(vertex_panels[face_vertex])
            spring_family = families(spring_panels)
            face_family = families(face_panels)
            family_pair = "|".join(sorted((spring_family, face_family)))
            panel_pair = "|".join(("+".join(sorted(spring_panels)), "+".join(sorted(face_panels))))
            crossing_family_pair_counts[family_pair] += 1
            crossing_panel_pair_counts[panel_pair] += 1
            midpoint_y = float((points[int(e0), 1] + points[int(e1), 1]) * 0.5)
            height_bin = f"{int(midpoint_y // 10) * 10:03d}-{int(midpoint_y // 10) * 10 + 10:03d}cm"
            crossing_height_bin_counts[height_bin] += 1
            crossing_point = edge_origins[spring_index] + edge_dirs[spring_index] * hit_distances[spring_index]
            all_panels = spring_panels | face_panels
            has_cuff = any("cuff" in name for name in all_panels)
            has_sleeve = any("sleeve" in name or "cuff" in name for name in all_panels)
            has_torso = any("torso" in name for name in all_panels)
            if has_cuff and has_torso:
                region = "cuff_torso"
            elif has_cuff:
                region = "cuff"
            elif has_sleeve and has_torso:
                region = "armhole"
            elif has_sleeve:
                region = "sleeve"
            elif has_torso:
                region = "torso"
            else:
                region = "unknown"
            crossing_region_counts[region] += 1
            same_panel_overlap = bool(spring_panels & face_panels)
            same_panel_overlap_count += int(same_panel_overlap)
            records.append({
                "spring": int(spring_index),
                "vertices": [int(e0), int(e1)],
                "labels": [l0, l1],
                "spring_panels": sorted(spring_panels),
                "spring_family": spring_family,
                "face": face_index,
                "face_vertices": face_vertices,
                "face_panels": sorted(face_panels),
                "face_family": face_family,
                "family_pair": family_pair,
                "panel_pair": panel_pair,
                "region": region,
                "same_panel_overlap": same_panel_overlap,
                "spring_midpoint_y_cm": midpoint_y,
                "crossing_point_cm": [float(value) for value in crossing_point],
                "face_centroid_cm": [float(value) for value in points[face_vertices].mean(axis=0)],
            })

        cluster_radius_cm = 4.0
        crossing_points = np.asarray([record["crossing_point_cm"] for record in records], dtype=np.float32)
        parents = list(range(len(records)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        radius_squared = cluster_radius_cm * cluster_radius_cm
        for left in range(len(crossing_points)):
            squared_distances = np.sum(
                (crossing_points[left + 1:] - crossing_points[left]) ** 2,
                axis=1,
            )
            for offset in np.flatnonzero(squared_distances <= radius_squared):
                union(left, left + 1 + int(offset))

        cluster_members: dict[int, list[int]] = {}
        for index in range(len(records)):
            cluster_members.setdefault(find(index), []).append(index)
        spatial_clusters = []
        for member_indices in cluster_members.values():
            if len(member_indices) < 2:
                continue
            member_points = crossing_points[member_indices]
            member_records = [records[index] for index in member_indices]
            spatial_clusters.append({
                "count": len(member_indices),
                "centroid_cm": [float(value) for value in member_points.mean(axis=0)],
                "bounds_cm": [
                    [float(value) for value in member_points.min(axis=0)],
                    [float(value) for value in member_points.max(axis=0)],
                ],
                "region_counts": Counter(record["region"] for record in member_records),
                "family_pair_counts": Counter(record["family_pair"] for record in member_records),
                "top_panel_pairs": Counter(record["panel_pair"] for record in member_records).most_common(8),
                "same_panel_overlap_count": sum(record["same_panel_overlap"] for record in member_records),
                "spring_indices": [record["spring"] for record in member_records],
            })
        spatial_clusters.sort(key=lambda cluster: cluster["count"], reverse=True)

        payload = {
            "schema": "assetsstudio_garmentcode_self_intersection_diagnostic_v1",
            "pattern_spec": str(pattern_spec_path),
            "final_sim_obj": str(final_sim_path),
            "particle_count": int(len(points)),
            "spring_count": int(len(springs)),
            "self_intersection_count": int(hit_values.sum()),
            "crossing_endpoint_label_counts": endpoint_counts,
            "crossing_label_pair_counts": pair_counts,
            "crossing_family_pair_counts": crossing_family_pair_counts,
            "crossing_height_bin_counts": crossing_height_bin_counts,
            "crossing_panel_pair_counts": crossing_panel_pair_counts,
            "crossing_region_counts": crossing_region_counts,
            "same_panel_overlap_count": same_panel_overlap_count,
            "spatial_cluster_radius_cm": cluster_radius_cm,
            "spatial_cluster_count": len(spatial_clusters),
            "isolated_crossing_count": sum(len(members) == 1 for members in cluster_members.values()),
            "spatial_clusters": spatial_clusters,
            "crossing_springs": records,
            "query": "Warp mesh_query_edge on the final simulated cloth mesh, matching GarmentCode Cloth.count_self_intersections",
        }
        output = output_path
        output.mkdir(parents=True, exist_ok=True)
        (output / "self_intersection_diagnostic.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in payload.items() if k != "crossing_springs"}, indent=2))
        return 0
    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    raise SystemExit(main())
