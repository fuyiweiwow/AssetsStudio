import bpy
import math
import os
import sys
from mathutils import Vector


def arg(name):
    for item in sys.argv:
        if item.startswith(name + "="):
            return item.split("=", 1)[1]
    return os.environ.get("DEBUG_" + name.upper(), "")


def import_obj(path, label, color):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path)
    created = [o for o in bpy.data.objects if o not in before]
    for obj in created:
        obj.name = label + "_" + obj.name
        if obj.type == "MESH":
            mat = bpy.data.materials.new(label + "_material")
            mat.diffuse_color = (*color, 1.0)
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs["Base Color"].default_value = (*color, 1.0)
                bsdf.inputs["Roughness"].default_value = 0.72
                if "Emission Color" in bsdf.inputs:
                    bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
                    bsdf.inputs["Emission Strength"].default_value = 0.65
            obj.data.materials.append(mat)
    return created


bpy.ops.wm.read_factory_settings(use_empty=True)
avatar_path = arg("avatar")
garment_path = arg("garment")
out_path = arg("out")
avatar_objects = import_obj(avatar_path, "projected_avatar", (0.16, 0.36, 0.85)) if avatar_path else []
avatar_scale = float(arg("avatar_scale") or "1")
for obj in avatar_objects:
    obj.scale = (avatar_scale, avatar_scale, avatar_scale)
if garment_path:
    import_obj(garment_path, "garment", (0.72, 0.16, 0.08))

all_meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
corners = []
for obj in all_meshes:
    corners.extend([obj.matrix_world @ Vector(c) for c in obj.bound_box])
min_v = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
max_v = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
center = (min_v + max_v) * 0.5
extent = max(max_v.x - min_v.x, max_v.y - min_v.y, max_v.z - min_v.z)

view = (arg("view") or "three_quarter").lower()
if view == "front":
    # OBJ import rotates Y-up data into Blender's Z-up scene.  In the
    # Actor-first contract the face/front is +Z, which becomes Blender -Y.
    camera_location = (center.x, center.y - extent * 2.5, center.z + extent * 0.10)
elif view == "back":
    camera_location = (center.x, center.y + extent * 2.5, center.z + extent * 0.10)
elif view == "side":
    camera_location = (center.x + extent * 2.5, center.y, center.z + extent * 0.10)
else:
    camera_location = (center.x + extent * 1.8, center.y + extent * 2.3, center.z + extent * 0.45)
bpy.ops.object.camera_add(location=camera_location)
cam = bpy.context.object
cam.data.type = "ORTHO"
cam.data.ortho_scale = extent * 1.25
cam.rotation_euler = ((Vector(center) - cam.location).to_track_quat("-Z", "Y")).to_euler()
bpy.context.scene.camera = cam

bpy.ops.object.light_add(type="AREA", location=(center.x + extent, center.y - extent, center.z + extent * 1.5))
bpy.context.object.data.energy = 1400
bpy.context.object.data.shape = "DISK"
bpy.context.object.data.size = extent
bpy.ops.object.light_add(type="AREA", location=(center.x - extent, center.y + extent, center.z + extent * 0.5))
bpy.context.object.data.energy = 700
bpy.context.object.data.size = extent

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = out_path
scene.world = bpy.data.worlds.new("DebugWorld")
scene.world.color = (0.08, 0.08, 0.08)
bpy.ops.wm.save_as_mainfile(filepath=os.path.splitext(out_path)[0] + ".blend")
bpy.ops.render.render(write_still=True)
