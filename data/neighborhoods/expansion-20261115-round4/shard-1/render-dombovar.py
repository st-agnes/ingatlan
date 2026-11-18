from pathlib import Path
import json,gzip
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import shape,box
H=Path(__file__).resolve().parent;C=H.parent/'contexts'/'dombovar-ae117373';b=[18.129,46.3615,18.142,46.3705];W=1000;HH=800;v=box(*b)
def xy(q):return ((q[0]-b[0])/(b[2]-b[0])*W,(b[3]-q[1])/(b[3]-b[1])*HH)
f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13);im=Image.new('RGB',(W,HH),'#fffdf7');d=ImageDraw.Draw(im)
for a in json.load(gzip.open(C/'areas.geojson.gz','rt'))['features']:
 if not shape(a['geometry']).intersects(v):continue
 if a['geometry']['type']=='Polygon':d.polygon([xy(q) for q in a['geometry']['coordinates'][0]],fill='#dbe4cb',outline='#b4b6a3')
for a in json.load(gzip.open(C/'roads.geojson.gz','rt'))['features']:
 if not shape(a['geometry']).intersects(v):continue
 tags=a['properties']['tags'];d.line([xy(q) for q in a['geometry']['coordinates']],fill='#4591aa' if tags.get('waterway') else '#888981',width=2)
 n=a['properties'].get('name')
 if n:
  qs=[q for q in a['geometry']['coordinates'] if v.covers(shape({'type':'Point','coordinates':q}))]
  if qs:d.text(xy(qs[len(qs)//2]),n,font=f,fill='#35443b',stroke_width=1,stroke_fill='white')
d.rectangle((0,0,W,30),fill='white');d.text((10,5),'18 Dombóvár – Szuhay-domb | registered source streets, no name point invented',font=f,fill='black');im.save(H/'maps'/'18.png');(H/'maps'/'18.json').write_text(json.dumps({'index':18,'municipality':'Dombóvár','name':'Szuhay-domb','contextKey':'dombovar-ae117373','bounds':b,'width':W,'height':HH,'role':'RENDER_VIEWPORT_ONLY_NOT_OUTPUT_GEOMETRY'},ensure_ascii=False,indent=2)+'\n')
