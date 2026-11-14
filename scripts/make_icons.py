#!/usr/bin/env python3
"""Generate original application icons; no external artwork or bundled fonts."""
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]

def main():
    directory=ROOT/'src-tauri/icons';directory.mkdir(parents=True,exist_ok=True)
    image=Image.new('RGBA',(1024,1024),(0,0,0,0));draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((40,40,984,984),radius=225,fill='#eeeee3')
    draw.rounded_rectangle((60,60,964,964),radius=210,outline='#d4ddc8',width=5)
    color='#576e48'
    def bezier(p):
        pts=[]
        for i in range(121):
            t=i/120;u=1-t
            pts.append((sum((u**3,3*u*u*t,3*u*t*t,t**3)[j]*p[j][0] for j in range(4)),
                        sum((u**3,3*u*u*t,3*u*t*t,t**3)[j]*p[j][1] for j in range(4))))
        draw.line(pts,fill=color,width=15)
    bezier([(260,310),(255,565),(512,490),(512,800)])
    bezier([(764,310),(770,565),(512,490),(512,800)])
    draw.line((512,230,512,555),fill=color,width=13)
    for x,y,r in [(260,285,38),(764,285,38),(512,210,29)]:draw.ellipse((x-r,y-r,x+r,y+r),fill=color)
    for size,name in [(32,'32x32.png'),(128,'128x128.png'),(256,'128x128@2x.png'),(1024,'icon.png')]:
        image.resize((size,size),Image.Resampling.LANCZOS).save(directory/name)
    image.save(directory/'icon.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    image.save(directory/'icon.icns')
    print('Native macOS and Windows icon assets created.')
if __name__=='__main__':main()
