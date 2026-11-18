#!/usr/bin/env python3
from pathlib import Path
import json,gzip,math,sys
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import shape,box,Point
H=Path(__file__).resolve().parent;CTX=H.parent/'contexts';task=json.load(open(H/'target-selection.json'));(H/'maps').mkdir(exist_ok=True)
f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15);small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
def load(p):return json.load(gzip.open(p,'rt')) if p.suffix=='.gz' else json.load(open(p))
def rings(g):
 if g['type']=='Polygon':return [g['coordinates']]
 if g['type']=='MultiPolygon':return g['coordinates']
 return []
i=0;indices=set(map(int,sys.argv[1:])) if len(sys.argv)>1 else None
for city in task['municipalities']:
 c=CTX/city['contextKey'];rs=load(c/'roads.geojson.gz')['features'];ars=load(c/'areas.geojson.gz')['features'];labels=load(c/'labels.geojson')['features'];ads=load(c/'addresses.geojson.gz')['features']
 for t in city['targets']:
  idx=i;i+=1
  if indices is not None and idx not in indices:continue
  if not t['pointCandidates']:continue
  lon,lat=t['pointCandidates'][0]['coordinates'];n=t['name'].casefold()
  radius=550 if 'lakótelep' in n or 'lakópark' in n else 900
  if any(k in n for k in ['dűlő','hegy','hát','tüskés','feketés','besenyő','kígyós','suhogó']):radius=1250
  if n in ['balatonszéplak','szőny']:radius=2500
  W,Hh=1000,800;dy=radius/111320;dx=dy/math.cos(math.radians(lat))*W/Hh;b=[lon-dx,lat-dy,lon+dx,lat+dy];view=box(*b)
  def xy(c):return ((c[0]-b[0])/(b[2]-b[0])*W,(b[3]-c[1])/(b[3]-b[1])*Hh)
  im=Image.new('RGB',(W,Hh),'#fffdf6');d=ImageDraw.Draw(im)
  for a in ars:
   g=shape(a['geometry'])
   if not g.intersects(view):continue
   tags=a['properties']['tags'];col='#d5e6c9' if tags.get('natural') in ['wood','scrub'] or tags.get('landuse') in ['forest','orchard','vineyard','grass','recreation_ground'] else '#e5e2d7'
   if tags.get('natural')=='water' or tags.get('water'):col='#b5d9e7'
   for poly in rings(a['geometry']):d.polygon([xy(q) for q in poly[0]],fill=col,outline='#ada99a')
  near=[]
  for r in rs:
   g=shape(r['geometry'])
   if not g.intersects(view):continue
   tags=r['properties']['tags'];kind=tags.get('highway');width=3 if kind in ['motorway','trunk','primary','secondary','tertiary'] else 1;col='#c48b51' if width==3 else '#96958b'
   if tags.get('waterway'):col='#367fac';width=3
   if tags.get('railway'):col='#4c4a48';width=3
   d.line([xy(q) for q in r['geometry']['coordinates']],fill=col,width=width)
   if r['properties'].get('name'):near.append((g.distance(Point(lon,lat)),r))
  names=set()
  for dist,r in sorted(near,key=lambda x:x[0]):
   name=r['properties']['name'];tags=r['properties']['tags']
   if name in names or tags.get('highway') in ['path','footway','cycleway','steps','service']:continue
   visible=[xy(q) for q in r['geometry']['coordinates'] if view.covers(Point(q))]
   if not visible:continue
   names.add(name);x,y=visible[len(visible)//2]
   d.text((x+3,y),name,font=small,fill='#364444',stroke_width=1,stroke_fill='white')
   if len(names)>=20:break
  for a in ads:
   if view.covers(shape(a['geometry'])):
    x,y=xy(a['geometry']['coordinates']);d.ellipse((x-1,y-1,x+1,y+1),fill='#425b75')
  for lab in labels:
   if view.covers(shape(lab['geometry'])):
    x,y=xy(lab['geometry']['coordinates']);d.ellipse((x-3,y-3,x+3,y+3),fill='#e34b42');d.text((x+5,y-17),lab['properties']['name'],font=f,fill='#b02c26',stroke_width=1,stroke_fill='white')
  d.rectangle((0,0,W,30),fill='white');d.text((8,5),f"{idx:02d} {city['municipality']} – {t['name']} | map context only",font=f,fill='#1b3733')
  im.save(H/'maps'/f'{idx:02d}.png')
  (H/'maps'/f'{idx:02d}.json').write_text(json.dumps({'index':idx,'municipality':city['municipality'],'name':t['name'],'contextKey':city['contextKey'],'bounds':b,'width':W,'height':Hh,'sourceNamePoint':t['pointCandidates'][0],'role':'RENDER_VIEWPORT_ONLY_NOT_OUTPUT_GEOMETRY'},ensure_ascii=False,indent=2)+'\n')
  print(idx,city['municipality'],t['name'],flush=True)
