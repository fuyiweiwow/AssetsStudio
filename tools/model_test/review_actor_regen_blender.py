"""Read-only shorter-arm checkpoint review with shared front-derived framing."""
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
    ap.add_argument('--contract', type=Path, required=True)
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
    contract = json.loads(args.contract.read_text(encoding='utf-8'))
    reg = contract['registration']
    args.output.mkdir(parents=True, exist_ok=False)
    digest = hashlib.sha256(args.input.read_bytes()).hexdigest()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(args.input.resolve()))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    center = (lo + hi) / 2
    height = hi.z - lo.z
    scene = bpy.context.scene
    data = bpy.data.cameras.new('SharedFrontFrame')
    data.type = 'ORTHO'
    data.ortho_scale = height / reg['height_fraction']
    camera = bpy.data.objects.new('SharedFrontFrame', data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    shade = scene.display.shading
    shade.color_type = 'SINGLE'
    shade.show_shadows = False
    shade.show_cavity = False
    shade.background_type = 'WORLD'
    directions = {'front': (0,-1,0), 'right': (1,0,0), 'back': (0,1,0), 'left': (-1,0,0)}
    cameras = {}
    for mode in ('silhouette', 'beauty'):
        (args.output / mode).mkdir()
        shade.light = 'FLAT' if mode == 'silhouette' else 'STUDIO'
        shade.single_color = (1,1,1) if mode == 'silhouette' else (.55,.55,.55)
        scene.world.color = (0,0,0) if mode == 'silhouette' else (.08,.08,.08)
        for name, xyz in directions.items():
            camera.location = center + Vector(xyz) * height * 3
            camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler()
            rotation = camera.rotation_euler.to_quaternion()
            dx = (reg['common_frame_center_px'][0]-384)*data.ortho_scale/768
            dy = (reg['common_frame_center_px'][1]-384)*data.ortho_scale/768
            offset = -(rotation @ Vector((1,0,0)))*dx + (rotation @ Vector((0,1,0)))*dy
            camera.location += offset
            bpy.context.view_layer.update()
            cameras[name] = {'location': list(camera.location), 'rotation': list(camera.rotation_euler), 'ortho_scale': data.ortho_scale}
            scene.render.filepath = str((args.output/mode/f'{name}.png').resolve())
            bpy.ops.render.render(write_still=True)
    assert hashlib.sha256(args.input.read_bytes()).hexdigest() == digest
    (args.output/'registration.json').write_text(json.dumps({'source_sha256': digest, 'source_unchanged': True,
        'bounds_blender_z_up': [list(lo),list(hi)], 'contract': contract, 'cameras': cameras,
        'policy': 'single front-derived scale and image center for all views; no individual fitting; no floor'}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
