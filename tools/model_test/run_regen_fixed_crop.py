"""Checkpoint-local crop lock, without modifying frozen runner or model code."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import cv2
import numpy as np
from PIL import Image


def fixed_image(image, authority, size=512, border=.15):
    a = np.array(image.convert('RGBA'))
    ref = np.array(authority.convert('RGBA'))
    if a.shape != ref.shape:
        raise ValueError('Shared source canvas required')
    y,x = np.where(ref[:,:,3] != 0)
    top,bottom,left,right = y.min(),y.max(),x.min(),x.max()
    h,w = bottom-top,right-left
    side = max(a.shape[:2])
    scale = int(side*(1-border))/max(h,w)
    hh,ww = int(h*scale),int(w*scale)
    canvas = np.zeros((side,side,4),dtype=np.uint8)
    yy,xx = (side-hh)//2,(side-ww)//2
    canvas[yy:yy+hh,xx:xx+ww] = cv2.resize(a[top:bottom,left:right],(ww,hh),interpolation=cv2.INTER_AREA)
    alpha = canvas[:,:,3:].astype(np.float32)/255
    rgb = (canvas[:,:,:3]*alpha + np.ones((side,side,3),np.uint8)*255*(1-alpha)).clip(0,255).astype(np.uint8)
    mask = (alpha*255).clip(0,255).astype(np.uint8)
    return cv2.resize(rgb,(size,size),interpolation=cv2.INTER_CUBIC),cv2.resize(mask,(size,size),interpolation=cv2.INTER_NEAREST)[...,None]


class LockedProcessor:
    def __init__(self, original, authority):
        self.original,self.authority = original,authority

    def __call__(self, images, **kwargs):
        import torch
        result, masks, ids = [],[],[]
        for role in sorted(images,key=self.original.view2idx.get):
            rgb,mask = fixed_image(images[role],Image.open(self.authority/f'{role}.png'),self.original.size,self.original.border_ratio)
            to_tensor = lambda a: torch.from_numpy(a.copy()).float().permute(2,0,1)/255*2-1
            result.append(to_tensor(rgb)); masks.append(to_tensor(mask)); ids.append(self.original.view2idx[role])
        return {'image':torch.stack(result).unsqueeze(0),'mask':torch.stack(masks).unsqueeze(0),'view_idxs':tuple(ids)}


def audit(authority, candidate, processor_path, output):
    spec = importlib.util.spec_from_file_location('native_processor',processor_path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    native = module.ImageProcessorV2(size=512,border_ratio=.15)
    output.mkdir(parents=True,exist_ok=False)
    reports = {}
    for role in ('front','left','back'):
        ref = Image.open(authority/f'{role}.png')
        rgb,mask = native.load_image(ref,to_tensor=False)
        same,same_mask = fixed_image(ref,ref)
        changed,changed_mask = fixed_image(Image.open(candidate/f'{role}.png'),ref)
        gates = {'native_rgb_exact':bool(np.array_equal(rgb,same)), 'native_mask_exact':bool(np.array_equal(mask,same_mask)),
            'above_foot_rgb_exact':bool(np.array_equal(same[:420],changed[:420])),
            'above_foot_mask_exact':bool(np.array_equal(same_mask[:420],changed_mask[:420]))}
        reports[role] = {'gates':gates,'changed_rgb_pixels':int(np.any(same!=changed,axis=2).sum())}
        Image.fromarray(changed).save(output/f'{role}.png')
    report = {'status':'pass' if all(all(r['gates'].values()) for r in reports.values()) else 'fail','views':reports,
        'qualification':'Preprocessing equivalence and locality only; not model/style approval'}
    import torch
    mv = module.MVImageProcessorV2(size=512,border_ratio=.15)
    images = {role:Image.open(authority/f'{role}.png') for role in ('front','left','back')}
    a,b = mv(images),LockedProcessor(mv,authority)(images)
    report['native_tensor_exact'] = bool(torch.equal(a['image'],b['image']) and torch.equal(a['mask'],b['mask']) and a['view_idxs']==b['view_idxs'])
    if not report['native_tensor_exact']:
        report['status'] = 'fail'
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if report['status'] != 'pass':
        raise ValueError('Crop lock equivalence/locality failed')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--authority',type=Path,required=True)
    ap.add_argument('--candidate',type=Path)
    ap.add_argument('--processor',type=Path)
    ap.add_argument('--audit-output',type=Path)
    args,rest = ap.parse_known_args()
    if args.audit_output:
        print(json.dumps(audit(args.authority,args.candidate,args.processor,args.audit_output),indent=2))
        return
    import run_hunyuan3d_mv_shape as runner
    load = runner.load_split_pipeline
    def wrapped(*a,**kw):
        pipeline = load(*a,**kw)
        pipeline.image_processor = LockedProcessor(pipeline.image_processor,args.authority)
        return pipeline
    runner.load_split_pipeline = wrapped
    sys.argv = [sys.argv[0]] + rest
    raise SystemExit(runner.main())


if __name__ == '__main__':
    main()
