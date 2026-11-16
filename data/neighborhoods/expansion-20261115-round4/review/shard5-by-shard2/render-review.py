from pathlib import Path
import json,gzip
from PIL import Image,ImageDraw,ImageFont
R=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists());H=Path(__file__).resolve().parent;S=R/'data/neighborhoods/expansion-20261115-round4/shard-5';C=S/'source-inputs/felsozsolca-ab255f20';B=[20.851,48.114,20.884,48.137];W,HH=1800,1500;xy=lambda c:((c[0]-B[0])/(B[2]-B[0])*W,(B[3]-c[1])/(B[3]-B[1])*HH);im=Image.new('RGB',(W,HH),'white');d=ImageDraw.Draw(im);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
for f in json.load(gzip.open(C/'areas.geojson.gz','rt'))['features']:
 t=f['properties']['tags'];cs=f['geometry']['coordinates'];cs=[cs] if f['geometry']['type']=='Polygon' else cs
 for p in cs:
  if not any(B[0]<x<B[2] and B[1]<y<B[3] for x,y,*_ in p[0]):continue
  c='#ddd' if t.get('building') else {'industrial':'#dec3de','residential':'#ffeac4','farmland':'#f4f2d5'}.get(t.get('landuse'))
  if c:d.polygon([xy(c) for c in p[0]],fill=c)
for i in range(1,10):
 X=W*i/10;Y=HH*i/10;d.line((X,0,X,HH),fill='#ddd');d.line((0,Y,W,Y),fill='#ddd');d.text((X+2,1),f'{B[0]+(B[2]-B[0])*i/10:.5f}',font=font,fill='#777');d.text((1,Y),f'{B[3]-(B[3]-B[1])*i/10:.5f}',font=font,fill='#777')
seen=set()
for f in json.load(gzip.open(C/'roads.geojson.gz','rt'))['features']:
 cs=f['geometry']['coordinates'];n=f['properties'].get('name');t=f['properties']['tags']
 if not any(B[0]<x<B[2] and B[1]<y<B[3] for x,y,*_ in cs):continue
 d.line([xy(c) for c in cs],fill='#888',width=2 if t.get('highway') in ['motorway','trunk','primary','secondary'] else 1)
 if n and n not in seen:
  X,Y=xy(cs[len(cs)//2])
  if 0<X<W and 0<Y<HH:d.text((X,Y),n,font=font,fill='#666');seen.add(n)
f=next(f for f in json.load(open(S/'features.geojson'))['features'] if f['properties']['municipality']=='Felsőzsolca');d.line([xy(c) for c in f['geometry']['coordinates'][0]],fill='#0055cc',width=5)
p=[20.8729731,48.1238869];X,Y=xy(p);d.ellipse((X-6,Y-6,X+6,Y+6),fill='#c00');d.text((X+8,Y),'FIZ label',font=font,fill='#c00');im.save(H/'felsozsolca-source-review.png');(H/'map-registration.json').write_text(json.dumps({'boundsWgs84':B,'imageSize':[W,HH],'blue':'frozen polygon','red':'source label','purpose':'review only; not output geometry'},indent=2)+'\n')
