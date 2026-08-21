from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE_NAME = "Armature"
GARMENT_NAME = "Wearable_Adventurer_LegsOuterV1"
MASK_NAME = "WearableMask_AdventurerLegsOuterV1"
MASK_MODIFIER = "PreviewBodyHide_AdventurerLegsOuterV1"
ALLOWED_BONES = {
    "CC_Base_Pelvis",
    "CC_Base_Spine01",
    "CC_Base_L_Thigh",
    "CC_Base_R_Thigh",
}
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
    garment = bpy.data.objects.get(GARMENT_NAME)
    if actor is None or armature is None or garment is None:
        raise RuntimeError("Actor, Armature, or legs_outer garment missing")
    failures = []
    names = {group.index: group.name for group in garment.vertex_groups}
    used = {
        names[item.group]
        for vertex in garment.data.vertices
        for item in vertex.groups
        if item.weight > 1e-7
    }
    forbidden = sorted(used - ALLOWED_BONES)
    unweighted = 0
    non_normalized = 0
    for vertex in garment.data.vertices:
        total = sum(item.weight for item in vertex.groups if item.weight > 1e-7)
        unweighted += total <= 1e-7
        non_normalized += total > 1e-7 and abs(total - 1.0) > 1e-4
    if forbidden:
        failures.append(f"forbidden weight groups: {forbidden}")
    if unweighted:
        failures.append(f"unweighted vertices: {unweighted}")
    if non_normalized:
        failures.append(f"non-normalized vertices: {non_normalized}")
    modifiers = [m for m in garment.modifiers if m.type == "ARMATURE" and m.object == armature]
    if len(modifiers) != 1:
        failures.append(f"expected one Actor Armature modifier, found {len(modifiers)}")
    mask = actor.vertex_groups.get(MASK_NAME)
    mask_modifier = actor.modifiers.get(MASK_MODIFIER)
    if mask is None or mask_modifier is None or not mask_modifier.invert_vertex_group:
        failures.append("legs_outer body mask missing or inactive")

    frame_reports = {}
    contact_frames = []
    topology = None
    for frame in FRAMES:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        actor_eval = actor.evaluated_get(depsgraph)
        actor_mesh = actor_eval.to_mesh()
        actor_points = [actor_eval.matrix_world @ vertex.co for vertex in actor_mesh.vertices]
        actor_faces = [list(face.vertices) for face in actor_mesh.polygons]
        actor_bvh = BVHTree.FromPolygons(actor_points, actor_faces, all_triangles=False)
        garment_eval = garment.evaluated_get(depsgraph)
        garment_mesh = garment_eval.to_mesh()
        current_topology = (len(garment_mesh.vertices), len(garment_mesh.polygons))
        if topology is None:
            topology = current_topology
        elif current_topology != topology:
            failures.append(f"evaluated topology changed at frame {frame}")
        garment_points = [garment_eval.matrix_world @ vertex.co for vertex in garment_mesh.vertices]
        garment_faces = [list(face.vertices) for face in garment_mesh.polygons]
        garment_bvh = BVHTree.FromPolygons(garment_points, garment_faces, all_triangles=False)
        overlaps = actor_bvh.overlap(garment_bvh)
        actor_faces_hit = len({pair[0] for pair in overlaps})
        frame_reports[str(frame)] = {
            "actor_garment_face_pairs": len(overlaps),
            "intersecting_actor_faces": actor_faces_hit,
            "visible_actor_vertices": len(actor_mesh.vertices),
        }
        if len(overlaps) > 16 or actor_faces_hit > 2:
            contact_frames.append(frame)
        garment_eval.to_mesh_clear()
        actor_eval.to_mesh_clear()
    if contact_frames:
        failures.append(f"visible Actor/legs_outer contact exceeded tolerance at frames: {contact_frames}")
    report = {
        "schema": "hunyuan_generated_legs_outer_audit_v1",
        "input_blend": str(args.input_blend.resolve()),
        "actor_class": "ChibiActorV1",
        "slot": "legs_outer",
        "garment": {
            "vertices": len(garment.data.vertices),
            "faces": len(garment.data.polygons),
            "used_weight_groups": sorted(used),
            "forbidden_weight_groups": forbidden,
            "unweighted_vertices": unweighted,
            "non_normalized_vertices": non_normalized,
            "armature_modifiers": len(modifiers),
        },
        "frames": frame_reports,
        "summary": {"contact_frames": contact_frames, "failures": failures},
        "status": "pass" if not failures else "fail",
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
