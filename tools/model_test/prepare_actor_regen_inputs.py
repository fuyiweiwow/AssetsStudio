"""Bounded upper-body highlight recovery for the reviewed regeneration checkpoint.

Extends the existing v2 input contract without changing its historical replay.
Only colored bright pixels in the upper 60% of this neutral biped can grow the
mask; lower-body RGB and masks retain the existing leg-gap treatment.
"""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps
import actor_core_offline as base


def recover(image, rgba, record):
    rgb = np.array(image.convert('RGB'))
    result = np.array(rgba)
    mask = result[:, :, 3] > 128
    before = mask.copy()
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    x0, y0, x1, y1 = base.bbox(mask)
    height = y1-y0
    upper = np.indices(mask.shape)[0] < y0 + .60*height
    hue = float(np.median(hsv[:, :, 0][mask & upper]))
    delta = np.abs(hsv[:, :, 0].astype(float)-hue)
    delta = np.minimum(delta, 180-delta)
    eligible = upper & (hsv[:, :, 1] > 20) & (hsv[:, :, 2] > 150) & (delta < 12)
    mask = base.largest(mask | eligible)
    added = mask & ~before
    # The reviewed rear highlight occupies 10.8% of the old foreground. Keep
    # this extension explicitly bounded to this candidate family, not global.
    if added.sum() > .12*before.sum():
        raise ValueError('Highlight recovery exceeds 12% checkpoint budget')
    # This checkpoint has a solid broad head: open crown notches and holes must
    # not silently survive the mask stage. The gate is intentionally scoped.
    for y in range(round(y0+.08*height), round(y0+.48*height)):
        if len(base.runs(mask[y])) != 1:
            raise ValueError(f'Non-solid head scanline at y={y}')
    if not np.array_equal(mask[~upper], before[~upper]):
        raise ValueError('Highlight extension modified lower-body mask')
    result[:, :, 3] = mask.astype('uint8')*255
    if not np.array_equal(result[:, :, :3], rgb):
        raise ValueError('RGB changed')
    record['upper_highlight_recovery'] = {'added_pixels':int(added.sum()),
        'fraction':float(added.sum()/before.sum()), 'max_fraction':.12,
        'head_scanlines_solid':True, 'lower_mask_unchanged':True, 'rgb_unchanged':True}
    record['bbox'] = base.bbox(mask)
    return Image.fromarray(result), record


def prepare(front, right, back, output):
    output=Path(output)
    if output.exists():
        raise ValueError('Use a new output directory')
    images={}; records={}
    for role,path in [('front',front),('right',right),('back',back)]:
        image=Image.open(path)
        rgba, record=base.prepare_image(image,role)
        rgba, record=recover(image,rgba,record)
        record.update(source=str(Path(path).resolve()),source_sha256=base.sha256(path))
        images[role]=rgba; records[role]=record
    height=records['front']['bbox'][3]-records['front']['bbox'][1]
    for record in records.values():
        if abs((record['bbox'][3]-record['bbox'][1])/height-1)>.025:
            raise ValueError('Multiview height drift')
    images['left']=ImageOps.mirror(images['right'])
    records['left']={'derived_from':'right','method':'horizontal_mirror_including_lighting'}
    output.mkdir(parents=True)
    for role,image in images.items():
        image.save(output/(role+'.png'))
        records[role].update(file=role+'.png',sha256=base.sha256(output/(role+'.png')))
    manifest={'schema':'actor_core_offline_inputs_v1','profile':base.VERSION,
      'extension':'reviewed_biped_upper_highlight_recovery_v1',
      'implementation_sha256':base.sha256(__file__),
      'base_implementation_sha256':base.sha256(base.__file__),
      'status':'pass','qualification':'input_structure_only_not_art_or_rig_approval','views':records}
    (output/'input_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    base.validate_inputs(output/'input_manifest.json',{r:output/(r+'.png') for r in ['front','left','back']})
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['front','right','back','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(prepare(a.front,a.right,a.back,a.output),indent=2))
