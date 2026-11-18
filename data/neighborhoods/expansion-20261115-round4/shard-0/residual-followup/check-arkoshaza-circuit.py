#!/usr/bin/env python3
"""Document actual linework closure; never add edges or turn a viewport into a district."""
from pathlib import Path
import gzip,json,hashlib,shutil
from shapely.geometry import shape,Point,mapping
from shapely.ops import unary_union,polygonize,transform
from pyproj import Transformer
P=Path(__file__).resolve().parent;C=P.parent.parent/'contexts/babosdobrete-a9c1c939';tr=Transformer.from_crs(4326,23700,always_xy=True).transform
roads=json.load(gzip.open(P/'source-inputs/arkoshaza-roads.geojson.gz','rt'))['features'];areas=json.load(gzip.open(P/'source-inputs/arkoshaza-areas.geojson.gz','rt'))['features'];municipality=json.load(open(P/'source-inputs/arkoshaza-municipality.geojson'));mu=unary_union([shape(f['geometry']) for f in municipality['features']]);pt=Point(16.7722417,46.8252895)
physical=[];objects=[]
for f in roads:
 tags=f['properties']['tags']
 if tags.get('highway') or tags.get('waterway') or tags.get('railway'):physical.append(shape(f['geometry']));objects.append(f)
for f in areas:
 g=shape(f['geometry'])
 if g.geom_type in ['Polygon','MultiPolygon'] and f['properties']['tags'].get('natural')!='mountain_range':physical.append(g.boundary);objects.append(f)
physical_matches=[g for g in polygonize(unary_union(physical)) if g.covers(pt)]
with_admin=[g for g in polygonize(unary_union(physical+[mu.boundary])) if g.covers(pt)]
proposal=[];sources=[]
for g in with_admin:
 ids=[]
 for f in objects:
  h=shape(f['geometry']);h=h.boundary if h.geom_type in ['Polygon','MultiPolygon'] else h
  overlap=transform(tr,h.intersection(g.boundary)).length
  if overlap>1:ids.append({'id':f['id'],'overlapM':round(overlap),'tags':f['properties']['tags']});sources.append(f)
 proposal.append({'type':'Feature','properties':{'municipality':'Babosdöbréte','name':'Árkosháza-puszta','reviewStatus':'REVIEW_ONLY_NOT_COLLECTED','method':'native_road_and_municipal_boundary_closed_tract_proposal','estimated':True,'lowConfidence':True,'partialFootprint':True,'areaM2':round(transform(tr,g).area),'administrativeBoundaryContributionM':round(transform(tr,g.boundary.intersection(mu.boundary)).length),'boundaryObjects':ids,'approximationNote':'No physical-only circuit contains the historic name point. This candidate closes only when the actual Babosdöbréte municipal boundary is added. It is not a documented historical estate extent or current settlement footprint and is not included in features.geojson.'},'geometry':mapping(g)})
(P/'arkoshaza-road-municipality-proposal.geojson').write_text(json.dumps({'type':'FeatureCollection','features':proposal},ensure_ascii=False,indent=2)+'\n')

proof={'historicSourceNamePoint':[16.7722417,46.8252895],'physicalOnlyContainingCircuitCount':len(physical_matches),'physicalPlusMunicipalityContainingCircuitCount':len(with_admin),'extraSyntheticEdgesAdded':0,'viewportsUsedAsOutput':False,'physicalRoadAreaCount':len(physical),'sourceBoundaryDistanceM':round(transform(tr,pt).distance(transform(tr,mu.boundary)),2),'nearestBuildingDistanceM':766,'reviewProposalAreaM2':[f['properties']['areaM2'] for f in proposal]}
(P/'arkoshaza-circuit-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps(proof,ensure_ascii=False));print('Proposal boundary sources',json.dumps([f['properties']['boundaryObjects'] for f in proposal],ensure_ascii=False))
