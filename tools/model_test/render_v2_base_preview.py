"""Render a neutral front/three-quarter preview for the canonical v2 base."""

from pathlib import Path
import bpy
from mathutils import Vector


def material():
    m = bpy.data.materials.new("v2_base_neutral")
    m.diffuse_color = (0.36, 0.42, 0.48, 1.0)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.36, 0.42, 0.48, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.78
    return m


def main():
    source = Path(r"E:\WorkProject\AssetsStudio\workspace\model_test\male_adventurer_v2\hunyuan\male_adventurer_v2_base.glb")
    output = Path(r"E:\WorkProject\AssetsStudio\workspace\model_test\male_adventurer_v2\preview\male_adventurer_v2_base_front.png")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name.lower() != "cube"]
    mat = material()
    for obj in meshes:
        obj.data.materials.clear()
        obj.data.materials.append(mat)

    corners = [obj.matrix_world @ Vector(c) for obj in meshes for c in obj.bound_box]
    lo = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
    hi = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
    center = (lo + hi) / 2
    bpy.ops.object.camera_add(location=(0.0, -4.2, center.z))
    cam = bpy.context.object
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 2.35
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    for location, energy in (((2.5, -3.0, 4.0), 900), ((-2.0, -2.0, 2.5), 500), ((0.0, 2.5, 3.5), 700)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = 3.0
        light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.mesh.primitive_plane_add(size=5.0, location=(center.x, center.y, lo.z - 0.02))
    ground = bpy.context.object
    ground.data.materials.append(material())
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output)
    scene.world.color = (0.02, 0.025, 0.035)
    bpy.ops.render.render(write_still=True)
    print(f"V2_PREVIEW_WRITTEN {output}")


if __name__ == "__main__":
    main()
