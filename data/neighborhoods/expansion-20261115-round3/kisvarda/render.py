from pathlib import Path
import json,math,unicodedata,re
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import shape
P=Path(__file__).resolve().parent;fs=json.load(open(P/'source-lines.geojson'))['features'];areas=json.load(open(P/'source-areas.geojson'))['features'];defs=json.load(open(P/'source-boundary-definitions.json'))['definitions'];font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14);small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',11)
def norm(n):
 s=''.join(c for c in unicodedata.normalize('NFD',n.lower()) if not unicodedata.combining(c));s=re.sub(r'^(ii\.?\s*)','',s);s=s.replace('liptai','liptay').replace('halassy','halasy').replace('jekei','jeki');s=re.split(r'\butca\b|\butja\b|\but\b|\bter\b|\btere\b|:',s)[0];return ''.join(c for c in s if c.isalnum())
for k,definition in enumerate(defs):
 name=definition['name'];wanted={norm(n) for n in definition['boundaryElementsInSourceOrder']};bb=[(22.068,48.214,22.096,48.235),(22.047,48.195,22.080,48.239),(22.075,48.228,22.106,48.250),(22.058,48.225,22.083,48.242),(22.086,48.206,22.127,48.239),(22.060,48.183,22.107,48.221)][k];w=1500;h=int(w*(bb[3]-bb[1])/(bb[2]-bb[0])/math.cos(math.radians(48.22)));im=Image.new('RGB',(w,h),'white');d=ImageDraw.Draw(im)
 def xy(x,y):return ((x-bb[0])/(bb[2]-bb[0])*w,(bb[3]-y)/(bb[3]-bb[1])*h)
 for f in areas:
  g=shape(f['geometry']);tags=f['properties']['tags'];fill={'residential':'#fff6d6','industrial':'#ecd6e8','forest':'#dce8d1','allotments':'#dce9b9'}.get(tags.get('landuse'),'#eae8df')
  d.polygon([xy(x,y) for x,y in g.exterior.coords],fill=fill,outline='#bcc2b2')
 used=set()
 for f in fs:
  g=shape(f['geometry']);t=f['properties']['tags'];n=t.get('name','');match=norm(n) in wanted;rail=t.get('railway')=='rail';cs=[xy(x,y) for x,y in g.coords]
  d.line(cs,fill='red' if match else '#222222' if rail else '#bbbbbb',width=4 if match else 3 if rail else 1)
  if n and n not in used:
   a=g.interpolate(.5,normalized=True)
   if bb[0]<a.x<bb[2] and bb[1]<a.y<bb[3]:d.text(xy(a.x,a.y),n,font=font if match else small,fill='#a20000' if match else '#777777');used.add(n)
 d.text((15,15),name,font=font,fill='black');im.save(P/('context-'+str(k+1)+'.png'))
