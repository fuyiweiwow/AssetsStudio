from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ARMATURE_NAME = "Armature"
FRAMES = (1, 11, 21, 31, 41, 51, 61, 71)
SIDES = {
    "left": {
        "transition": "ActorProfile_LegTransition_L_ChibiActorV1",
        "boot": "Wearable_Adventurer_Boot_L_V1",
        "bones": {"CC_Base_L_Thigh", "CC_Base_L_Calf", "CC_Base_L_Foot"},
    },
    "right": {
        "transition": "ActorProfile_LegTransition_R_ChibiActorV1",
        "boot": "Wearable_Adventurer_Boot_R_V1",
        "bones": {"CC_Base_R_Thigh", "CC_Base_R_Calf", "CC_Base_R_Foot"},
    },
}


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def evaluated_bounds(
    obj: bpy.types.Object,
    depsgraph: bpy.types.Depsgraph,
) -> tuple[Vector, Vector, tuple[int, int], list[Vector]]:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
        high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
        return low, high, (len(mesh.vertices), len(mesh.polygons)), points
    finally:
        evaluated.to_mesh_clear()


def main() -> int:
    options = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(options.input_blend.resolve()))
    scene = bpy.context.scene
    armature = bpy.data.objects.get(ARMATURE_NAME)
    if armature is None:
        raise RuntimeError("Actor Armature missing")
    failures: list[str] = []
    objects = {}
    for side, contract in SIDES.items():
        transition = bpy.data.objects.get(contract["transition"])
        boot = bpy.data.objects.get(contract["boot"])
        if transition is None or boot is None:
            failures.append(f"{side}: transition or boot missing")
            continue
        names = {group.index: group.name for group in transition.vertex_groups}
        used = {
            names[item.group]
            for vertex in transition.data.vertices
            for item in vertex.groups
            if item.weight > 1e-7
        }
        if used != contract["bones"]:
            failures.append(f"{side}: expected groups {sorted(contract['bones'])}, got {sorted(used)}")
        unweighted = 0
        non_normalized = 0
        for vertex in transition.data.vertices:
            total = sum(item.weight for item in vertex.groups if item.weight > 1e-7)
            unweighted += total <= 1e-7
            non_normalized += total > 1e-7 and abs(total - 1.0) > 1e-4
        if unweighted:
            failures.append(f"{side}: unweighted vertices {unweighted}")
        if non_normalized:
            failures.append(f"{side}: non-normalized vertices {non_normalized}")
        modifiers = [modifier for modifier in transition.modifiers if modifier.type == "ARMATURE"]
        if len(modifiers) != 1 or modifiers[0].object != armature:
            failures.append(f"{side}: invalid Actor Armature binding")
        if transition.get("actor_profile_component") != "leg_opening_transition":
            failures.append(f"{side}: ActorProfile transition metadata missing")
        objects[side] = (transition, boot)

    frame_reports = {}
    topology = {}
    for frame in FRAMES:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        frame_report = {}
        for side, pair in objects.items():
            transition, boot = pair
            transition_low, transition_high, transition_topology, transition_points = evaluated_bounds(
                transition, depsgraph
            )
            boot_low, boot_high, boot_topology, _boot_points = evaluated_bounds(boot, depsgraph)
            topology.setdefault(side, (transition_topology, boot_topology))
            if topology[side] != (transition_topology, boot_topology):
                failures.append(f"{side}: topology changed at frame {frame}")
            boot_overlap = boot_high.z - transition_low.z
            exposed_span = transition_high.z - boot_high.z
            lower_ring_center = sum(transition_points[-16:], Vector()) / 16
            boot_center = (boot_low + boot_high) * 0.5
            center_offset = Vector(
                (lower_ring_center.x - boot_center.x, lower_ring_center.y - boot_center.y)
            ).length
            if boot_overlap < 0.04:
                failures.append(f"{side}: boot overlap {boot_overlap:.4f} below 0.04 at frame {frame}")
            if exposed_span < 0.10:
                failures.append(f"{side}: visible bridge span {exposed_span:.4f} below 0.10 at frame {frame}")
            if center_offset > 0.10:
                failures.append(f"{side}: boot/bridge center offset {center_offset:.4f} above 0.10 at frame {frame}")
            frame_report[side] = {
                "transition_low": list(transition_low),
                "transition_high": list(transition_high),
                "boot_low": list(boot_low),
                "boot_high": list(boot_high),
                "boot_overlap": boot_overlap,
                "exposed_span": exposed_span,
                "center_offset_xy": center_offset,
                "transition_topology": list(transition_topology),
                "boot_topology": list(boot_topology),
            }
        frame_reports[str(frame)] = frame_report
    report = {
        "schema": "actor_profile_leg_opening_continuity_audit_v1",
        "input_blend": str(options.input_blend.resolve()),
        "frames": frame_reports,
        "limits": {
            "minimum_boot_overlap": 0.04,
            "minimum_exposed_bridge_span": 0.10,
            "maximum_center_offset_xy": 0.10,
        },
        "failures": sorted(set(failures)),
        "status": "pass" if not failures else "fail",
    }
    options.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
