"""Read-only cranium views, crown sections and pre/post-foot-repair comparison."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


def load(path):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    if path.suffix.lower() == '.fbx':
        bpy.ops.import_scene.fbx(filepath=str(path.resolve()), use_anim=False)
    else:
        bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if len(objects) != 1:
        raise ValueError('Expected one mesh')
    obj = objects[0]
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    return obj, points


def distance(a, b):
    tree = KDTree(len(b))
    for i, p in enumerate(b):
        tree.insert(p, i)
    tree.balance()
    return max(tree.find(p)[2] for p in a)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--fbx', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
    args.output.mkdir(parents=True, exist_ok=False)
    paths = [args.input, args.baseline, args.fbx]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    _, baseline = load(args.baseline)
    _, interchange = load(args.fbx)
    obj, points = load(args.input)
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    height = hi.z - lo.z
    head = [p for p in points if p.z > lo.z + height * .60]
    comparisons = {}
    for name, other in [('before_foot_repair', baseline), ('fbx_roundtrip', interchange)]:
        region = [p for p in other if p.z > lo.z + height * .60]
        comparisons[name] = {'current_head_vertices': len(head), 'other_head_vertices': len(region),
                             'bidirectional_max_distance': max(distance(head, region), distance(region, head))}
    bvh = BVHTree.FromPolygons(points, [list(p.vertices) for p in obj.data.polygons])
    sections = {}
    # Actual surface intersections; no fitted sphere or smoothing reference.
    for axis in (0, 1):
        samples = []
        for i in range(201):
            t = -.24 * height + .48 * height * i / 200
            origin = Vector((0, 0, hi.z + height))
            origin[axis] = t
            hit, _, _, _ = bvh.ray_cast(origin, Vector((0, 0, -1)))
            if hit is not None and hit.z > lo.z + height * .80:
                samples.append([t / height, (hit.z - lo.z) / height])
        sections['x' if axis == 0 else 'y'] = samples
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    shading = scene.display.shading
    shading.light = 'STUDIO'
    shading.color_type = 'SINGLE'
    shading.single_color = (.55, .55, .55)
    shading.show_shadows = False
    shading.show_cavity = False
    shading.show_specular_highlight = True
    shading.background_type = 'WORLD'
    scene.world.color = (.08, .08, .08)
    camera_data = bpy.data.cameras.new('CraniumInspection')
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = height * .69
    camera = bpy.data.objects.new('CraniumInspection', camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    aim = Vector((0, 0, lo.z + height * .775))
    views = {'front': (0,-1,0), 'right': (1,0,0), 'back': (0,1,0), 'left': (-1,0,0),
             'top': (0,0,1), 'front_upper': (1,-1,1), 'back_upper': (1,1,1), 'left_upper': (-1,1,1)}
    for name, xyz in views.items():
        camera.location = aim + Vector(xyz).normalized() * height * 3
        camera.rotation_euler = (aim-camera.location).to_track_quat('-Z','Y').to_euler()
        bpy.context.view_layer.update()
        scene.render.filepath = str((args.output / f'{name}.png').resolve())
        bpy.ops.render.render(write_still=True)
    unchanged = all(hashlib.sha256(p.read_bytes()).hexdigest() == hashes[str(p)] for p in paths)
    report = {'source_hashes': hashes, 'sources_unchanged': unchanged, 'height': height,
              'head_region': 'world z > min_z + 0.60H; includes face and ears',
              'comparisons': comparisons, 'crown_center_sections_normalized': sections,
              'views': list(views), 'limitations': 'Static geometry only. Two sections do not certify all surface concavity or animation.'}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    assert unchanged
    print(json.dumps({'sources_unchanged': unchanged, 'comparisons': comparisons}))


if __name__ == '__main__':
    main()
