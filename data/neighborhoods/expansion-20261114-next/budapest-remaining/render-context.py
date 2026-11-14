#!/usr/bin/env python3
"""Saved street contexts for rapid manual estate tracing, using existing local sources."""
from pathlib import Path
import gzip,json,sys
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent
title=sys.argv[1];B=tuple(map(float,sys.argv[2:6]));W,H=1800,1500
xy=lambda p:((p[0]-B[0])/(B[2]-B[0])*W,(B[3]-p[1])/(B[3]-B[1])*H)
im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14);big=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
seen=set()
for fn in HERE.glob('*-source-roads.geojson.gz'):
 for f in json.loads(gzip.open(fn,'rt').read())['features']:
  cs=f['geometry']['coordinates'];k=f['properties']['source']['tags'];name=f['properties'].get('name') or ''
  if not any(B[0]<x<B[2] and B[1]<y<B[3] for x,y,*_ in cs):continue
  road=k.get('highway');major=road in ['motorway','trunk','primary','secondary','tertiary']
  if road in ['footway','path','steps','cycleway','track','service']:color='#ededed'
  elif k.get('railway'):color='#666'
  elif k.get('waterway'):color='#66b0bc'
  else:color='#aaa' if major else '#ccc'
  d.line([xy(a) for a in cs],fill=color,width=3 if major else 1)
  if name and name not in seen and (major or road in ['residential','living_street','pedestrian','unclassified'] or k.get('waterway')):
   X,Y=xy(cs[len(cs)//2])
   if 0<X<W and 0<Y<H:d.text((X,Y),name,fill='#555' if major else '#999',font=font);seen.add(name)
for i in range(1,6):
 lon=B[0]+(B[2]-B[0])*i/6;x,_=xy((lon,B[1]));d.line((x,0,x,H),fill='#eee');d.text((x+2,3),str(round(lon,5)),fill='#888',font=font)
 lat=B[1]+(B[3]-B[1])*i/6;_,y=xy((B[0],lat));d.line((0,y,W,y),fill='#eee');d.text((2,y),str(round(lat,5)),fill='#888',font=font)
pts=json.loads((HERE/'name-points.geojson').read_text())['features']
for f in pts:
 X,Y=xy(f['geometry']['coordinates'])
 if 0<X<W and 0<Y<H:d.ellipse((X-5,Y-5,X+5,Y+5),fill='#d00000');d.text((X+6,Y-19),f['properties']['name'],fill='#a00000',font=big)
im.save(HERE/(title+'-context.png'))
(HERE/(title+'-context-registration.json')).write_text(json.dumps({'boundsWgs84':B,'imageSize':[W,H],'operation':'x=(lon-west)/(east-west)*width; y=(north-lat)/(north-south)*height'},indent=2)+'\n')
print(title,'saved',flush=True)
