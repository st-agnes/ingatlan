from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
H=Path(__file__).resolve().parent
fig,ax=plt.subplots(figsize=(10,14));seen=set()
for f in json.loads((H/'source-contexts.geojson').read_text())['features']:
 g=shape(f['geometry'])
 for p in g.geoms:
  xs,ys=p.exterior.xy;ax.fill(xs,ys,color='#dbe8ce',alpha=.55)
for f in json.loads((H/'source-roads.geojson').read_text())['features']:
 g=shape(f['geometry']);n=f['properties'].get('name')or'';tags=f['properties']['source']['tags']
 if tags.get('highway')in ['footway','path','steps']:continue
 xs,ys=g.xy;ax.plot(xs,ys,color='#555555',lw=.7)
 if n and n not in seen:ax.text(g.centroid.x,g.centroid.y,n,fontsize=7);seen.add(n)
if (H/'features.geojson').exists():
 poly=shape(json.loads((H/'features.geojson').read_text())['features'][0]['geometry']);xs,ys=poly.exterior.xy;ax.fill(xs,ys,color='#f3cb5a',alpha=.25);ax.plot(xs,ys,color='#166534',lw=1.5)
ax.plot(21.409731,48.1243666,'ro');ax.text(21.409731,48.1243666,'Óváros',color='red',fontsize=13)
ax.set_xlim(21.395,21.421);ax.set_ylim(48.114,48.138);ax.set_aspect(1/.667);ax.grid();fig.savefig(H/'source-street-context.png',dpi=150)
