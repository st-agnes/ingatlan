from pathlib import Path
import json,gzip
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).parent
P=HERE.parent
roads=[]
for fn in P.glob('*-source-roads.geojson.gz'):
 roads.extend(json.load(gzip.open(fn,'rt'))['features'])
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19)
for key,B in [('szentlaszlo',[19.268,47.468,19.299,47.485]),('szaraz',[19.291,47.46,19.319,47.479]),('kiraly',[19.202,47.416,19.216,47.427])]:
 W,H=2000,1600
 xy=lambda c:((c[0]-B[0])/(B[2]-B[0])*W,(B[3]-c[1])/(B[3]-B[1])*H)
 im=Image.new('RGB',(W,H),'white');dr=ImageDraw.Draw(im);labels=[]
 for i in range(1,10):
  x=W*i/10;y=H*i/10
  dr.line((x,0,x,H),fill='#ddd');dr.line((0,y,W,y),fill='#ddd')
  dr.text((x+2,2),f'{B[0]+(B[2]-B[0])*i/10:.5f}',fill='#777',font=font)
  dr.text((2,y),f'{B[3]-(B[3]-B[1])*i/10:.5f}',fill='#777',font=font)
 for f in roads:
  cs=f['geometry']['coordinates'];k=f['properties']['source']['tags'];name=f['properties'].get('name') or ''
  if not any(B[0]<x<B[2] and B[1]<y<B[3] for x,y,*_ in cs):continue
  dr.line([xy(c) for c in cs],fill='#2a83aa' if k.get('waterway') else '#777',width=3)
  if name not in labels and name:
   x,y=xy(cs[len(cs)//2])
   if 0<x<W and 0<y<H:dr.text((x,y),name,fill='#444',font=font);labels.append(name)
 im.save(HERE/(key+'-roads.png'))
