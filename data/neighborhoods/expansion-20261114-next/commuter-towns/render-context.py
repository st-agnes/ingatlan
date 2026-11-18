#!/usr/bin/env python3
"""Draw retained streets/landuse/parent context; no online map tiles."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform
HERE=Path(__file__).resolve().parent
load=lambda fn:json.loads((HERE/fn).read_text())
forward=Transformer.from_crs(4326,23700,always_xy=True).transform
labels=load('source-labels.geojson')['features'];roads=load('source-barriers.geojson')['features'];land=load('source-landuse.geojson')['features'];parents=load('prior-parent-features.geojson')['features'];targets=load('target-circles-reference.geojson')['features']
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
def polygons(g):
 if g.geom_type=='Polygon':yield g
 elif hasattr(g,'geoms'):
  for a in g.geoms:yield from polygons(a)
for city in ['Budaörs','Tatabánya','Dunakeszi','Szigetszentmiklós','Gödöllő']:
 local=[f for f in labels if f['properties']['municipality']==city];pts=[forward(*f['geometry']['coordinates']) for f in local]
 wanted=[f for f in targets if f['properties']['municipality']==city];wp=[forward(*f['properties']['sourcePoint']['coordinates']) for f in wanted]
 x0=min(x for x,y in wp)-700;x1=max(x for x,y in wp)+700;y0=min(y for x,y in wp)-700;y1=max(y for x,y in wp)+700
 width=2000;height=int(width*(y1-y0)/(x1-x0));height=max(1200,min(2600,height));sx=(width-80)/(x1-x0);sy=(height-80)/(y1-y0)
 xy=lambda p:(round(40+(p[0]-x0)*sx),round(height-40-(p[1]-y0)*sy))
 im=Image.new('RGB',(width,height),'#fffdf7');d=ImageDraw.Draw(im)
 palette={'residential':'#fff4d9','industrial':'#ecd7ed','retail':'#f2d3db','commercial':'#f2d3db','forest':'#dbead0','wood':'#dbead0','scrub':'#e4eddb','meadow':'#e6eedf','water':'#c4e3ef','allotments':'#efe8c8'}
 for f in land:
  if city not in f['properties']['municipalities']:continue
  g=transform(forward,shape(f['geometry']));t=f['properties']['source']['tags'];fill=palette.get(t.get('landuse',t.get('natural')),'#edf0e0')
  for a in polygons(g):d.polygon([xy(p) for p in a.exterior.coords],fill=fill)
 for f in parents:
  if f['properties']['municipality']!=city:continue
  for a in polygons(transform(forward,shape(f['geometry']))):d.line([xy(p) for p in a.exterior.coords],fill='#cc5871',width=3)
 for f in roads:
  if city not in f['properties']['municipalities']:continue
  t=f['properties']['source']['tags'];g=transform(forward,shape(f['geometry']));k=t.get('highway');bold=k in {'motorway','trunk','primary','secondary','tertiary'} or 'railway' in t or 'waterway' in t
  color='#54729b' if 'waterway' in t else '#66606a' if 'railway' in t else '#c2a46a' if bold else '#bdb9b0'
  d.line([xy(p) for p in g.coords],fill=color,width=3 if bold else 1)
  if bold and f['properties'].get('name'):
   m=g.interpolate(.5,normalized=True);x,y=xy((m.x,m.y))
   if 0<x<width and 0<y<height:d.text((x,y),f['properties']['name'],fill='#544a3a',font=small)
 for i,f in enumerate(wanted):
  x,y=xy(wp[i]);d.ellipse((x-5,y-5,x+5,y+5),fill='#a20000');text=str(i+1)+'. '+f['properties']['name'];box=d.textbbox((x+7,y-14),text,font=font);d.rectangle(box,fill='white');d.text((x+7,y-14),text,fill='#770000',font=font)
 for xx in range(int(x0)//500*500,int(x1)+500,500):
  x,y=xy((xx,y0));d.line((x,30,x,height-30),fill='#dddada');d.text((x,5),str(xx),font=small,fill='#777')
 for yy in range(int(y0)//500*500,int(y1)+500,500):
  x,y=xy((x0,yy));d.line((30,y,width-30,y),fill='#dddada');d.text((5,y),str(yy),font=small,fill='#777')
 slug={'Budaörs':'budaors','Tatabánya':'tatabanya','Dunakeszi':'dunakeszi','Szigetszentmiklós':'szigetszentmiklos','Gödöllő':'godollo'}[city]
 im.save(HERE/(slug+'-context.png'))
 (HERE/(slug+'-registration.json')).write_text(json.dumps({'municipality':city,'extentEov':[x0,y0,x1,y1],'pixelSize':[width,height],'pixelPadding':40,'targets':[{'number':i+1,'name':f['properties']['name'],'sourcePoint':f['properties']['sourcePoint']} for i,f in enumerate(wanted)]},ensure_ascii=False,indent=2)+'\n')
 print(city,width,height,flush=True)
