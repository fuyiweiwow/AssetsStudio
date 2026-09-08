"""Untextured, ground-free body and foot inspection; no geometry mutation."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--frame', type=Path, help='Reuse an earlier framing.json')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
    args.output.mkdir(parents=True, exist_ok=False)
    original_hash = hashlib.sha256(args.input.read_bytes()).hexdigest()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(args.input.resolve()))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    for obj in meshes:
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    frame = json.loads(args.frame.read_text()) if args.frame else {'lo': list(lo), 'hi': list(hi)}
    lo, hi = Vector(frame['lo']), Vector(frame['hi'])
    center = (lo + hi) / 2
    height = hi.z - lo.z
    scene = bpy.context.scene
    camera_data = bpy.data.cameras.new('OrthographicInspection')
    camera_data.type = 'ORTHO'
    camera = bpy.data.objects.new('OrthographicInspection', camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'SINGLE'
    scene.display.shading.single_color = (.55, .55, .55)
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = False
    scene.display.shading.show_specular_highlight = True
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (.08, .08, .08)
    views = {'front': (0, -1, 0), 'right': (1, 0, 0), 'back': (0, 1, 0),
             'left': (-1, 0, 0), 'oblique': (1, -1, .7), 'bottom': (0, 0, -1)}
    for scope in ['body', 'feet']:
        aim = center.copy()
        if scope == 'feet':
            aim.z = lo.z + height * .06
        camera_data.ortho_scale = height / .8671875 if scope == 'body' else height * .40
        for name, xyz in views.items():
            direction = Vector(xyz).normalized()
            camera.location = aim + direction * height * 3
            camera.rotation_euler = (aim - camera.location).to_track_quat('-Z', 'Y').to_euler()
            bpy.context.view_layer.update()
            scene.render.filepath = str((args.output / f'{scope}_{name}.png').resolve())
            bpy.ops.render.render(write_still=True)
    (args.output / 'framing.json').write_text(json.dumps(frame, indent=2), encoding='utf-8')
    assert hashlib.sha256(args.input.read_bytes()).hexdigest() == original_hash
    (args.output / 'report.json').write_text(json.dumps({'source_sha256': original_hash,
        'source_unchanged': True, 'method': 'fixed shared orthographic framing; texture-free studio shading, no ground/shadow/cavity',
        'views': list(views)}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
