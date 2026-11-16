from pathlib import Path
import json,gzip,math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from shapely.geometry import shape
from shapely.ops import transform,unary_union
from pyproj import Transformer
R=Path(__file__).resolve().parent;T=Transformer.from_crs(4326,23700,always_xy=True).transform
fs=json.loads((R/'features.geojson').read_text())['features'];task=json.loads((R/'source-inputs/task.json').read_text());bycity={m['municipality']:m for m in task['municipalities']}
with PdfPages(R/'features-preview.pdf') as pdf:
 for city in sorted(bycity):
  features=[f for f in fs if f['properties']['municipality']==city];m=bycity[city];c=R/'source-inputs'/m['contextKey'];roads=json.loads(gzip.decompress((c/'roads.geojson.gz').read_bytes()))['features'];g=unary_union([transform(T,shape(f['geometry'])) for f in features]);minx,miny,maxx,maxy=g.bounds;pad=max((maxx-minx)*.06,(maxy-miny)*.06,100)
  fig,ax=plt.subplots(figsize=(12,10));colors=plt.cm.tab20.colors
  for f in roads:
   z=transform(T,shape(f['geometry']));gs=list(z.geoms) if hasattr(z,'geoms') else [z]
   for l in gs:
    if hasattr(l,'xy'):
     x,y=l.xy;ax.plot(x,y,color='#bbbbbb',lw=.4)
  for i,f in enumerate(features):
   z=transform(T,shape(f['geometry']));gs=list(z.geoms) if hasattr(z,'geoms') else [z]
   for p in gs:
    x,y=p.exterior.xy;ax.fill(x,y,color=colors[i%20],alpha=.23);ax.plot(x,y,color=colors[i%20],lw=1.2)
   p=z.representative_point();ax.text(p.x,p.y,f['properties']['name'],fontsize=8,color='#222222',bbox={'facecolor':'white','alpha':.6,'edgecolor':'none','pad':1})
  ax.set_xlim(minx-pad,maxx+pad);ax.set_ylim(miny-pad,maxy+pad);ax.set_aspect('equal');ax.ticklabel_format(style='plain',useOffset=False);ax.grid(alpha=.2);ax.set_title(city+' — low-confidence source-informed search neighborhoods');pdf.savefig(fig,bbox_inches='tight');plt.close(fig)
print('preview pages',len(bycity))
