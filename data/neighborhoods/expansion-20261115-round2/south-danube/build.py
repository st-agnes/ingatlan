#!/usr/bin/env python3
"""Offline source/rough-map search extents. Frozen source ways + explicit manual traces.
No network, PBF, radius, Voronoi or point-only shape generation in this rebuild.
"""
from pathlib import Path
from collections import Counter
import json,gzip,hashlib
from shapely.geometry import shape,mapping,Point,Polygon
from shapely.ops import transform
from shapely import make_valid
from pyproj import Transformer
H=Path(__file__).resolve().parent
ROOT=H.parents[3]
def load(n):
 p=H/n;return json.loads(gzip.open(p,'rt').read()) if n.endswith('.gz') else json.loads(p.read_text())
def dump(n,x):(H/n).write_text(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
def polys(g):
 if g.geom_type=='Polygon':return [g]
 if g.geom_type in ['MultiPolygon','GeometryCollection']:return [p for x in g.geoms for p in polys(x)]
 return []
def area(g):return transform(Transformer.from_crs(4326,23700,always_xy=True).transform,g).area
roads=load('source-roads.geojson.gz')['features'];surfs=load('source-surfaces.geojson.gz')['features'];contexts=load('source-built-contexts.geojson')['features']
objects={x['id']:x for x in roads+surfs+contexts}
municipal={x['properties']['name']:shape(x['geometry']) for x in load('source-municipalities.geojson')['features']}
targets={(x['municipality'],x['name']):x for x in load('target-selection.json')}
facts=load('source-facts.json')['facts']
features=[];results=[]
for spec in load('trace-specifications.json')['traces']:
 city,name=spec['municipality'],spec['name'];t=targets[(city,name)];native=spec.get('nativeAreaId')
 if native:g=shape(objects[native]['geometry'])
 else:g=Polygon(spec['coordinates'])
 if not g.is_valid:raise ValueError('invalid source/manual trace '+name)
 if spec.get('clipToBuiltContextId'):g=g.intersection(shape(objects[spec['clipToBuiltContextId']]['geometry']))
 g=g.intersection(municipal[city]);parts=polys(g)
 if not parts:raise ValueError('empty '+name)
 from shapely.ops import unary_union
 g=unary_union(parts)
 if not g.is_valid:raise ValueError('invalid final '+name)
 sourceIds=spec.get('sourceWayIds',[])+([native] if native else [])+([spec['clipToBuiltContextId']] if spec.get('clipToBuiltContextId') else [])
 src=[objects[i]['properties'].get('source',{}) for i in sourceIds]
 p={'municipality':city,'municipalityId':'city:'+city,'name':name,'method':'source_polygon' if native else 'rough_manual_map_partition','estimated':not bool(native),'qualityScore':80 if native else 20,'pointRadiusFallback':False,'boundaryKind':'neighbourhood','searchable':True,'confidence':'source_named_area' if native else 'low','wholeQuarterAccuracyVerified':False,'approximationNote':spec['note'],'namePoint':t['pointCandidates'][0], 'source': {'provider':'openstreetmap' if native else 'manual-osm-road-context-inference','url':src[0].get('url') if src else t['pointCandidates'][0]['sourceUrl'],'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','pbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','sourceGeometryIds':sourceIds,'sourceGeometryFile':str((H/'source-surfaces.geojson.gz').relative_to(ROOT)) if native else str((H/'source-roads.geojson.gz').relative_to(ROOT)),'traceFile':str((H/'trace-specifications.json').relative_to(ROOT))},'supportingFacts':[facts[i] for i in spec.get('sourceFactIndexes',[])]}
 ident='south-danube:'+hashlib.sha256((city+'|'+name).encode()).hexdigest()[:20]
 features.append({'type':'Feature','id':ident,'geometry':mapping(g),'properties':p})
 results.append({'municipality':city,'name':name,'areaSquareMetres':round(area(g),1),'valid':g.is_valid,'coversNamePoint':g.covers(Point(t['pointCandidates'][0]['coordinates'])),'method':p['method']})
features.sort(key=lambda x:(x['properties']['municipality'],x['properties']['name']))
dump('features.geojson',{'type':'FeatureCollection','features':features})
dump('validation.json',{'scope':'technical_not_exact_accuracy_review','featureCount':len(features),'allValid':all(x['valid'] for x in results),'allCoverNamePoint':all(x['coversNamePoint'] for x in results),'results':results})
covered={(f['properties']['municipality'],f['properties']['name']) for f in features}
unresolved=[{'municipality':city,'name':name,'reason':'No sufficiently grounded complete polygon generated in this batch; source availability not exhausted.'} for city,name in targets if (city,name) not in covered]
dump('unresolved.json',unresolved)
dump('summary.json',{'schemaVersion':1,'featureCount':len(features),'municipalities':dict(Counter(f['properties']['municipality'] for f in features)),'methods':dict(Counter(f['properties']['method'] for f in features)),'baselineMissingTargets':len(targets),'remaining':len(unresolved),'circleCount':0,'geojsonSha256':hashlib.sha256((H/'features.geojson').read_bytes()).hexdigest(),'scope':'Saved source boundaries and explicitly rough road/map-informed search estimates, not validated cadastral/quarter boundaries.'})
print(json.dumps(load('summary.json'),ensure_ascii=False))
