"""Build diagnostic pose-space armhole correctives for an Actor garment.

The GarmentCode rest mesh remains the Basis shape.  Each corrective is derived
from an actual walk peak, mapped back through the vertex's blended armature
transform, and animated with continuous influence around that peak.  This is a
fixed-action diagnostic, not a replacement for GarmentCode pattern geometry.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--panel-membership", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--garment-name", default="GarmentCodeShirt_ActorTransfer")
    parser.add_argument("--clearance", type=float, default=0.002)
    parser.add_argument("--region-width", type=float, default=0.04)
    parser.add_argument("--max-rest-displacement", type=float, default=0.015)
    parser.add_argument("--smooth-iterations", type=int, default=3)
    parser.add_argument(
        "--armhole-scope",
        choices=("posterior", "full"),
        default="posterior",
        help="limit correction to sleeve_b or include the complete front/back armhole ring",
    )
    return parser.parse_args(argv)


CORRECTIVES = (
    {"name": "ArmholeCorrective_L_21", "side": "left", "peak": 21, "keys": ((7, 0.0), (14, 0.35), (21, 1.0), (28, 0.70), (34, 0.0))},
    {"name": "ArmholeCorrective_R_38", "side": "right", "peak": 38, "keys": ((27, 0.0), (33, 0.55), (38, 1.0), (46, 0.75), (56, 0.0))},
    {"name": "ArmholeCorrective_R_67", "side": "right", "peak": 67, "keys": ((54, 0.0), (61, 0.45), (67, 1.0), (71, 0.45))},
)


def panel_side(panels: list[str]) -> str | None:
    if any(name.startswith("left_sleeve_") for name in panels):
        return "left"
    if any(name.startswith("right_sleeve_") for name in panels):
        return "right"
    return None


def is_posterior(panels: list[str]) -> bool:
    return any(name.endswith("_sleeve_b") for name in panels)


def blended_deform_matrix(
    garment: bpy.types.Object,
    armature: bpy.types.Object,
    vertex: bpy.types.MeshVertex,
    group_names: dict[int, str],
) -> Matrix:
    object_to_armature = armature.matrix_world.inverted() @ garment.matrix_world
    armature_to_object = garment.matrix_world.inverted() @ armature.matrix_world
    result = Matrix(((0.0, 0.0, 0.0, 0.0),) * 4)
    total = 0.0
    for assignment in vertex.groups:
        name = group_names.get(assignment.group)
        pose_bone = armature.pose.bones.get(name) if name else None
        rest_bone = armature.data.bones.get(name) if name else None
        if pose_bone is None or rest_bone is None or assignment.weight <= 0.0:
            continue
        transform = (
            armature_to_object
            @ pose_bone.matrix
            @ rest_bone.matrix_local.inverted()
            @ object_to_armature
        )
        result += transform * assignment.weight
        total += assignment.weight
    if total <= 1e-8:
        return Matrix.Identity(4)
    return result * (1.0 / total)


def main() -> int:
    options = cli_args()
    if options.clearance <= 0.0 or options.region_width <= 0.0:
        raise ValueError("clearance and region width must be positive")
    membership = json.loads(options.panel_membership.resolve().read_text(encoding="utf-8"))
    if membership.get("schema") != "assetsstudio_garmentcode_panel_membership_v1":
        raise RuntimeError("unsupported panel-membership schema")
    vertex_panels = membership["vertex_panels"]

    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    scene = bpy.context.scene
    garment = bpy.data.objects.get(options.garment_name)
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if garment is None or actor is None or armature is None:
        raise RuntimeError("blend is missing garment, Actor, or Armature")
    if len(vertex_panels) != len(garment.data.vertices):
        raise RuntimeError("panel membership does not match garment vertices")
    action = armature.animation_data.action if armature.animation_data else None
    if action is None:
        raise RuntimeError("Actor armature has no active action")
    armature.data.pose_position = "POSE"

    # Stable REST-space seam distances define the same posterior armhole band
    # used by the motion audit.
    rest_points = [garment.matrix_world @ vertex.co for vertex in garment.data.vertices]
    seam_indices: dict[str, list[int]] = {"left": [], "right": []}
    for index, panels in enumerate(vertex_panels):
        side = panel_side(panels)
        in_scope = options.armhole_scope == "full" or is_posterior(panels)
        if side and in_scope and any("torso" in name for name in panels):
            seam_indices[side].append(index)
    seam_distance: dict[str, list[float]] = {}
    for side in ("left", "right"):
        if not seam_indices[side]:
            raise RuntimeError(f"no shared posterior armhole seam for {side}")
        seam_distance[side] = [
            min((point - rest_points[item]).length for item in seam_indices[side])
            for point in rest_points
        ]

    adjacency: dict[int, set[int]] = defaultdict(set)
    for edge in garment.data.edges:
        a, b = edge.vertices
        adjacency[a].add(b)
        adjacency[b].add(a)
    group_names = {group.index: group.name for group in garment.vertex_groups}

    if garment.data.shape_keys is not None:
        for block in list(garment.data.shape_keys.key_blocks)[1:]:
            garment.shape_key_remove(block)
    basis = garment.shape_key_add(name="Basis", from_mix=False) if garment.data.shape_keys is None else garment.data.shape_keys.key_blocks[0]
    reports = []

    for config in CORRECTIVES:
        side = config["side"]
        scene.frame_set(config["peak"])
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated_garment = garment.evaluated_get(depsgraph)
        evaluated_actor = actor.evaluated_get(depsgraph)
        garment_mesh = evaluated_garment.to_mesh()
        actor_mesh = evaluated_actor.to_mesh()
        posed_points = [evaluated_garment.matrix_world @ vertex.co for vertex in garment_mesh.vertices]
        actor_points = [evaluated_actor.matrix_world @ vertex.co for vertex in actor_mesh.vertices]
        actor_faces = [tuple(poly.vertices) for poly in actor_mesh.polygons]
        actor_bvh = BVHTree.FromPolygons(actor_points, actor_faces, all_triangles=False)

        target = {
            index
            for index, panels in enumerate(vertex_panels)
            if panel_side(panels) == side
            and (options.armhole_scope == "full" or is_posterior(panels))
            and seam_distance[side][index] <= options.region_width
        }
        raw: dict[int, Vector] = {index: Vector((0.0, 0.0, 0.0)) for index in target}
        before_depths = []
        for index in target:
            nearest = actor_bvh.find_nearest(posed_points[index])
            if nearest is None:
                continue
            location, normal, _face, _distance = nearest
            normal = normal.normalized()
            signed = (posed_points[index] - location).dot(normal)
            needed = options.clearance - signed
            if needed <= 0.0:
                continue
            before_depths.append(max(0.0, -signed))
            desired_world = normal * needed
            desired_local_pose = garment.matrix_world.inverted().to_3x3() @ desired_world
            deform = blended_deform_matrix(garment, armature, garment.data.vertices[index], group_names)
            try:
                rest_delta = deform.to_3x3().inverted() @ desired_local_pose
            except ValueError:
                continue
            if rest_delta.length > options.max_rest_displacement:
                rest_delta.normalize()
                rest_delta *= options.max_rest_displacement
            raw[index] = rest_delta

        # Spread the correction inside the posterior band to avoid isolated
        # spikes.  Vertices outside the band never move.
        smoothed = raw
        for _ in range(options.smooth_iterations):
            updated = {}
            for index in target:
                neighbours = [item for item in adjacency[index] if item in target]
                average = sum((smoothed[item] for item in neighbours), Vector()) / max(len(neighbours), 1)
                updated[index] = smoothed[index] * 0.65 + average * 0.35
            smoothed = updated

        key = garment.shape_key_add(name=config["name"], from_mix=False)
        moved = 0
        max_delta = 0.0
        for index, delta in smoothed.items():
            if delta.length <= 1e-7:
                continue
            key.data[index].co = basis.data[index].co + delta
            moved += 1
            max_delta = max(max_delta, delta.length)
        key.value = 0.0
        for frame, value in config["keys"]:
            key.value = value
            key.keyframe_insert(data_path="value", frame=frame, group="ActorGarmentPoseCorrectives")
        if key.id_data.animation_data and key.id_data.animation_data.action:
            for curve in key.id_data.animation_data.action.fcurves:
                if curve.data_path.endswith(f'key_blocks["{key.name}"].value'):
                    for point in curve.keyframe_points:
                        point.interpolation = "BEZIER"
        key.value = 0.0
        reports.append({
            "name": key.name,
            "side": side,
            "peak_frame": config["peak"],
            "influence_keys": config["keys"],
            "target_vertices": len(target),
            "moved_vertices": moved,
            "penetrating_or_low_clearance_vertices": len(before_depths),
            "before_max_depth_m": max(before_depths, default=0.0),
            "max_rest_displacement_m": max_delta,
        })
        evaluated_garment.to_mesh_clear()
        evaluated_actor.to_mesh_clear()

    garment["assetsstudio_pose_corrective_schema"] = "assetsstudio_actor_garment_pose_corrective_diagnostic_v1"
    garment["assetsstudio_pose_corrective_policy"] = "GarmentCode Basis unchanged; fixed-walk diagnostic morphs only"
    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    report = {
        "schema": "assetsstudio_actor_garment_pose_corrective_diagnostic_v1",
        "source_blend": str(options.blend.resolve()),
        "output_blend": str(output),
        "garment": garment.name,
        "action": action.name,
        "action_frames": [int(action.frame_range[0]), int(action.frame_range[1])],
        "clearance_m": options.clearance,
        "region_width_m": options.region_width,
        "armhole_scope": options.armhole_scope,
        "basis_geometry_policy": "unchanged GarmentCode simulation mesh",
        "scope": "fixed action diagnostic; not yet a generic joint-angle driver",
        "correctives": reports,
    }
    report_path = options.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
