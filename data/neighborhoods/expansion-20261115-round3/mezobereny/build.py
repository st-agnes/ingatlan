#!/usr/bin/env python3
"""Reconstruct the explicit municipal street circuit from frozen actual road nodes."""
import heapq,hashlib,json,math
from collections import defaultdict
from pathlib import Path
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import LineString,Polygon,Point,shape,mapping
from shapely.ops import transform,unary_union
H=Path(__file__).resolve().parent
F=Transformer.from_crs(4326,23700,always_xy=True).transform
def read(n):return json.loads((H/n).read_bytes())
def write(n,o):(H/n).write_text(json.dumps(o,ensure_ascii=False,separators=(',',':'))+'\n')
def key(p):return tuple(p)
def main():
 definition=read('boundary-definition.json');legs=definition['legs'];roads=read('source-roads.geojson')['features'];graph=defaultdict(list);nodesByName=defaultdict(set);xy={}
 for f in roads:
  name=f['properties'].get('name');coords=f['geometry']['coordinates']
  if not f['properties'].get('source',{}).get('tags',{}).get('highway'):continue
  for a,b in zip(coords,coords[1:]):
   a,b=key(a),key(b);xy.setdefault(a,F(*a));xy.setdefault(b,F(*b))
   dist=math.dist(xy[a],xy[b]);edge={'wayId':f['id'],'name':name,'metres':dist}
   graph[a].append((b,edge));graph[b].append((a,edge));nodesByName[name].update([a,b])
 sets=[set().union(*(nodesByName[n] for n in leg['osmNames'])) for leg in legs]
 start=sorted(sets[-1]&sets[0])[0]
 def shortest(a,goals,allowed):
  queue=[(0,a)];cost={a:0};back={}
  while queue:
   value,p=heapq.heappop(queue)
   if value!=cost[p]:continue
   if p in goals:
    route=[p];es=[]
    while p!=a:p0,e=back[p];es.append(e);route.append(p0);p=p0
    return list(reversed(route)),list(reversed(es))
   for p2,e in graph[p]:
    v=value+e['metres']*(1 if e['name'] in allowed else 100)
    if v<cost.get(p2,float('inf')):cost[p2]=v;back[p2]=(p,e);heapq.heappush(queue,(v,p2))
  raise ValueError('Disconnected road circuit at '+str(a))
 ring=[start];audit=[]
 for i,leg in enumerate(legs):
  goals=sets[(i+1)%len(legs)] if i<len(legs)-1 else {start}
  path,edges=shortest(ring[-1],goals,set(leg['osmNames']))
  assert edges,'Empty named boundary leg '+leg['sourceStreet']
  ring.extend(path[1:])
  gaps=[e for e in edges if e['name'] not in leg['osmNames']]
  audit.append({'sourceStreet':leg['sourceStreet'],'mappedNames':leg['osmNames'],'sourceWayIds':sorted({e['wayId'] for e in edges}),'lengthMetres':round(sum(e['metres'] for e in edges),2),'connectorMetres':round(sum(e['metres'] for e in gaps),2),'connectorWayIds':sorted({e['wayId'] for e in gaps}),'connectorNames':sorted({e['name'] or '<unnamed>' for e in gaps})})
 assert ring[-1]==start,'No fabricated closing segment permitted'
 raw=Polygon(ring);g=make_valid(raw);point=Point(read('baseline-target.json')['pointCandidates'][0]['coordinates'])
 if g.geom_type not in ['Polygon','MultiPolygon']:g=unary_union([p for p in g.geoms if p.geom_type in ['Polygon','MultiPolygon']])
 if g.geom_type=='MultiPolygon':g=max([p for p in g.geoms if p.covers(point)],key=lambda p:p.area)
 mun=read('source-municipality.geojson')['features']
 if mun:g=g.intersection(shape(mun[0]['geometry']))
 assert g.is_valid and not g.is_empty and g.covers(point)
 area=transform(F,g).area
 assert 200000<area<3000000,area
 p={'municipality':'Mezőberény','name':'Városközpont','method':'map_or_text_estimate','estimated':True,'lowConfidence':True,'qualityScore':35,'semanticFootprint':False,'pointRadiusFallback':False,'candidateBoundaryKind':'neighbourhood','sourceUrl':definition['definitionSource']['url'],'source':{'provider':'municipal-planning-street-description-interpreted-on-actual-osm-road-network','path':'data/neighborhoods/expansion-20261115-round3/mezobereny','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','pbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'},'nameEvidence':read('baseline-target.json')['pointCandidates'],'constructionEvidence':{'definition':'boundary-definition.json','routeAudit':'boundary-route-audit.json','actualRoads':'source-roads.geojson','historicalDefinitionYear':2010,'laterContextYear':2021,'streetLegCount':len(legs),'allEdgesActualSourceRoadSegments':True,'connectorMetres':round(sum(a['connectorMetres'] for a in audit),2)},'approximateAreaSquareMetres':round(area,1),'approximationNote':'Whole municipal Városközpont street circuit from the 2010 plan, retained as relevant context in the 2021 study; reconstructed on 2026 archived actual road geometry. Street-name changes, roundabout/short local-road links and road centerline versus parcel-side extent are approximate. This is a full district estimate, not a building/one-block footprint or an official current cadastral survey.'}
 feature={'type':'Feature','id':'round3:mezobereny:varoskozpont','properties':p,'geometry':mapping(g)}
 write('features.geojson',{'type':'FeatureCollection','features':[feature]})
 write('boundary-route.geojson',{'type':'FeatureCollection','features':[{'type':'Feature','properties':{'description':'Actual source-road-node sequence of the municipal boundary circuit'},'geometry':mapping(LineString(ring))}]})
 write('boundary-route-audit.json',{'legs':audit,'rawRingValid':raw.is_valid,'finalGeometryValid':g.is_valid,'sourceSidePrecisionReproduced':False})
 write('summary.json',{'status':'frozen_completed_packet','featureCount':1,'municipality':'Mezőberény','targetName':'Városközpont','unresolvedCount':0,'estimatedCount':1,'lowConfidenceCount':1,'circleCount':0,'areaSquareMetres':round(area,1),'actualRoadCircuitMetres':round(transform(F,LineString(ring)).length,1),'sourceDescriptionLegs':len(legs),'connectorMetres':round(sum(a['connectorMetres'] for a in audit),2),'sourceLabelCovered':g.covers(point),'allValid':g.is_valid,'completeNationalCoverage':False})
 write('unresolved.json',[])
 print(json.dumps(read('summary.json'),ensure_ascii=False))
if __name__=='__main__':main()
