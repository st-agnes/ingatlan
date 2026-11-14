from pathlib import Path
import json,math
from PIL import Image,ImageDraw,ImageFont
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3]
fwd=Transformer.from_crs(4326,23700,always_xy=True).transform
labels=json.loads((OUT/'source-labels.geojson').read_text())['features'];roads=json.loads((OUT/'source-barriers.geojson').read_text())['features']
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16);small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',11)
config=[('fehervar', 'Székesfehérvár',(598800,201500,606500,208500),['Almássytelep','Demkóhegy','Fecskepart','Feketehegy','Kadocsa','Királykút','Oncsatelep','Palotavárosi lakótelep','Papagáj-telep','Szedreskert','Sóstó','Tóváros','Velinszky László-lakótelep','Ősz utca'])]
for ident,city,bounds,wanted in config:
 W,H=1500,1450;x0,y0,x1,y1=bounds
 project=lambda x,y:((x-x0)/(x1-x0)*(W-100)+50,H-50-(y-y0)/(y1-y0)*(H-100))
 im=Image.new('RGB',(W,H),'white');draw=ImageDraw.Draw(im)
 native=json.loads((OUT/'fehervar-native-features.geojson').read_text())['features']
 for i,f in enumerate(native[:13]):
  g=transform(fwd,shape(f['geometry']));polys=list(g.geoms) if g.geom_type=='MultiPolygon' else [g]
  for p in polys:draw.polygon([project(x,y) for x,y in p.exterior.coords],fill=(240-i%3*10,245-i%5*5,235),outline=(155,175,150),width=2)
 for f in roads:
  p=f['properties'];t=p['source']['tags']
  if city not in p['municipalities']:continue
  g=transform(fwd,shape(f['geometry']));bb=g.bounds
  if bb[2]<x0 or bb[0]>x1 or bb[3]<y0 or bb[1]>y1:continue
  coords=[project(x,y) for x,y in g.coords];major=t.get('highway') in ['motorway','trunk','primary','secondary','tertiary']
  color=(70,70,70) if major else (160,160,160)
  if t.get('waterway'):color=(50,130,210)
  if t.get('railway'):color=(130,60,90)
  draw.line(coords,fill=color,width=3 if major else 1)
  if major and p.get('name'):
   pos=g.interpolate(.5,normalized=True);px,py=project(pos.x,pos.y)
   if 0<px<W and 0<py<H:draw.text((px,py),p['name'],font=small,fill=(30,30,30))
 for f in labels:
  p=f['properties']
  if p['municipality']!=city or p['name'] not in wanted:continue
  ex,ey=fwd(*f['geometry']['coordinates']);px,py=project(ex,ey)
  draw.ellipse((px-4,py-4,px+4,py+4),fill='red');draw.text((px+7,py-15),p['name'],font=font,fill=(180,0,0))
 for ex in range(math.ceil(x0/500)*500,int(x1),500):
  px,py=project(ex,y0);draw.text((px,H-35),str(ex),font=small,fill=(20,80,150));draw.line((px,0,px,H-50),fill=(200,220,230),width=1)
 for ey in range(math.ceil(y0/500)*500,int(y1),500):
  px,py=project(x0,ey);draw.text((3,py),str(ey),font=small,fill=(20,80,150));draw.line((50,py,W,py),fill=(200,220,230),width=1)
 im.save(OUT/(ident+'-remaining-context.png'))
