#!/usr/bin/env python3
from pathlib import Path
import json
from PIL import Image,ImageDraw
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
HERE=Path(__file__).resolve().parent
forward=Transformer.from_crs(4326,23700,always_xy=True).transform
for row in json.loads((HERE/'summary.json').read_text())['towns']:
 slug=row['file'].removesuffix('-features.geojson');reg=json.loads((HERE/(slug+'-registration.json')).read_text());x0,y0,x1,y1=reg['extentEov'];w,h=reg['pixelSize'];xy=lambda p:(40+(p[0]-x0)*(w-80)/(x1-x0),h-40-(p[1]-y0)*(h-80)/(y1-y0))
 im=Image.open(HERE/(slug+'-context.png')).convert('RGBA');layer=Image.new('RGBA',im.size);d=ImageDraw.Draw(layer)
 for f in json.loads((HERE/row['file']).read_text())['features']:
  g=transform(forward,shape(f['geometry']));polys=[g] if g.geom_type=='Polygon' else list(g.geoms)
  for a in polys:
   pts=[xy(p) for p in a.exterior.coords];d.polygon(pts,fill=(30,90,210,24));d.line(pts,fill=(25,70,190,220),width=4)
 Image.alpha_composite(im,layer).convert('RGB').save(HERE/(slug+'-selected.png'))
