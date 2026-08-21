from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree


GARMENT_NAME = "Wearable_Adventurer_TorsoOuterV1"
FRAMES = [1, 11, 21, 31, 41, 51, 61, 71]
TORSO_BONES = {"CC_Base_Waist", "CC_Base_Spine01", "CC_Base_Spine02"}
SIDE_BONES = {
    "left": {
        "CC_Base_L_Clavicle",
        "CC_Base_L_Upperarm",
        "CC_Base_L_Forearm",
        "CC_Base_L_Hand",
    },
    "right": {
        "CC_Base_R_Clavicle",
        "CC_Base_R_Upperarm",
        "CC_Base_R_Forearm",
        "CC_Base_R_Hand",
    },
}


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def vertex_weight(vertex: bpy.types.MeshVertex, indices: set[int]) -> float:
    return sum(item.weight for item in vertex.groups if item.group in indices)


def main() -> int:
    options = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    scene = bpy.context.scene
    garment = bpy.data.objects.get(GARMENT_NAME)
    if garment is None:
        raise RuntimeError(f"garment missing: {GARMENT_NAME}")

    group_indices = {group.name: group.index for group in garment.vertex_groups}
    torso_indices = {group_indices[name] for name in TORSO_BONES if name in group_indices}
    side_indices = {
        side: {group_indices[name] for name in names if name in group_indices}
        for side, names in SIDE_BONES.items()
    }

    torso_weight = [vertex_weight(vertex, torso_indices) for vertex in garment.data.vertices]
    side_weight = {
        side: [vertex_weight(vertex, indices) for vertex in garment.data.vertices]
        for side, indices in side_indices.items()
    }

    # The generated shell is one mesh. Partition faces by the weights that drive
    # them so the audit can test non-adjacent sleeve triangles against torso
    # triangles without counting their intentionally shared armhole boundary.
    face_vertices = [tuple(poly.vertices) for poly in garment.data.polygons]
    partitions: dict[str, dict[str, list[int]]] = {}
    for side in SIDE_BONES:
        sleeve_faces: list[int] = []
        torso_faces: list[int] = []
        for poly in garment.data.polygons:
            vertices = tuple(poly.vertices)
            arm_average = sum(side_weight[side][index] for index in vertices) / len(vertices)
            torso_average = sum(torso_weight[index] for index in vertices) / len(vertices)
            if arm_average >= 0.40 and arm_average > torso_average:
                sleeve_faces.append(poly.index)
            elif torso_average >= 0.40 and torso_average >= arm_average:
                torso_faces.append(poly.index)
        partitions[side] = {"sleeve": sleeve_faces, "torso": torso_faces}

    report = {
        "schema": "sleeve_torso_self_intersection_v1",
        "input_blend": str(options.input_blend.resolve()),
        "garment": GARMENT_NAME,
        "partition_rule": "average semantic weight >= 0.40 and dominant over opposite region",
        "partitions": {
            side: {
                "sleeve_faces": len(parts["sleeve"]),
                "torso_faces": len(parts["torso"]),
            }
            for side, parts in partitions.items()
        },
        "frames": {},
    }

    for frame in FRAMES:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        evaluated = garment.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        frame_report = {}
        for side, parts in partitions.items():
            sleeve_faces = parts["sleeve"]
            torso_faces = parts["torso"]
            sleeve_polys = [face_vertices[index] for index in sleeve_faces]
            torso_polys = [face_vertices[index] for index in torso_faces]
            sleeve_tree = BVHTree.FromPolygons(points, sleeve_polys, all_triangles=True)
            torso_tree = BVHTree.FromPolygons(points, torso_polys, all_triangles=True)
            raw_pairs = sleeve_tree.overlap(torso_tree)

            non_adjacent_pairs = []
            for sleeve_local, torso_local in raw_pairs:
                sleeve_index = sleeve_faces[sleeve_local]
                torso_index = torso_faces[torso_local]
                if set(face_vertices[sleeve_index]).isdisjoint(face_vertices[torso_index]):
                    non_adjacent_pairs.append((sleeve_index, torso_index))
            frame_report[side] = {
                "raw_overlap_pairs": len(raw_pairs),
                "non_adjacent_intersection_pairs": len(non_adjacent_pairs),
                "sample_face_pairs": non_adjacent_pairs[:16],
            }
        evaluated.to_mesh_clear()
        report["frames"][str(frame)] = frame_report

    counts = [
        side_report["non_adjacent_intersection_pairs"]
        for frame_report in report["frames"].values()
        for side_report in frame_report.values()
    ]
    report["summary"] = {
        "maximum_non_adjacent_intersection_pairs": max(counts),
        "frames_with_intersection": sum(value > 0 for value in counts),
        "side_frame_tests": len(counts),
        "interpretation": (
            "Non-adjacent pairs confirm that differently weighted regions of the single "
            "generated shell fold through each other; an armhole deformation contract is required."
        ),
    }
    options.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
