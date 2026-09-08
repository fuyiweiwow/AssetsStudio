import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from actor_core_offline import prepare_image, prepare, validate_inputs, audit_mesh


def fixture(size=384, shift=0, leg_width=.09, shadow=False):
    image = Image.new('RGB', (size, size), (230, 230, 230))
    draw = ImageDraw.Draw(image)
    def rect(bounds, color=(216, 155, 115)):
        draw.rectangle(tuple(round((v + (shift if i % 2 == 0 else 0))*size) for i,v in enumerate(bounds)), fill=color)
    rect((.32,.08,.68,.35))
    rect((.40,.30,.60,.62))
    rect((.17,.37,.83,.44))
    rect((.40,.60,.40+leg_width,.91))
    rect((.60-leg_width,.60,.60,.91))
    if shadow:
        rect((.40,.895,.60,.91), (180, 130, 100))
    return image


class OfflineTests(unittest.TestCase):
    def test_proportions_and_translation(self):
        for size in [192,384,640]:
            for shift in [-.07,0,.055]:
                for width in [.075,.09]:
                    with self.subTest(size=size,shift=shift,width=width):
                        source = fixture(size,shift,width,True)
                        result, report = prepare_image(source,'front')
                        self.assertTrue(np.array_equal(np.array(source),np.array(result)[:,:,:3]))
                        gap=report['leg_gap']
                        self.assertFalse(np.array(result)[gap['start_y']:,gap['left']:gap['right'],3].any())
                        self.assertEqual(result.getpixel((round((.43+shift)*size),round(.85*size)))[3],255)

    def test_no_added_foreground(self):
        _, report=prepare_image(fixture(),'back')
        self.assertEqual(report['removed_fraction'],0)
        self.assertEqual(report['added_foreground_pixels'],0)

    def test_reject_no_gap(self):
        with self.assertRaisesRegex(ValueError,'separated-leg'):
            prepare_image(fixture(leg_width=.12),'front')

    def test_pale_highlight_not_punched_out(self):
        image=fixture()
        ImageDraw.Draw(image).ellipse((175,60,187,72),fill=(245,230,220))
        result,report=prepare_image(image,'back')
        self.assertEqual(result.getpixel((180,65))[3],255)
        self.assertGreater(report['added_foreground_pixels'],0)

    def test_neutral_hole_rejected(self):
        image=fixture()
        ImageDraw.Draw(image).ellipse((175,60,187,72),fill=(230,230,230))
        with self.assertRaisesRegex(ValueError,'interior holes'):
            prepare_image(image,'back')

    def test_reject_background(self):
        with self.assertRaisesRegex(ValueError,'neutral'):
            prepare_image(Image.new('RGB',(192,192),'green'),'front')

    def test_manifest_and_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/'source.png'
            fixture().save(source)
            out=root/'inputs'
            prepare(source,source,source,out)
            paths={role:out/(role+'.png') for role in ['front','left','back']}
            validate_inputs(out/'input_manifest.json',paths)
            with self.assertRaisesRegex(ValueError,'already exists'):
                prepare(source,source,source,out)
            image=Image.open(paths['front']).copy()
            image.putpixel((0,0),(0,0,0,0))
            image.save(paths['front'])
            with self.assertRaisesRegex(ValueError,'match'):
                validate_inputs(out/'input_manifest.json',paths)

    def test_mesh_slices_detect_bridge_without_mutation(self):
        import trimesh
        feet=[]
        for x in [-.2,.2]:
            foot=trimesh.creation.box(extents=[.2,1,.2])
            foot.apply_translation([x,.5,0])
            feet.append(foot)
        separated=trimesh.util.concatenate(feet)
        before=separated.vertices.copy()
        self.assertTrue(audit_mesh(separated)['gates']['separated_feet'])
        self.assertTrue(np.array_equal(before,separated.vertices))
        bridge=trimesh.creation.box(extents=[.6,.016,.2])
        bridge.apply_translation([0,.008,0])
        glued=trimesh.util.concatenate([separated,bridge])
        self.assertFalse(audit_mesh(glued)['gates']['separated_feet'])
        separated.apply_scale(3)
        separated.apply_translation([7,-4,2])
        self.assertTrue(audit_mesh(separated)['gates']['separated_feet'])


if __name__ == '__main__':
    unittest.main()
