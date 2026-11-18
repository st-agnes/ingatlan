#!/usr/bin/env python3
from pathlib import Path
import json,os
os.environ.setdefault('MPLCONFIGDIR','/tmp/ingatlan-hod-matplotlib')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
import numpy as np
P=Path(__file__).resolve().parent;ROOT=P.parents[3];T=Transformer.from_crs(4326,23700,always_xy=True).transform
D=json.loads((P/'estimated-world-candidates.geojson').read_text());ALT=json.loads((P/'alternative-two-control-world.geojson').read_text());C=json.loads((P/'road-control-specification.json').read_text());M=np.array(json.loads((P/'registration-and-uncertainty.json').read_text())['mainMatrixPdfToEov'])
W=json.loads((ROOT/'data/neighborhoods/sources/municipal-hodmezovasarhely-hodto-first/hod-local-lines.geojson').read_text());fig,ax=plt.subplots(figsize=(12,10),dpi=160)
for f in W['features']:
 p=f['properties']['tags'];g=transform(T,shape(f['geometry']))
 if p.get('railway') in ['rail','disused','abandoned']:color='#333333';lw=.8
 elif p.get('highway')in['primary','secondary','tertiary','residential','unclassified','living_street']:color='#b8bcc2';lw=.35
 else:continue
 x,y=g.xy;ax.plot(x,y,color=color,linewidth=lw,zorder=1)
for f in D['features']:
 g=transform(T,shape(f['geometry']));parts=list(g.geoms)if hasattr(g,'geoms')else[g]
 for a in parts:
  x,y=a.exterior.xy;ax.fill(x,y,alpha=.25,facecolor='#36a28c',edgecolor='#156a5a',linewidth=1,zorder=2)
 c=g.representative_point();ax.text(c.x,c.y,f['properties']['name'],ha='center',va='center',fontsize=8,bbox={'facecolor':'white','edgecolor':'none','alpha':.85,'pad':1.2},zorder=4)
for f in ALT['features']:
 g=transform(T,shape(f['geometry']));parts=list(g.geoms)if hasattr(g,'geoms')else[g]
 for a in parts:
  x,y=a.exterior.xy;ax.plot(x,y,color='#c47e2f',linewidth=.6,linestyle='--',zorder=3)
for c in C['controls']+C['heldOutAmbiguousChecks']:
 e,n=T(*c['targetWgs84']);pred=np.array([*c['sourcePdfPoint'],1])@M;ax.plot([e,pred[0]],[n,pred[1]],color='#ad2244',linewidth=1,zorder=6);ax.plot(e,n,'o',color='#ad2244',markersize=4,zorder=6);ax.annotate(c['id'],(e,n),xytext=(4,6),textcoords='offset points',fontsize=8,zorder=7)
B=[transform(T,shape(f['geometry'])).bounds for f in D['features']];x0=min(a[0]for a in B);y0=min(a[1]for a in B);x1=max(a[2]for a in B);y1=max(a[3]for a in B);ax.set_xlim(x0-350,x1+350);ax.set_ylim(y0-350,y1+350);ax.set_aspect('equal');ax.grid(alpha=.15);ax.set_xlabel('EOV easting (m), EPSG:23700');ax.set_ylabel('EOV northing (m)')
ax.set_title('Hódmezővásárhely KSH 2005: 9 observed contours, ESTIMATED placement\nGreen = main; orange dashed = two-control alternative; gray/black = actual 2026 roads/rails\nNames and source shapes are historical; complete current extents and absolute accuracy unverified',fontsize=10);fig.tight_layout();fig.savefig(P/'estimated-world-review.png');plt.close(fig)
