"""Validate candidate geometry against independently loaded source lines and parent.

This is a second code path by the same author, not an independent human/agent
source-map review. It cannot resolve source-era semantic or junction uncertainty.
"""
import json,hashlib
from pathlib import Path
from shapely.geometry import shape,LineString,Point
from shapely.ops import transform,unary_union
from pyproj import Transformer
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3] if len(OUT.parents)>3 else OUT
T=Transformer.from_crs(4326,23700,always_xy=True).transform
F=json.loads((OUT/'szentes-local-lines.geojson').read_text())['features']
source_nodes={tuple(c)for f in F for c in f['geometry']['coordinates']}
line_graph=unary_union([shape(f['geometry'])for f in F])
source_edges=[]
for f in F:
 cs=f['geometry']['coordinates'];ids=f['properties']['source']['nodeRefs']
 for i,(a,b)in enumerate(zip(cs,cs[1:])):source_edges.append((LineString([a,b]),f['properties']['source']['osmId'],i,ids[i:i+2]))
parent_path=OUT/'szentes-parent-control.geojson'
parents=json.loads(parent_path.read_text())['features'] if parent_path.exists() else json.loads((ROOT/'.local/neighborhoods/country/municipalities.geojson').read_text())['features']
parent=next(f for f in parents if f['properties']['name']=='Szentes')
(OUT/'szentes-parent-control.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[parent]},ensure_ascii=False,indent=2)+'\n')
results=[]
for key in ['deak-side','apponyi-around']:
 path=OUT/f'szentes-belvaros-{key}-inferred-review.geojson';feature=json.loads(path.read_text())['features'][0];p=shape(feature['geometry'])
 missing=transform(T,p.boundary.difference(line_graph)).length
 constructed=[tuple(c)for c in p.exterior.coords[:-1]if tuple(c)not in source_nodes]
 intersection_proof=[]
 for c in constructed:
  # Native linear intersections may have floating arithmetic differences from
  # two-input segment evaluation. Require proximity below 1e-10 degrees.
  hits=[{'osmWayId':f['properties']['source']['osmId'],'name':f['properties']['name'],'distanceDegrees':shape(f['geometry']).distance(Point(c))}for f in F if shape(f['geometry']).distance(Point(c))<1e-10]
  intersection_proof.append({'coordinate':c,'sourceWays':hits})
  assert len(hits)>=2
 outside=transform(T,p.difference(shape(parent['geometry']))).area
 segment_proof=[]
 for a,b in zip(p.exterior.coords,p.exterior.coords[1:]):
  hits=[]
  for edge,w,i,refs in source_edges:
   da,db=Point(a).distance(edge),Point(b).distance(edge)
   if max(da,db)<1e-11:hits.append({'osmWayId':w,'sourceNodeIndex':i,'sourceNodeRefs':refs,'maxEndpointDistanceDegrees':max(da,db)})
  assert hits,('Unsupported native boundary segment',a,b)
  segment_proof.append({'from':list(a),'to':list(b),'sourceSegments':hits})
 assert p.is_valid and p.geom_type=='Polygon' and len(p.interiors)==0 and outside==0
 results.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'valid':p.is_valid,'holes':len(p.interiors),'vertices':len(p.exterior.coords),'areaM2':transform(T,p).area,'rawGeosDifferenceFromEntireNodedSourceGraphM':missing,'rawGeosDifferenceNote':'Exact union/difference may miss collinear floating point partial intersections at bridges; every output segment is separately verified against a single original source segment with both endpoint distances below 1e-11 degrees. No geometry was snapped or repaired.','unsupportedBoundarySegments':0,'nativeSegmentSupportToleranceDegrees':1e-11,'nativeSegmentSupport':segment_proof,'outsideSzentesParentAreaM2':outside,'literalOriginalSourceVertices':len(p.exterior.coords)-1-len(constructed),'constructedVerticesAtActualLineIntersections':intersection_proof,'usableForAddressAssignment':False,'sourceContourIsObserved':False})
proof={'schemaVersion':1,'validatorAuthor':'Same reconstruction author, separate code path; not an independent source/map review.','parentOsmRelation':1025074,'parentSourcePbfSha256':parent['properties']['source']['pbfSha256'],'results':results,'materialLimits':['No source contour pixels were observed. Six current street/path/junction choices remain inferred.','Passing checks establish topology, actual current source-line support and municipal containment; they do not establish historical or present neighborhood correctness.']}
(OUT/'szentes-final-checks.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'checkedCandidates':len(results),'unsupportedBoundarySegments':sum(x['unsupportedBoundarySegments']for x in results),'outsideParentAreaM2':sum(x['outsideSzentesParentAreaM2']for x in results)},ensure_ascii=False))
