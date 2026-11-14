#!/usr/bin/env python3
from pathlib import Path
import json
from PIL import Image,ImageDraw
from pyproj import Transformer

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
MAPS={'Pécs':{'prefix':'pecs','bbox':[18.14,46.022,18.285,46.122],'size':[1800,1600]},'Szeged':{'prefix':'szeged','bbox':[20.125,46.22,20.26,46.298],'size':[1700,1500]}}
points=json.loads((ROOT/'data/neighborhoods/expansion-20261114/inventory/known-names.json').read_text())['names']
catalog=json.loads((ROOT/'data/neighborhoods/search-areas.geojson').read_text())['features']
projection=Transformer.from_crs(4326,23700,always_xy=True)
for city,config in MAPS.items():
 left,bottom,right,top=config['bbox'];width,height=config['size'];origin=projection.transform(left,bottom);upper=projection.transform(right,top);scale=min(width/(upper[0]-origin[0]),height/(upper[1]-origin[1]))
 def px(pt):
  east,north=projection.transform(*pt);return((east-origin[0])*scale,height-(north-origin[1])*scale)
 img=Image.new('RGB',(width,height),'white');dr=ImageDraw.Draw(img)
 # Old broad source partitions give context, not a claim that fine borders are printed.
 for f in catalog:
  if f['properties']['municipality']!=city:continue
  polys=f['geometry']['coordinates'] if f['geometry']['type']=='MultiPolygon' else [f['geometry']['coordinates']]
  for poly in polys:
   for ring in poly:dr.line([px(p) for p in ring],fill='#bad8ce',width=1)
 for f in json.loads((HERE/(config['prefix']+'-roads.geojson')).read_text())['features']:
  t=f['properties']['tags'];cs=f['geometry']['coordinates'];color='#bbb';weight=1
  if 'waterway' in t:color='#2f63ba';weight=3
  elif 'railway' in t:color='black';weight=2
  elif t.get('highway') in ['motorway','trunk','primary','secondary','tertiary']:color='#666';weight=2
  elif t.get('highway') in ['footway','path','steps']:color='#ddd'
  dr.line([px(p) for p in cs],fill=color,width=weight)
 labels=[]
 for index,r in enumerate([r for r in points if r['municipality']==city and not r['hasCollectedPolygon'] and r['pointCandidates']],1):
  p=r['pointCandidates'][0];x,y=px(p['coordinates']);labels.append({'name':r['name'],'pixel':[x,y],'sourcePoint':p})
  dr.ellipse((x-5,y-5,x+5,y+5),fill='red');dr.text((x+8,y-6),str(index)+':'+r['name'],fill='red',stroke_fill='white',stroke_width=1)
 (HERE/(config['prefix']+'-registration.json')).write_text(json.dumps({'city':city,'eovOrigin':origin,'height':height,'scalePixelsPerMetre':scale,'size':config['size'],'labels':labels,'oldSourceOutlinesAreContextOnly':True},ensure_ascii=False,indent=2)+'\n')
 img.save(HERE/(config['prefix']+'-road-map.png'))
 print(city,[(r['name'],[round(x) for x in r['pixel']]) for r in labels])
