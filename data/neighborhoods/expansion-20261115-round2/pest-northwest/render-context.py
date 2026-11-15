#!/usr/bin/env python3
from pathlib import Path
import gzip,json,sys
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent
pts=json.loads((HERE/'target-selection.json').read_text())
fns=[HERE/'source-roads.geojson.gz'] if (HERE/'source-roads.geojson.gz').exists() else list(HERE.glob('cached-*-roads.geojson.gz'))
roads=[]
for fn in fns:roads+=json.loads(gzip.open(fn,'rt').read())['features']
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18);big=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',24)
regs=[]
for idx,p in enumerate(pts):
 if len(sys.argv)>1 and p['municipality']!=sys.argv[1]:continue
 lon,lat=p['pointCandidates'][0]['coordinates'];dx=.014;dy=.009
 if 'lakótelep' in p['name'] or p['name']=='Palota-kert':dx=.007;dy=.0045
 B=[lon-dx,lat-dy,lon+dx,lat+dy];W,H=1800,1600
 xy=lambda c:((c[0]-B[0])/(B[2]-B[0])*W,(B[3]-c[1])/(B[3]-B[1])*H)
 im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
 for i in range(1,8):
  X=W*i/8;Y=H*i/8;d.line((X,0,X,H),fill='#ddd');d.line((0,Y,W,Y),fill='#ddd')
  d.text((X+2,2),f'{B[0]+(B[2]-B[0])*i/8:.5f}',font=font,fill='#888');d.text((2,Y),f'{B[3]-(B[3]-B[1])*i/8:.5f}',font=font,fill='#888')
 seen=set()
 for r in roads:
  cs=r['geometry']['coordinates'];t=r['properties']['source']['tags'];n=r['properties'].get('name')
  if not any(B[0]<x<B[2] and B[1]<y<B[3] for x,y,*_ in cs):continue
  hw=t.get('highway');major=hw in ['motorway','trunk','primary','secondary','tertiary']
  color='#888' if major else '#bbb'
  if hw in ['service','track','footway','path','cycleway','steps']:color='#ddd'
  if t.get('railway'):color='#555'
  if t.get('waterway'):color='#4aa'
  d.line([xy(c) for c in cs],fill=color,width=3 if major else 1)
  if n and n not in seen and (major or hw in ['residential','living_street','unclassified'] or t.get('waterway')):
   X,Y=xy(cs[len(cs)//2])
   if 0<X<W and 0<Y<H:d.text((X,Y),n,font=font,fill='#666');seen.add(n)
 for q in pts:
  if q['municipality']!=p['municipality']:continue
  X,Y=xy(q['pointCandidates'][0]['coordinates'])
  if 0<X<W and 0<Y<H:d.ellipse((X-5,Y-5,X+5,Y+5),fill='#b00');d.text((X+7,Y-24),q['name'],font=big,fill='#a00')
 key=f'context-{idx:02d}.png';im.save(HERE/key);regs.append({'municipality':p['municipality'],'name':p['name'],'image':key,'boundsWgs84':B,'imageSize':[W,H]})
(HERE/'context-registration.json').write_text(json.dumps(regs,ensure_ascii=False,indent=2)+'\n')
print('rendered',len(regs),'maps')
