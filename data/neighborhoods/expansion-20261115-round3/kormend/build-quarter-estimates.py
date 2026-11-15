#!/usr/bin/env python3
"""Offline rough quarter envelopes from archived actual streets, never place-point rings."""
import json,hashlib
from pathlib import Path
from shapely.geometry import shape,mapping,box,Polygon
from shapely.ops import unary_union,transform,linemerge
from pyproj import Transformer,Geod
P=Path(__file__).resolve().parent
W=json.load(open(P/'source-ways.geojson'))['features']; A=json.load(open(P/'source-areas.geojson'))['features']
city=shape(json.load(open(P/'municipality.geojson'))['features'][0]['geometry'])
recipes=json.load(open(P/'quarter-recipes.json'))
forward=Transformer.from_crs(4326,23700,always_xy=True).transform;reverse=Transformer.from_crs(23700,4326,always_xy=True).transform;geod=Geod(ellps='WGS84')
features=[];proof=[]
for r in recipes:
 pieces=[];used=[]
 for rule in r['roads']:
  found=0
  for f in W:
   if f['properties']['name']!=rule['name']:continue
   g=shape(f['geometry'])
   if not g.intersects(city):continue
   if 'scopeBbox' in rule:g=g.intersection(box(*rule['scopeBbox']))
   if g.is_empty or g.length==0:continue
   pieces.append(g);used.append(dict(name=rule['name'],wayId=f['properties']['source']['osmId'],scopeBbox=rule.get('scopeBbox'),sourceUrl=f['properties']['source']['url']));found+=1
  if not found:raise ValueError('Missing actual source road: '+rule['name'])
 for aid in r.get('areas',[]):
  f=next(f for f in A if f['properties']['source']['osmId']==aid);pieces.append(shape(f['geometry']));used.append(dict(areaWayId=aid,sourceUrl=f['properties']['source']['url']))
 # A convex envelope of the actual connected street grid estimates whole blocks;
 # the square-cornered outward allowance includes one outer frontage depth.
 # These deliberately inferred edges are not published administrative lines.
 base=unary_union([transform(forward,g) for g in pieces]).convex_hull
 g=transform(reverse,base.buffer(r['frontageAllowanceM'],join_style=2)).intersection(city)
 if r.get('westOfHunyadi'):
  # The primary notice puts Tisztviselő on/east of Hunyadi. Use the actual
  # main-road trace as an inferred Rokkant east edge, excluding its named spur.
  scope=box(16.58,47.014,16.62,47.022)
  main=linemerge(unary_union([shape(f['geometry']).intersection(scope) for f in W if f['properties']['name']=='Hunyadi János utca' and f['properties']['source']['tags'].get('highway')=='secondary' and shape(f['geometry']).intersects(scope)]))
  if main.geom_type!='LineString':raise ValueError('Main Hunyadi road is disconnected')
  cs=list(main.coords)
  if cs[0][1]>cs[-1][1]:cs.reverse()
  half=Polygon([(16.58,cs[0][1])]+cs+[(16.58,cs[-1][1]),(16.58,cs[0][1])])
  g=g.intersection(half)
 if not g.is_valid or g.is_empty or g.geom_type!='Polygon':raise ValueError('Invalid quarter '+r['name'])
 props=dict(name=r['name'],municipality='Körmend',method='Estimated whole-quarter street-grid envelope: convex envelope of archived named street segments and any specified estate open-land polygon, plus an explicitly inferred square-cornered outer frontage allowance.',estimated=True,lowConfidence=True,confidence='low',sourceUrl=r['sourceUrl'],supportingUrls=r['supportingUrls'],approximationNote=r['approximationNote'],sourcePeriod='Municipal 2021/2025 quarter names and descriptions; OSM snapshot 2026-11-12',boundaryKind='neighbourhood',partialFootprint=False,usableForAddressAssignment=False,areaM2=round(abs(geod.geometry_area_perimeter(g)[0])),frontageAllowanceM=r['frontageAllowanceM'],license='ODbL-1.0',attribution='Körmend municipality; © OpenStreetMap contributors; OSM-derived Openalfa street associations')
 features.append(dict(type='Feature',id=r['id'],properties=props,geometry=mapping(g)))
 proof.append(dict(name=r['name'],recipe=r,usedSourceObjects=used,sourceObjectCount=len(used),areaM2=props['areaM2'],inferredEnvelopeEdges=True,pointBuffersCreated=0))
(P/'quarter-estimates.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features),ensure_ascii=False,indent=2)+'\n')
(P/'quarter-build-proof.json').write_text(json.dumps(dict(schemaVersion=1,method='Actual street network envelope with explicit inferred frontage allowance; no place-point geometry construction',crsForMetricOperations='EPSG:23700',quarters=proof,inputSha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ['quarter-recipes.json','source-ways.geojson','source-areas.geojson','municipality.geojson']}),ensure_ascii=False,indent=2)+'\n')
print('Generated',len(features),'source-street/estate estimates:',[(f['properties']['name'],f['properties']['areaM2']) for f in features])
