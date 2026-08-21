from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE_NAME = "Armature"
GARMENT_NAME = "Wearable_Hunyuan2MV_ZipJacket"
MASK_NAME = "WearableMask_HunyuanZipJacketV1"
MASK_MODIFIER = "PreviewBodyHide_HunyuanZipJacketV1"
NECK_SEAL_NAME = "ActorProfile_NeckSeal_ChibiActorV1"
ALLOWED_BONES = {
    "CC_Base_Waist", "CC_Base_Spine01", "CC_Base_Spine02",
    "CC_Base_L_Clavicle", "CC_Base_L_Upperarm", "CC_Base_L_Forearm", "CC_Base_L_Hand",
    "CC_Base_R_Clavicle", "CC_Base_R_Upperarm", "CC_Base_R_Forearm", "CC_Base_R_Hand",
}
FRAMES = [1, 11, 21, 31, 41, 51, 61, 71]
MAX_CONTACT_PAIRS_PER_FRAME = 16
MAX_CONTACT_ACTOR_FACES_PER_FRAME = 2
SHOULDER_BRIDGE_LIMITS = {
    "front": {"inner": 1.44, "middle": 1.44, "outer": 1.45},
    "back": {"inner": 1.47, "middle": 1.46, "outer": 1.47},
}
SHOULDER_BRIDGE_BANDS = {
    "inner": (0.12, 0.18),
    "middle": (0.18, 0.24),
    "outer": (0.24, 0.30),
}


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def main() -> int:
    args = cli()
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    scene = bpy.context.scene
    actor = bpy.data.objects.get(ACTOR_NAME)
    armature = bpy.data.objects.get(ARMATURE_NAME)
    garment = bpy.data.objects.get(GARMENT_NAME)
    neck_seal = bpy.data.objects.get(NECK_SEAL_NAME)
    if actor is None or armature is None or garment is None or neck_seal is None:
        raise RuntimeError("canonical Actor, Armature, Hunyuan jacket, or neck seal missing")

    failures: list[str] = []
    group_names = {group.index: group.name for group in garment.vertex_groups}
    used_groups = {
        group_names[item.group]
        for vertex in garment.data.vertices
        for item in vertex.groups
        if item.weight > 1e-7
    }
    forbidden = sorted(used_groups - ALLOWED_BONES)
    unweighted = 0
    non_normalized = 0
    max_weight_error = 0.0
    for vertex in garment.data.vertices:
        total = sum(item.weight for item in vertex.groups if item.weight > 1e-7)
        error = abs(total - 1.0)
        max_weight_error = max(max_weight_error, error)
        unweighted += total <= 1e-7
        non_normalized += total > 1e-7 and error > 1e-4
    if forbidden:
        failures.append(f"forbidden weight groups: {forbidden}")
    if unweighted:
        failures.append(f"unweighted vertices: {unweighted}")
    if non_normalized:
        failures.append(f"non-normalized vertices: {non_normalized}")

    armature_modifiers = [m for m in garment.modifiers if m.type == "ARMATURE" and m.object == armature]
    if len(armature_modifiers) != 1:
        failures.append(f"expected one Actor Armature modifier, found {len(armature_modifiers)}")
    mask = actor.vertex_groups.get(MASK_NAME)
    mask_count = 0
    if mask is None:
        failures.append(f"missing body mask: {MASK_NAME}")
    else:
        mask_count = sum(
            any(item.group == mask.index and item.weight > 0.0 for item in vertex.groups)
            for vertex in actor.data.vertices
        )
    mask_modifier = actor.modifiers.get(MASK_MODIFIER)
    if mask_modifier is None or mask_modifier.type != "MASK" or not mask_modifier.invert_vertex_group:
        failures.append("body mask is not applied to the review Actor")

    frame_reports = {}
    total_intersections = 0
    total_degenerate = 0
    excessive_contact_frames = []
    evaluated_topology = None
    shoulder_bridge_report = None
    for frame in FRAMES:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        actor_eval = actor.evaluated_get(depsgraph)
        actor_mesh = actor_eval.to_mesh()
        actor_points = [actor_eval.matrix_world @ vertex.co for vertex in actor_mesh.vertices]
        actor_faces = [list(face.vertices) for face in actor_mesh.polygons]
        bvh = BVHTree.FromPolygons(actor_points, actor_faces, all_triangles=False)

        garment_eval = garment.evaluated_get(depsgraph)
        garment_mesh = garment_eval.to_mesh()
        topology = (len(garment_mesh.vertices), len(garment_mesh.polygons))
        if evaluated_topology is None:
            evaluated_topology = topology
        elif topology != evaluated_topology:
            failures.append(f"evaluated topology changed at frame {frame}")

        garment_points = [garment_eval.matrix_world @ vertex.co for vertex in garment_mesh.vertices]
        if frame == 1:
            shoulder_bridge_report = {}
            for side, side_limits in SHOULDER_BRIDGE_LIMITS.items():
                side_report = {}
                for band, minimum_z in side_limits.items():
                    low_x, high_x = SHOULDER_BRIDGE_BANDS[band]
                    heights = [
                        point.z
                        for point in garment_points
                        if low_x <= abs(point.x) <= high_x
                        and point.z >= 1.25
                        and (point.y < -0.02 if side == "front" else point.y > 0.02)
                    ]
                    p95_z = percentile(heights, 0.95)
                    side_report[band] = {
                        "vertex_count": len(heights),
                        "p95_z": p95_z,
                        "minimum_p95_z": minimum_z,
                    }
                    if p95_z is None or p95_z < minimum_z:
                        failures.append(
                            f"{side} {band} shoulder bridge p95 z {p95_z} below {minimum_z}"
                        )
                shoulder_bridge_report[side] = side_report
        garment_faces = [list(face.vertices) for face in garment_mesh.polygons]
        garment_bvh = BVHTree.FromPolygons(garment_points, garment_faces, all_triangles=False)
        actor_overlaps = bvh.overlap(garment_bvh)
        neck_eval = neck_seal.evaluated_get(depsgraph)
        neck_mesh = neck_eval.to_mesh()
        neck_points = [neck_eval.matrix_world @ vertex.co for vertex in neck_mesh.vertices]
        neck_faces = [list(face.vertices) for face in neck_mesh.polygons]
        neck_bvh = BVHTree.FromPolygons(neck_points, neck_faces, all_triangles=False)
        neck_overlaps = neck_bvh.overlap(garment_bvh)
        overlaps = actor_overlaps + neck_overlaps
        actor_overlap_faces = sorted({pair[0] for pair in overlaps})
        garment_overlap_faces = sorted({pair[1] for pair in overlaps})
        degenerate = sum(face.area < 1e-10 for face in garment_mesh.polygons)
        frame_reports[str(frame)] = {
            "visible_actor_vertices": len(actor_mesh.vertices),
            "neck_seal_vertices": len(neck_mesh.vertices),
            "actor_intersecting_face_pairs": len(actor_overlaps),
            "neck_seal_intersecting_face_pairs": len(neck_overlaps),
            "intersecting_face_pairs": len(overlaps),
            "intersecting_actor_faces": len(actor_overlap_faces),
            "intersecting_garment_faces": len(garment_overlap_faces),
            "garment_face_samples": garment_overlap_faces[:16],
            "degenerate_faces": degenerate,
        }
        total_intersections += len(overlaps)
        if len(overlaps) > MAX_CONTACT_PAIRS_PER_FRAME or len(actor_overlap_faces) > MAX_CONTACT_ACTOR_FACES_PER_FRAME:
            excessive_contact_frames.append(frame)
        total_degenerate += degenerate
        garment_eval.to_mesh_clear()
        neck_eval.to_mesh_clear()
        actor_eval.to_mesh_clear()

    if excessive_contact_frames:
        failures.append(f"visible Actor/garment contact exceeded tolerance at frames: {excessive_contact_frames}")
    if total_degenerate:
        failures.append(f"degenerate evaluated faces: {total_degenerate}")

    report = {
        "schema": "hunyuan_generated_garment_adapter_audit_v1",
        "input_blend": str(args.input_blend.resolve()),
        "actor_class": "ChibiActorV1",
        "slot": "torso_outer",
        "visible_geometry_source": garment.get("source_kind"),
        "frames": FRAMES,
        "garment": {
            "name": GARMENT_NAME,
            "vertices": len(garment.data.vertices),
            "faces": len(garment.data.polygons),
            "evaluated_vertices": evaluated_topology[0] if evaluated_topology else None,
            "evaluated_faces": evaluated_topology[1] if evaluated_topology else None,
            "used_weight_groups": sorted(used_groups),
            "forbidden_weight_groups": forbidden,
            "unweighted_vertices": unweighted,
            "non_normalized_vertices": non_normalized,
            "max_weight_sum_error": max_weight_error,
            "armature_modifiers": len(armature_modifiers),
        },
        "body_mask": {"name": MASK_NAME, "vertex_count": mask_count, "applied_in_review": True},
        "actor_profile_neck_seal": {
            "name": NECK_SEAL_NAME,
            "vertices": len(neck_seal.data.vertices),
            "faces": len(neck_seal.data.polygons),
        },
        "collar_shoulder_coverage": shoulder_bridge_report,
        "frame_reports": frame_reports,
        "summary": {
            "visible_actor_garment_intersecting_face_pairs": total_intersections,
            "contact_tolerance": {
                "maximum_pairs_per_frame": MAX_CONTACT_PAIRS_PER_FRAME,
                "maximum_actor_faces_per_frame": MAX_CONTACT_ACTOR_FACES_PER_FRAME,
                "excessive_contact_frames": excessive_contact_frames,
            },
            "degenerate_faces": total_degenerate,
            "failures": failures,
        },
        "status": "pass" if not failures else "fail",
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
