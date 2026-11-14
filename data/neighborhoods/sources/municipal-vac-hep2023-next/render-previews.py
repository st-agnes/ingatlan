#!/usr/bin/env python3
"""Technical review previews only; stored geometry is never edited by rendering."""
from pathlib import Path
import json,os
os.environ.setdefault('MPLCONFIGDIR','/tmp/vac-matplotlib')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform
P=Path(__file__).resolve().parent
read=lambda n:json.loads((P/n).read_text())
im=Image.open(P/'source-map-native.png');traces=read('native-contour-traces.json')['features'];spec=read('registration-control-specification.json');proof=read('registration-proof.json');m=np.array(proof['affinePixelToEovRows']);M=np.array([[m[0,0],m[1,0],m[2,0]],[m[0,1],m[1,1],m[2,1]],[0,0,1]]);inverse=np.linalg.inv(M);tr=Transformer.from_crs(4326,23700,always_xy=True).transform;roads=read('selected-actual-osm-ways.geojson')['features'];by={f['id']:f for f in roads};world=shape(read('marialiget-estimated-proposal.geojson')['features'][0]['geometry']);wg=transform(tr,world)
fig,axes=plt.subplots(1,3,figsize=(16,6),dpi=160)
for ax,c in zip(axes,spec['controls']):
 ax.imshow(im,interpolation='nearest')
 for i,color in zip(c['actualWayIds'],['#07b5c2','#e26b2b']):
  w=by[i];a=np.array([tr(*p)for p in w['geometry']['coordinates']]);pix=np.c_[a,np.ones(len(a))]@inverse.T;ax.plot(pix[:,0],pix[:,1],color=color,lw=1,label=i)
 x,y=c['sourcePixel'];ax.plot(x,y,'x',color='blue',ms=8,mew=1.4);ax.set_xlim(x-17,x+17);ax.set_ylim(y+17,y-17);ax.grid(alpha=.3);ax.set_title(c['id']+': '+c['label'],fontsize=9);ax.legend(fontsize=6,loc='lower right');ax.set_xlabel('native source pixel x');ax.set_ylabel('native source pixel y')
fig.suptitle('Three physical road/rail calibration crossings — approximate manual pixel readings\nCurrent literal PBF geometry over source raster; exact 3-pair fit has no independent accuracy validation',fontsize=10);fig.tight_layout(rect=(0,0,1,.9));fig.savefig(P/'physical-control-review.png');plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(16,8),dpi=160)
axes[0].imshow(im,interpolation='nearest');axes[0].set_title('Literal source map; five larger parent groups',fontsize=9)
for ax in [axes[0],axes[1]]:
 for t,color in zip(traces,['#0660d9','#f29020']):
  a=np.array(t['sourcePixels']);ax.plot(a[:,0],a[:,1],color=color,lw=1.2 if ax==axes[1]else.7)
axes[1].imshow(im,interpolation='nearest');a=np.array(traces[0]['sourcePixels']);axes[1].plot(a[:,0],a[:,1],color='#0660d9',lw=1.2);axes[1].set_xlim(325,389);axes[1].set_ylim(449,386);axes[1].grid(alpha=.2);axes[1].set_title('Mária-liget: reconciled concave dashed contour',fontsize=9)
for f in read('identity-points.geojson')['features']:
 if f['properties']['name']!='Mária-liget':continue
 p=transform(tr,shape(f['geometry']));pix=inverse@np.array([p.x,p.y,1]);axes[1].plot(pix[0],pix[1],'o',color='#a1178f',ms=3.5);axes[1].annotate('Actual name point; not a fit control\n~8 m outside under this registration',(pix[0],pix[1]),xytext=(326,387),fontsize=6.5,color='#8c1476',arrowprops={'arrowstyle':'-','lw':.6})
 axes[2].plot(p.x,p.y,'o',color='#a1178f',ms=3.5)
for f in roads:
 if f['properties']['name']=='Árvácska utca':continue
 g=transform(tr,shape(f['geometry']));axes[2].plot(*g.xy,color='#989898',lw=.55,alpha=.7)
for f in read('unadmitted-registration-variants.geojson')['features']:
 g=transform(tr,shape(f['geometry']));axes[2].plot(*g.exterior.xy,color='#ad7c46',lw=.45,alpha=.4)
axes[2].plot(*wg.exterior.xy,color='#0660d9',lw=1.4);a,b,c,d=wg.bounds;axes[2].set_xlim(a-180,c+180);axes[2].set_ylim(b-180,d+180);axes[2].set_aspect('equal');axes[2].grid(alpha=.2);axes[2].set_title('One LOW-CONFIDENCE estimate + 24 unadmitted sensitivities',fontsize=9);axes[2].set_xlabel('EOV easting (m), EPSG:23700');axes[2].set_ylabel('EOV northing (m)')
fig.suptitle('Vác: Mária-liget first proposal only; source map year and current whole-quarter extent unknown\nManual source trace, conventional dashed-gap interpolation and southern registration extrapolation are explicit; no accuracy claim',fontsize=10);fig.tight_layout(rect=(0,0,1,.9));fig.savefig(P/'candidate-and-native-review.png');plt.close(fig)
