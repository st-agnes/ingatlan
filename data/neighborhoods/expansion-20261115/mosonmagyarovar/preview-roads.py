import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
P=Path(__file__).parent
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
for title,bounds in [('core',(17.264,47.865,17.289,47.883)),('north',(17.252,47.876,17.302,47.895)),('south',(17.266,47.855,17.292,47.875))]:
 W,H=1400,1100
 def xy(c):return ((c[0]-bounds[0])/(bounds[2]-bounds[0])*W,(bounds[3]-c[1])/(bounds[3]-bounds[1])*H)
 im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
 for f in json.load(open(P/'source-areas.geojson'))['features']:
  t=f['properties']['source']['tags'];cs=[xy(c) for c in f['geometry']['coordinates'][0]]
  if max(x for x,y in cs)<0 or min(x for x,y in cs)>W or max(y for x,y in cs)<0 or min(y for x,y in cs)>H:continue
  d.polygon(cs,fill='#edf4e6' if t.get('leisure') else '#eeeeee',outline='#aaaaaa')
 for f in json.load(open(P/'source-ways.geojson'))['features']:
  t=f['properties']['source']['tags'];cs=f['geometry']['coordinates'];px=[xy(c) for c in cs]
  if max(x for x,y in px)<0 or min(x for x,y in px)>W or max(y for x,y in px)<0 or min(y for x,y in px)>H:continue
  if not t.get('highway') and not t.get('waterway'):continue
  d.line(px,fill='blue' if t.get('waterway') else '#888888',width=2)
  if t.get('highway') in ['primary','secondary','tertiary','residential','unclassified'] and f['properties']['name']:
   x,y=px[len(px)//2]
   if 0<x<W-130 and 0<y<H-20:d.text((x,y),f['properties']['name'],fill='black',font=font)
 for f in json.load(open(P/'source-named-points.geojson'))['features']:
  x,y=xy(f['geometry']['coordinates'])
  if 0<x<W and 0<y<H:d.ellipse((x-5,y-5,x+5,y+5),fill='red');d.text((x+6,y),f['properties']['name'],fill='red',font=font)
 for x in range(0,W,250):d.text((x,0),str(round(bounds[0]+x/W*(bounds[2]-bounds[0]),5)),fill='blue',font=font)
 for y in range(0,H,150):d.text((0,y),str(round(bounds[3]-y/H*(bounds[3]-bounds[1]),5)),fill='blue',font=font)
 im.save(P/f'roads-{title}.png')
