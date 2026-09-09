"""Regression: a bright connected crown highlight must not become a skull hole."""
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
import actor_core_offline as base
from prepare_actor_regen_inputs import recover

SOURCE=Path(__file__).resolve().parents[2]/'milestones/actor_regen_20260909/source/back.png'


class HighlightRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.image=Image.open(SOURCE)
        self.rgba,self.record=base.prepare_image(self.image,'back')

    def test_reviewed_highlight_recovers_without_changing_rgb_or_feet(self):
        before=np.array(self.rgba)
        fixed,record=recover(self.image,self.rgba,self.record)
        after=np.array(fixed)
        self.assertGreater(record['upper_highlight_recovery']['added_pixels'],10000)
        np.testing.assert_array_equal(after[:,:,:3],before[:,:,:3])
        np.testing.assert_array_equal(after[500:,:,3],before[500:,:,3])
        for y in range(120,300):self.assertEqual(len(base.runs(after[y,:,3]>128)),1)

    def test_neutral_gap_is_rejected_not_filled(self):
        source=np.array(self.image.convert('RGB'))
        source[70:210,390:420]=[190,190,190]
        rgba=np.array(self.rgba)
        rgba[70:210,390:420,3]=0
        with self.assertRaisesRegex(ValueError,'Non-solid head'):
            recover(Image.fromarray(source),Image.fromarray(rgba),self.record)


if __name__=='__main__':unittest.main()
