from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ARMATURE_NAME = "Armature"
ACCESSORY_NAME = "Wearable_Adventurer_WaistAccessoryV1"
TORSO_NAME = "Wearable_Adventurer_TorsoOuterV1"
CINCH_KEY_NAME = "AccessoryFit_AdventurerWaistV1"
WAIST_BONE = "CC_Base_Waist"
SOURCE_LOW = Vector((-0.992293, -0.985579, -0.299774))
SOURCE_HIGH = Vector((0.983379, 0.992294, 0.301924))
SOURCE_CENTER = (SOURCE_LOW + SOURCE_HIGH) * 0.5
TARGET_CENTER = Vector((0.0, -0.010, 0.810))
TARGET_SCALE = Vector((0.315, 0.235, 0.32))


def cli() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--source-glb", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--decimate-ratio", type=float, default=0.18)
    return parser.parse_args(argv)


def bounds(obj: bpy.types.Object) -> dict[str, list[float]]:
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    low = Vector(tuple(min(point[i] for point in points) for i in range(3)))
    high = Vector(tuple(max(point[i] for point in points) for i in range(3)))
    return {
        "low": [round(value, 6) for value in low],
        "high": [round(value, 6) for value in high],
        "size": [round(value, 6) for value in high - low],
    }


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = min(1.0, max(0.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def add_accessory_cinch_shape(
    torso: bpy.types.Object,
    accessory: bpy.types.Object,
) -> dict[str, float | int | list[float]]:
    """Create the equipped-belt corrective shape on the generated tunic.

    The belt remains rigid.  The tunic receives a reversible morph target that
    compresses only vertices inside the belt's vertical contact band.  This is
    the same asset-layer contract a runtime morph target can toggle when the
    waist accessory is equipped; it is not replacement garment geometry.
    """
    if torso.data.shape_keys is None:
        torso.shape_key_add(name="Basis")
    existing = torso.data.shape_keys.key_blocks.get(CINCH_KEY_NAME)
    if existing is not None:
        torso.shape_key_remove(existing)
    key = torso.shape_key_add(name=CINCH_KEY_NAME)

    points = [accessory.matrix_world @ vertex.co for vertex in accessory.data.vertices]
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    center = (low + high) * 0.5
    belt_half = (high - low) * 0.5
    inner_x = belt_half.x * 0.87
    inner_y = belt_half.y * 0.80
    moved = 0
    maximum_offset = 0.0
    for index, vertex in enumerate(torso.data.vertices):
        point = torso.matrix_world @ vertex.co
        lower_fade = smoothstep(low.z, low.z + 0.045, point.z)
        upper_fade = 1.0 - smoothstep(high.z - 0.055, high.z, point.z)
        influence = lower_fade * upper_fade
        if influence <= 1e-5:
            continue
        local_x = point.x - center.x
        local_y = point.y - center.y
        radius = ((local_x / inner_x) ** 2 + (local_y / inner_y) ** 2) ** 0.5
        if radius <= 1.0:
            continue
        target_world = point.copy()
        target_world.x = center.x + local_x / radius
        target_world.y = center.y + local_y / radius
        target_local = torso.matrix_world.inverted() @ target_world
        offset = (target_local - vertex.co) * min(1.0, influence * 0.92)
        key.data[index].co = vertex.co + offset
        moved += 1
        maximum_offset = max(maximum_offset, offset.length)
    key.value = 1.0
    torso["accessory_fit_shape"] = CINCH_KEY_NAME
    torso["accessory_fit_slot"] = "waist_accessory"
    return {
        "shape_key": CINCH_KEY_NAME,
        "moved_vertices": moved,
        "maximum_offset": maximum_offset,
        "belt_inner_half": [inner_x, inner_y],
        "belt_z_band": [low.z, high.z],
    }


def main() -> None:
    args = cli()
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    bpy.context.scene.frame_set(1)
    armature = bpy.data.objects.get(ARMATURE_NAME)
    if armature is None or armature.data.bones.get(WAIST_BONE) is None:
        raise RuntimeError("canonical Armature or waist bone missing")
    torso = bpy.data.objects.get(TORSO_NAME)
    if torso is None:
        raise RuntimeError("generated torso garment missing for waist corrective shape")
    old = bpy.data.objects.get(ACCESSORY_NAME)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)

    existing = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.source_glb.resolve()))
    imported = [obj for obj in bpy.data.objects if obj not in existing and obj.type == "MESH"]
    if not imported:
        raise RuntimeError("Hunyuan waist accessory GLB contains no mesh")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in imported:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = imported[0]
    bpy.ops.object.join()
    accessory = bpy.context.object
    accessory.name = ACCESSORY_NAME
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    source_vertices = len(accessory.data.vertices)
    source_faces = len(accessory.data.polygons)

    decimate = accessory.modifiers.new("GeneratedAssetRetopoProxy", "DECIMATE")
    decimate.decimate_type = "COLLAPSE"
    decimate.ratio = args.decimate_ratio
    decimate.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = accessory
    bpy.ops.object.modifier_apply(modifier=decimate.name)

    brown = bpy.data.materials.get("AdventurerLeather_Brown") or bpy.data.materials.new(
        "AdventurerLeather_Brown"
    )
    brown.diffuse_color = (0.20, 0.075, 0.025, 1.0)
    brown.use_nodes = True
    brown.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = brown.diffuse_color
    brown.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.74
    silver = bpy.data.materials.get("AdventurerHardware_Silver") or bpy.data.materials.new(
        "AdventurerHardware_Silver"
    )
    silver.diffuse_color = (0.42, 0.46, 0.48, 1.0)
    silver.use_nodes = True
    silver.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = silver.diffuse_color
    silver.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.65
    silver.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.42
    accessory.data.materials.clear()
    accessory.data.materials.append(brown)
    accessory.data.materials.append(silver)

    silver_faces = 0
    for polygon in accessory.data.polygons:
        center = polygon.center
        is_front_hardware = center.y <= -0.84 and abs(center.x) <= 0.28 and abs(center.z) <= 0.20
        polygon.material_index = 1 if is_front_hardware else 0
        silver_faces += int(is_front_hardware)

    for vertex in accessory.data.vertices:
        local = vertex.co - SOURCE_CENTER
        radius = Vector((local.x, local.y)).length
        # Increase the closed ring's inner clearance while preserving its
        # accepted outer silhouette and hand-swing clearance.  This compresses
        # radial leather thickness instead of uniformly scaling buckle/pouch.
        # Keep the generated closed ring inside the measured waist envelope.
        # The former outward radial expansion was the source of the visible
        # belt gap and made the pouches overshoot the Actor's sides.
        radial_offset = 0.0
        if radius > 1e-8 and radial_offset > 0.0:
            factor = (radius + radial_offset) / radius
            local.x *= factor
            local.y *= factor
        vertex.co = Vector(
            (
                TARGET_CENTER.x + local.x * TARGET_SCALE.x,
                TARGET_CENTER.y + local.y * TARGET_SCALE.y,
                TARGET_CENTER.z + local.z * TARGET_SCALE.z,
            )
        )
    accessory.data.update()
    group = accessory.vertex_groups.new(name=WAIST_BONE)
    group.add([vertex.index for vertex in accessory.data.vertices], 1.0, "REPLACE")
    modifier = accessory.modifiers.new("ActorArmature", "ARMATURE")
    modifier.object = armature
    modifier.use_vertex_groups = True
    accessory["source_kind"] = "Hunyuan3D-2MV generated waist accessory"
    accessory["wearable_slot"] = "waist_accessory"
    accessory["binding_mode"] = "rigid_waist_bone"
    accessory["actor_class"] = "ChibiActorV1"
    cinch_shape = add_accessory_cinch_shape(torso, accessory)

    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    report = {
        "schema": "hunyuan_generated_waist_accessory_adapter_v1",
        "actor_class": "ChibiActorV1",
        "slot": "waist_accessory",
        "visible_geometry_source": str(args.source_glb.resolve()),
        "source_vertices": source_vertices,
        "source_faces": source_faces,
        "compiled_vertices": len(accessory.data.vertices),
        "compiled_faces": len(accessory.data.polygons),
        "decimate_ratio": args.decimate_ratio,
        "bounds_frame_1": bounds(accessory),
        "binding": {"bone": WAIST_BONE, "weight": 1.0},
        "torso_corrective_shape": cinch_shape,
        "material_faces": {"leather": len(accessory.data.polygons) - silver_faces, "silver": silver_faces},
        "transform": {
            "source_center": list(SOURCE_CENTER),
            "target_center": list(TARGET_CENTER),
            "scale": list(TARGET_SCALE),
        },
        "status": "compiled_motion_and_visual_review_required",
    }
    args.manifest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
