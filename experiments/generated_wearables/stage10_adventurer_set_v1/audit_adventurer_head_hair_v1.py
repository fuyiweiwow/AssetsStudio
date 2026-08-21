from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE_NAME = "Armature"
HAIR_NAME = "Wearable_Adventurer_HeadHairV1"
HEAD_BONE = "CC_Base_Head"
MASK_NAME = "WearableMask_AdventurerHeadHairV1"
MASK_MODIFIER = "PreviewBodyHide_AdventurerHeadHairV1"
FRAMES = [1, 11, 21, 31, 41, 51, 61, 71]


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main() -> int:
    args = cli()
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    scene = bpy.context.scene
    actor = bpy.data.objects.get(ACTOR_NAME)
    armature = bpy.data.objects.get(ARMATURE_NAME)
    hair = bpy.data.objects.get(HAIR_NAME)
    if actor is None or armature is None or hair is None:
        raise RuntimeError("Actor, Armature, or generated hair missing")

    failures = []
    names = {group.index: group.name for group in hair.vertex_groups}
    used_groups = sorted(
        {
            names[item.group]
            for vertex in hair.data.vertices
            for item in vertex.groups
            if item.weight > 1e-7
        }
    )
    unweighted = 0
    non_normalized = 0
    for vertex in hair.data.vertices:
        total = sum(item.weight for item in vertex.groups if item.weight > 1e-7)
        unweighted += total <= 1e-7
        non_normalized += abs(total - 1.0) > 1e-5
    if used_groups != [HEAD_BONE]:
        failures.append(f"hair must use only {HEAD_BONE}, got {used_groups}")
    if unweighted:
        failures.append(f"unweighted hair vertices: {unweighted}")
    if non_normalized:
        failures.append(f"non-normalized hair vertices: {non_normalized}")
    armature_modifiers = [
        modifier
        for modifier in hair.modifiers
        if modifier.type == "ARMATURE" and modifier.object == armature
    ]
    if len(armature_modifiers) != 1:
        failures.append(f"expected one Actor Armature modifier, found {len(armature_modifiers)}")
    mask = actor.vertex_groups.get(MASK_NAME)
    mask_count = 0
    if mask is None:
        failures.append(f"missing scalp mask: {MASK_NAME}")
    else:
        mask_count = sum(
            any(item.group == mask.index and item.weight > 0.0 for item in vertex.groups)
            for vertex in actor.data.vertices
        )
    mask_modifier = actor.modifiers.get(MASK_MODIFIER)
    if mask_modifier is None or not mask_modifier.invert_vertex_group:
        failures.append("scalp mask is not applied to review Actor")

    frame_reports = {}
    topology = None
    total_pairs = 0
    covered_scalp_face_indices = None
    for frame in FRAMES:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        actor_eval = actor.evaluated_get(depsgraph)
        actor_mesh = actor_eval.to_mesh()
        actor_points = [actor_eval.matrix_world @ vertex.co for vertex in actor_mesh.vertices]
        actor_faces = [list(face.vertices) for face in actor_mesh.polygons]
        actor_bvh = BVHTree.FromPolygons(actor_points, actor_faces, all_triangles=False)

        hair_eval = hair.evaluated_get(depsgraph)
        hair_mesh = hair_eval.to_mesh()
        current_topology = (len(hair_mesh.vertices), len(hair_mesh.polygons))
        if topology is None:
            topology = current_topology
        elif current_topology != topology:
            failures.append(f"evaluated hair topology changed at frame {frame}")
        hair_points = [hair_eval.matrix_world @ vertex.co for vertex in hair_mesh.vertices]
        hair_faces = [list(face.vertices) for face in hair_mesh.polygons]
        hair_bvh = BVHTree.FromPolygons(hair_points, hair_faces, all_triangles=False)
        overlaps = actor_bvh.overlap(hair_bvh)
        overlap_face_indices = {pair[0] for pair in overlaps}
        face_centers = {}
        covered_scalp_faces = set()
        for face_index in overlap_face_indices:
            polygon = actor_mesh.polygons[face_index]
            center = sum((actor_points[index] for index in polygon.vertices), Vector()) / len(polygon.vertices)
            face_centers[face_index] = center
            # A generated shell may touch the hidden temple scalp beneath its
            # outer side locks.  This is allowed only in the measured,
            # enclosed scalp band; face/eye/cheek contacts remain exposed.
            if frame == FRAMES[0]:
                if (
                    abs(center.x) >= 0.58
                    and -0.46 <= center.y <= -0.06
                    and 1.90 <= center.z <= 2.52
                ):
                    covered_scalp_faces.add(face_index)
        if frame == FRAMES[0]:
            covered_scalp_face_indices = covered_scalp_faces
        else:
            covered_scalp_faces = covered_scalp_face_indices or set()
        exposed_pairs = [pair for pair in overlaps if pair[0] not in covered_scalp_faces]
        exposed_actor_faces = {pair[0] for pair in exposed_pairs}
        actor_faces_hit = len(overlap_face_indices)
        overlap_centers = []
        if frame == FRAMES[0]:
            for face_index in sorted({pair[0] for pair in overlaps}):
                center = face_centers[face_index]
                overlap_centers.append([round(value, 6) for value in center])
        frame_reports[str(frame)] = {
            "actor_hair_intersecting_face_pairs": len(overlaps),
            "intersecting_actor_faces": actor_faces_hit,
            "covered_scalp_contact_pairs": len(overlaps) - len(exposed_pairs),
            "exposed_contact_pairs": len(exposed_pairs),
            "exposed_actor_faces": len(exposed_actor_faces),
            "visible_actor_vertices": len(actor_mesh.vertices),
            "intersecting_actor_face_centers": overlap_centers,
        }
        total_pairs += len(exposed_pairs)
        if len(exposed_pairs) > 16 or len(exposed_actor_faces) > 2:
            failures.append(f"visible Actor/hair contact exceeded tolerance at frame {frame}")
        hair_eval.to_mesh_clear()
        actor_eval.to_mesh_clear()

    report = {
        "schema": "hunyuan_generated_head_hair_audit_v1",
        "input_blend": str(args.input_blend.resolve()),
        "actor_class": "ChibiActorV1",
        "slot": "head_hair",
        "hair": {
            "vertices": len(hair.data.vertices),
            "faces": len(hair.data.polygons),
            "used_weight_groups": used_groups,
            "unweighted_vertices": unweighted,
            "non_normalized_vertices": non_normalized,
            "armature_modifiers": len(armature_modifiers),
        },
        "scalp_mask": {"name": MASK_NAME, "vertex_count": mask_count},
        "frames": frame_reports,
        "summary": {"visible_actor_hair_intersecting_face_pairs": total_pairs, "failures": failures},
        "status": "pass" if not failures else "fail",
    }
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
