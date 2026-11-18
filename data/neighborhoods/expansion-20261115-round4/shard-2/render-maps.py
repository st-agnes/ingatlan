#!/usr/bin/env python3
from pathlib import Path
import json,gzip,sys
from PIL import Image,ImageDraw,ImageFont
H=Path(__file__).resolve().parent;R=next(x for x in H.parents if (x/'AGENTS.md').exists());T=json.loads((H/'task-selection.json').read_text());font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16);big=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',21);regs=[]
for m in T['municipalities']:
 if len(sys.argv)>1 and m['municipality'] not in sys.argv[1:]:continue
 C=H.parent/'contexts'/m['contextKey']
 if not (C/'roads.geojson.gz').exists() or not (C/'areas.geojson.gz').exists():continue
 roads=json.load(gzip.open(C/'roads.geojson.gz','rt'))['features'];areas=json.load(gzip.open(C/'areas.geojson.gz','rt'))['features'];pts=[p['coordinates'] for t in m['targets'] for p in t['pointCandidates']]
 # Each per-name map is a viewport only; no viewport is used as output geometry.
 for idx,tgt in enumerate(m['targets']):
  lon,lat=tgt['pointCandidates'][0]['coordinates'];dx=.012;dy=.008
  if any(x in tgt['name'] for x in ['lakó','Lakó','Misszió']):dx=.007;dy=.0047
  if tgt['name'] in ['Bösztör','Bösztörpuszta','Csanádpuszta','Homokpuszta','Petőfitanya']:dx=.023;dy=.015
  B=[lon-dx,lat-dy,lon+dx,lat+dy];W,HH=1800,1500;xy=lambda c:((c[0]-B[0])/(B[2]-B[0])*W,(B[3]-c[1])/(B[3]-B[1])*HH);im=Image.new('RGB',(W,HH),'white');d=ImageDraw.Draw(im)
  for f in areas:
   t=f['properties'].get('tags',f['properties'].get('source',{}).get('tags',{}));cs=f['geometry']['coordinates'];cs=[cs] if f['geometry']['type']=='Polygon' else cs
   for poly in cs:
    ring=poly[0]
    if not any(B[0]<x<B[2] and B[1]<y<B[3] for x,y,*_ in ring):continue
    lu=t.get('landuse');c='#ccc' if t.get('building') else {'residential':'#fff7d5','industrial':'#e8dfe8','farmyard':'#f3edd9','commercial':'#efdfef','cemetery':'#dcebdc'}.get(lu)
    if t.get('natural')=='water':c='#d8f0ff'
    if c:d.polygon([xy(c) for c in ring],fill=c)
  for i in range(1,9):
   X=W*i/9;Y=HH*i/9;d.line((X,0,X,HH),fill='#ddd');d.line((0,Y,W,Y),fill='#ddd');d.text((X+2,1),f'{B[0]+(B[2]-B[0])*i/9:.5f}',font=font,fill='#777');d.text((1,Y),f'{B[3]-(B[3]-B[1])*i/9:.5f}',font=font,fill='#777')
  seen=set()
  for f in roads:
   cs=f['geometry']['coordinates'];t=f['properties'].get('tags',f['properties'].get('source',{}).get('tags',{}));n=f['properties'].get('name');hw=t.get('highway');major=hw in ['primary','secondary','tertiary','trunk','motorway']
   if not any(B[0]<x<B[2] and B[1]<y<B[3] for x,y,*_ in cs):continue
   c='#777' if major else '#aaa';c='#ddd' if hw in ['service','track','path','footway','cycleway','steps'] else c;c='#3aa5be' if t.get('waterway') else c;c='#333' if t.get('railway') else c
   d.line([xy(c) for c in cs],fill=c,width=3 if major else 1)
   if n and n not in seen and (major or hw in ['residential','living_street','unclassified'] or t.get('waterway')):
    X,Y=xy(cs[len(cs)//2])
    if 0<X<W and 0<Y<HH:d.text((X,Y),n,font=font,fill='#666');seen.add(n)
  for t in m['targets']:
   for p in t['pointCandidates']:
    X,Y=xy(p['coordinates'])
    if 0<X<W and 0<Y<HH:d.ellipse((X-4,Y-4,X+4,Y+4),fill='#a00');d.text((X+6,Y-21),t['name'],font=big,fill='#a00')
  fn=f'map-{m["contextKey"]}-{idx:02d}.png';im.save(H/fn);regs.append(dict(municipality=m['municipality'],name=tgt['name'],image=fn,boundsWgs84=B,imageSize=[W,HH],contextKey=m['contextKey']))
old=H/'map-registration.json';prior=json.loads(old.read_text()) if old.exists() else [];keys={(x['municipality'],x['name']) for x in regs};prior=[x for x in prior if (x['municipality'],x['name']) not in keys];old.write_text(json.dumps(prior+regs,ensure_ascii=False,indent=2)+'\n');print('Rendered',len(regs),'maps')
