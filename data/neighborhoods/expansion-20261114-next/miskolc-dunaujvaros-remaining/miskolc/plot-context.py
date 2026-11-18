from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,gzip,sys
HERE=Path(__file__).resolve().parent
points=json.load(open(HERE/'target-names.json'));font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
lines=json.load(open(HERE/'literal-local-lines.geojson'))['features'];areas=json.load(open(HERE/'literal-local-areas.geojson'))['features']
configs={'west':(20.669,48.098,20.735,48.125),'south':(20.749,48.048,20.786,48.081),'industrial':(20.795,48.043,20.83,48.063),'mexiko':(20.70,48.08,20.726,48.096)}
for key,b in configs.items():
 w=1800;h=int(w*(b[3]-b[1])/((b[2]-b[0])*.669));im=Image.new('RGB',(w,h),'white');d=ImageDraw.Draw(im)
 def xy(c):return ((c[0]-b[0])/(b[2]-b[0])*w,(b[3]-c[1])/(b[3]-b[1])*h)
 for f in areas:
  t=f['properties'];cs=f['geometry']['coordinates'][0]
  if t.get('building'):continue
  fill={'residential':'#f1e6dd','industrial':'#e5d4eb','commercial':'#f3d9dc','farmland':'#eff2c8','forest':'#d3e5ce','vineyard':'#e5edb4'}.get(t.get('landuse'),None)
  if fill:d.polygon([xy(c) for c in cs],fill=fill,outline='#b9b9b9')
 for f in lines:
  t=f['properties'];cs=f['geometry']['coordinates'];xys=[xy(c) for c in cs]
  color='#888888';width=2
  if t.get('waterway'):color='#3d8bd9';width=3
  if t.get('railway'):color='#333333';width=3
  if t.get('highway') in ['motorway','trunk','primary','secondary']:color='#bd984e';width=4
  d.line(xys,fill=color,width=width)
  if t.get('name') and len(cs)>2:
   mid=cs[len(cs)//2];x,y=xy(mid)
   if 10<x<w-150 and 10<y<h-20:d.text((x,y),t['name'],font=font,fill='#777777')
 for f in points:
  if not f['pointCandidates']:continue
  c=f['pointCandidates'][0]['coordinates'];x,y=xy(c)
  if 0<x<w and 0<y<h:
   d.ellipse((x-7,y-7,x+7,y+7),fill='red');d.text((x+10,y-22),f['name'],font=font,fill='#c00000',stroke_width=2,stroke_fill='white')
 # Longitude/latitude grid retained for reproducible manual vertex placement.
 for k in range(11):
  lon=b[0]+(b[2]-b[0])*k/10;x,_=xy((lon,b[1]));d.text((max(0,x-40),h-25),f'{lon:.4f}',font=font,fill='#0050aa')
 for k in range(11):
  lat=b[1]+(b[3]-b[1])*k/10;_,y=xy((b[0],lat));d.text((0,max(0,y-10)),f'{lat:.4f}',font=font,fill='#0050aa')
 im.save(HERE/f'context-{key}.png')
 print(key,w,h)
