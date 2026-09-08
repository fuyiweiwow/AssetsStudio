"""Display alpha and RGB together; no generated or edited source imagery."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--before',type=Path,required=True)
    parser.add_argument('--after',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    sheet=Image.new('RGB',(1536,818),'#292929')
    draw=ImageDraw.Draw(sheet)
    for col,role in enumerate(['front','back']):
        for row,folder in enumerate([args.before,args.after]):
            with Image.open(folder/(role+'.png')) as source:
                rgba=source.convert('RGBA').resize((384,384))
                background=Image.new('RGBA',rgba.size,'#808080')
                background.alpha_composite(rgba)
                x,y=col*768,row*400+25
                sheet.paste(background.convert('RGB'),(x,y))
                sheet.paste(rgba.getchannel('A').convert('RGB'),(x+384,y))
            draw.text((x+10,row*400+8),('OLD' if row==0 else 'NEW')+' '+role.upper()+' RGB / ALPHA',fill='white')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    sheet.save(args.output)


if __name__=='__main__':
    main()
