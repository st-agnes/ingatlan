#!/usr/bin/env python3
import json,gzip
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
H=Path(__file__).resolve().parent
fs=json.loads(gzip.open(H/'szekszard-source-roads.geojson.gz','rt').read())['features'];ps=json.loads((H/'szekszard-source-points.geojson').read_text())['features']
fig,ax=plt.subplots(figsize=(14,15));seen=set()
for f in fs:
 g=shape(f['geometry']);p=f['properties'];tags=p.get('source',{}).get('tags',{});n=p.get('name')or''
 if g.geom_type!='LineString':continue
 if tags.get('highway')in ['path','footway','steps']:continue
 x,y=g.centroid.coords[0]
 if not(18.67<x<18.75 and 46.305<y<46.385):continue
 xs,ys=g.xy;ax.plot(xs,ys,color='#bbbbbb'if tags.get('highway')in ['track','service']else'#444444',lw=.5)
 if n and n not in seen and tags.get('highway')not in ['track','service']and g.length>.001:
  ax.text(x,y,n,fontsize=6,color='#333333');seen.add(n)
for f in ps:
 x,y=f['geometry']['coordinates'];n=f['properties']['name']
 if f['properties'].get('municipality')=='Szekszárd':ax.plot(x,y,'ro',ms=3);ax.text(x,y,n,fontsize=11,color='red')
ax.set_xlim(18.67,18.75);ax.set_ylim(46.305,46.385);ax.set_aspect(1/.69);ax.grid();fig.savefig(H/'szekszard-road-context.png',dpi=180)
