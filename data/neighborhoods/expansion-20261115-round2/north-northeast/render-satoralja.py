from pathlib import Path
import json,gzip
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
H=Path(__file__).resolve().parent
rs=json.loads(gzip.open(H/'satoraljaujhely-source-roads.geojson.gz','rt').read())['features'];ars=json.loads(gzip.open(H/'satoraljaujhely-source-areas.geojson.gz','rt').read())['features'];ps=[f for f in json.loads(gzip.open(H/'source-points.geojson.gz','rt').read())['features']if f['properties'].get('municipality')=='Sátoraljaújhely']
fig,ax=plt.subplots(figsize=(14,14));seen=set();w,s,e,n=(21.615,48.37,21.675,48.417)
for f in ars:
 g=shape(f['geometry']);x,y=g.centroid.coords[0]
 if not(w<x<e and s<y<n)or not g.is_valid:continue
 xs,ys=g.exterior.xy;ax.fill(xs,ys,color='#dddddd'if 'building'in f['properties']['tags']else'#bbd9a8',alpha=.5)
for f in rs:
 g=shape(f['geometry']);x,y=g.centroid.coords[0]
 if not(w<x<e and s<y<n):continue
 p=f['properties'];tags=p['tags'];name=p.get('name')or''
 if tags.get('highway')in ['footway','steps','path','service']:continue
 xs,ys=g.xy;ax.plot(xs,ys,color='#666666',lw=.6)
 if name and name not in seen:ax.text(x,y,name,fontsize=6);seen.add(name)
for f in ps:
 x,y=f['geometry']['coordinates']
 if w<x<e and s<y<n:ax.plot(x,y,'ro',ms=3);ax.text(x,y,f['properties']['name'],color='red',fontsize=10)
ax.set_xlim(w,e);ax.set_ylim(s,n);ax.set_aspect(1/.665);ax.grid();fig.savefig(H/'satoralja-road-land-context.png',dpi=160)
