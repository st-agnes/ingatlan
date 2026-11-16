#!/usr/bin/env python3
"""Rebuild selected source-backed estimates offline. Requires shapely and pyproj."""
from pathlib import Path
from collections import Counter
import json,gzip,hashlib,unicodedata
from shapely.geometry import shape,Point,mapping
from shapely.ops import unary_union,polygonize,transform
from pyproj import Transformer
P=Path(__file__).resolve().parent;FW=Transformer.from_crs(4326,23700,always_xy=True).transform;IV=Transformer.from_crs(23700,4326,always_xy=True).transform
S=json.load(open(P/'selection.json'));T=json.load(open(P/'targets.json'));cache={};features=[];evidence=[]
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def ctx(key):
 if key not in cache:
  d=P/'source-inputs'/key;parent=transform(FW,shape(read(d/'municipality.geojson')['features'][0]['geometry']));roads=read(d/'roads.geojson.gz')['features'];areas=read(d/'areas.geojson.gz')['features'];cache[key]=(parent,roads,areas,{})
 return cache[key]
for s in S:
 parent,roads,areas,cells=ctx(s['contextKey']);byid={f['id']:f for f in roads+areas};src=[]
 if s['kind']=='cell':
  variant=s['cellId'].split(':')[-1]
  if variant not in cells:
   gs=[];used=[]
   for f in roads:
    tags=f['properties']['tags'];hw=tags.get('highway');rail=tags.get('railway');water=tags.get('waterway')
    if variant=='major' and hw not in {'motorway','trunk','primary','secondary','tertiary','unclassified'} and rail not in {'rail','light_rail'} and water not in {'river','canal','stream'}:continue
    if variant=='street' and hw in {'path','footway','cycleway','steps','track','bridleway','pedestrian'}:continue
    g=transform(FW,shape(f['geometry'])).intersection(parent)
    if not g.is_empty:gs.append(g);used.append((f,g))
   cells[variant]=(list(polygonize(unary_union([parent.boundary]+gs))),used)
  point=transform(FW,Point(s['pointSource']['coordinates']));candidates=[g for g in cells[variant][0] if g.covers(point) and 1000<g.area<12000000]
  assert len(candidates)==1,(s['name'],len(candidates));g=candidates[0]
  src=[f for f,line in cells[variant][1] if g.boundary.intersection(line).length>5]
  method='manual_road_water_rail_enclosure_estimate'
 elif s['kind']=='area':
  src=[byid[i] for i in s['sourceAreaIds']];g=unary_union([transform(FW,shape(f['geometry'])) for f in src]);method='mapped_landuse_locality_association_estimate'
 elif s['kind'] in ['roadHull','sourceHull']:
  src=[byid[i] for i in s.get('sourceLineIds',[])+s.get('sourceAreaIds',[])];g=unary_union([transform(FW,shape(f['geometry'])) for f in src]).convex_hull.intersection(parent);method='manual_named_street_network_envelope_estimate'
 elif s['kind']=='manual':
  f=next(f for f in read(P/'source-inputs'/'manual-traces.geojson')['features'] if f['id']==s['manualId']);g=transform(FW,shape(f['geometry']));src=[byid[i] for i in s.get('sourceLineIds',[]) if i in byid];method='manual_map_and_street_trace_estimate'
 elif s['kind']=='externalAreaMask':
  src=read(P/'source-inputs'/'tokaj-native-urban.geojson')['features'];g=unary_union([transform(FW,shape(f['geometry'])) for f in src]);mask=next(f for f in read(P/'source-inputs'/'manual-masks.geojson')['features'] if f['id']==s['maskId']);g=g.intersection(transform(FW,shape(mask['geometry'])));method='primary_text_street_and_native_landuse_partition_estimate'
 elif s['kind']=='parentRemainder':
  comps=read(P/'source-inputs'/'existing-miskolc-components.geojson')['features'];sourceParent=next(f for f in comps if f['id']==s['parentId']);ex=[f for f in comps if f['id'] in s['excludeComponentIds']]+[byid[i] for i in s['excludeAreaIds']];src=[sourceParent]+ex;g=transform(FW,shape(sourceParent['geometry'])).difference(unary_union([transform(FW,shape(f['geometry'])) for f in ex]));method='primary_constituent_table_parent_remainder_estimate'
 elif s['kind']=='importUnion':
  src=[f for f in read(P/'source-inputs'/'existing-miskolc-components.geojson')['features'] if f['id'] in s['componentIds']];g=unary_union([transform(FW,shape(f['geometry'])) for f in src]);method='source_verified_constituent_union_estimate'
 else:raise ValueError(s['kind'])
 if not g.is_valid:g=g.buffer(0)
 assert g.geom_type in ['Polygon','MultiPolygon'] and g.is_valid and g.area>1000,(s['name'],g.geom_type,g.area)
 slug=''.join(c for c in unicodedata.normalize('NFKD',s['municipality']+'-'+s['name']) if not unicodedata.combining(c));slug=''.join(c.lower() if c.isalnum() else '-' for c in slug).strip('-')
 urls=[f['properties'].get('source',{}).get('url') for f in src];urls=[x for x in urls if x]
 pointUrl=s.get('pointSource',{}).get('sourceUrl');primary=(s.get('supportingUrls') or urls or [pointUrl])[0]
 props={'name':s['name'],'municipality':s['municipality'],'method':method,'estimated':True,'lowConfidence':True,'confidence':'low','sourceUrl':primary,'supportingUrls':list(dict.fromkeys(s.get('supportingUrls',[])+([pointUrl] if pointUrl else [])+urls)),'approximationNote':s['approximationNote'],'sourceWayIds':[f['id'] for f in src],'areaSquareMetres':round(g.area),'sourceSnapshot':'2026-11-12T21:23:05Z','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','batch':s['batch']}
 f={'type':'Feature','id':'expansion:20261115-round4:shard5:'+slug,'properties':props,'geometry':mapping(transform(IV,g))};features.append(f)
 evidence.append({'featureId':f['id'],'municipality':s['municipality'],'name':s['name'],'boundaryEvidence':s['kind'],'pointUsedForNameAssociationOnly':bool(s.get('pointSource')),'sources':[x['properties'].get('source',{'id':x['id']}) for x in src],'supportingUrls':props['supportingUrls'],'note':s['approximationNote'],'sourceExcerpt':s.get('sourceExcerpt')})
