from pathlib import Path
import json
from shapely.geometry import shape,Point,mapping
from shapely.ops import transform,unary_union,polygonize
from pyproj import Transformer
P=Path(__file__).resolve().parent;fwd=Transformer.from_crs(4326,23700,always_xy=True).transform;inv=Transformer.from_crs(23700,4326,always_xy=True).transform
areas=json.load(open(P/'source-areas.geojson'))['features'];lines=json.load(open(P/'source-lines.geojson'))['features'];targets=json.load(open(P/'targets.json'));parents={f['properties']['name']:transform(fwd,shape(f['geometry'])) for f in json.load(open(P/'source-municipalities.geojson'))['features']}
ags=[transform(fwd,shape(f['geometry'])) for f in areas];candidates=[]
for city,par in parents.items():
 ts=[t for t in targets if t['municipality']==city]
 print('\nCITY',city,flush=True)
 for t in ts:
  pt=transform(fwd,Point(t['pointCandidates'][0]['coordinates']));ids=[i for i,f in enumerate(areas) if city in f['properties']['municipalities'] and ags[i].distance(pt)<1000];ids.sort(key=lambda i:(ags[i].distance(pt),ags[i].area));print('AREA',t['name'],[(areas[i]['id'],areas[i]['properties']['tags'],round(ags[i].distance(pt)),round(ags[i].area)) for i in ids[:4]],flush=True)
 for variant in ['major','street','rural']:
  gs=[par.boundary]
  src=[]
  for f in lines:
   if city not in f['properties']['municipalities']:continue
   tags=f['properties']['tags'];hw=tags.get('highway')
   if variant=='major' and hw and hw not in {'motorway','trunk','primary','secondary','tertiary','unclassified'}:continue
   if variant=='street' and hw in {'footway','path','track','cycleway','steps','pedestrian'}:continue
   g=transform(fwd,shape(f['geometry'])).intersection(par)
   if g.is_empty:continue
   gs.append(g);src.append((f,g))
  cells=list(polygonize(unary_union(gs)))
  for t in ts:
   pt=transform(fwd,Point(t['pointCandidates'][0]['coordinates']));near=[g for g in cells if g.covers(pt) and g.area>1000 and g.area<10_000_000]
   for g in near:
    ids=[f['id'] for f,l in src if g.boundary.intersection(l).length>20]
    props={'municipality':city,'name':t['name'],'variant':variant,'area':round(g.area),'sourceLineIds':ids}
    candidates.append({'type':'Feature','id':city+':'+t['name']+':'+variant,'properties':props,'geometry':mapping(transform(inv,g))});print('CELL',t['name'],variant,round(g.area),flush=True)
(P/'candidate-cells.geojson').write_text(json.dumps({'type':'FeatureCollection','features':candidates},ensure_ascii=False,separators=(',',':'))+'\n')
