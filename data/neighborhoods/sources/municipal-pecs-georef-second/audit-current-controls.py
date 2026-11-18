#!/usr/bin/env python3
"""Offline current-OSM feature identity audit, not a georeferencing fit."""
from pathlib import Path
import json,hashlib,sys,os,math
os.environ['PROJ_NETWORK']='OFF'
import osmium
from pyproj import Transformer
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
OLD=P.parent/'municipal-pecs-grounded-next';NEXT=P.parent/'municipal-pecs-next'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def encoded(o):return json.dumps(o,ensure_ascii=False,indent=2)+'\n'
municipality=json.loads((OLD/'source-municipality.geojson').read_text());oldproof=json.loads((OLD/'boundary-source-proof.json').read_text())
ring=municipality['geometry']['coordinates'][0][0]
roadmap={f['properties']['osmWayId']:f for f in json.loads((NEXT/'pecs-review-road-control-numbered-highways.geojson').read_text())['features']}
rails={f['properties']['osmWayId']:f for f in json.loads((P/'local-rail-original.geojson').read_text())['features']}
# Read the current raw source objects independently, retaining exact node IDs/tags/locations.
wayids={w['osmWayId']for w in oldproof['rawMemberWays']}|{312297473,312297417,353613221,31279904,208759579}
pbf=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf';ways={};nodes={};relation=None
for o in osmium.FileProcessor(str(pbf)).with_filter(osmium.filter.IdFilter(wayids|{575380})):
 if isinstance(o,osmium.osm.Way)and o.id in wayids:ways[o.id]={'osmWayId':o.id,'nodeRefs':[n.ref for n in o.nodes],'tags':dict(o.tags),'version':o.version,'timestamp':str(o.timestamp)}
 elif isinstance(o,osmium.osm.Relation)and o.id==575380:relation={'osmRelationId':o.id,'tags':dict(o.tags),'members':[{'type':{'w':'way','n':'node','r':'relation'}.get(m.type,m.type),'ref':m.ref,'role':m.role}for m in o.members],'version':o.version,'timestamp':str(o.timestamp)}
assert set(ways)==wayids
ids={n for w in ways.values()for n in w['nodeRefs']}
for o in osmium.FileProcessor(str(pbf)).with_filter(osmium.filter.IdFilter(ids)):
 if isinstance(o,osmium.osm.Node)and o.id in ids:nodes[o.id]={'osmNodeId':o.id,'coordinates':[o.lon,o.lat],'version':o.version,'timestamp':str(o.timestamp)}
assert set(nodes)==ids
assert relation==oldproof['sourceRelation']
for prior in oldproof['rawMemberWays']:assert ways[prior['osmWayId']]==prior
for prior in oldproof['rawBoundaryNodes']:assert nodes[prior['osmNodeId']]==prior
for wid in [312297473,312297417,353613221,31279904,208759579]:
 f=(rails if wid in [31279904,208759579] else roadmap)[wid];p=f['properties'];w=ways[wid]
 assert p['nodeRefs']==w['nodeRefs'] and p['tags']==w['tags']
 assert f['geometry']['coordinates']==[nodes[n]['coordinates']for n in w['nodeRefs']]
bycoord={tuple(n['coordinates']):n['osmNodeId']for n in nodes.values()}
t=Transformer.from_crs(4326,23700,always_xy=True)
def eov(c):return list(t.transform(*c))
def direction(a,b):
 x,y=b[0]-a[0],b[1]-a[1]
 return {'deltaEovMetres':[x,y],'lengthMetres':math.hypot(x,y),'bearingDegreesFromNorth':math.degrees(math.atan2(x,y))%360}
# Determinant planar line intersections on literal adjacent source nodes, no snapping.
def cross(a,b,c,d):
 ux,uy=b[0]-a[0],b[1]-a[1];vx,vy=d[0]-c[0],d[1]-c[1];den=ux*vy-uy*vx
 if abs(den)<1e-15:return None
 dx,dy=c[0]-a[0],c[1]-a[1];q=(dx*vy-dy*vx)/den;r=(dx*uy-dy*ux)/den
 if 0<=q<=1 and 0<=r<=1:return {'eov':[a[0]+q*ux,a[1]+q*uy],'firstSegmentFraction':q,'secondSegmentFraction':r}
 return None
