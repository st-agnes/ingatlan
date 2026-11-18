#!/usr/bin/env python3
"""Render frozen shared road/parcel contexts as interpretation maps; never creates geometry."""
import argparse,gzip,json,re,unicodedata
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from pyproj import Transformer
from shapely.geometry import shape,box
from shapely.ops import transform
H=Path(__file__).resolve().parent;R=H.parents[3];TASK=json.loads((H/'targets.json').read_bytes());C=R/TASK['contextRoot'];F=Transformer.from_crs(4326,23700,always_xy=True).transform
def read(p):
 b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def slug(x):return re.sub('[^a-z0-9]+','-',unicodedata.normalize('NFD',x).encode('ascii','ignore').decode().lower()).strip('-')
def props(f):return f['properties'].get('tags',f['properties'].get('source',{}).get('tags',{}))
def draw(city,target,idx,pointidx=0,span=None):
 ctx=C/city['contextKey'];roads=read(ctx/'roads.geojson.gz')['features'];areas=read(ctx/'areas.geojson.gz')['features'];addresses=read(ctx/'addresses.geojson.gz')['features']
 p=target['pointCandidates'][pointidx]['coordinates'];cx,cy=F(*p)
 if span is None:span=6000 if any(v in target['name'].casefold() for v in ['dűlő','szőlők','adacs','tanya','puszta','ráda']) else 2800
 w=1600;h=1400;s=w/span;x1=cx-span/2;x2=cx+span/2;y1=cy-h/2/s;y2=cy+h/2/s
 im=Image.new('RGB',(w,h),'#ffffff');d=ImageDraw.Draw(im);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12);bold=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',17)
 def px(c):x,y=F(*c);return(round((x-x1)*s),round((y2-y)*s))
 screen=box(x1,y1,x2,y2)
 def parts(g):
  if g['type']=='Polygon':return [g['coordinates']]
  if g['type']=='MultiPolygon':return g['coordinates']
  return []
 for f in areas:
  if not transform(F,shape(f['geometry'])).intersects(screen):continue
  tags=props(f);typ=tags.get('landuse');col='#cccccc' if tags.get('building') else {'residential':'#f2e6d6','industrial':'#dcd2ec','forest':'#cde5be','grass':'#e8f2d5','farmland':'#faf4df','orchard':'#e7e7b2','vineyard':'#f3dfad','allotments':'#f3ddbc'}.get(typ,'#f1f1dd')
  for rings in parts(f['geometry']):
   d.polygon([px(c) for c in rings[0]],fill=col,outline='#c4c0af')
   for ring in rings[1:]:d.polygon([px(c) for c in ring],fill='white')
  name=f['properties'].get('name') or tags.get('name')
  if name:
   rp=shape(f['geometry']).representative_point();q=px([rp.x,rp.y]);d.text(q,name,font=font,fill='#77905d')
 for f in roads:
  if not transform(F,shape(f['geometry'])).intersects(screen):continue
  tags=props(f);col='#257cc0' if tags.get('waterway') else '#686868' if tags.get('railway') else '#be9a71' if tags.get('highway') in ['primary','secondary','trunk','motorway'] else '#a0a0a0'
  coords=f['geometry']['coordinates'];lines=[coords] if f['geometry']['type']=='LineString' else coords
  for cs in lines:
   ps=[px(c) for c in cs];d.line(ps,fill=col,width=3 if tags.get('highway') in ['primary','secondary','trunk','motorway'] else 1)
   name=f['properties'].get('name') or tags.get('name')
   if name and tags.get('highway') not in ['footway','path','cycleway']:
    a=ps[len(ps)//2]
    if 0<a[0]<w and 35<a[1]<h-35:d.text(a,name,font=font,fill='#4f5477')
 for f in addresses:
  if f['geometry']['type']!='Point':continue
  q=px(f['geometry']['coordinates'])
  if 0<q[0]<w and 0<q[1]<h:d.ellipse((q[0]-1,q[1]-1,q[0]+1,q[1]+1),fill='#bb8484')
 for t in city['targets']:
  for k,c in enumerate(t['pointCandidates']):
   q=px(c['coordinates'])
   if 0<q[0]<w and 0<q[1]<h:d.ellipse((q[0]-5,q[1]-5,q[0]+5,q[1]+5),fill='#bd0743');d.text((q[0]+8,q[1]-7),t['name']+(' #'+str(k) if len(t['pointCandidates'])>1 else ''),font=bold,fill='#9e0031')
 d.rectangle((0,0,w,32),fill='white');d.text((10,6),city['municipality']+' / '+target['name']+' — tényleges forrásadatok értelmezési térképe',font=bold,fill='#183c20')
 d.rectangle((0,h-28,w,h),fill='white');d.text((10,h-24),'© OpenStreetMap contributors / ODbL-1.0 — névpont nem határ; a megjelenítési keret nem kimeneti poligon.',font=font,fill='#344339')
 name=f"{idx:02d}-{slug(city['municipality'])}-{slug(target['name'])}-{pointidx}"
 out=H/'maps';out.mkdir(exist_ok=True);im.save(out/(name+'.png'))
 (out/(name+'.json')).write_text(json.dumps({'municipality':city['municipality'],'name':target['name'],'contextKey':city['contextKey'],'pointIndex':pointidx,'crs':'EPSG:23700','metreBounds':[x1,y1,x2,y2],'scale':s,'pixelSize':[w,h]},ensure_ascii=False,indent=2)+'\n')
 print(name,flush=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--town');p.add_argument('--name');p.add_argument('--span',type=float);a=p.parse_args();i=0
 for city in TASK['municipalities']:
  for t in city['targets']:
   if (not a.town or a.town==city['municipality']) and (not a.name or a.name==t['name']):
    for k in range(len(t['pointCandidates'])):draw(city,t,i,k,a.span)
   i+=1
if __name__=='__main__':main()
