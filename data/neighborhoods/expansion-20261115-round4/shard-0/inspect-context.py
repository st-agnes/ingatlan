#!/usr/bin/env python3
from pathlib import Path
import json,gzip,sys,math
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import shape,Point,box
P=Path(__file__).resolve().parent;C=P.parent/'contexts';out=P/'review-maps';out.mkdir(exist_ok=True)
fs=json.load(open(P/'assignment.json'))['municipalities'];remaining=json.load(open(P/'unresolved.json'))['remainingNames'];wanted={(r['municipality'],r['name']) for r in remaining}
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12);titlefont=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
manifest=[]
proposals=json.load(open(P/'field-circuit-proposals.geojson'))['features'] if (P/'field-circuit-proposals.geojson').exists() else []
for c in fs:
 roads=json.load(gzip.open(C/c['contextKey']/'roads.geojson.gz','rt'))['features'];areas=json.load(gzip.open(C/c['contextKey']/'areas.geojson.gz','rt'))['features'];labels=json.load(open(C/c['contextKey']/'labels.geojson'))['features']
 for t in c['targets']:
  if (c['municipality'],t['name']) not in wanted or not t['pointCandidates']:continue
  lon,lat=t['pointCandidates'][0]['coordinates'];metres=900;dy=metres/111320;dx=dy/math.cos(math.radians(lat));bounds=(lon-dx,lat-dy,lon+dx,lat+dy);view=box(*bounds);W,H=900,850
  def xy(cs):return ((cs[0]-bounds[0])/(bounds[2]-bounds[0])*W,(bounds[3]-cs[1])/(bounds[3]-bounds[1])*H)
  im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
  candidates=[]
  for i,f in enumerate(areas):
   g=shape(f['geometry']);tags=f['properties']['tags']
   if not g.intersects(view) or tags.get('natural')=='mountain_range':continue
   if g.geom_type!='Polygon':continue
   if g.area<1e-7 and not tags.get('name'):continue
   px=[xy(c) for c in f['geometry']['coordinates'][0]]
   color='#e8f2dc' if tags.get('landuse') in ['forest','meadow','grass','orchard'] or tags.get('natural') in ['wood','grassland','scrub'] else '#f3ecd5' if tags.get('landuse') in ['farmland','vineyard','allotments'] else '#d8eaff' if tags.get('natural') in ['water','wetland'] else '#eeeeee'
   d.polygon(px,fill=color,outline='#bbbbbb');q=g.intersection(view).representative_point();x,y=xy(q.coords[0]);label='A'+str(i)+' '+str(f['properties']['name'] or tags.get('landuse') or tags.get('natural') or tags.get('amenity') or '')
   if 0<x<W-80 and 0<y<H-20:d.text((x,y),label,font=font,fill='#777777')
   candidates.append(dict(key='A'+str(i),sourceId=f['id'],name=f['properties']['name'],tags=tags,bounds=g.bounds))
  for i,f in enumerate(roads):
   g=shape(f['geometry']);tags=f['properties']['tags']
   if not g.intersects(view):continue
   if tags.get('highway') in ['footway','path','steps','cycleway']:co='#bbbbbb'
   elif tags.get('waterway'):co='#2674c4'
   elif tags.get('railway'):co='#a070b0'
   elif tags.get('highway') in ['track','service']:co='#aaaaaa'
   else:co='#555555'
   d.line([xy(c) for c in f['geometry']['coordinates']],fill=co,width=2 if co in ['#555555','#2674c4'] else 1)
   if tags.get('highway') in ['footway','path','steps','cycleway']:continue
   q=g.intersection(view).interpolate(0.5,normalized=True);x,y=xy(q.coords[0]);label='R'+str(i)+' '+str(f['properties']['name'] or tags.get('ref') or '')
   if 0<x<W-80 and 0<y<H-20:d.text((x,y),label,font=font,fill=co)
   candidates.append(dict(key='R'+str(i),sourceId=f['id'],name=f['properties']['name'],tags=tags,bounds=g.bounds))
  for f in proposals:
   if f['properties']['municipality']==c['municipality'] and f['properties']['name']==t['name']:
    d.line([xy(c) for c in f['geometry']['coordinates'][0]],fill='#ea5b00',width=4)
  for f in labels:
   if f['geometry']['type']!='Point':continue
   x,y=xy(f['geometry']['coordinates'])
   if 0<x<W and 0<y<H:d.ellipse((x-4,y-4,x+4,y+4),fill='red');d.text((x+5,y),str(f['properties']['name']),font=font,fill='red',stroke_fill='white',stroke_width=1)
  d.rectangle((0,0,W,29),fill='white');d.text((7,5),c['municipality']+' / '+t['name']+' – context, not a boundary',font=titlefont,fill='black')
  for x in range(0,W,150):d.text((x,H-20),str(round(bounds[0]+x/W*(bounds[2]-bounds[0]),5)),font=font,fill='blue')
  for y in range(150,H-30,150):d.text((0,y),str(round(bounds[3]-y/H*(bounds[3]-bounds[1]),5)),font=font,fill='blue')
  slug=c['contextKey']+'-'+str(c['targets'].index(t));im.save(out/(slug+'.png'))
  manifest.append(dict(city=c['municipality'],name=t['name'],contextKey=c['contextKey'],path='review-maps/'+slug+'.png',bounds=bounds,objects=candidates))
(P/'review-map-index.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print('Rendered',len(manifest),'context maps')
