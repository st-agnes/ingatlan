from pathlib import Path
import json,gzip
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape,Point,box
from shapely.ops import transform,unary_union,polygonize
from pyproj import Transformer
ROOT=Path(__file__).resolve().parent
R=ROOT.parent
TASK=json.loads((R/'tasks/shard-4.json').read_text())
T=Transformer.from_crs(4326,23700,always_xy=True).transform
B=Transformer.from_crs(23700,4326,always_xy=True).transform
D=ROOT/'inspection';D.mkdir(exist_ok=True)
for m in TASK['municipalities']:
 if m['municipality']!='Tiszaföldvár':continue
 if m['municipality']=='Salgótarján':continue
 c=R/'contexts'/m['contextKey']
 roads=json.loads(gzip.decompress((c/'roads.geojson.gz').read_bytes()))['features']
 areas=json.loads(gzip.decompress((c/'areas.geojson.gz').read_bytes()))['features']
 labels=json.loads((c/'labels.geojson').read_text())['features']
 pts=[transform(T,Point(x['pointCandidates'][0]['coordinates'])) for x in m['targets'] if x['pointCandidates']]
 if not pts:continue
 minx=min(p.x for p in pts)-700;maxx=max(p.x for p in pts)+700;miny=min(p.y for p in pts)-700;maxy=max(p.y for p in pts)+700
 minx,miny,maxx,maxy=740350,177400,743700,180850
 extent=box(minx,miny,maxx,maxy)
 geoms=[]
 for i,f in enumerate(roads):
  p=f['properties'];tags=p.get('tags',{});g=transform(T,shape(f['geometry']))
  if not g.intersects(extent):continue
  geoms.append((i,f,g))
 fig,ax=plt.subplots(figsize=(14,12))
 for i,f in enumerate(areas):
  g=transform(T,shape(f['geometry']))
  if not g.intersects(extent):continue
  tags=f['properties'].get('tags',{})
  color='#d7e7c7' if tags.get('landuse') in ['forest','meadow','grass'] or tags.get('natural') in ['wood','scrub'] else '#ece1cc'
  if tags.get('natural')=='water':color='#9dcedb'
  parts=list(g.geoms) if g.geom_type=='MultiPolygon' else [g]
  for s in parts:
   if not hasattr(s,'exterior'):continue
   x,y=s.exterior.xy;ax.fill(x,y,color=color,alpha=.65,edgecolor='#abb9a1',lw=.4)
   if s.area>30000 and s.area<5e6 and s.intersects(extent):
    p=s.intersection(extent).representative_point();ax.text(p.x,p.y,'a'+str(i),fontsize=6,color='#6f795d')
 for i,f,g in geoms:
  tags=f['properties'].get('tags',{});h=tags.get('highway');w=tags.get('waterway')
  col='#3582a4' if w else '#aaaaaa' if h in ['path','footway','track','service'] else '#555555';lw=.5 if col=='#aaaaaa' else 1
  gs=list(g.geoms) if g.geom_type=='MultiLineString' else [g]
  for l in gs:
   x,y=l.xy;ax.plot(x,y,color=col,lw=lw)
  name=f['properties'].get('name')
  if name and g.length>200:
   p=g.interpolate(.5,normalized=True)
   ax.text(p.x,p.y,name,fontsize=5.5,color='#444444',rotation=0,clip_on=True)
 for f in labels:
  p=transform(T,shape(f['geometry']))
  if p.geom_type=='Point' and extent.covers(p):
   name=f['properties'].get('name','');ax.plot(p.x,p.y,'o',ms=3,color='#5555bb');ax.text(p.x,p.y,name,fontsize=8,color='#3333bb')
 for t,p in [(x,transform(T,Point(x['pointCandidates'][0]['coordinates']))) for x in m['targets'] if x['pointCandidates']]:
  ax.plot(p.x,p.y,'o',color='red',ms=5);ax.text(p.x,p.y,t['name'],fontsize=10,color='#aa0000',weight='bold')
 ax.set_xlim(minx,maxx);ax.set_ylim(miny,maxy);ax.set_aspect('equal');ax.ticklabel_format(style='plain',useOffset=False);ax.grid(alpha=.3);ax.set_title(m['municipality']+' — actual OSM roads and surface footprints, EPSG:23700 metres')
 fig.savefig(D/(m['contextKey']+'-whole.png'),dpi=150,bbox_inches='tight');plt.close(fig)
 print(m['municipality'])
