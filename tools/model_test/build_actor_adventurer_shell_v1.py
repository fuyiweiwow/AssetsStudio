"""Build a composable Actor V1 adventure outfit shell for model_test."""

from __future__ import annotations

import argparse
import sys
import bmesh
from pathlib import Path

import bpy
from mathutils import Vector


def cli_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-blend", required=True, type=Path)
    parser.add_argument("--top-blend", required=True, type=Path)
    parser.add_argument("--pants-blend", required=True, type=Path)
    parser.add_argument("--shoes-blend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--glb-output", required=True, type=Path)
    return parser.parse_args(argv)


def append_named_objects(blend_path: Path, names: list[str]) -> list[bpy.types.Object]:
    with bpy.data.libraries.load(str(blend_path), link=False) as (source, target):
        available = set(source.objects)
        missing = [name for name in names if name not in available]
        if missing:
            raise RuntimeError(f"missing objects in {blend_path}: {missing}")
        target.objects = names
    appended = [obj for obj in target.objects if obj is not None]
    for obj in appended:
        if obj.name not in bpy.context.scene.objects:
            bpy.context.scene.collection.objects.link(obj)
    return appended


def append_prefix_objects(blend_path: Path, prefix: str) -> list[bpy.types.Object]:
    with bpy.data.libraries.load(str(blend_path), link=False) as (source, target):
        names = [name for name in source.objects if name.startswith(prefix)]
        target.objects = names
    appended = [obj for obj in target.objects if obj is not None]
    for obj in appended:
        if obj.name not in bpy.context.scene.objects:
            bpy.context.scene.collection.objects.link(obj)
    return appended


def retarget_armature(obj: bpy.types.Object, armature: bpy.types.Object) -> None:
    for modifier in obj.modifiers:
        if modifier.type == "ARMATURE":
            modifier.object = armature
    if obj.parent and obj.parent.type == "ARMATURE":
        obj.parent = armature


def material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.78
    return mat


def assign_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def bevelled_cube(name: str, location: tuple[float, float, float], scale: tuple[float, float, float], mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = obj.modifiers.new(name="SoftEdge", type="BEVEL")
    bevel.width = 0.035
    bevel.segments = 3
    assign_material(obj, mat)
    obj["assetsstudio_component"] = name.split("_", 1)[-1].lower()
    obj["assetsstudio_binding"] = "static_actor_rest_pose_v1"
    return obj


def create_hair_cap(mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=(0.0, 0.03, 2.73))
    obj = bpy.context.object
    obj.name = "GEO_HairWigShell_V1"
    obj.scale = (0.84, 0.80, 0.46)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    # Keep the top/back cap while removing the lower sphere that would cover
    # the eyes and face contract.
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.delete(bm, geom=[vertex for vertex in bm.verts if vertex.co.z < -0.10], context="VERTS")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    assign_material(obj, mat)
    obj["assetsstudio_component"] = "hair_wig"
    obj["assetsstudio_binding"] = "static_actor_rest_pose_v1"
    return obj


def create_hair_bangs(mat: bpy.types.Material) -> list[bpy.types.Object]:
    bangs: list[bpy.types.Object] = []
    specs = (
        ("GEO_HairBang_C_V2", (0.00, -0.60, 2.76), (0.25, 0.11, 0.28), 0.00),
        ("GEO_HairBang_L_V2", (-0.25, -0.57, 2.76), (0.23, 0.11, 0.27), -0.22),
        ("GEO_HairBang_R_V2", (0.25, -0.57, 2.76), (0.23, 0.11, 0.27), 0.22),
        ("GEO_HairSide_L_V2", (-0.54, -0.42, 2.57), (0.13, 0.11, 0.32), -0.35),
        ("GEO_HairSide_R_V2", (0.54, -0.42, 2.57), (0.13, 0.11, 0.32), 0.35),
    )
    for name, location, scale, rotation in specs:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, location=location)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        obj.rotation_euler[1] = rotation
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
        assign_material(obj, mat)
        obj["assetsstudio_component"] = "hair_wig"
        obj["assetsstudio_binding"] = "static_actor_rest_pose_v1"
        bangs.append(obj)
    return bangs


def create_scarf_and_belt(materials: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    created: list[bpy.types.Object] = []
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.29,
        minor_radius=0.085,
        major_segments=48,
        minor_segments=12,
        location=(0.0, 0.0, 2.08),
    )
    scarf = bpy.context.object
    scarf.name = "GEO_ScarfShell_V1"
    scarf.scale.y = 0.86
    assign_material(scarf, materials["scarf"])
    scarf["assetsstudio_component"] = "scarf"
    scarf["assetsstudio_binding"] = "static_actor_rest_pose_v1"
    created.append(scarf)

    bib = bevelled_cube("GEO_ScarfBib_V1", (0.0, -0.55, 1.94), (0.34, 0.08, 0.34), materials["scarf"])
    bib.rotation_euler[1] = 0.785
    created.append(bib)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.43,
        minor_radius=0.045,
        major_segments=48,
        minor_segments=10,
        location=(0.0, 0.0, 1.34),
    )
    belt = bpy.context.object
    belt.name = "GEO_BeltShell_V1"
    belt.scale.y = 0.77
    assign_material(belt, materials["belt"])
    belt["assetsstudio_component"] = "belt_and_pouch"
    belt["assetsstudio_binding"] = "static_actor_rest_pose_v1"
    created.append(belt)

    buckle = bevelled_cube("GEO_BeltBuckle_V1", (0.0, -0.54, 1.34), (0.20, 0.07, 0.17), materials["buckle"])
    created.append(buckle)
    pouch = bevelled_cube("GEO_BeltPouch_V1", (0.38, -0.50, 1.28), (0.27, 0.16, 0.30), materials["pouch"])
    created.append(pouch)
    return created


