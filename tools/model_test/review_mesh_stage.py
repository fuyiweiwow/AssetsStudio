"""Two-stage four-view contact sheet from existing renders, without image edits."""
import argparse
from PIL import Image, ImageDraw
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    for name in ['before','after','output']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--before-label',default='SOURCE MESH')
    p.add_argument('--after-label',default='CANDIDATE - REVIEW REQUIRED')
    args=p.parse_args()
    sheet=Image.new('RGB',(1536,830),'#202124')
    draw=ImageDraw.Draw(sheet)
    for row,(folder,label) in enumerate([(args.before,args.before_label),(args.after,args.after_label)]):
        for col,view in enumerate(['front','right','back','left']):
            with Image.open(folder/(view+'.png')) as image:
                sheet.paste(image.convert('RGB').resize((384,384)),(col*384,row*410+25))
            draw.text((col*384+8,row*410+8),label+' '+view.upper(),fill='white')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    sheet.save(args.output)


if __name__=='__main__':
    main()
