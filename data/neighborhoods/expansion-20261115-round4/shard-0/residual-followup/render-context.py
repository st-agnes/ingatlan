from pathlib import Path
import gzip,json,math
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import shape,box
P=Path(__file__).resolve().parent;R=P.parent.parent;C=R/'contexts';B=R/'residual-buildings'
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)
for slug,ctx,lon,lat,radius in [('sandipuszta','gyugy-90c0585a',17.6649526,46.6866203,550),('arkoshaza','babosdobrete-a9c1c939',16.7722417,46.8252895,1100)]:
 dy=radius/111320;dx=dy/math.cos(math.radians(lat));bounds=(lon-dx,lat-dy,lon+dx,lat+dy);view=box(*bounds);W=H=1100
 def xy(c):return ((c[0]-bounds[0])/(bounds[2]-bounds[0])*W,(bounds[3]-c[1])/(bounds[3]-bounds[1])*H)
 im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
 for f in json.load(gzip.open(P/'source-inputs'/(slug+'-areas.geojson.gz'),'rt'))['features']:
  g=shape(f['geometry']);t=f['properties']['tags']
  if g.geom_type!='Polygon' or not g.intersects(view):continue
  color='#e0efd4' if t.get('landuse')=='forest' or t.get('natural') in ['wood','scrub'] else '#e9d8a5' if t.get('landuse')=='vineyard' else '#e0efff' if t.get('natural')=='water' else '#f5f0de'
  d.polygon([xy(c) for c in f['geometry']['coordinates'][0]],fill=color,outline='#b3b3b3')
 for f in json.load(gzip.open(P/'source-inputs'/(slug+'-roads.geojson.gz'),'rt'))['features']:
  if not shape(f['geometry']).intersects(view):continue
  t=f['properties']['tags'];co='#2275b4' if t.get('waterway') else '#aaaaaa' if t.get('highway') in ['track','path','footway','service'] else '#555555'
  d.line([xy(c) for c in f['geometry']['coordinates']],fill=co,width=2)
  if t.get('name'):
   q=shape(f['geometry']).intersection(view).interpolate(.5,normalized=True);d.text(xy(q.coords[0]),t['name'],font=font,fill=co)
 fs=json.load(gzip.open(P/'source-inputs'/(slug+'.geojson.gz'),'rt'))['features']
 for i,f in enumerate(fs):
  g=shape(f['geometry'])
  if not g.intersects(view):continue
  d.polygon([xy(c) for c in f['geometry']['coordinates'][0]],fill='#b63831',outline='black');d.text(xy(g.centroid.coords[0]),str(i),font=font,fill='black')
 if slug=='sandipuszta' and (P/'features.geojson').exists():
  for f in json.load(open(P/'features.geojson'))['features']:d.line([xy(c) for c in f['geometry']['coordinates'][0]],fill='#14762c',width=4)
 labels=json.load(open(P/'source-inputs'/(slug+'-labels.geojson')))['features']
 for f in labels:
  if f['geometry']['type']!='Point':continue
  x,y=xy(f['geometry']['coordinates'])
  if 0<x<W and 0<y<H:d.ellipse((x-5,y-5,x+5,y+5),fill='blue');d.text((x+7,y+5),f['properties']['name'],font=font,fill='blue')
 d.rectangle((0,0,W,28),fill='white');d.text((8,4),slug+' : actual OSM buildings, land use and roads; not a neighborhood boundary',font=font,fill='black')
 for x in range(0,W,200):d.text((x,H-25),str(round(bounds[0]+x/W*(bounds[2]-bounds[0]),5)),font=font,fill='blue')
 for y in range(200,H-30,200):d.text((0,y),str(round(bounds[3]-y/H*(bounds[3]-bounds[1]),5)),font=font,fill='blue')
 im.save(P/(slug+'-context.png'))
