#!/usr/bin/env python3
"""Render complete estimated rings over preserved actual street fabric, offline."""
from pathlib import Path
import gzip,json,math
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent
features=json.loads((HERE/'features.geojson').read_text())['features']
roads=[]
for fn in HERE.glob('*-source-roads.geojson.gz'):roads+=json.loads(gzip.open(fn,'rt').read())['features']
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15)
big=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
registrations=[];thumbs=[]
for idx,f in enumerate(features):
 ring=f['geometry']['coordinates'][0];xs=[c[0] for c in ring];ys=[c[1] for c in ring]
 dx=max(xs)-min(xs);dy=max(ys)-min(ys)
 B=[min(xs)-dx*.15,min(ys)-dy*.15,max(xs)+dx*.15,max(ys)+dy*.15]
 W,H=1200,1100
 xy=lambda c:((c[0]-B[0])/(B[2]-B[0])*W,(B[3]-c[1])/(B[3]-B[1])*(H-45)+45)
 im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
 d.text((8,6),f['properties']['name']+' — estimated / low confidence',fill='#300',font=big)
 seen=set()
 for road in roads:
  cs=road['geometry']['coordinates'];t=road['properties']['source']['tags'];name=road['properties'].get('name')
  if not any(B[0]<=x<=B[2] and B[1]<=y<=B[3] for x,y,*_ in cs):continue
  hw=t.get('highway');major=hw in ['motorway','trunk','primary','secondary','tertiary']
  color='#999' if major else '#ccc'
  if t.get('railway'):color='#666'
  if t.get('waterway'):color='#5aa'
  d.line([xy(c) for c in cs],fill=color,width=3 if major else 1)
  if name and name not in seen and (major or hw in ['residential','living_street','unclassified'] or t.get('waterway')):
   X,Y=xy(cs[len(cs)//2])
   if 0<X<W and 45<Y<H:d.text((X,Y),name,fill='#666',font=font);seen.add(name)
 d.line([xy(c) for c in ring],fill='#c42f28',width=4)
 X,Y=xy(f['properties']['namePoint']['coordinates'])
 if 0<X<W and 45<Y<H:d.ellipse((X-5,Y-5,X+5,Y+5),fill='#c00')
 key=f'preview-{idx:02d}.png';im.save(HERE/key)
 registrations.append({'name':f['properties']['name'],'image':key,'boundsWgs84':B,'imageSize':[W,H],'titleHeight':45,'redOutline':'Estimated manual ring','redPoint':'Archived name point; may be outside the ring'})
 thumb=im.copy();thumb.thumbnail((400,367));thumbs.append(thumb)
rows=math.ceil(len(thumbs)/4);sheet=Image.new('RGB',(1600,367*rows),'white')
for i,t in enumerate(thumbs):sheet.paste(t,((i%4)*400,(i//4)*367))
sheet.save(HERE/'preview-contact-sheet.jpg',quality=88)
(HERE/'preview-registration.json').write_text(json.dumps(registrations,ensure_ascii=False,indent=2)+'\n')
print('Rendered',len(features),'complete-boundary previews')
