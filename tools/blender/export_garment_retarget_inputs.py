"""Prepare OBJ and skeleton inputs for the open-source garment retargeter.

The retargeter expects a closed target avatar, a connected triangular garment,
and source/target skeleton OBJ files with identical edge connectivity.  This
exporter keeps the source garment unchanged and builds a small torso skeleton
from the Actor armature so the first validation can focus on fit quality.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


SKELETON_BONES = (
    "CC_Base_Pelvis",
    "CC_Base_Spine02",
    "CC_Base_NeckTwist01",
    "CC_Base_L_Clavicle",
    "CC_Base_R_Clavicle",
)
SKELETON_EDGES = ((0, 1), (1, 2), (1, 3), (1, 4))


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--garment", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--actor-object", default="ChibiBaseMesh_AccuRIG_InputMesh")
    parser.add_argument("--armature", default="Armature")
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument("--rest-pose", action="store_true")
    parser.add_argument("--fit-weight", type=float, default=2.0)
    parser.add_argument("--incremental-steps", type=int, default=3)
    return parser.parse_args(argv)


def read_obj(path: Path) -> tuple[list[Vector], list[tuple[int, ...]]]:
    vertices: list[Vector] = []
    faces: list[tuple[int, ...]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        tokens = raw.split()
        if not tokens:
            continue
        if tokens[0] == "v" and len(tokens) >= 4:
            # GarmentCode simulation OBJ uses centimetres and (x, y-up,
            # z-depth).  The Actor scene uses metres and Blender's
            # (x, y-depth, z-up), matching the existing transfer bridge.
            gc_x = float(tokens[1]) * 0.01
            gc_y = float(tokens[2]) * 0.01
            gc_z = float(tokens[3]) * 0.01
            vertices.append(Vector((gc_x, -gc_z, gc_y)))
        elif tokens[0] == "f" and len(tokens) >= 4:
            indices = []
            for token in tokens[1:]:
                index = int(token.split("/")[0])
                indices.append(index - 1 if index > 0 else len(vertices) + index)
            for offset in range(1, len(indices) - 1):
                faces.append((indices[0], indices[offset], indices[offset + 1]))
    if not vertices or not faces:
        raise RuntimeError(f"invalid or empty OBJ: {path}")
    return vertices, faces


def write_surface(path: Path, vertices: list[Vector], faces: list[tuple[int, ...]]) -> None:
    lines = ["# AssetsStudio retargeting input\n"]
    lines.extend(f"v {point.x:.9f} {point.y:.9f} {point.z:.9f}\n" for point in vertices)
    lines.extend("f " + " ".join(str(index + 1) for index in face) + "\n" for face in faces)
    path.write_text("".join(lines), encoding="utf-8")


def write_skeleton(path: Path, points: list[Vector]) -> None:
    lines = ["# AssetsStudio retargeting skeleton\n"]
    lines.extend(f"v {point.x:.9f} {point.y:.9f} {point.z:.9f}\n" for point in points)
    lines.extend(f"l {first + 1} {second + 1}\n" for first, second in SKELETON_EDGES)
    path.write_text("".join(lines), encoding="utf-8")


def bone_point(armature: bpy.types.Object, name: str, tail: bool) -> Vector:
    bone = armature.data.bones.get(name)
    if bone is None:
        raise RuntimeError(f"Actor armature bone not found: {name}")
    local = bone.tail_local if tail else bone.head_local
    return armature.matrix_world @ local


def target_skeleton(armature: bpy.types.Object) -> list[Vector]:
    return [
        bone_point(armature, SKELETON_BONES[0], False),
        bone_point(armature, SKELETON_BONES[1], True),
        bone_point(armature, SKELETON_BONES[2], True),
        bone_point(armature, SKELETON_BONES[3], True),
        bone_point(armature, SKELETON_BONES[4], True),
    ]


def source_skeleton(vertices: list[Vector]) -> list[Vector]:
    minimum = Vector((min(point.x for point in vertices), min(point.y for point in vertices), min(point.z for point in vertices)))
    maximum = Vector((max(point.x for point in vertices), max(point.y for point in vertices), max(point.z for point in vertices)))
    center_y = (minimum.y + maximum.y) * 0.5
    height = max(maximum.z - minimum.z, 1e-6)
    width = max(maximum.x - minimum.x, 1e-6)
    return [
        Vector((0.0, center_y, minimum.z + height * 0.24)),
        Vector((0.0, center_y, minimum.z + height * 0.58)),
        Vector((0.0, center_y, minimum.z + height * 0.78)),
        Vector((-width * 0.24, center_y, minimum.z + height * 0.69)),
        Vector((width * 0.24, center_y, minimum.z + height * 0.69)),
    ]


def write_setup(output_dir: Path, fit_weight: float, incremental_steps: int) -> None:
    setup = {
        "incremental_steps": incremental_steps,
        "avatar_mesh_path": "target_avatar.obj",
        "target_skeleton_path": "target_skeleton.obj",
        "garment_mesh_path": "source_garment.obj",
        # The retargeter treats an existing empty no-fit file as invalid.  A
        # missing path means "fit all garment faces" and is handled safely.
        "no_fit_spec_path": "missing-no-fit.txt",
        "source_skeleton_path": "source_skeleton.obj",
        "similarity_penalty_weight": 1,
        "curvature_penalty_weight": 0.01,
        "twist_penalty_weight": 0.01,
        "curve_center_target_weight": 1,
        "fit_weight": fit_weight,
        "symmetry_weight": 0,
        "curve_size_weight": 0,
        "voxel_size": 0.01,
        "contact": {"enabled": True, "dhat": 0.002},
        "solver": {
            "max_threads": 8,
            "linear": {"solver": ["Eigen::SimplicialLDLT"]},
            "augmented_lagrangian": {
                "initial_weight": 1,
                "max_weight": 1000000.0,
                "eta": 1,
                "nonlinear": {"grad_norm": 1, "max_iterations": 50},
            },
            "nonlinear": {
                "Newton": {
                    "use_psd_projection": True,
                    "use_psd_projection_in_regularized": True,
                    "reg_weight_max": 1e16,
                    "reg_weight_min": 1,
                    "reg_weight_inc": 10000.0,
                },
                "grad_norm": 0.01,
                "line_search": {
                    "max_step_size_limiter": 0.5,
                    "use_grad_norm_tol": 1e-4,
                    "method": "Backtracking",
                    "min_step_size": 1e-8,
                },
                "max_iterations": 500,
            },
            "contact": {
                "CCD": {"broad_phase": "BVH", "max_iterations": 100, "tolerance": 1e-3},
                "barrier_stiffness": 1e8,
            },
        },
        "output": {"skip_frame": 2, "log": {"level": "debug"}},
    }
    (output_dir / "setup.json").write_text(json.dumps(setup, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.actor.resolve()))
    if options.rest_pose:
        for armature in (obj for obj in bpy.data.objects if obj.type == "ARMATURE"):
            armature.data.pose_position = "REST"
            if armature.animation_data is not None:
                armature.animation_data.action = None
        bpy.context.scene.frame_set(0)
    else:
        bpy.context.scene.frame_set(options.frame)
    bpy.context.view_layer.update()

    actor = bpy.data.objects.get(options.actor_object)
    armature = bpy.data.objects.get(options.armature)
    if actor is None or actor.type != "MESH":
        raise RuntimeError(f"Actor mesh not found: {options.actor_object}")
    if armature is None or armature.type != "ARMATURE":
        raise RuntimeError(f"Actor armature not found: {options.armature}")

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = actor.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        actor_vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        actor_faces: list[tuple[int, ...]] = []
        for polygon in mesh.polygons:
            for offset in range(1, len(polygon.vertices) - 1):
                actor_faces.append((polygon.vertices[0], polygon.vertices[offset], polygon.vertices[offset + 1]))
    finally:
        evaluated.to_mesh_clear()

    garment_vertices, garment_faces = read_obj(options.garment.resolve())
    output_dir = options.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    write_surface(output_dir / "target_avatar.obj", actor_vertices, actor_faces)
    write_surface(output_dir / "source_garment.obj", garment_vertices, garment_faces)
    write_skeleton(output_dir / "target_skeleton.obj", target_skeleton(armature))
    write_skeleton(output_dir / "source_skeleton.obj", source_skeleton(garment_vertices))
    write_setup(output_dir, options.fit_weight, options.incremental_steps)

    report = {
        "schema": "assetsstudio_garment_retarget_inputs_v1",
        "actor": str(options.actor.resolve()),
        "garment": str(options.garment.resolve()),
        "output_dir": str(output_dir),
        "actor_vertices": len(actor_vertices),
        "actor_triangles": len(actor_faces),
        "garment_vertices": len(garment_vertices),
        "garment_triangles": len(garment_faces),
        "skeleton_nodes": len(SKELETON_BONES),
        "skeleton_edges": [list(edge) for edge in SKELETON_EDGES],
        "pose_mode": "REST" if options.rest_pose else f"FRAME_{options.frame}",
        "next_command": "PolyFEM_bin -j setup.json --max_threads 8",
    }
    (output_dir / "export_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
