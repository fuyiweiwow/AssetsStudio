from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree


ACTOR_NAME = "ChibiBaseMesh_AccuRIG_InputMesh"
ARMATURE_NAME = "Armature"
ACCESSORY_NAME = "Wearable_Adventurer_WaistAccessoryV1"
TORSO_NAME = "Wearable_Adventurer_TorsoOuterV1"
WAIST_BONE = "CC_Base_Waist"
FRAMES = [1, 11, 21, 31, 41, 51, 61, 71]


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def evaluated_bvh(obj: bpy.types.Object, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    faces = [list(face.vertices) for face in mesh.polygons]
    return evaluated, mesh, BVHTree.FromPolygons(points, faces, all_triangles=False)


def main() -> int:
    args = cli()
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    scene = bpy.context.scene
    actor = bpy.data.objects[ACTOR_NAME]
    armature = bpy.data.objects[ARMATURE_NAME]
    accessory = bpy.data.objects[ACCESSORY_NAME]
    torso = bpy.data.objects[TORSO_NAME]
    failures = []

    names = {group.index: group.name for group in accessory.vertex_groups}
    used = sorted(
        {
            names[item.group]
            for vertex in accessory.data.vertices
            for item in vertex.groups
            if item.weight > 1e-7
        }
    )
    unweighted = 0
    non_normalized = 0
    for vertex in accessory.data.vertices:
        total = sum(item.weight for item in vertex.groups if item.weight > 1e-7)
        unweighted += total <= 1e-7
        non_normalized += abs(total - 1.0) > 1e-5
    modifiers = [
        modifier
        for modifier in accessory.modifiers
        if modifier.type == "ARMATURE" and modifier.object == armature
    ]
    if used != [WAIST_BONE]:
        failures.append(f"waist accessory must use only {WAIST_BONE}, got {used}")
    if unweighted or non_normalized:
        failures.append(f"weight failure: unweighted={unweighted} non_normalized={non_normalized}")
    if len(modifiers) != 1:
        failures.append(f"expected one Actor Armature modifier, found {len(modifiers)}")

    frame_reports = {}
    topology = None
    for frame in FRAMES:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        actor_eval, actor_mesh, actor_bvh = evaluated_bvh(actor, depsgraph)
        torso_eval, torso_mesh, torso_bvh = evaluated_bvh(torso, depsgraph)
        accessory_eval, accessory_mesh, accessory_bvh = evaluated_bvh(accessory, depsgraph)
        current_topology = (len(accessory_mesh.vertices), len(accessory_mesh.polygons))
        if topology is None:
            topology = current_topology
        elif current_topology != topology:
            failures.append(f"evaluated waist topology changed at frame {frame}")
        actor_pairs = actor_bvh.overlap(accessory_bvh)
        torso_pairs = torso_bvh.overlap(accessory_bvh)
        frame_reports[str(frame)] = {
            "actor_accessory_face_pairs": len(actor_pairs),
            "torso_accessory_face_pairs": len(torso_pairs),
        }
        if actor_pairs:
            failures.append(f"visible Actor/waist contact at frame {frame}: {len(actor_pairs)} pairs")
        if torso_pairs:
            failures.append(f"torso/waist contact at frame {frame}: {len(torso_pairs)} pairs")
        accessory_eval.to_mesh_clear()
        torso_eval.to_mesh_clear()
        actor_eval.to_mesh_clear()

    report = {
        "schema": "hunyuan_generated_waist_accessory_audit_v1",
        "input_blend": str(args.input_blend.resolve()),
        "actor_class": "ChibiActorV1",
        "slot": "waist_accessory",
        "accessory": {
            "vertices": len(accessory.data.vertices),
            "faces": len(accessory.data.polygons),
            "used_weight_groups": used,
            "unweighted_vertices": unweighted,
            "non_normalized_vertices": non_normalized,
            "armature_modifiers": len(modifiers),
        },
        "frames": frame_reports,
        "summary": {"failures": failures},
        "status": "pass" if not failures else "fail",
    }
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
