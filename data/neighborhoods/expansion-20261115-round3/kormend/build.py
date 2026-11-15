#!/usr/bin/env python3
import json,heapq,math,hashlib,runpy
from pathlib import Path
from shapely.geometry import shape,Point,Polygon,mapping
from shapely.ops import unary_union,nearest_points,substring
from pyproj import Geod
P=Path(__file__).resolve().parent
runpy.run_path(str(P/'build-quarter-estimates.py'),run_name='__main__')
URL='https://www.kormend.hu/Hirek/2021_evi_hulladekszallitassal_kapcsolatos_tajekoztato.html';GEOD=Geod(ellps='WGS84')
ways=json.load(open(P/'source-ways.geojson'))['features'];city=shape(json.load(open(P/'municipality.geojson'))['features'][0]['geometry'])
def length(a,b):return abs(GEOD.inv(*a,*b)[2])
def select(name):return [f for f in ways if f['properties']['name']==name and shape(f['geometry']).intersects(city)]
def trace(name,start,end):
 fs=select(name);nodes={};graph={}
 for f in fs:
  ids=f['properties']['source']['nodeRefs'];cs=f['geometry']['coordinates'];wid=f['properties']['source']['osmId']
  for n,c in zip(ids,cs):nodes[n]=tuple(c)
  for a,b in zip(ids,ids[1:]):
   d=length(nodes[a],nodes[b]);graph.setdefault(a,[]).append((b,d,wid));graph.setdefault(b,[]).append((a,d,wid))
 a=min(nodes,key=lambda n:length(nodes[n],start));b=min(nodes,key=lambda n:length(nodes[n],end));best={a:0};back={};queue=[(0,a)]
 while queue:
  cost,n=heapq.heappop(queue)
  if cost!=best.get(n):continue
  if n==b:break
  for nxt,d,wid in graph.get(n,[]):
   if cost+d<best.get(nxt,math.inf):best[nxt]=cost+d;back[nxt]=(n,wid);heapq.heappush(queue,(cost+d,nxt))
 if b not in best:raise ValueError('Disconnected named source road '+name)
 path=[b];used=[]
 while path[-1]!=a:n,wid=back[path[-1]];used.append(wid);path.append(n)
 path.reverse();return [nodes[n] for n in path],dict(road=name,nodeIds=path,sourceWayIds=sorted(set(used)),sourceLengthM=round(best[b],2),startSnapM=round(length(start,nodes[a]),2),endSnapM=round(length(end,nodes[b]),2))
rr=unary_union([shape(f['geometry']) for f in select('Rákóczi utca')]);m=unary_union([shape(f['geometry']) for f in select('Munkácsy Mihály utca')]);s=unary_union([shape(f['geometry']) for f in select('Sport utca')]);river=unary_union([shape(f['geometry']) for f in select('Rába')])
west=tuple(nearest_points(rr,m)[0].coords[0]);eastjoint=tuple(nearest_points(rr,s)[0].coords[0]);sportend=max([tuple(c) for f in select('Sport utca') for c in f['geometry']['coordinates']],key=lambda c:c[0])
north,northproof=trace('Rákóczi utca',west,eastjoint);sport,sportproof=trace('Sport utca',eastjoint,sportend)
riverwest=nearest_points(river,Point(west))[0];rivereast=nearest_points(river,Point(sportend))[0]
riverpart=substring(river,river.project(rivereast),river.project(riverwest));rivercoords=[tuple(c) for c in riverpart.coords]
coords=north+sport[1:]+[tuple(rivereast.coords[0])]+rivercoords[1:]+[west];poly=Polygon(coords)
if not poly.is_valid:raise ValueError('Invalid whole-centre interpretation')
properties=dict(name='Belváros',municipality='Körmend',estimated=True,lowConfidence=True,confidence='low',method='Whole city-centre interpretation of the municipal Rákóczi-utca-to-Rába description: original named Rákóczi/Sport street-node paths and Rába river arc, with two explicit inferred outer side closures.',sourceUrl=URL,supportingUrls=['https://www.openstreetmap.org/way/38415576'],approximationNote='The municipal notice explicitly calls the streets south of Rákóczi utca (to Kauz rét) and north of the Rába Belváros. This estimates the whole central quarter, including its residential streets, historic core and castle/park side, rather than using only the castle footprint. The western Munkácsy-side continuation and eastern Sport/Kauz-side continuation to the river are inferred straight outer-edge closures; street sides, floodplain edge and quarter extremities remain low confidence.',sourcePeriod='Municipal 2021 spatial description; OSM2026-11-12 geometry',boundaryKind='neighbourhood',partialFootprint=False,usableForAddressAssignment=False,areaM2=round(abs(GEOD.geometry_area_perimeter(poly)[0])),license='ODbL-1.0',attribution='Körmend municipal spatial facts; © OpenStreetMap contributors')
features=[dict(type='Feature',id='estimated:kormend:belvaros:municipal-rakoczi-raba',properties=properties,geometry=mapping(poly))]
extra=P/'quarter-estimates.geojson'
if extra.exists():features+=json.load(open(extra))['features']
(P/'features.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features),ensure_ascii=False,indent=2)+'\n')
proof=dict(schemaVersion=1,municipalSource=URL,sourceRiverWayIds=[f['id'] for f in select('Rába')],northBoundary=northproof,sportSide=sportproof,inferredSideClosures=[dict(fromCoordinate=sportend,toCoordinate=list(rivereast.coords[0]),lengthM=round(length(sportend,rivereast.coords[0]),2),reason='Estimate of eastern Sport/Kauz quarter extremity to river'),dict(fromCoordinate=list(riverwest.coords[0]),toCoordinate=west,lengthM=round(length(riverwest.coords[0],west),2),reason='Estimate of western centre extremity toward Munkácsy junction')],pointBuffersCreated=0,allValid=all(shape(f['geometry']).is_valid for f in features),belvarosNativeRoadRiverVerticesPreserved=True,quarterEnvelopeProof='quarter-build-proof.json',inputsSha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ['source-ways.geojson','source-areas.geojson','source-named-points.geojson','municipality.geojson','municipal-quarter-facts.json','quarter-recipes.json']})
(P/'build-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print('Generated',len(features),'valid quarters; Belváros',properties['areaM2'],'m²; inferred closures',[(c['lengthM']) for c in proof['inferredSideClosures']])
