#!/usr/bin/env python3
from pathlib import Path
import json,gzip
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
H=Path(__file__).resolve().parent
roads=json.loads(gzip.open(H/'ozd-source-roads.geojson.gz','rt').read())['features'];areas=json.loads(gzip.open(H/'ozd-source-areas.geojson.gz','rt').read())['features'];points=json.loads((H/'ozd-source-points.geojson').read_text())['features']
fig,ax=plt.subplots(figsize=(12,12));seen=set()
for f in areas:
 g=shape(f['geometry']);x,y=g.centroid.coords[0]
 if not(20.348<x<20.37 and 48.239<y<48.260):continue
 xs,ys=g.exterior.xy;ax.fill(xs,ys,color='#999999',alpha=.65)
for f in roads:
 g=shape(f['geometry']);x,y=g.centroid.coords[0]
 if not(20.348<x<20.37 and 48.239<y<48.260):continue
 p=f['properties'];n=p.get('name')or'';xs,ys=g.xy;ax.plot(xs,ys,color='#2563eb'if p['tags'].get('highway')else'#b91c1c',lw=.9)
 if n and n not in seen:ax.text(x,y,n,fontsize=8);seen.add(n)
for f in points:
 x,y=f['geometry']['coordinates'];n=f['properties']['name']
 if n in ['Bánszállás','Center']:ax.plot(x,y,'ro');ax.text(x,y,n,color='red',fontsize=13)
ax.set_xlim(20.348,20.37);ax.set_ylim(48.239,48.260);ax.set_aspect(1/.666);ax.grid();fig.savefig(H/'ozd-outer-road-context.png',dpi=150)
