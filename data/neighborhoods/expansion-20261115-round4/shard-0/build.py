#!/usr/bin/env python3
"""Offline reconstruction from selected original source objects and explicit recipes."""
from pathlib import Path
import json,gzip,hashlib
from shapely.geometry import shape,mapping,box
from shapely.ops import unary_union,transform,polygonize
from pyproj import Transformer,Geod
P=Path(__file__).resolve().parent
with gzip.open(P/'source-objects.geojson.gz','rt',encoding='utf-8') as h:objects={f['id']:f for f in json.load(h)['features']}
to=Transformer.from_crs(4326,23700,always_xy=True).transform;back=Transformer.from_crs(23700,4326,always_xy=True).transform;geod=Geod(ellps='WGS84')
recipes=json.load(open(P/'recipes.json'));features=[];proof=[]
bybatch={}
for r in recipes:
 selected=[objects[i] for i in r['inputIds']];pieces=[]
 for f in selected:
  g=shape(f['geometry'])
  if f['id'] in r.get('inputScopes',{}):g=g.intersection(box(*r['inputScopes'][f['id']]))
  if not g.is_empty:pieces.append(g)
 g=unary_union(pieces)
 op=r['operation']
 if op=='physical-circuit':
  lines=[shape(f['geometry']).boundary if f['geometry']['type'] in ['Polygon','MultiPolygon'] else shape(f['geometry']) for f in selected]
  from shapely.geometry import Point
  matches=[p for p in polygonize(unary_union(lines)) if p.covers(Point(r['sourceNameAssociationPoint']))]
  if not matches:raise ValueError('Unclosed physical source circuit '+r['name'])
  g=min(matches,key=lambda p:p.area)
 if op in ['convex-envelope','street-envelope']:
  g=transform(to,g).convex_hull
  if r.get('frontageAllowanceM'):g=g.buffer(r['frontageAllowanceM'],join_style=2)
  g=transform(back,g)
 elif op not in ['union','physical-circuit']:raise ValueError('Unknown recipe '+op)
 if r.get('clipGeometry'):g=g.intersection(shape(r['clipGeometry']))
 if not g.is_valid:raise ValueError('Invalid output '+r['name'])
 if g.geom_type not in ['Polygon','MultiPolygon'] or g.is_empty:raise ValueError('Nonpolygon '+r['name'])
 key=hashlib.sha256((r['municipality']+'|'+r['name']).encode()).hexdigest()[:16]
 props=dict(name=r['name'],municipality=r['municipality'],method={'union':'source_defined_surface_or_component_union_estimate','convex-envelope':'source_surface_occupied_extent_envelope_estimate','street-envelope':'source_named_street_grid_envelope_estimate','physical-circuit':'reviewed_native_road_stream_or_parcel_field_circuit_estimate'}[op],estimated=True,lowConfidence=True,confidence='low',partialFootprint=r.get('partialFootprint',False),sourceUrl=r['sourceUrl'],supportingUrls=r.get('supportingUrls',[]),approximationNote=r['approximationNote'],evidenceFiles=r.get('evidenceFiles',[]),sourceObjectIds=r['inputIds'],sourcePeriod='OSM snapshot 2026-11-12 and archived documentary sources of stated periods',usableForAddressAssignment=False,boundaryKind='neighbourhood',areaM2=round(abs(geod.geometry_area_perimeter(g)[0])),license='ODbL-1.0',attribution='© OpenStreetMap contributors; municipal and cited factual evidence')
 features.append(dict(type='Feature',id='estimated:round4:shard0:'+key,properties=props,geometry=mapping(g)))
 if r.get('batch'):bybatch.setdefault(r['batch'],[]).append(features[-1])
 proof.append(dict(name=r['name'],municipality=r['municipality'],operation=op,sourceObjectCount=len(selected),pointBuffersCreated=0,areaM2=props['areaM2']))
(P/'features.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features),ensure_ascii=False,indent=2)+'\n')
for name,fs in bybatch.items():
 folder=P/'batches'/name;folder.mkdir(parents=True,exist_ok=True)
 (folder/'features.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=fs),ensure_ascii=False,indent=2)+'\n')
(P/'build-proof.json').write_text(json.dumps(dict(schemaVersion=1,allValid=True,pointBuffersCreated=0,inputSha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ['source-objects.geojson.gz','recipes.json']},features=proof),ensure_ascii=False,indent=2)+'\n')
print('Built',len(features),'valid source-based polygons')
