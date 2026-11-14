#!/usr/bin/env python3
from pathlib import Path
import json,gzip,math
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import shape,box,Point
from shapely.ops import transform
from pyproj import Transformer
HERE=Path(__file__).resolve().parent;to=Transformer.from_crs(4326,23700,always_xy=True).transform
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
def load(p):
 b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)['features']
def render(name,c,rad,roads,areas,points):
 x,y=to(*c);B=(x-rad,y-rad,x+rad,y+rad);bb=box(*B);sz=1200
 im=Image.new('RGB',(sz,sz),'#fffdf5');d=ImageDraw.Draw(im)
 def xy(x,y):return ((x-B[0])/(2*rad)*sz,sz-(y-B[1])/(2*rad)*sz)
 def lines(g,color,w):
  if g.geom_type in ['MultiPolygon','MultiLineString','GeometryCollection']:
   for q in g.geoms:lines(q,color,w)
  elif g.geom_type=='Polygon':
   d.polygon([xy(*p) for p in g.exterior.coords],fill=color,outline='#aaaaaa')
  elif g.geom_type in ['LineString','LinearRing']:d.line([xy(*p) for p in g.coords],fill=color,width=w)
 for f in sorted(areas,key=lambda f:-shape(f['geometry']).area):
  g=transform(to,shape(f['geometry']))
  t=f['properties']['source']['tags'];kind=t.get('landuse')
  color=('#c46c63' if t.get('building') else {'forest':'#d6e7c5','residential':'#f6dca4','farmyard':'#e2c7b0','industrial':'#c4bbdd','meadow':'#e0f0ce'}.get(kind,'#e6e9df'))
  if g.intersects(bb):lines(g.intersection(bb),color,1)
 rnames=[]
 for f in roads:
  g=transform(to,shape(f['geometry']))
  if not g.intersects(bb):continue
  part=g.intersection(bb);tags=f['properties']['source']['tags'];lines(part,'#585858' if tags.get('highway') else '#9b6a34',3)
  nm=f['properties'].get('name')
  if nm and part.length>40:
   p=part.centroid;tx,ty=xy(p.x,p.y);rnames.append((nm,tx,ty))
 seen=set()
 for nm,tx,ty in rnames:
  if nm in seen:continue
  seen.add(nm);d.text((tx,ty),nm,fill='#222',font=font,stroke_width=2,stroke_fill='white')
 for f in points:
  p=transform(to,shape(f['geometry']))
  if p.intersects(bb):
   tx,ty=xy(p.x,p.y);d.ellipse((tx-4,ty-4,tx+4,ty+4),fill='red');d.text((tx+5,ty+5),f['properties']['name'],fill='red',font=font,stroke_width=2,stroke_fill='white')
 for q in range(7):
  v=B[0]+2*rad*q/6;px,_=xy(v,y);d.line([(px,0),(px,sz)],fill='#ddd');d.text((px+2,2),str(round(v)),font=font,fill='blue')
  v=B[1]+2*rad*q/6;_,py=xy(x,v);d.line([(0,py),(sz,py)],fill='#ddd');d.text((2,py+2),str(round(v)),font=font,fill='blue')
 im.save(HERE/(name+'.png'))
 (HERE/(name+'-extent.json')).write_text(json.dumps({'crs':'EPSG:23700','bounds':B,'pixels':[sz,sz]},indent=2))
if __name__=='__main__':
 d=HERE.parent/'debrecen-kecskemet';render('feszek-context',[21.5838284,47.5253452],500,load(d/'context-roads.geojson'),load(d/'context-source-areas.geojson'),load(d/'context-name-points.geojson'))
