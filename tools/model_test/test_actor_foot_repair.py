"""Frozen foot-flange counterexample and protection regressions; no GPU."""
import unittest
from pathlib import Path
import numpy as np
import trimesh
from audit_actor_foot_repair import audit
from repair_actor_foot_local import flange_audit

ROOT = Path(__file__).resolve().parents[2]


class FootRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = trimesh.load(ROOT / 'workspace/local_generation/actor_offline_gate_20260908/static_50k_v2/actor_offline_v2_50k_rig_mesh.glb', force='mesh', process=False)
        cls.fixed = trimesh.load(ROOT / 'workspace/local_generation/actor_foot_repair_20260908/local_v2/foot_candidate.glb', force='mesh', process=False)

    def test_original_closed_mesh_still_fails_foot_check(self):
        self.assertTrue(self.source.is_watertight)
        self.assertEqual(self.source.euler_number, 2)
        self.assertFalse(flange_audit(self.source)['pass'])

    def test_repaired_export_passes(self):
        self.assertTrue(all(audit(self.source, self.fixed)['gates'].values()))

    def test_upper_body_drift_rejected(self):
        broken = self.fixed.copy()
        i = int(np.argmax(broken.vertices[:, 1]))
        broken.vertices[i, 0] += .01
        self.assertFalse(audit(self.source, broken)['gates']['protected_geometry_preserved'])

    def test_new_hole_rejected(self):
        broken = self.fixed.copy()
        broken.update_faces(np.arange(len(broken.faces)) != 0)
        self.assertFalse(audit(self.source, broken)['gates']['structure'])


if __name__ == '__main__':
    unittest.main()
