from pathlib import Path
import json,math
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import shape
P=Path(__file__).resolve().parent;areas=json.load(open(P/'source-areas.geojson'))['features'];lines=json.load(open(P/'source-lines.geojson'))['features'];labels=json.load(open(P/'source-labels.geojson'))['features'];font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14);small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',11)
views={'palyi':(21.698,47.389,21.811,47.450),'szalmas':(21.723,47.341,21.750,47.366),'mateszalka':(22.275,47.930,22.349,47.981),'oroshaza':(20.648,46.548,20.704,46.587)}
for n,b in views.items():
 w=1900;h=int(w*(b[3]-b[1])/(b[2]-b[0])/math.cos(math.radians((b[1]+b[3])/2)));im=Image.new('RGB',(w,h),'white');d=ImageDraw.Draw(im)
 def pixel(x,y):return ((x-b[0])/(b[2]-b[0])*w,(b[3]-y)/(b[3]-b[1])*h)
 def relevant(g):
  a=g.bounds;return not(a[2]<b[0] or a[0]>b[2] or a[3]<b[1] or a[1]>b[3])
 for f in areas:
  g=shape(f['geometry'])
  if not relevant(g):continue
  tags=f['properties']['tags'];fill={'residential':'#fff4ca','farmland':'#f4f2e8','forest':'#d9e6d0','farmyard':'#e5d2b9','allotments':'#e1edb0','industrial':'#e9d6e8','commercial':'#e9d6e8'}.get(tags.get('landuse'),'#e5e8d9')
  for a in (g.geoms if g.geom_type=='MultiPolygon' else [g]):
   cs=[pixel(x,y) for x,y in a.exterior.coords];d.polygon(cs,fill=fill,outline='#a5ad8c')
   if a.area<.00008 and a.area>.000001:
    c=a.representative_point();d.text(pixel(c.x,c.y),f['id'].split(':')[-1],font=small,fill='#557744')
 used=set()
 for f in lines:
  g=shape(f['geometry'])
  if not relevant(g):continue
  t=f['properties']['tags'];hw=t.get('highway');color='#2e74b5' if t.get('waterway') else '#242424' if t.get('railway') else '#747474' if hw=='track' else '#444444';width=4 if hw in ['primary','secondary','tertiary'] else 1
  cs=[pixel(x,y) for x,y in g.coords];d.line(cs,fill=color,width=width)
  name=f['properties']['name']
  if name and name not in used:
   q=g.interpolate(.5,normalized=True)
   if b[0]<q.x<b[2] and b[1]<q.y<b[3]:d.text(pixel(q.x,q.y),name,font=small,fill='#223b70');used.add(name)
 for f in labels:
  x,y=f['geometry']['coordinates']
  if b[0]<x<b[2] and b[1]<y<b[3]:
   xx,yy=pixel(x,y);d.ellipse((xx-4,yy-4,xx+4,yy+4),fill='red');d.text((xx+6,yy),f['properties']['name'],font=font,fill='red')
 im.save(P/(n+'-context.png'))
