import unittest
import numpy as np
from audit_actor_regen_review import compare


class SharedFrameTests(unittest.TestCase):
    def setUp(self):
        self.mask = np.zeros((768,768), dtype=bool)
        self.mask[66:732,186:583] = True

    def test_identity(self):
        self.assertTrue(compare(self.mask,self.mask)['pass'])

    def test_translation_not_normalized_away(self):
        shifted = np.roll(self.mask, 20, axis=1)
        self.assertFalse(compare(self.mask,shifted)['pass'])
        self.assertEqual(compare(self.mask,shifted)['center_error_px'],20)

    def test_width_drift_not_normalized_away(self):
        wider = self.mask.copy()
        wider[66:732,176:593] = True
        self.assertFalse(compare(self.mask,wider)['pass'])

    def test_empty_and_wrong_canvas_rejected(self):
        for mask in (np.zeros_like(self.mask),self.mask[:500]):
            with self.assertRaises(ValueError):
                compare(self.mask,mask)


if __name__ == '__main__':
    unittest.main()
