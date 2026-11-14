#!/usr/bin/env python3
from pathlib import Path
import os,json
os.environ.setdefault('MPLCONFIGDIR','/tmp/ingatlan-debrecen-matplotlib')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
D=json.loads((P/'debrecen-source-normalized.geojson').read_text());B=json.loads((ROOT/'data/neighborhoods/neighborhoods.geojson').read_text());T=Transformer.from_crs(4326,23700,always_xy=True).transform
fig,ax=plt.subplots(figsize=(13,9.5),dpi=150);selected={6,42,59,60,61,65};conflicts={4,11,67}
for f in D['features']:
 g=transform(T,shape(f['geometry']));fid=f['properties']['sourceFID'];color='#87bfa7'if fid in selected else('#eab879'if fid in conflicts else'#d9e4ec');x,y=g.exterior.xy;ax.fill(x,y,facecolor=color,edgecolor='#59717f',linewidth=.65,alpha=.85)
 if fid in selected|conflicts:
  c=g.representative_point();ax.text(c.x,c.y,f"{fid} {f['properties']['name']}",fontsize=6.6,ha='center',va='center',bbox={'boxstyle':'round,pad=.1','facecolor':'white','edgecolor':'none','alpha':.8})
for f in B['features']:
 if f['properties'].get('municipality')!='Debrecen':continue
 g=transform(T,shape(f['geometry']));geoms=list(g.geoms)if hasattr(g,'geoms')else[g]
 for a in geoms:
  x,y=a.exterior.xy;ax.plot(x,y,color='#98545b',linewidth=.8,linestyle='--',alpha=.65)
ax.set_aspect('equal');ax.set_title('Debrecen:77literal ArcGIS areas; green=6ESTIMATED candidates; dashed=26existing OSM outlines\nPublished source coordinates unchanged; source placement and whole current extents unverified',fontsize=10)
ax.set_xlabel('EOV easting(m), EPSG:23700');ax.set_ylabel('EOV northing(m)');ax.grid(alpha=.15);fig.tight_layout();fig.savefig(P/'debrecen-source-geometry-review.png');plt.close(fig)
