from pathlib import Path
import json,gzip
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape,box
H=Path(__file__).resolve().parent
S=H.parent/'ozd-szekszard/szekszard-source-roads.geojson.gz'
features=json.loads(gzip.open(S,'rt').read())['features'];extent=box(18.727,46.345,18.752,46.362)
rows=[f for f in features if shape(f['geometry']).intersects(extent)]
(H/'source-context.geojson').write_text(json.dumps({'type':'FeatureCollection','features':rows},ensure_ascii=False,separators=(',',':'))+'\n')
fig,ax=plt.subplots(figsize=(12,10));seen=set()
for f in rows:
 g=shape(f['geometry']);p=f['properties'];n=p.get('name')or'';tags=p.get('source',{}).get('tags',{})
 if g.geom_type=='LineString':
  xs,ys=g.xy;ax.plot(xs,ys,color='#666666',lw=1)
  if n and n not in seen:
   ax.text(g.centroid.x,g.centroid.y,n,fontsize=8);seen.add(n)
 else:
  for part in g.geoms if g.geom_type=='MultiPolygon'else[g]:
   xs,ys=part.exterior.xy;ax.fill(xs,ys,color='#80c6ec')
if (H/'features.geojson').exists():
 env=shape(json.loads((H/'features.geojson').read_text())['features'][0]['geometry']);xs,ys=env.exterior.xy;ax.fill(xs,ys,color='#e9b949',alpha=.18);ax.plot(xs,ys,color='#b7791f',lw=1.5)
ax.set_xlim(18.727,18.752);ax.set_ylim(46.345,46.362);ax.set_aspect(1/.69);ax.grid();fig.savefig(H/'source-road-lake-context.png',dpi=150)
print('localfeatures',len(rows))
for f in rows:
 if f['properties'].get('name'):print(f['properties']['name'],f['properties']['source']['osmId'],shape(f['geometry']).bounds)
