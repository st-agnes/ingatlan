#!/usr/bin/env python3
"""Render archived actual road, building and address evidence for manual tracing."""
import gzip,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform
H=Path(__file__).resolve().parent
F=Transformer.from_crs(4326,23700,always_xy=True).transform
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font=ImageFont.truetype(FONT,13);small=ImageFont.truetype(FONT,10)
def load(n):
 b=(H/n).read_bytes();return json.loads(gzip.decompress(b) if n.endswith('.gz') else b)
roads=load('source-roads.geojson.gz')['features'];areas=load('source-areas.geojson.gz')['features'];buildings=load('source-buildings.geojson.gz')['features'];addresses=load('source-addresses.geojson.gz')['features']
targets=load('baseline-targets.json')['targets']
for city,bounds in [('Dorog',(18.718,47.715,18.748,47.737)),('Jászberény',(19.861,47.482,19.949,47.520)),('Jászberény-Újerdő',(19.833,47.428,19.873,47.452))]:
 x1,y1=F(bounds[0],bounds[1]);x2,y2=F(bounds[2],bounds[3]);w=1500;scale=w/(x2-x1);h=round((y2-y1)*scale)
 im=Image.new('RGB',(w,h),'#ffffff');d=ImageDraw.Draw(im)
 def px(p):
  x,y=F(*p);return (round((x-x1)*scale),round((y2-y)*scale))
 for f in areas:
  if f['properties']['municipality']!=city.split('-')[0]:continue
  g=f['geometry'];col={'residential':'#f6eedb','industrial':'#ded8e8','forest':'#d5eacb','grass':'#ecf4df'}.get(f['properties']['tags'].get('landuse'),'#faf9ef')
  d.polygon([px(p) for p in g['coordinates'][0]],fill=col,outline='#aaa999')
 for f in buildings:
  d.polygon([px(p) for p in f['geometry']['coordinates'][0]],fill='#c4c4c4',outline='#999999')
 for f in roads:
  t=f['properties']['tags'];col='#2498d0' if t.get('waterway') else '#666666' if t.get('railway') else '#cdad82' if t.get('highway') in ['primary','secondary'] else '#aaaabb'
  d.line([px(p) for p in f['geometry']['coordinates']],fill=col,width=3 if t.get('highway') in ['primary','secondary'] else 1)
  name=f['properties'].get('name')
  if name and t.get('highway') not in ['footway','path','service','track']:
   p=px(f['geometry']['coordinates'][len(f['geometry']['coordinates'])//2])
   if 0<=p[0]<w and 0<=p[1]<h:d.text(p,name,font=small,fill='#555577')
 for f in addresses:
  t=f['properties']['tags'];st=t.get('addr:street',t.get('addr:place',''))
  if 'lakótelep' in st:
   p=px(f['geometry']['coordinates']);d.ellipse((p[0]-2,p[1]-2,p[0]+2,p[1]+2),fill='#ff7777')
 for i,t in enumerate(targets):
  if t['municipality']!=city.split('-')[0]:continue
  p=px(t['pointCandidates'][0]['coordinates']);d.ellipse((p[0]-5,p[1]-5,p[0]+5,p[1]+5),fill='#c70037')
  text=f"{i}: {t['name']}";bb=d.textbbox((p[0]+7,p[1]-8),text,font=font);d.rectangle(bb,fill='white');d.text((p[0]+7,p[1]-8),text,font=font,fill='#8a0030')
 im.save(H/(city+'-context.png'))
 (H/(city+'-registration.json')).write_text(json.dumps({'crs':'EPSG:23700','pixelWidth':w,'pixelHeight':h,'metreBounds':[x1,y1,x2,y2],'scale':scale,'sourceBoundsWgs84':bounds},ensure_ascii=False,indent=2)+'\n')
 print(city,w,h)
