import json,heapq,math
from pathlib import Path
from shapely.geometry import shape,Polygon,LineString,Point,mapping
from shapely.ops import unary_union,nearest_points,polygonize
from pyproj import Geod
P=Path(__file__).parent; GEOD=Geod(ellps='WGS84');city=shape(json.load(open(P/'municipality.geojson'))['features'][0]['geometry'])
ways=[f for f in json.load(open(P/'source-ways.geojson'))['features'] if f['properties']['source']['tags'].get('highway') and shape(f['geometry']).intersects(city.buffer(.001))]
coords={};graph={};named={}
def dist(a,b):return math.hypot((a[0]-b[0])*77000,(a[1]-b[1])*111000)
for f in ways:
 p=f['properties'];s=p['source'];ids=s['nodeRefs'];cs=f['geometry']['coordinates']; names={p['name'],s['tags'].get('old_name','')}
 for n in names:
  if n:named.setdefault(n,[]).append(f)
 for i,c in zip(ids,cs):coords[i]=tuple(c)
 for a,b in zip(ids,ids[1:]):
  edge=(b,dist(coords[a],coords[b]),s['osmId'],names);graph.setdefault(a,[]).append(edge);graph.setdefault(b,[]).append((a,edge[1],edge[2],names))
outer=['Erzsébet utca','Rákóczi utca','Teleki utca','Kesztyű utca','Köztársaság utca','Vörösmarty utca','Tóth Ede utca','Kölcsey utca','Kazinczy sor','Mikszáth Kálmán utca','Népköztársaság útja','Kórház utca','Kandó Kálmán utca','Berzsenyi utca','Dózsa György utca','Kossuth Lajos utca','Szabadság utca']
inner=['Szepessi utca','Széchenyi István utca','Ady Endre utca','Népköztársaság útja','Vörösmarty utca','Bajcsy-Zsilinszky utca','Jókai utca']
def circuit(names):
 groups=[named[n] for n in names]; geoms=[unary_union([shape(f['geometry']) for f in g]) for g in groups]; nodes=[set(n for f in g for n in f['properties']['source']['nodeRefs']) for g in groups]
 joints=[]
 for i in range(len(names)):
  a,b=nearest_points(geoms[i],geoms[(i+1)%len(names)]);ia=min(nodes[i],key=lambda n:dist(coords[n],a.coords[0]));ib=min(nodes[(i+1)%len(names)],key=lambda n:dist(coords[n],b.coords[0]));joints.append((ia,ib))
 def route(start,end,label=None):
  best={start:0};back={};queue=[(0,start)]
  while queue:
   cost,node=heapq.heappop(queue)
   if cost!=best.get(node):continue
   if node==end:break
   for nxt,length,wid,nameset in graph.get(node,[]):
    new=cost+length*(1 if label is None or label in nameset else 50)
    if new<best.get(nxt,math.inf):best[nxt]=new;back[nxt]=(node,wid,length,label not in nameset if label else False);heapq.heappush(queue,(new,nxt))
  if end not in best:return [start,end],dict(inferredDirectConnectorM=dist(coords[start],coords[end]))
  path=[end];ws=[];inferred=0
  while path[-1]!=start:
   prev,wid,length,off=back[path[-1]];ws.append(wid);inferred+=length if off else 0;path.append(prev)
  path.reverse();return path,dict(sourceWayIds=sorted(set(ws)),offNamedRoadLengthM=round(inferred,1))
 allnodes=[];proof=[]
 for i,label in enumerate(names):
  start=joints[i-1][1];end=joints[i][0];path,note=route(start,end,label);allnodes+=(path if not allnodes else path[1:]);proof.append(dict(road=label,**note))
  bridge,note=route(end,joints[i][1]);allnodes+=bridge[1:]
  if len(bridge)>1:proof.append(dict(junctionConnector=True,**note))
 if allnodes[-1]!=allnodes[0]:raise ValueError('open')
 ring=LineString([coords[n] for n in allnodes]);poly=Polygon(ring)
 if not poly.is_valid:
  faces=list(polygonize(unary_union(ring)));poly=max(faces,key=lambda p:p.area)
 return poly,proof
op,proofO=circuit(outer);ip,proofI=circuit(inner);poly=op.difference(ip)
if not poly.is_valid:raise ValueError('Invalid result')
url='https://www.dombovar.hu/media/files/Dombovar_helyzetertekeles_0804.pdf'
f=dict(type='Feature',id='estimated:west-planning:Dombóvár:inner-surroundings',properties=dict(name='Egyéb, belvárost övező városi területek',municipality='Dombóvár',estimated=True,lowConfidence=True,confidence='low',method='Historical KSH/municipal outer and inner street circuits interpreted on the archived current OSM road network; named-road routes preferred, actual junction connectors retained; the Belváros inner circuit is excluded.',sourceUrl=url,supportingUrls=['https://www.openstreetmap.org/copyright'],approximationNote='Full source-defined surrounding inner-city unit, not an unlocated label or an action area. Historical Népköztársaság útja is resolved by explicit OSM old_name tags to Pannónia/Park streets. Current-road junction and continuation choices are inferred where the documentary circuit is not directly closed; low-confidence search area, not legal boundary.',sourcePeriod='2015 municipal/KSH quarter description; OSM2026-11-12',sourceDocuments=[dict(url=url,section='3.3.1.2 Egyéb, belvárost övező városi területek')],boundaryKind='neighbourhood',usableForAddressAssignment=False,areaM2=round(abs(GEOD.geometry_area_perimeter(poly)[0])),license='ODbL-1.0',attribution='Dombóvár municipal assessment; © OpenStreetMap contributors'),geometry=mapping(poly))
(P/'additional-features.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=[f]),ensure_ascii=False,indent=2)+'\n');(P/'circuit-proof.json').write_text(json.dumps(dict(outerRoads=outer,innerRoads=inner,outerProof=proofO,innerProof=proofI,outerAreaM2=round(abs(GEOD.geometry_area_perimeter(op)[0])),innerAreaM2=round(abs(GEOD.geometry_area_perimeter(ip)[0]))),ensure_ascii=False,indent=2)+'\n');print('area',f['properties']['areaM2'],'outer',op.area,'inner',ip.area,'bounds',poly.bounds)
