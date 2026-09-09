import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from prepare_regen_foot_ab import clean


class FootAlphaTests(unittest.TestCase):
    def test_frozen_sources_protected(self):
        root = Path(__file__).resolve().parents[2]/'milestones/actor_regen_20260909/inputs'
        for role, expected in [('front',217),('right',79),('back',293)]:
            with self.subTest(role=role):
                a = np.array(Image.open(root/f'{role}.png').convert('RGBA'))
                b, report = clean(a)
                self.assertEqual(report['removed_pixels'],expected)
                self.assertEqual(report['added_pixels'],0)
                self.assertTrue(np.array_equal(a[:690],b[:690]))
                self.assertTrue(np.array_equal(a[:,:,:3],b[:,:,:3]))

    def test_wrong_canvas_rejected(self):
        with self.assertRaises(ValueError):
            clean(np.zeros((512,512,4),np.uint8))

    def test_excess_cleanup_rejected(self):
        a = np.zeros((768,768,4),np.uint8)
        a[690:734,290:480] = (120,110,110,255)
        with self.assertRaisesRegex(ValueError,'budget'):
            clean(a)


if __name__ == '__main__':
    unittest.main()
