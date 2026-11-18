import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from PIL import Image
N=Path(__file__).resolve().parents[2];P=N/'shard-4';R=Path(__file__).resolve().parent;im=Image.open(P/'kecskemet/page138-xref164.png')
fig,ax=plt.subplots(figsize=(20,14));ax.imshow(im)
for s in json.load(open(P/'selections.json')):
 if s['kind']!='raster-map':continue
 xy=s['pixels'];ax.add_patch(Polygon(xy,fill=False,linewidth=2,edgecolor='red'));x=sum(x[0] for x in xy)/len(xy);y=sum(x[1] for x in xy)/len(xy);ax.text(x,y,s['name'],fontsize=8,color='blue',bbox={'facecolor':'white','alpha':.6,'pad':1})
ax.set_xlim(250,1020);ax.set_ylim(570,150);fig.savefig(R/'kecskemet-source-traces-overlay.png',dpi=140)
