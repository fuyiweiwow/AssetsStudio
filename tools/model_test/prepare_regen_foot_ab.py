"""Frozen shorter-arm checkpoint: bounded foot-alpha-only input experiment."""
import argparse
import copy
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from actor_core_offline import bbox, sha256, validate_inputs


def clean(rgba):
    if rgba.shape != (768,768,4):
        raise ValueError('Checkpoint requires 768x768 RGBA')
    roi = np.zeros((768,768),bool)
    roi[690:734,290:480] = True
    mask = rgba[:,:,3] > 128
    hsv = cv2.cvtColor(rgba[:,:,:3],cv2.COLOR_RGB2HSV)
    shadow = (hsv[:,:,1] < 145) & ((hsv[:,:,0] < 9) | (hsv[:,:,2] < 205))
    after = mask & ~(roi & shadow)
    opened = cv2.morphologyEx(after.astype('uint8'),cv2.MORPH_OPEN,np.ones((3,3),np.uint8)) > 0
    after[roi] &= opened[roi]
    removed = mask & ~after
    if removed.sum() > 500:
        raise ValueError('Foot-alpha budget exceeded: 500 pixels per source view')
    out = rgba.copy()
    out[:,:,3] = after.astype('uint8')*255
    if not np.array_equal(out[~roi],rgba[~roi]) or not np.array_equal(out[:,:,:3],rgba[:,:,:3]):
        raise ValueError('Protected source changed')
    before_box, after_box = bbox(mask), bbox(after)
    if before_box[:3] != after_box[:3] or not 0 <= before_box[3]-after_box[3] <= 1:
        raise ValueError('Only a one-pixel floor-shadow reduction is allowed; no other bbox drift')
    return out, {'removed_pixels':int(removed.sum()), 'added_pixels':int((after & ~mask).sum()),
        'rgb_exact':True, 'outside_roi_exact':True, 'bbox_before':before_box, 'bbox_after':after_box,
        'floor_pixel_reduction':before_box[3]-after_box[3]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise ValueError('New output root required')
    contract = json.loads((args.baseline/'preflight.json').read_text(encoding='utf-8'))
    source = args.baseline/'input_replay/inputs'
    original = json.loads((source/'input_manifest.json').read_text(encoding='utf-8'))
    records, pending = {}, {}
    sheet = Image.new('RGB',(1200,600),'#252525')
    draw = ImageDraw.Draw(sheet)
    for col,role in enumerate(('front','right','back')):
        path = source/f'{role}.png'
        if sha256(path) != contract['input_sha256'][role]:
            raise ValueError('Frozen input hash mismatch: '+role)
        rgba = np.array(Image.open(path).convert('RGBA'))
        out, records[role] = clean(rgba)
        pending[role] = Image.fromarray(out)
        records[role]['parent_sha256'] = sha256(path)
        for row, data in enumerate((rgba,out)):
            crop = Image.fromarray(data).crop((285,674,485,744))
            bg = Image.new('RGBA',crop.size,'#66a0a8')
            bg.alpha_composite(crop)
            sheet.paste(bg.convert('RGB').resize((400,140),Image.Resampling.NEAREST),(col*400,row*300+20))
            mask = Image.fromarray(data[:,:,3]).crop((285,674,485,744))
            sheet.paste(mask.convert('RGB').resize((400,140),Image.Resampling.NEAREST),(col*400,row*300+160))
            draw.text((col*400+4,row*300+4),role+(' BEFORE' if row == 0 else ' ALPHA ONLY'),fill='white')
    pending['left'] = ImageOps.mirror(pending['right'])
    output = args.output/'input_replay/inputs'
    output.mkdir(parents=True)
    manifest = copy.deepcopy(original)
    manifest['extension'] = 'short_arm_bounded_foot_alpha_ab_v1'
    manifest['implementation_sha256'] = sha256(__file__)
    manifest['parent_manifest_sha256'] = sha256(source/'input_manifest.json')
    manifest['experimental_change'] = {'roi_xyxy':[290,690,480,734], 'pixel_budget_per_view':500, 'views':records}
    for role,img in pending.items():
        path = output/f'{role}.png'
        img.save(path)
        manifest['views'][role]['sha256'] = sha256(path)
        if role != 'left':
            manifest['views'][role]['bbox'] = records[role]['bbox_after']
        contract['input_sha256'][role] = sha256(path)
    (output/'input_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    validate_inputs(output/'input_manifest.json',{r:output/f'{r}.png' for r in ('front','left','back')})
    contract['scope'] = 'Foot-alpha-only AB; failed baseline preserved; no art or rig approval'
    contract['experimental_change'] = manifest['experimental_change']
    contract['parent_experiment'] = str(args.baseline)
    (args.output/'preflight.json').write_text(json.dumps(contract,indent=2),encoding='utf-8')
    (args.output/'reference_manifest.json').write_text(json.dumps(contract,indent=2),encoding='utf-8')
    sheet.save(args.output/'foot_alpha_review.png')
    print(json.dumps(records,indent=2))


if __name__ == '__main__':
    main()
