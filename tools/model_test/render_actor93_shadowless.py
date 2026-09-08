"""Render the existing probe mesh with bright normal shading and no cast shadows."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def geometry_hash():
    digest = hashlib.sha256()
    for obj in sorted(bpy.context.scene.objects, key=lambda item: item.name):
        if obj.type == 'MESH':
            digest.update(obj.name.encode())
            for v in obj.data.vertices:
                digest.update(str(tuple(v.co)).encode())
            for p in obj.data.polygons:
                digest.update(str(tuple(p.vertices)).encode())
    return digest.hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
args.output.mkdir(parents=True, exist_ok=True)
before = geometry_hash()
scene = bpy.context.scene
camera = scene.camera
targets = [o for o in scene.objects if o.type == 'MESH']
corners = [o.matrix_world @ Vector(v) for o in targets for v in o.bound_box]
lo = Vector(tuple(min(v[i] for v in corners) for i in range(3)))
hi = Vector(tuple(max(v[i] for v in corners) for i in range(3)))
center = (lo + hi) * 0.5
height = hi.z - lo.z

material = bpy.data.materials.new('ShadowlessGeometryReview')
material.use_nodes = True
nodes = material.node_tree.nodes
nodes.clear()
links = material.node_tree.links
normal = nodes.new('ShaderNodeNewGeometry')
dot = nodes.new('ShaderNodeVectorMath')
dot.operation = 'DOT_PRODUCT'
links.new(normal.outputs['Normal'], dot.inputs[0])
absolute = nodes.new('ShaderNodeMath')
absolute.operation = 'ABSOLUTE'
links.new(dot.outputs['Value'], absolute.inputs[0])
brightness = nodes.new('ShaderNodeMath')
brightness.operation = 'MULTIPLY_ADD'
brightness.inputs[1].default_value = 0.3
brightness.inputs[2].default_value = 0.7
links.new(absolute.outputs[0], brightness.inputs[0])
emission = nodes.new('ShaderNodeEmission')
emission.inputs['Color'].default_value = (0.65, 0.45, 0.30, 1)
links.new(brightness.outputs[0], emission.inputs['Strength'])
output = nodes.new('ShaderNodeOutputMaterial')
links.new(emission.outputs[0], output.inputs['Surface'])
for obj in targets:
    obj.data.materials.clear()
    obj.data.materials.append(material)
scene.view_layers[0].material_override = material
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = scene.render.resolution_y = 768
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.view_settings.exposure = 0
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.22, 0.22, 0.22, 1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1
views = {'front': (0,-1,0), 'right': (1,0,0), 'back': (0,1,0), 'left': (-1,0,0), 'under_chin': (1,-1,-0.3)}
for name, xyz in views.items():
    direction = Vector(xyz).normalized()
    camera.location = center + direction * height * 2.8
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler()
    dot.inputs[1].default_value = direction
    scene.render.filepath = str((args.output / (name+'.png')).resolve())
    bpy.ops.render.render(write_still=True)
after = geometry_hash()
assert before == after, 'Preview changed geometry'
(args.output / 'report.json').write_text(json.dumps({'method': 'emission driven by 0.7 + 0.3 abs(normal dot view); no cast shadows or AO', 'geometry_sha256_before': before, 'geometry_sha256_after': after, 'geometry_unchanged': True, 'views': list(views)}, indent=2), encoding='utf-8')
