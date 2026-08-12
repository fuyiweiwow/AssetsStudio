"""Transfer simulated GarmentCode shorts to the Actor without geometry fitting."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


TORSO_GROUPS = {
    "CC_Base_Hip", "CC_Base_Waist", "CC_Base_Spine01",
}
LEFT_GROUPS = {
    "CC_Base_Hip", "CC_Base_L_Thigh", "CC_Base_L_ThighTwist01", "CC_Base_L_ThighTwist02",
}
RIGHT_GROUPS = {
    "CC_Base_Hip", "CC_Base_R_Thigh", "CC_Base_R_ThighTwist01", "CC_Base_R_ThighTwist02",
}


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-blend", required=True, type=Path)
    parser.add_argument("--sim-obj", required=True, type=Path)
    parser.add_argument("--panel-membership", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--garment-name", default="GarmentCodeShorts_ActorTransfer")
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def make_surface(actor, group_names, selectors, transfers):
    def weight(index, allowed):
        return sum(
            assignment.weight for assignment in actor.data.vertices[index].groups
            if group_names.get(assignment.group) in allowed
        )
    faces = []
    source_indices = set()
    for polygon in actor.data.polygons:
        face = tuple(polygon.vertices)
        if max((weight(index, selectors) for index in face), default=0.0) < 0.20:
            continue
        faces.append(face)
        source_indices.update(face)
    order = sorted(source_indices)
    local = {source: index for index, source in enumerate(order)}
    points = [actor.matrix_world @ actor.data.vertices[index].co for index in order]
    return {
        "faces": faces,
        "points": points,
        "local": local,
        "transfers": transfers,
        "bvh": BVHTree.FromPolygons(
            points, [tuple(local[index] for index in face) for face in faces], all_triangles=False
        ),
    }


def main() -> int:
    options = cli_args()
    membership_path = options.panel_membership.resolve()
    membership = json.loads(membership_path.read_text(encoding="utf-8"))
    if membership.get("schema") != "assetsstudio_garmentcode_panel_membership_v1":
        raise RuntimeError("unsupported panel membership")
    if membership["sim_obj"]["sha256"] != sha256(options.sim_obj.resolve()):
        raise RuntimeError("panel membership does not match simulation OBJ")

    bpy.ops.wm.open_mainfile(filepath=str(options.actor_blend.resolve()))
    actor = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    armature = bpy.data.objects.get("Armature")
    if actor is None or armature is None:
        raise RuntimeError("Actor blend is missing expected objects")
    group_names = {group.index: group.name for group in actor.vertex_groups}
    existing_names = set(group_names.values())
    surfaces = {
        "torso": make_surface(actor, group_names, TORSO_GROUPS, TORSO_GROUPS | LEFT_GROUPS | RIGHT_GROUPS),
        "left": make_surface(actor, group_names, LEFT_GROUPS, TORSO_GROUPS | LEFT_GROUPS),
        "right": make_surface(actor, group_names, RIGHT_GROUPS, TORSO_GROUPS | RIGHT_GROUPS),
    }

    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(options.sim_obj.resolve()))
    imported = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    if len(imported) != 1:
        raise RuntimeError(f"expected one imported simulation mesh, got {len(imported)}")
    garment = imported[0]
    garment.name = options.garment_name
    for vertex in garment.data.vertices:
        gc = vertex.co.copy() * 0.01
        vertex.co = Vector((gc.x, -gc.z, gc.y))
    garment.location = (0.0, 0.0, 0.0)
    garment.rotation_euler = (0.0, 0.0, 0.0)
    garment.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    memberships = membership["vertex_panels"]
    if len(memberships) != len(garment.data.vertices):
        raise RuntimeError("panel membership vertex count mismatch")
    garment_groups = {name: garment.vertex_groups.new(name=name) for name in existing_names}
    region_counts = {"torso": 0, "left": 0, "right": 0, "crotch_shared": 0}

    for vertex, panels in zip(garment.data.vertices, memberships):
        panel_set = set(panels)
        left = any(name.endswith("_l") for name in panel_set)
        right = any(name.endswith("_r") for name in panel_set)
        if left and right:
            region = "torso"
            region_counts["crotch_shared"] += 1
        elif left:
            region = "left"
        elif right:
            region = "right"
        else:
            region = "torso"
        region_counts[region] += 1
        surface = surfaces[region]
        point = garment.matrix_world @ vertex.co
        nearest = surface["bvh"].find_nearest(point)
        if nearest is None:
            continue
        nearest_point, _normal, face_index, _distance = nearest
        face = surface["faces"][face_index]
        distances = [
            max((nearest_point - surface["points"][surface["local"][index]]).length, 1e-5)
            for index in face
        ]
        inverse = [1.0 / distance for distance in distances]
        denominator = sum(inverse)
        blended = {}
        for source_index, factor in zip(face, inverse):
            for assignment in actor.data.vertices[source_index].groups:
                name = group_names.get(assignment.group)
                if name not in surface["transfers"]:
                    continue
                blended[name] = blended.get(name, 0.0) + assignment.weight * factor / denominator
        total = sum(blended.values())
        if total <= 1e-8:
            continue
        for name, weight in blended.items():
            garment_groups[name].add([vertex.index], weight / total, "REPLACE")

    material = bpy.data.materials.new("GarmentCodeShorts_Material")
    material.diffuse_color = (0.08, 0.22, 0.52, 1.0)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    if shader is not None:
        shader.inputs["Base Color"].default_value = (0.08, 0.22, 0.52, 1.0)
        shader.inputs["Roughness"].default_value = 0.86
    garment.data.materials.clear()
    garment.data.materials.append(material)
    modifier = garment.modifiers.new("ActorArmature_GarmentCodeShorts", "ARMATURE")
    modifier.object = armature
    modifier.use_deform_preserve_volume = True
    garment["assetsstudio_transfer_schema"] = "assetsstudio_garmentcode_shorts_actor_transfer_v1"
    garment["assetsstudio_surface_policy"] = "direct simulation geometry; no shrinkwrap or repair"

    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    blend_path = output / "garmentcode_actor_shorts_transfer.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report = {
        "schema": "assetsstudio_garmentcode_shorts_actor_transfer_v1",
        "actor_blend": str(options.actor_blend.resolve()),
        "sim_obj": str(options.sim_obj.resolve()),
        "panel_membership": str(membership_path),
        "output_blend": str(blend_path),
        "garment_name": garment.name,
        "geometry_policy": "direct simulation geometry; no scale fit, shrinkwrap, push, or seam repair",
        "weight_policy": "exact left/right Pants panel membership plus nearest Actor pelvis/thigh surface mixed weights",
        "vertices": len(garment.data.vertices),
        "polygons": len(garment.data.polygons),
        "region_counts": region_counts,
        "status": "review_required",
    }
    (output / "transfer_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
