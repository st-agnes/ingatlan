#!/usr/bin/env python3
from pathlib import Path
import json
from PIL import Image,ImageDraw
from pyproj import Transformer
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
CONFIG={'Szentes':('szentes',[20.23,46.632,20.277,46.681],[1600,1600]),'Ajka':('ajka',[17.516,47.087,17.602,47.122],[1900,1200]),'Baja':('baja',[18.92,46.16,18.975,46.198],[1600,1600])}
inv=json.loads((HERE/'target-name-points.json').read_text())['names'];cat=json.loads((HERE/'broader-source-contexts.geojson').read_text())['features'];eov=Transformer.from_crs(4326,23700,always_xy=True)
for city,(prefix,bbox,size) in CONFIG.items():
 left,bottom,right,top=bbox;width,height=size;origin=eov.transform(left,bottom);upper=eov.transform(right,top);scale=min(width/(upper[0]-origin[0]),height/(upper[1]-origin[1]))
 def px(pt):
  east,north=eov.transform(*pt);return((east-origin[0])*scale,height-(north-origin[1])*scale)
 img=Image.new('RGB',(width,height),'white');dr=ImageDraw.Draw(img)
 for f in cat:
  if f['properties']['municipality']!=city:continue
  polys=f['geometry']['coordinates'] if f['geometry']['type']=='MultiPolygon' else [f['geometry']['coordinates']]
  for poly in polys:
   for ring in poly:dr.line([px(p) for p in ring],fill='#bad8ce',width=1)
 for f in json.loads((HERE/(prefix+'-roads.geojson')).read_text())['features']:
  tags=f['properties']['tags'];color='#bbb';stroke=1
  if 'waterway' in tags:color='#2f63ba';stroke=3
  elif 'railway' in tags:color='black';stroke=2
  elif tags.get('highway') in ['motorway','trunk','primary','secondary','tertiary']:color='#666';stroke=2
  elif tags.get('highway') in ['footway','path','steps']:color='#ddd'
  dr.line([px(p) for p in f['geometry']['coordinates']],fill=color,width=stroke)
 if prefix=='szentes':
  for f in json.loads((HERE/'szentes-extra-water-context.geojson').read_text())['features']:dr.line([px(pt) for pt in f['geometry']['coordinates']],fill='#2f63ba',width=3)
 labels=[]
 for i,r in enumerate([r for r in inv if r['municipality']==city and not r['hasCollectedPolygon'] and r['pointCandidates']],1):
  point=r['pointCandidates'][0];x,y=px(point['coordinates']);labels.append({'name':r['name'],'pixel':[x,y],'sourcePoint':point})
  dr.ellipse((x-5,y-5,x+5,y+5),fill='red');dr.text((x+8,y-6),str(i)+':'+r['name'],fill='red',stroke_fill='white',stroke_width=1)
 (HERE/(prefix+'-registration.json')).write_text(json.dumps({'city':city,'eovOrigin':origin,'height':height,'scalePixelsPerMetre':scale,'labels':labels,'broaderOutlinesAreContextOnly':True},ensure_ascii=False,indent=2)+'\n');img.save(HERE/(prefix+'-road-map.png'))
 print(city,[(r['name'],[round(x) for x in r['pixel']]) for r in labels])