fc={'type':'FeatureCollection','features':features};write(P/'features.geojson',fc);write(P/'evidence.json',{'schemaVersion':1,'features':evidence})
for batch in sorted({s['batch'] for s in S}):
 subset={'type':'FeatureCollection','features':[f for f in features if f['properties']['batch']==batch]};p=P/'batches'/('batch-%02d.geojson'%batch)
 if p.exists():assert read(p)==json.loads(json.dumps(subset)),('Frozen batch changed',batch)
 else:write(p,subset)
known={(f['properties']['municipality'],f['properties']['name']) for f in features};unresolved=[]
for m in T['municipalities']:
 for t in m['targets']:
  if (m['municipality'],t['name']) not in known:unresolved.append({'municipality':m['municipality'],'name':t['name'],'status':'remaining_under_review','searched':['Shared OSM names, whole mapped land-use outlines, actual road/water/rail network enclosures'],'reason':'Not selected in the frozen batch yet.'})
write(P/'unresolved.json',{'count':len(unresolved),'targets':unresolved})
sha=hashlib.sha256((P/'features.geojson').read_bytes()).hexdigest();write(P/'summary.json',{'featureCount':len(features),'targetCount':T['targetCount'],'remainingCount':len(unresolved),'allEstimated':True,'lowConfidenceCount':len(features),'municipalities':dict(Counter(f['properties']['municipality'] for f in features)),'featuresSha256':sha,'geometryValidation':'all nonempty valid Polygon/MultiPolygon; WGS84 output; source-preserving batch snapshots'})
print(json.dumps({'featureCount':len(features),'remaining':len(unresolved),'sha256':sha}))
