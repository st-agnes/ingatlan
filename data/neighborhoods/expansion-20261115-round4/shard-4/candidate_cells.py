from pathlib import Path
import json,gzip
from shapely.geometry import shape,Point,mapping
from shapely.ops import transform,unary_union,polygonize
from pyproj import Transformer
ROOT=Path(__file__).resolve().parent;R=ROOT.parent;TASK=json.loads((R/'tasks/shard-4.json').read_text())
T=Transformer.from_crs(4326,23700,always_xy=True).transform;B=Transformer.from_crs(23700,4326,always_xy=True).transform
D=ROOT/'inspection';D.mkdir(exist_ok=True)
out=[]
for m in TASK['municipalities']:
 if m['municipality'] in ['Kecskemét','Salgótarján']:continue
 c=R/'contexts'/m['contextKey'];roads=json.loads(gzip.decompress((c/'roads.geojson.gz').read_bytes()))['features'];areas=json.loads(gzip.decompress((c/'areas.geojson.gz').read_bytes()))['features'];mun=unary_union([transform(T,shape(f['geometry'])) for f in json.loads((c/'municipality.geojson').read_text())['features']])
 lines=[mun.boundary]
 for f in roads:
  tags=f['properties'].get('tags',{});h=tags.get('highway');g=transform(T,shape(f['geometry']))
  if h in ['motorway','trunk','primary','secondary','tertiary','unclassified','residential','living_street','track'] or tags.get('waterway') or tags.get('railway'):
   lines.append(g.intersection(mun))
 for f in areas:
  tags=f['properties'].get('tags',{});g=transform(T,shape(f['geometry']))
  if tags.get('building') or g.area<10000:continue
  if tags.get('landuse') in ['residential','industrial','forest','farmyard','farmland','orchard','vineyard'] or tags.get('natural') in ['wood','water']:
   lines.append(g.boundary.intersection(mun))
 cells=list(polygonize(unary_union(lines)))
 cells=[x for x in cells if x.area>100 and mun.covers(x.representative_point())]
 fc=[]
 for i,g in enumerate(cells):fc.append({'type':'Feature','id':i,'properties':{'cellIndex':i,'areaM2':g.area},'geometry':mapping(transform(B,g))})
 (D/(m['contextKey']+'-cells.geojson')).write_text(json.dumps({'type':'FeatureCollection','features':fc},ensure_ascii=False,separators=(',',':')))
 for t in m['targets']:
  if not t['pointCandidates']:continue
  p=transform(T,Point(t['pointCandidates'][0]['coordinates']));hits=sorted([(g.area,i) for i,g in enumerate(cells) if g.covers(p)])
  q={'municipality':m['municipality'],'name':t['name'],'contextKey':m['contextKey'],'candidates':[{'cellIndex':i,'areaKm2':round(a/1e6,5)} for a,i in hits]};out.append(q);print(m['municipality'],t['name'],q['candidates'])
(ROOT/'candidate-cell-review.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