def segments(wid):
 w=ways[wid];n=w['nodeRefs']
 return [{'osmWayId':wid,'nodeRefs':n[i:i+2],'wgs84':[nodes[n[i]]['coordinates'],nodes[n[i+1]]['coordinates']],'eov':[eov(nodes[n[i]]['coordinates']),eov(nodes[n[i+1]]['coordinates'])]}for i in range(len(n)-1)]
boundarysegs=[s for w in oldproof['rawMemberWays']for s in segments(w['osmWayId'])]
intersections=[]
for wid in [312297473,353613221]:
 for a in segments(wid):
  for b in boundarysegs:
   z=cross(*a['eov'],*b['eov'])
   if z:intersections.append({'type':'road6-current-municipality-boundary','roadSegment':a,'boundarySegment':b,'computedIntersection':z,'literalCrossingNode':False,'sourceCorrespondenceApproved':False})
for a in segments(312297417):
 for b in segments(31279904):
  z=cross(*a['eov'],*b['eov'])
  if z:intersections.append({'type':'road6-rail64-grade-separated-plan-crossing','roadSegment':a,'railSegment':b,'computedIntersection':z,'literalCrossingNode':False,'sourceCorrespondenceApproved':False})
for a in segments(208759579):
 for b in boundarysegs:
  z=cross(*a['eov'],*b['eov'])
  if z:intersections.append({'type':'rail64-current-municipality-boundary','railSegment':a,'boundarySegment':b,'computedIntersection':z,'literalCrossingNode':False,'sourceCorrespondenceApproved':False})
assert len(intersections)==4
contexts=[]
for i,lo,hi in [(457,449,460),(386,378,395),(467,460,472)]:
 verts=[]
 for j in range(lo,hi):
  c=ring[j];n=bycoord[tuple(c)]
  verts.append({'ringVertexIndex':j,'osmNodeId':n,'wgs84':c,'eov':eov(c),'outgoingSegment':direction(eov(c),eov(ring[j+1]))})
 contexts.append({'candidateRingVertexIndex':i,'candidateOsmNodeId':bycoord[tuple(ring[i])],'literalRawMemberWayIds':[wid for wid,w in ways.items()if bycoord[tuple(ring[i])]in w['nodeRefs'] and wid in {x['osmWayId']for x in oldproof['rawMemberWays']}],'vertices':verts,'imageCorrespondenceApproved':False})
sourcehashes=[{'path':str(q.relative_to(ROOT)),'sha256':sha(q)}for q in [pbf,OLD/'source-name-map.jpeg',OLD/'source-municipality.geojson',OLD/'boundary-source-proof.json',OLD/'independent-review.json',NEXT/'pecs-review-road-control-numbered-highways.geojson',P/'local-rail-original.geojson']]
assert sourcehashes[0]['sha256']=='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
out={'schemaVersion':1,'status':'literal_current_osm_objects_and_plan_crossings_verified_source_identity_not_approved','networkUsed':False,'sourceInputs':sourcehashes,'relation':relation,'rawMemberAndCandidateWays':sorted(ways.values(),key=lambda w:w['osmWayId']),'rawReferencedNodes':sorted(nodes.values(),key=lambda n:n['osmNodeId']),'boundaryCandidateContexts':contexts,'computedFeatureCrossings':intersections,'rawSourceObjectsIndependentlyReadFromOriginalPbf':True,'originalArchivedBoundaryAndSelectedWaysMatchExactly':True,'coordinateOperation':{'sourceCrs':'EPSG:4326','targetCrs':'EPSG:23700','alwaysXY':True,'networkEnabled':False,'description':t.description,'metadataAccuracyMetresNotMapAccuracy':t.accuracy},'worldPointsFromOriginalAdjacentSourceSegments':True,'quarterNameCoordinatesUsed':False,'georeferenceModelFitted':False,'quarterGeometriesGeneratedOrChanged':False,'claimedAbsoluteAccuracy':None,'absoluteBoundaryAccuracyMetres':None,'primaryApproved':False,'usableForAddressAssignment':False}
target=P/'source-target-topology-proof.json';s=encoded(out)
if '--check'in sys.argv:assert target.read_text()==s;print('source-target topology exact reproducibility: PASS')
else:target.write_text(s);print(json.dumps({'verifiedRawWays':len(ways),'verifiedRawNodes':len(nodes),'planCrossings':len(intersections),'output':str(target.relative_to(ROOT))}))
