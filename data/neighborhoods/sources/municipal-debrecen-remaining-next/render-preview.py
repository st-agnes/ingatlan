#!/usr/bin/env python3
"""Diagnostic preview only; display projection never edits stored geometries."""
from pathlib import Path
import json,os
os.environ.setdefault('MPLCONFIGDIR','/tmp/debrecen-remaining-matplotlib')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent
def read(n):return json.loads((P/n).read_text())
tr=Transformer.from_crs(4326,23700,always_xy=True).transform
src=read('debrecen-source-service.geojson')['features']
selected={f['properties']['sourceFID']:f for f in read('debrecen-remaining-estimated.geojson')['features']}
points={f['properties']['name']:f for f in read('selected-osm-name-points.geojson')['features']}
refs=read('existing-32-reference.geojson')['features']
fig,axes=plt.subplots(1,2,figsize=(16,9),dpi=150)
for ax in axes:
    for f in src:
        g=transform(tr,shape(f['geometry']));fid=f['properties']['FID'];x,y=g.exterior.xy
        ax.fill(x,y,facecolor='#92c4ad' if fid in selected else '#e7edf1',edgecolor='#67828c',linewidth=.6,alpha=.85)
        if fid in selected:
            n=selected[fid]['properties']['name'];p=transform(tr,shape(points[n]['geometry']))
            ax.plot(p.x,p.y,'o',color='#174d3c',markersize=2.7)
            ax.annotate(str(fid)+' '+n,(p.x,p.y),xytext=(3,3),textcoords='offset points',fontsize=6.5,color='#143c31',bbox={'facecolor':'white','edgecolor':'none','alpha':.7,'pad':.5})
    for f in refs:
        g=transform(tr,shape(f['geometry']));parts=list(g.geoms) if hasattr(g,'geoms') else [g]
        for a in parts:
            x,y=a.exterior.xy;ax.plot(x,y,color='#98545b',linewidth=.65,linestyle='--',alpha=.65)
    ax.set_aspect('equal');ax.grid(alpha=.15);ax.set_xlabel('EOV easting (m), EPSG:23700');ax.set_ylabel('EOV northing (m)')
# Source-record extent is displayed; no source coordinates are altered.
core=[transform(tr,shape(f['geometry'])) for fid,f in selected.items() if fid not in {2,38,72,73,75,76,77}]
axes[0].set_xlim(min(g.bounds[0] for g in core)-400,max(g.bounds[2] for g in core)+400)
axes[0].set_ylim(min(g.bounds[1] for g in core)-400,max(g.bounds[3] for g in core)+400)
axes[0].set_title('Central quarters: 16 additional candidates',fontsize=10)
axes[1].set_title('All 23 candidates, including 7 outlying built-up quarters',fontsize=10)
fig.suptitle('Debrecen: green = additional ESTIMATED polygons; dots = actual current name points; dashed = 26 primary + 6 prior estimated\nLiteral published source coordinates unchanged; source placement and present whole-quarter extents unverified',fontsize=11)
fig.tight_layout(rect=(0,0,1,.93));fig.savefig(P/'candidate-review.png');plt.close(fig)
