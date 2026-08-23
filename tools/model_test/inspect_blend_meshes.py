import bpy

print("FILE", bpy.data.filepath)
for obj in bpy.context.scene.objects:
    if obj.type == "MESH":
        print(
            "MESH",
            obj.name,
            "dims",
            tuple(round(value, 3) for value in obj.dimensions),
            "verts",
            len(obj.data.vertices),
        )
