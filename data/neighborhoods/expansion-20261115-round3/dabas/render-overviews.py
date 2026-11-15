from pathlib import Path
import json,gzip
from PIL import Image,ImageDraw,ImageFont
H=Path(__file__).resolve().parent
R=json.load(gzip.open(H/'source-roads.geojson.gz','rt'))['features'];S=json.load(gzip.open(H/'source-surfaces.geojson.gz','rt'))['features'];pts=json.loads((H/'target-selection.json').read_text());font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17);big=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',24)
views=[('sari',[19.250,47.195,19.305,47.237]),('gyon',[19.305,47.140,19.378,47.185]),('dabas-core',[19.283,47.169,19.349,47.208]),('rural',[19.220,47.160,19.291,47.217]),('oregorszagut',[19.300,47.185,19.374,47.238])]
regs=[]
for name,B in views:
 W,HH=2200,1800;xy=lambda c:((c[0]-B[0])/(B[2]-B[0])*W,(B[3]-c[1])/(B[3]-B[1])*HH);im=Image.new('RGB',(W,HH),'white');d=ImageDraw.Draw(im)
 for f in S:
  cs=f['geometry']['coordinates'][0];t=f['properties']['source']['tags'];lu=t.get('landuse')
  if (lu not in ['residential','industrial','farmyard','commercial','retail','cemetery'] and not t.get('building')) or not any(B[0]<x<B[2] and B[1]<y<B[3] for x,y,*_ in cs):continue
  d.polygon([xy(c) for c in cs],fill={'building':'#888888','residential':'#ffffdf','industrial':'#eee5ee','farmyard':'#f3efd7','cemetery':'#dfefdf'}.get('building' if t.get('building') else lu,'#efeaff'))
 for i in range(1,11):
  X=W*i/11;Y=HH*i/11;d.line((X,0,X,HH),fill='#ddd');d.line((0,Y,W,Y),fill='#ddd');d.text((X+2,2),f'{B[0]+(B[2]-B[0])*i/11:.5f}',font=font,fill='#777');d.text((2,Y),f'{B[3]-(B[3]-B[1])*i/11:.5f}',font=font,fill='#777')
 seen=set()
 for f in R:
  cs=f['geometry']['coordinates'];t=f['properties']['source']['tags'];n=f['properties'].get('name');hw=t.get('highway');major=hw in ['primary','secondary','tertiary','trunk']
  if not any(B[0]<x<B[2] and B[1]<y<B[3] for x,y,*_ in cs):continue
  color='#777' if major else '#aaa';color='#ddd' if hw in ['service','track','path','footway','cycleway'] else color;color='#33aabb' if t.get('waterway') else color;color='#111' if t.get('railway') else color
  d.line([xy(c) for c in cs],fill=color,width=3 if major else 1)
  if n and n not in seen and (major or hw in ['residential','living_street','unclassified'] or t.get('waterway')):
   X,Y=xy(cs[len(cs)//2])
   if 0<X<W and 0<Y<HH:d.text((X,Y),n,font=font,fill='#666');seen.add(n)
 for p in pts:
  X,Y=xy(p['pointCandidates'][0]['coordinates'])
  if 0<X<W and 0<Y<HH:d.ellipse((X-5,Y-5,X+5,Y+5),fill='#b00');d.text((X+8,Y-25),p['name'],font=big,fill='#a00')
 fn=f'overview-{name}.png';im.save(H/fn);regs.append({'image':fn,'boundsWgs84':B,'imageSize':[W,HH]})
(H/'overview-registration.json').write_text(json.dumps(regs,ensure_ascii=False,indent=2)+'\n')
