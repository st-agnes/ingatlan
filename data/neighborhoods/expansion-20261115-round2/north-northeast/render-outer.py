from pathlib import Path
import json,gzip
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
H=Path(__file__).resolve().parent
rs=json.loads(gzip.open(H/'gyongyos-source-roads.geojson.gz','rt').read())['features'];ars=json.loads(gzip.open(H/'gyongyos-source-areas.geojson.gz','rt').read())['features']
for key,box in [('matrafured',(19.955,47.817,19.99,47.841)),('iparipark',(19.937,47.746,19.970,47.765))]:
 fig,ax=plt.subplots(figsize=(11,9));seen=set();w,s,e,n=box
 for f in ars:
  g=shape(f['geometry']);x,y=g.centroid.coords[0]
  if not(w<x<e and s<y<n)or not g.is_valid:continue
  xs,ys=g.exterior.xy;ax.fill(xs,ys,color='#cccccc'if 'building'in f['properties']['tags']else'#bbd9a8',alpha=.5)
 for f in rs:
  g=shape(f['geometry']);x,y=g.centroid.coords[0]
  if not(w<x<e and s<y<n):continue
  p=f['properties'];tags=p['tags'];name=p.get('name')or''
  if tags.get('highway')in ['footway','steps','path']:continue
  xs,ys=g.xy;ax.plot(xs,ys,color='#444444',lw=.6)
  if name and name not in seen:ax.text(x,y,name,fontsize=7);seen.add(name)
 ax.set_xlim(w,e);ax.set_ylim(s,n);ax.set_aspect(1/.672);ax.grid();fig.savefig(H/f'gyongyos-{key}-context.png',dpi=150);plt.close(fig)
