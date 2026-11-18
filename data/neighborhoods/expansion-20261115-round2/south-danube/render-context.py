#!/usr/bin/env python3
from pathlib import Path
import json,gzip,math
from PIL import Image,ImageDraw,ImageFont
H=Path(__file__).resolve().parent
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
def load(n):
 p=H/n;return json.loads(gzip.open(p,'rt').read()) if n.endswith('.gz') else json.loads(p.read_text())
roads=load('source-roads.geojson.gz')['features'];surfs=load('source-surfaces.geojson.gz')['features'];targets=load('target-selection.json')
views=[('Dunaföldvár','dunafoldvar',[18.923,46.796,18.936,46.813]),('Fonyód','fonyod',[17.50885,46.713,17.622,46.768]),('Kalocsa','kalocsa',[18.968,46.529,18.997,46.540]),('Kalocsa','kalocsa-rural',[19.004,46.531,19.043,46.549]),('Kalocsa','kalocsa-arendas',[18.949,46.507,18.971,46.525])]
for city,fn,viewbounds in views:
 rows=[x for x in targets if x['municipality']==city]
 cs=[x['pointCandidates'][0]['coordinates'] for x in rows]
 mi=[min(x[0] for x in cs),min(x[1] for x in cs)];ma=[max(x[0] for x in cs),max(x[1] for x in cs)]
 margin=.002 if city=='Dunaföldvár' else .005
 b=[mi[0]-margin,mi[1]-margin,ma[0]+margin,ma[1]+margin]
 b=viewbounds
 w,h=1700,1150;cos=math.cos(math.radians((b[1]+b[3])/2));sx=(w-50)/((b[2]-b[0])*cos);sy=(h-50)/(b[3]-b[1]);scale=min(sx,sy)
 def px(c):return (int(25+(c[0]-b[0])*cos*scale),int(h-25-(c[1]-b[1])*scale))
 im=Image.new('RGB',(w,h),'#fcfaf2');d=ImageDraw.Draw(im)
 for f in surfs:
  if city not in f['properties'].get('municipalities',[]):continue
  c=f['geometry']['coordinates'][0];t=f['properties']['source']['tags'];color='#e4ebda' if t.get('landuse') not in ['residential','industrial'] else ('#e5ded8' if t.get('landuse')=='residential' else '#dedce3')
  if t.get('natural') in ['water','wetland']:color='#c2dfed'
  d.polygon([px(p) for p in c],fill=color,outline='#bbbbaa')
 for f in roads:
  if city not in f['properties'].get('municipalities',[]):continue
  t=f['properties']['source']['tags'];c=f['geometry']['coordinates'];kind=t.get('highway');color='#a4a39c';wid=1
  if kind in ['primary','secondary','tertiary']:color='#d49253';wid=3
  if t.get('railway'):color='#545454';wid=3
  if t.get('waterway'):color='#4685b3';wid=3
  d.line([px(p) for p in c],fill=color,width=wid)
 names=set()
 for f in roads:
  if city not in f['properties'].get('municipalities',[]):continue
  name=f['properties'].get('name');cs=f['geometry']['coordinates'];c=cs[len(cs)//2]
  if not name or name in names or not(b[0]<c[0]<b[2] and b[1]<c[1]<b[3]):continue
  if city=='Fonyód' and f['properties']['source']['tags'].get('highway') not in ['primary','secondary','tertiary']:continue
  names.add(name);d.text(px(c),name,fill='#555544',font=small,stroke_width=1,stroke_fill='white')
 for i,x in enumerate(rows):
  c=x['pointCandidates'][0]['coordinates'];xx,yy=px(c);d.ellipse((xx-5,yy-5,xx+5,yy+5),fill='red');d.text((xx+6,yy-21),str(i)+':'+x['name'],fill='#bd142b',font=font,stroke_width=1,stroke_fill='white')
 im.save(H/(fn+'-context.png'))
 (H/(fn+'-context-registration.json')).write_text(json.dumps({'city':city,'bounds':b,'width':w,'height':h,'originPixel':[25,h-25],'scale':scale,'longitudeScaleCosine':cos,'targets':[{'index':i,'name':x['name'],'coordinates':x['pointCandidates'][0]['coordinates']} for i,x in enumerate(rows)]},ensure_ascii=False,indent=2)+'\n')
 print(fn,'saved')
