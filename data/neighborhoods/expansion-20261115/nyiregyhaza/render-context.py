#!/usr/bin/env python3
from pathlib import Path
import json
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
P=Path(__file__).resolve().parents[2]/'expansion-20261114-next/fehervar-nyiregyhaza';OUT=Path(__file__).resolve().parent
roads=json.load(open(P/'source-barriers.geojson'))['features'];areas=json.load(open(OUT/'source-landuse.geojson'))['features'];labels=json.load(open(P/'source-labels.geojson'))['features']
views={'bathory':(21.657,47.952,21.692,47.975),'kun':(21.716,47.910,21.750,47.932),'sosto':(21.720,47.998,21.763,48.021),'rural1':(21.555,47.905,21.615,47.935),'rural2':(21.648,47.849,21.755,47.886),'badur':(21.681,47.988,21.707,48.007),'bokors':(21.64,47.933,21.68,47.973)}
for name,bb in views.items():
 fig,ax=plt.subplots(figsize=(15,13),dpi=150)
 for f in areas:
  g=shape(f['geometry']);b=g.bounds
  if b[2]<bb[0] or b[0]>bb[2] or b[3]<bb[1] or b[1]>bb[3]:continue
  for a in ([g] if g.geom_type=='Polygon' else g.geoms):
   x,y=a.exterior.xy;ax.fill(x,y,alpha=.12,color='green' if f['properties']['tags'].get('landuse')=='farmyard' else 'gold');ax.plot(x,y,color='olive',lw=.3)
   if a.area<.00001:
    c=a.representative_point();ax.text(c.x,c.y,f['id'].split(':')[-1],fontsize=5,color='olive')
 used=set()
 for f in roads:
  g=shape(f['geometry']);b=g.bounds
  if b[2]<bb[0] or b[0]>bb[2] or b[3]<bb[1] or b[1]>bb[3]:continue
  p=f['properties'];tags=p['source']['tags'];x,y=g.xy;major=tags.get('highway') in {'trunk','primary','secondary','tertiary'}
  ax.plot(x,y,lw=1.8 if major else .65,color='#444444')
  n=p.get('name')
  if n and n not in used:
   m=g.interpolate(.5,normalized=True)
   if bb[0]<m.x<bb[2] and bb[1]<m.y<bb[3]:ax.text(m.x,m.y,n,fontsize=6,color='navy',rotation=15);used.add(n)
 for f in labels:
  x,y=f['geometry']['coordinates']
  if bb[0]<x<bb[2] and bb[1]<y<bb[3]:ax.plot(x,y,'ro',ms=3);ax.text(x,y,f['properties']['name'],color='red',fontsize=9)
 ax.set_xlim(bb[0],bb[2]);ax.set_ylim(bb[1],bb[3]);ax.set_aspect(1.49);ax.grid(alpha=.15);fig.tight_layout();fig.savefig(OUT/(name+'-context.png'));plt.close(fig)
