#!/usr/bin/env python3
"""Render frozen street maps for manual bounds (no network)."""
from pathlib import Path
import gzip,json
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import shape,box
HERE=Path(__file__).resolve().parent
pts=json.loads((HERE/'name-points.geojson').read_text())['features']
roads=[];seen=set()
for fn in HERE.glob('*-source-roads.geojson.gz'):
 for f in json.loads(gzip.open(fn,'rt').read())['features']:
  if f['id'] not in seen:roads.append(f);seen.add(f['id'])
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19)
big=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',26)
regs=[]
for idx,p in enumerate(pts):
 lon,lat=p['geometry']['coordinates'];dx=.012;dy=.008
 if p['properties']['name'] in ['Csabaliget','Európa lakókert','EcoLiget lakópark','Honfoglalás lakópark','Óhegyi lakótelep']:dx=.006;dy=.004
 B=[lon-dx,lat-dy,lon+dx,lat+dy];W,H=2000,1800
 xy=lambda c:((c[0]-B[0])/(B[2]-B[0])*W,(B[3]-c[1])/(B[3]-B[1])*H)
 im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im);labels=[]
 for i in range(1,8):
  x=W*i/8;y=H*i/8;d.line((x,0,x,H),fill='#ddd');d.line((0,y,W,y),fill='#ddd')
  d.text((x+2,3),f'{B[0]+(B[2]-B[0])*i/8:.5f}',fill='#888',font=font)
  d.text((2,y),f'{B[3]-(B[3]-B[1])*i/8:.5f}',fill='#888',font=font)
 for f in roads:
  cs=f['geometry']['coordinates'];k=f['properties']['source']['tags'];name=f['properties'].get('name') or ''
  if not any(B[0]<x<B[2] and B[1]<y<B[3] for x,y,*_ in cs):continue
  road=k.get('highway');major=road in ['motorway','trunk','primary','secondary','tertiary']
  color='#dedede' if road in ['footway','path','steps','cycleway','track','service'] else '#888' if major else '#aaa'
  if k.get('railway'):color='#444'
  if k.get('waterway'):color='#4aa6c2'
  d.line([xy(c) for c in cs],fill=color,width=4 if major else 2)
  if name and (major or road in ['residential','living_street','pedestrian','unclassified'] or k.get('waterway')):
   X,Y=xy(cs[len(cs)//2])
   if 0<X<W and 0<Y<H and name not in labels:d.text((X,Y),name,fill='#444' if major else '#666',font=font);labels.append(name)
 for pt in pts:
  X,Y=xy(pt['geometry']['coordinates'])
  if 0<X<W and 0<Y<H:d.ellipse((X-6,Y-6,X+6,Y+6),fill='#c00');d.text((X+7,Y-25),pt['properties']['name'],font=big,fill='#a00')
 key=f'context-{idx:02d}';im.save(HERE/(key+'.png'))
 regs.append({'name':p['properties']['name'],'image':key+'.png','boundsWgs84':B,'imageSize':[W,H]})
 print(key,p['properties']['name'],flush=True)
(HERE/'context-registration.json').write_text(json.dumps(regs,ensure_ascii=False,indent=2)+'\n')
