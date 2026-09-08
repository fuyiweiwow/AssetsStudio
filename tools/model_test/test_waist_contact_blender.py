"""Headless analytic regression fixtures, not production accessory geometry."""
import math
import sys
import unittest
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fit_tpose_accessory_blender import build_bvh
from waist_contact_fit import fit_contact, audit_contact, sampled_containment


def ring(radius=.25, missing=False):
    n=180
    verts=[(r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n),z)
           for r,z in [(radius,.9),(radius,1.1),(radius+.02,.9),(radius+.02,1.1)] for i in range(n)]
    faces=[]
    for i in range(n):
        if missing and i<30:
            continue
        j=(i+1)%n
        faces.extend([(i,j,n+j,n+i),(2*n+j,2*n+i,3*n+i,3*n+j),
                      (n+i,n+j,3*n+j,3*n+i),(j,i,2*n+i,2*n+j)])
    data=bpy.data.meshes.new('ring')
    data.from_pydata(verts,[],faces)
    obj=bpy.data.objects.new('ring',data)
    bpy.context.collection.objects.link(obj)
    return obj


class Tests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cylinder_add(vertices=180,radius=.2,depth=2,location=(0,0,1))
        self.actor=bpy.context.object
        self.bvh=build_bvh([self.actor])
        self.center=Vector((0,0,1))

    def test_fit_and_budget(self):
        obj=ring()
        before=[tuple(p.vertices) for p in obj.data.polygons]
        fit_contact([obj],self.bvh,build_bvh([obj]),self.center,2,.012)
        result=audit_contact([obj],self.bvh,build_bvh([obj]),self.center,2,Vector((-.3,-.3,.8)),Vector((.3,.3,1.2)))
        self.assertTrue(all(result['gates'].values()))
        self.assertEqual(before,[tuple(p.vertices) for p in obj.data.polygons])
        self.assertAlmostEqual(result['contact_gap_h_min'],.006,delta=.0001)

    def test_reject_open_ring(self):
        obj=ring(missing=True)
        with self.assertRaisesRegex(ValueError,'complete'):
            fit_contact([obj],self.bvh,build_bvh([obj]),self.center,2,.012)

    def test_reject_large_displacement(self):
        obj=ring(radius=.6)
        with self.assertRaisesRegex(ValueError,'budget'):
            fit_contact([obj],self.bvh,build_bvh([obj]),self.center,2,.012)

    def test_containment_detects_enclosed_points(self):
        self.assertFalse(sampled_containment([Vector((0,0,1))],self.bvh,2)['pass'])
        self.assertTrue(sampled_containment([Vector((.4,0,1))],self.bvh,2)['pass'])

    def test_dense_ring_containment_with_zero_epsilon(self):
        obj=ring()
        tree=build_bvh([obj],epsilon=0)
        points=[Vector((.2*math.cos(i*.1),.2*math.sin(i*.1),1)) for i in range(128)]
        self.assertTrue(sampled_containment(points,tree,2)['pass'])
        self.assertFalse(sampled_containment([Vector((.26,0,1))],tree,2)['pass'])


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise RuntimeError('Waist contact regression failed')
