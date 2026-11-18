import json,gzip,math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape,Point
P=Path(__file__).resolve().parent;R=P.parent/'contexts'
T=json.load(open(P/'targets.json'));cs=json.load(open(P/'candidate-cells.geojson'))['features']
fig,axs=plt.subplots(6,8,figsize=(32,23))
for ax,m in zip(axs.ravel(),T['municipalities']):
 roads=json.loads(gzip.decompress((R/m['contextKey']/'roads.geojson.gz').read_bytes()))['features'];areas=json.loads(gzip.decompress((R/m['contextKey']/'areas.geojson.gz').read_bytes()))['features'];points=[t['pointCandidates'][0]['coordinates'] for t in m['targets'] if t['pointCandidates']]
 if not points:ax.set_title(m['municipality']);continue
 x=[p[0] for p in points];y=[p[1] for p in points];dx=max(max(x)-min(x),.012)*.7;dy=max(max(y)-min(y),.009)*.7
 ax.set_xlim((min(x)+max(x))/2-dx,(min(x)+max(x))/2+dx);ax.set_ylim((min(y)+max(y))/2-dy,(min(y)+max(y))/2+dy)
 for f in areas:
  g=shape(f['geometry']);tags=f['properties']['tags'];c={'residential':'#dfd5c1','industrial':'#b8abca','forest':'#b9d5ae','allotments':'#d0d5b4','farmland':'#e9e7c8'}.get(tags.get('landuse'),'#ddd')
  try: ax.fill(*g.exterior.xy,color=c,alpha=.4)
  except:pass
 for f in roads:
  g=shape(f['geometry']);tags=f['properties']['tags'];ax.plot(*g.xy,c='#65a5c9' if tags.get('waterway') else '#555',lw=.4 if tags.get('highway') not in ['track','path','footway'] else .2,alpha=.55)
 for p,t in zip(points,m['targets']):ax.scatter(*p,s=12,c='red');ax.text(*p,t['name'],fontsize=6)
 ax.set_title(m['municipality'],fontsize=11);ax.tick_params(labelsize=5)
fig.tight_layout();fig.savefig(P/'context-preview.png',dpi=120)
