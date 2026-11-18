from pathlib import Path
import json,numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
R=Path(__file__).resolve().parent;T=Transformer.from_crs(4326,23700,always_xy=True).transform
px=shape(json.loads((R/'source-green-X-pixel-geometry.geojson').read_text())['features'][0]['geometry']);old=next(s for s in json.loads((R.parent/'selections.json').read_text()) if s['name']=='Budaihegy-Vacshegy')['pixels'];im=Image.open(R/'municipal-figure71.png')
fig,ax=plt.subplots(figsize=(11,9));ax.imshow(im);parts=list(px.geoms) if hasattr(px,'geoms') else [px]
for p in parts:
 x,y=p.exterior.xy;ax.plot(x,y,color='#0033ff',lw=2,label='corrected greenX enclosure')
x,y=zip(*(old+[old[0]]));ax.plot(x,y,color='red',lw=2,ls='--',label='superseded hand trace');ax.set_xlim(585,710);ax.set_ylim(365,250);ax.set_title('Source figure71: corrected greenX in blue, superseded trace in red');ax.legend();ax.grid(alpha=.2);fig.savefig(R/'budai-correction-source-overlay.png',dpi=170,bbox_inches='tight');plt.close(fig)
fs=json.loads((R/'features.geojson').read_text())['features'];g=transform(T,shape(fs[1]['geometry']));urban=transform(T,shape(json.loads((R/'excluded-urban-proxy.geojson').read_text())['features'][0]['geometry']));mun=transform(T,shape(json.loads((R/'salgotarjan-municipality.geojson').read_text())['features'][0]['geometry']));checks=json.loads((R/'source-evidence.json').read_text())['salgotarjan']['allSourcePlaceChecks']
fig,ax=plt.subplots(figsize=(11,13))
for geom,color in [(g,'#d9e1c9'),(urban,'#7ba9cc')]:
 for p in list(geom.geoms) if hasattr(geom,'geoms') else [geom]:
  x,y=p.exterior.xy;ax.fill(x,y,color=color,alpha=.8);ax.plot(x,y,color='#555555',lw=.5)
for c in checks:
 if c['name'] in ['Belváros','Vásártér','Beszterce-lakótelep','Kemerovó-lakótelep','Gorkij-lakótelep','Zagyvapálfalva','Baglyasalja','Somoskő','Eresztvény','Kotyháza','Ponyipuszta','Pécskőpuszta']:
  x,y=T(*c['coordinates']);ax.plot(x,y,'o',ms=4,color='red' if not c['insideCorrectedRural'] else '#38691b');ax.text(x,y,c['name'],fontsize=7,bbox={'facecolor':'white','edgecolor':'none','alpha':.5,'pad':1})
ax.set_aspect('equal');ax.ticklabel_format(style='plain',useOffset=False);ax.grid(alpha=.2);ax.set_title('Salgótarján: corrected rural estimate green; full urban/Eresztvény proxy blue\n73.73km² rural /92.63km²municipality; checked urbanplaces excluded')
fig.savefig(R/'salgotarjan-corrected-rural-preview.png',dpi=150,bbox_inches='tight');plt.close(fig)
