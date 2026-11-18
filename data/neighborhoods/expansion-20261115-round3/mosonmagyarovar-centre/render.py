#!/usr/bin/env python3
from pathlib import Path
import json,gzip
from PIL import Image,ImageDraw,ImageFont
H=Path(__file__).resolve().parent
ways=json.load(gzip.open(H/'source-roads.geojson.gz','rt'))['features'];areas=json.load(gzip.open(H/'source-areas.geojson.gz','rt'))['features'];targets=json.load(open(H/'target-selection.json'))
f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15)
small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)
views=[('belvaros',[17.2655,47.8737,17.2751,47.8812]),('dunapart',[17.2760,47.8545,17.2915,47.8665])]
for title,b in views:
 W,Hh=1500,1200
 def xy(c):return ((c[0]-b[0])/(b[2]-b[0])*W,(b[3]-c[1])/(b[3]-b[1])*Hh)
 im=Image.new('RGB',(W,Hh),'#fffdf7');d=ImageDraw.Draw(im)
 for a in areas:
  t=a['properties']['source']['tags'];cs=[xy(c) for c in a['geometry']['coordinates'][0]]
  if max(x for x,y in cs)<0 or min(x for x,y in cs)>W or max(y for x,y in cs)<0 or min(y for x,y in cs)>Hh:continue
  d.polygon(cs,fill='#dce9d0' if t.get('leisure') or t.get('landuse') in ['forest','grass','recreation_ground'] else '#e6e4df',outline='#aaa89a')
 names=set()
 for w in ways:
  t=w['properties']['source']['tags'];cs=w['geometry']['coordinates'];px=[xy(c) for c in cs]
  if max(x for x,y in px)<0 or min(x for x,y in px)>W or max(y for x,y in px)<0 or min(y for x,y in px)>Hh:continue
  if not t.get('highway') and not t.get('waterway'):continue
  d.line(px,fill='#3186b9' if t.get('waterway') else '#bf8658' if t.get('highway') in ['primary','secondary','tertiary'] else '#92918b',width=4 if t.get('waterway') else 3 if t.get('highway') in ['primary','secondary','tertiary'] else 1)
 for w in ways:
  t=w['properties']['source']['tags'];cs=w['geometry']['coordinates'];n=w['properties'].get('name');px=[xy(c) for c in cs]
  visible=[(x,y) for x,y in px if 20<x<W-100 and 20<y<Hh-30]
  if not n or n in names or not visible or t.get('highway') not in ['primary','secondary','tertiary','residential','pedestrian','unclassified'] and not t.get('waterway'):continue
  names.add(n);x,y=visible[len(visible)//2];d.text((x+3,y),n,fill='#172d32',font=small,stroke_width=1,stroke_fill='white')
 if (H/'features.geojson').exists():
  for area in json.load(open(H/'features.geojson'))['features']:
   g=area['geometry'];polygons=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
   for poly in polygons:
    for ring in poly:d.line([xy(c) for c in ring],fill='#d1195a',width=5)
 for row in targets:
  c=row['pointCandidates'][0]['coordinates'];x,y=xy(c)
  if 0<x<W and 0<y<Hh:d.ellipse((x-5,y-5,x+5,y+5),fill='red');d.text((x+7,y-20),row['name'],fill='red',font=f,stroke_width=1,stroke_fill='white')
 im.save(H/(title+'-context.png'))
 (H/(title+'-registration.json')).write_text(json.dumps({'view':title,'bounds':b,'width':W,'height':Hh},indent=2)+'\n')
 print(title)
