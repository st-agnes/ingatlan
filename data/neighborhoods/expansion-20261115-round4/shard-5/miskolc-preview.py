from pathlib import Path
import json,gzip
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
P=Path(__file__).resolve().parent;ctx=P.parent/'contexts'/'miskolc-33d4e745';fs=json.load(open(P.parents[1]/'sources/municipal-local-map-next/miskolc-source-raster.geojson'))['features'];g=shape(next(f for f in fs if f['properties']['sourceUnitNumber']==2)['geometry']);fig,ax=plt.subplots(figsize=(18,12));a,b,c,d=g.bounds;ax.set_xlim(a-.004,c+.003);ax.set_ylim(b-.004,d+.003)
for f in json.loads(gzip.decompress((ctx/'areas.geojson.gz').read_bytes()))['features']:
 h=shape(f['geometry']);t=f['properties']['tags']
 if not h.intersects(g):continue
 try:ax.fill(*h.exterior.xy,c={'industrial':'#ddc0de','residential':'#ead6aa','forest':'#b8d4b8','railway':'#ccc'}.get(t.get('landuse'),'#ddd'),alpha=.4)
 except:pass
for f in json.loads(gzip.decompress((ctx/'roads.geojson.gz').read_bytes()))['features']:
 h=shape(f['geometry']);t=f['properties']['tags']
 if not h.intersects(g.buffer(.003)):continue
 ax.plot(*h.xy,c='#2c7fb8' if t.get('waterway') else '#777',lw=.3)
 if t.get('name') and h.length>.004 and t.get('highway') in ['primary','secondary','tertiary','unclassified','residential']:
  pt=h.interpolate(.5,normalized=True);ax.text(pt.x,pt.y,t['name'],fontsize=6)
for f in json.load(open(P.parents[1]/'expansion-20261114/szeged-miskolc/miskolc-features.geojson'))['features']:
 if f['properties']['name'] not in ['Selyemrét','Szondi-telep','Martinkertváros']:continue
 h=shape(f['geometry'])
 for part in h.geoms if h.geom_type=='MultiPolygon' else [h]:ax.plot(*part.exterior.xy,lw=2,label=f['properties']['name'])
for part in g.geoms if g.geom_type=='MultiPolygon' else [g]:ax.plot(*part.exterior.xy,lw=3,c='cyan')
ax.legend();fig.savefig(P/'miskolc-context-preview.png',dpi=140)
