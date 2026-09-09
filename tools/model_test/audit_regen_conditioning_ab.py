"""Save actual local Hunyuan preprocessor outputs without loading weights."""
import argparse
import importlib.util
import json
from pathlib import Path
import numpy as np
from PIL import Image


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--before',type=Path,required=True)
    ap.add_argument('--after',type=Path,required=True)
    ap.add_argument('--processor',type=Path,required=True)
    args = ap.parse_args()
    spec = importlib.util.spec_from_file_location('local_hunyuan_preprocessor',args.processor)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    processor = module.ImageProcessorV2(size=512)
    output = args.after/'conditioning_audit'
    output.mkdir(exist_ok=False)
    reports = {}
    for role in ('front','left','back'):
        images = []
        for label,root in [('before',args.before),('after',args.after)]:
            rgb,mask = processor.load_image(Image.open(root/'input_replay/inputs'/f'{role}.png'),to_tensor=False)
            images.append(rgb)
            Image.fromarray(rgb).save(output/f'{label}_{role}.png')
        delta = np.any(images[0] != images[1],axis=2)
        diff = np.abs(images[0].astype(float)-images[1].astype(float))
        reports[role] = {'changed_rgb_pixels':int(delta.sum()),'changed_pixels_above_row_420':int(delta[:420].sum()),'mean_absolute_rgb_delta':float(diff.mean())}
    report = {'processor':str(args.processor),'border_ratio':.15,'size':512,'views':reports,
        'interpretation':'A source-local alpha change need not remain local after bbox-derived crop/resize. No inference weights loaded.'}
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
