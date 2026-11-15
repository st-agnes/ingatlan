from pathlib import Path
import json,gzip
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
H=Path(__file__).resolve().parent
p=H/'gyongyos-source-roads.geojson.gz'
roads=json.loads(gzip.open(p,'rt').read())['features'] if p.exists()else json.loads(Path('data/neighborhoods/sources/municipal-gyongyos-more/osm-calibration-lines.geojson').read_text())['features']
points=[f for f in json.loads(gzip.open(H/'source-points.geojson.gz','rt').read())['features']if f['properties'].get('municipality')=='Gyöngyös']
for key,box in [('core',(19.901,47.762,19.948,47.803)),('estates',(19.913,47.766,19.940,47.791))]:
 fig,ax=plt.subplots(figsize=(14,14));seen=set();w,s,e,n=box
 for f in roads:
  g=shape(f['geometry']);x,y=g.centroid.coords[0]
  if not(w<x<e and s<y<n):continue
  p=f['properties'];tags=p.get('tags',p.get('source',{}).get('tags',{}));name=p.get('name')or''
  if tags.get('highway')in ['path','footway','steps','service']:continue
  xs,ys=g.xy;ax.plot(xs,ys,color='#666666',lw=.6)
  if name and name not in seen and g.length>.0007:ax.text(x,y,name,fontsize=6);seen.add(name)
 for f in points:
  x,y=f['geometry']['coordinates']
  if w<x<e and s<y<n:ax.plot(x,y,'ro',ms=3);ax.text(x,y,f['properties']['name'],color='red',fontsize=10)
 ax.set_xlim(w,e);ax.set_ylim(s,n);ax.set_aspect(1/.672);ax.grid();fig.savefig(H/f'gyongyos-{key}-context.png',dpi=160);plt.close(fig)
