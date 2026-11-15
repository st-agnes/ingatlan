from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import json,math
P=Path(__file__).parent
W,H=1600,1050;bounds=(16.584,47.220,16.620,47.234)
def xy(c): return ((c[0]-bounds[0])/(bounds[2]-bounds[0])*W,(bounds[3]-c[1])/(bounds[3]-bounds[1])*H)
im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
if (P/'estate-source-areas.geojson').exists():
 for f in json.load(open(P/'estate-source-areas.geojson'))['features']:
  cs=[xy(c) for c in f['geometry']['coordinates'][0]];t=f['properties']['tags'];d.polygon(cs,fill='#eeeeee' if t.get('building') else '#ddeddd',outline='#cccccc')
for f in json.load(open(P/'source-ways.geojson'))['features']:
 if f['geometry']['type']!='LineString':continue
 t=f['properties']['source']['tags'];cs=f['geometry']['coordinates'];cs2=[xy(c) for c in cs]
 if max(x for x,y in cs2)<0 or min(x for x,y in cs2)>W or max(y for x,y in cs2)<0 or min(y for x,y in cs2)>H:continue
 if not (t.get('highway') or t.get('waterway')):continue
 color='#0088ff' if t.get('waterway') else '#555555';d.line(cs2,fill=color,width=2 if t.get('highway') in ['primary','secondary','tertiary'] else 1)
 name=f['properties']['name']
 if name and t.get('highway') and len(cs)>1:
  x,y=cs2[len(cs2)//2]
  if 0<x<W-100 and 0<y<H:d.text((x,y),name,fill='#000000',font=font)
for n,c in [('Géfin',[16.6092432,47.2273048]),('Öntöde',[16.6095069,47.2286067]),('Lovasiskola',[16.5940921,47.2263873])]:
 x,y=xy(c);d.ellipse((x-7,y-7,x+7,y+7),fill='red');d.text((x+9,y),n,fill='red',font=font)
for x in range(0,W,200):
 lon=bounds[0]+x/W*(bounds[2]-bounds[0]);d.text((x,0),str(round(lon,5)),font=font,fill='blue')
for y in range(0,H,150):
 lat=bounds[3]-y/H*(bounds[3]-bounds[1]);d.text((0,y),str(round(lat,5)),font=font,fill='blue')
im.save(P/'estates-reference.png')