def create_jacket_panels(materials: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    """Add the open-jacket/inner-shirt read from the front reference."""
    panel = bevelled_cube("GEO_AdventurerInnerShirt_V1", (0.0, -0.56, 1.70), (0.34, 0.07, 0.52), materials["inner"])
    panel["assetsstudio_component"] = "adventurer_jacket"
    left = bevelled_cube("GEO_AdventurerLapel_L_V1", (-0.205, -0.58, 1.87), (0.14, 0.07, 0.42), materials["inner"])
    left.rotation_euler[1] = -0.26
    left["assetsstudio_component"] = "adventurer_jacket"
    right = bevelled_cube("GEO_AdventurerLapel_R_V1", (0.205, -0.58, 1.87), (0.14, 0.07, 0.42), materials["inner"])
    right.rotation_euler[1] = 0.26
    right["assetsstudio_component"] = "adventurer_jacket"
    return [panel, left, right]


def tag(obj: bpy.types.Object, component: str) -> None:
    obj["assetsstudio_component"] = component
    obj["assetsstudio_version"] = "male_adventurer_shell_v1"
    obj.hide_render = False
    obj.hide_viewport = False


def main() -> int:
    options = cli_args()
    bpy.ops.wm.open_mainfile(filepath=str(options.base_blend.resolve()))
    armature = bpy.data.objects.get("Armature")
    body = bpy.data.objects.get("ChibiBaseMesh_AccuRIG_InputMesh")
    if armature is None or body is None:
        raise RuntimeError("Actor V1 armature/body baseline is missing")
    tag(body, "actor_body_no_nose_no_mouth")
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.name.startswith(("EyePackageV1_", "MikuEar_")):
            tag(obj, "eye_assembly" if obj.name.startswith("EyePackage") else "ears")

    mats = {
        "jacket": material("MAT_AdventurerJacket_V1", (0.055, 0.19, 0.43, 1.0)),
        "inner": material("MAT_AdventurerInnerShirt_V1", (0.72, 0.61, 0.38, 1.0)),
        "trousers": material("MAT_AdventurerTrousers_V1", (0.20, 0.34, 0.12, 1.0)),
        "boots": material("MAT_AdventurerBoots_V1", (0.27, 0.12, 0.045, 1.0)),
        "hair": material("MAT_AdventurerHair_V1", (0.16, 0.075, 0.035, 1.0)),
        "scarf": material("MAT_AdventurerScarf_V1", (0.68, 0.10, 0.055, 1.0)),
        "belt": material("MAT_AdventurerBelt_V1", (0.23, 0.10, 0.035, 1.0)),
        "buckle": material("MAT_AdventurerBuckle_V1", (0.55, 0.35, 0.12, 1.0)),
        "pouch": material("MAT_AdventurerPouch_V1", (0.32, 0.15, 0.055, 1.0)),
    }

    top = append_named_objects(options.top_blend.resolve(), ["GarmentCodeShirt_ActorTransfer"])[0]
    top.name = "GEO_AdventurerJacketShell_V1"
    retarget_armature(top, armature)
    assign_material(top, mats["jacket"])
    tag(top, "adventurer_jacket")

    pants = append_named_objects(options.pants_blend.resolve(), ["NativeControlShorts"])[0]
    pants.name = "GEO_AdventurerTrousersShell_V1"
    retarget_armature(pants, armature)
    assign_material(pants, mats["trousers"])
    tag(pants, "trousers")

    shoe_objects = append_prefix_objects(options.shoes_blend.resolve(), "ActorCartoonSneaker_")
    for shoe in shoe_objects:
        retarget_armature(shoe, armature)
        assign_material(shoe, mats["boots"])
        tag(shoe, "boots_and_gloves")

    hair = create_hair_cap(mats["hair"])
    hair_bangs = create_hair_bangs(mats["hair"])
    jacket_panels = create_jacket_panels(mats)
    scarf_belt = create_scarf_and_belt(mats)
    for obj in jacket_panels:
        tag(obj, "adventurer_jacket")
    for obj in hair_bangs:
        tag(obj, "hair_wig")
    for obj in scarf_belt:
        tag(obj, "scarf" if "Scarf" in obj.name else "belt_and_pouch")

    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    export_objects = [obj for obj in bpy.context.scene.objects if obj.type in {"ARMATURE", "MESH"} and not obj.hide_render]
    for obj in export_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = armature

    options.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    options.glb_output.resolve().parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(options.output.resolve()))
    bpy.ops.export_scene.gltf(
        filepath=str(options.glb_output.resolve()),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_animation_mode="ACTIVE_ACTIONS",
        export_frame_range=True,
        export_force_sampling=True,
        export_def_bones=True,
        export_optimize_animation_size=True,
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )
    print(
        "ACTOR_ADVENTURER_SHELL_V1_PASS "
        f"objects={len(export_objects)} blend={options.output.resolve()} glb={options.glb_output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
