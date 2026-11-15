#!/usr/bin/env python3
"""Draw a review map from local source roads and the reconstructed full district."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform
H=Path(__file__).resolve().parent;F=Transformer.from_crs(4326,23700,always_xy=True).transform
def read(n):return json.loads((H/n).read_bytes())
g=transform(F,shape(read('features.geojson')['features'][0]['geometry']));x1,y1,x2,y2=g.bounds
x1-=200;y1-=200;x2+=200;y2+=200;w=1200;s=w/(x2-x1);h=round((y2-y1)*s)
im=Image.new('RGB',(w,h),'white');d=ImageDraw.Draw(im)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)
bold=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',17)
def px(p):x,y=F(*p);return (round((x-x1)*s),round((y2-y)*s))
poly=read('features.geojson')['features'][0]['geometry']['coordinates'][0];d.polygon([px(p) for p in poly],fill='#e8f0de',outline='#325c20',width=4)
selected=set(x for leg in read('boundary-route-audit.json')['legs'] for x in leg['sourceWayIds'])
for f in read('source-roads.geojson')['features']:
 ps=[px(p) for p in f['geometry']['coordinates']];hot=f['id'] in selected;name=f['properties'].get('name')
 d.line(ps,fill='#a23720' if hot else '#b4bbc6',width=3 if hot else 1)
 if name:
  x,y=ps[len(ps)//2]
  if 0<x<w and 0<y<h:d.text((x+3,y+2),name,font=font,fill='#a23720' if hot else '#718094')
p=px(read('baseline-target.json')['pointCandidates'][0]['coordinates']);d.ellipse((p[0]-6,p[1]-6,p[0]+6,p[1]+6),fill='#263c1e');d.text((p[0]+10,p[1]-18),'Városközpont',font=bold,fill='#173519')
d.rectangle((0,0,w,50),fill='white');d.text((12,7),'Mezőberény Városközpont – önkormányzati utcajegyzékből becsült terület',font=bold,fill='#183c20')
d.rectangle((0,h-35,w,h),fill='white');d.text((12,h-29),'© OpenStreetMap contributors / ODbL-1.0; 2010-es határleírás, 2021-es tervezési kontextus; becsült, nem földmérési határ.',font=font,fill='#344339')
im.save(H/'center-review.png')
(H/'review-map-registration.json').write_text(json.dumps({'crs':'EPSG:23700','metreBounds':[x1,y1,x2,y2],'scale':s,'pixelSize':[w,h]},indent=2)+'\n')
