from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
H=Path(__file__).resolve().parent
fs=json.loads((H/'source-roads.geojson').read_text())['features'];names=['Bethlen Gábor utca','Újfehértói utca','Ady Endre tér','Korpona utca','Kálvin tér','Szent István tér','Árpád utca','Vörösmarty Mihály utca','Polgári utca']
fig,ax=plt.subplots(figsize=(14,11));seen=set()
for f in fs:
 g=shape(f['geometry']);p=f['properties'];n=p.get('name')or'';s=p['source'];tags=s['tags']
 if g.geom_type!='LineString':continue
 if tags.get('highway')in ['footway','path','steps']:continue
 xs,ys=g.xy;wanted=n in names;ax.plot(xs,ys,color='#b91c1c'if wanted else'#aaaaaa',lw=1.5 if wanted else.6)
 if n and n not in seen and 21.498<g.centroid.x<21.517 and 47.667<g.centroid.y<47.678:
  ax.text(g.centroid.x,g.centroid.y,n,fontsize=8,color='#9f1239'if wanted else'#444444');seen.add(n)
if (H/'features.geojson').exists():
 poly=shape(json.loads((H/'features.geojson').read_text())['features'][0]['geometry']);xs,ys=poly.exterior.xy;ax.fill(xs,ys,color='#f6d365',alpha=.16);ax.plot(xs,ys,color='#166534',lw=1.7)
ax.plot(21.5066435,47.6748665,'bo');ax.text(21.5066435,47.6748665,'Belváros name point',color='blue')
ax.set_xlim(21.498,21.517);ax.set_ylim(47.667,47.678);ax.set_aspect(1/.673);ax.grid();fig.savefig(H/'source-street-context.png',dpi=150)
