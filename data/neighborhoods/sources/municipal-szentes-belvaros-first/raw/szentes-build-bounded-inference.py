"""Create two explicitly estimated review candidates from a cited circuit and finite actual OSM road alternatives.

No source boundary contour has been observed. All chosen coordinate segments are
literal current OSM road/waterway segments, split only at actual intersections.
"""
import json,heapq,math,hashlib,itertools
from pathlib import Path
from shapely.geometry import shape,LineString,mapping,Polygon,Point
from shapely.ops import transform,unary_union,polygonize
from pyproj import Transformer
from PIL import Image,ImageDraw,ImageFont
OUT=Path(__file__).resolve().parent
F=json.loads((OUT/'szentes-local-lines.geojson').read_text())['features']
T=Transformer.from_crs(4326,23700,always_xy=True).transform
U=Transformer.from_crs(23700,4326,always_xy=True).transform
S={f['properties']['source']['osmId']:f for f in F}
G={};XY={};SRC={}
for f in F:
 p=f['properties'];s=p['source'];tags=s['tags']
 if 'highway' not in tags:continue
 cs=f['geometry']['coordinates'];refs=s['nodeRefs']
 for ref,c in zip(refs,cs):XY[ref]=c
 for i,(a,b) in enumerate(zip(refs,refs[1:])):
  x1,y1=T(*cs[i]);x2,y2=T(*cs[i+1]);length=math.hypot(x2-x1,y2-y1)
  edge=(s['osmId'],i);SRC[edge]={'a':a,'b':b,'coordinates':cs[i:i+2],'name':p['name'],'lengthM':length,'sourceWayId':s['osmId'],'sourceNodeIndex':i}
  G.setdefault(a,[]).append((b,length,edge));G.setdefault(b,[]).append((a,length,edge))
def name_nodes(name):return {r for f in F if f['properties']['name']==name for r in f['properties']['source']['nodeRefs']}
def shortest(starts,ends,excluded_names=(),main_roads_only=False):
 q=[(0,n)for n in starts];heapq.heapify(q);dist={n:0 for n in starts};prev={}
 while q:
  cost,n=heapq.heappop(q)
  if cost!=dist[n]:continue
  if n in ends:
   edges=[];end=n
   while n in prev:
    before,e=prev[n];edges.append(e);n=before
   edges.reverse();return edges,dist[end]
  for v,l,e in G.get(n,[]):
   if SRC[e]['name']in excluded_names:continue
   if main_roads_only and (S[e[0]]['properties']['source']['tags'].get('highway')in ['footway','path','cycleway','steps']or S[e[0]]['properties']['source']['tags'].get('service')=='parking_aisle'):continue
   alt=cost+l
   if alt<dist.get(v,math.inf):dist[v]=alt;prev[v]=(n,e);heapq.heappush(q,(alt,v))
 raise ValueError('No observed road path')
# The source river/street junctions do not meet in present OSM. These finite
# alternatives take current paths to actual physical bridge/river crossings.
upper,ul=shortest(name_nodes('Arany János utca'),set(S[178546767]['properties']['source']['nodeRefs']))
lower,ll=shortest(name_nodes('Szent Anna utca'),set(S[370667751]['properties']['source']['nodeRefs']))
inner1,il1=shortest(name_nodes('Attila út'),name_nodes('Koszta József utca'))
inner2,il2=shortest(name_nodes('Szilfa utca'),name_nodes('Vásárhelyi út'))
villogo,vl=shortest(set(S[68081946]['properties']['source']['nodeRefs']),set(S[327694529]['properties']['source']['nodeRefs']))
direct,dl=shortest(name_nodes('Apponyi tér'),name_nodes('Baross utca'))
app_ends=S[149888202]['properties']['source']['nodeRefs']
around,al=shortest({app_ends[0]},name_nodes('Baross utca'),excluded_names=('Deák Ferenc utca','Apponyi tér'),main_roads_only=True)
names={'Arany János utca','Bajcsy-Zsilinszky utca','Deák Ferenc utca','Baross utca','Kolozsvár utca','Attila út','Koszta József utca','Zrínyi utca','Villogó utca','Somogyi Béla utca','Szilfa utca','Vásárhelyi út','Nyíri köz','Kisér utca','Szent Anna utca'}
base={e for e,s in SRC.items()if s['name']in names and S[e[0]]['properties']['source']['tags'].get('highway')not in ['footway','cycleway','path','steps']}
base.update(upper+lower+inner1+inner2+villogo)
for w in (178546767,370667751):base.update(e for e in SRC if e[0]==w)
river=S[591675710];river_native=shape(river['geometry']);river_eov=transform(T,river_native)
outputs=[];polys=[]
def save_candidate(key,edges,description):
 lines=[LineString(SRC[e]['coordinates'])for e in sorted(edges)]+[river_native]
 graph=unary_union(lines);faces=sorted(polygonize(graph),key=lambda p:p.area,reverse=True)
 if not faces:raise ValueError('No polygon from actual lines')
 expected_names=names
 matches=[]
 if len(faces)>12:raise ValueError('Unexpected unconstrained face count')
 for count in range(1,len(faces)+1):
  for subset in itertools.combinations(faces,count):
   face=unary_union(subset)
   if face.geom_type!='Polygon' or len(face.interiors):continue
   hit_names={SRC[e]['name'] for e in edges if LineString(SRC[e]['coordinates']).intersection(face.boundary).length>1e-10}
   if expected_names<=hit_names and transform(T,river_native.intersection(face.boundary)).length>200:matches.append(face)
 if not matches:raise ValueError(f'No entire circuit face union; all face areas {[f.area for f in faces]}')
 p_native=min(matches,key=lambda x:x.area);p=transform(T,p_native)
 # Boundary cannot silently contain fabricated repair/closure edges.
 unaccounted=transform(T,p_native.boundary.difference(graph)).length
 assert unaccounted<1e-6 and p.is_valid
 boundary_edges=[]
 for e in sorted(edges):
  native=LineString(SRC[e]['coordinates']);l=transform(T,native);covered=transform(T,native.intersection(p_native.boundary)).length
  if covered>1e-6:boundary_edges.append({**SRC[e],'overlapOnBoundaryM':covered,'fullSourceEdgeUsed':abs(covered-l.length)<1e-5})
 river_overlap=transform(T,river_native.intersection(p_native.boundary)).length
 ring=mapping(p_native)
 feature={'type':'Feature','id':f'inferred:szentes:belvaros:source-circuit:{key}','properties':{
 'name':'Belváros','municipality':'Szentes','geometryStatus':'inferred','confidence':'low','sourceContourIsObserved':False,
 'sourceBoundaryEra':'Older municipal IVS (2015 reupload of 2009/2010-era material); present OSM road/path/river centerlines',
 'sourceUrl':'https://szentes.hu/wp-content/uploads/2015/01/szentes_ivs.pdf','sourceLocator':'Section IV.1, printed pages 147-148, Belváros street/river list',
 'construction':description,'candidateOnly':True,'approvedForRegistry':False,'usableForAddressAssignment':False,
 'accuracyMeters':None,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors; municipal street/river boundary facts'},'geometry':ring}
 path=OUT/f'szentes-belvaros-{key}-inferred-review.geojson';path.write_text(json.dumps({'type':'FeatureCollection','features':[feature]},ensure_ascii=False,indent=2)+'\n')
 proof={'key':key,'description':description,'areaM2':p.area,'perimeterM':p.length,'vertices':len(p.exterior.coords),'valid':p.is_valid,'polygonFaces':len(faces),'largestFaceAreasM2':[transform(T,x).area for x in faces[:8]],'boundaryOutsideSelectedActualLineGraphM':unaccounted,'selectedEdgeCount':len(edges),'boundaryRoadEdges':boundary_edges,'sourceRiverWayId':591675710,'riverOverlapOnBoundaryM':river_overlap,'sourceContourIsObserved':False,'usableForAddressAssignment':False,'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
 outputs.append(proof);polys.append(p)
 return p
A=save_candidate('deak-side',base,'The Apponyi tér place reference is interpreted as the square edge along the continuing named Deák road; actual Nagyvölgy sor and Lajos tér bridge the two inner gaps; actual current paths reach Munkácsy pedestrian bridge and Eszperantó bridge for the two river closures. These source-unspecified choices are estimated, not observed boundaries.')
B_edges=(base-set(direct))|set(around)|{e for e in SRC if e[0]==149888202}
B=save_candidate('apponyi-around',B_edges,'Alternative Apponyi traversal includes its actual named road, then the shortest existing public Rákóczi/Kossuth/Attila road connection to Baross, excluding the direct Deák side of the square. Other source-unspecified choices equal the deak-side candidate.')
# A finite nearby alternative for each source-unspecified segment is disclosed,
# rather than claiming an absolute error bound or historical accuracy.
proof={'schemaVersion':1,'method':'Native WGS84 literal OSM segment graph plus exact geometric road/river intersections; EPSG23700 used only for length/area and preview; polygonize existing edges; enumerate finite contiguous face unions and choose minimum-area union whose boundary contains every cited named road and the river. No buffer, circle, bounding box, synthetic connector, straight endpoint closure, repair or snapping.',
 'sourceContourIsObserved':False,'sourcePbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','sourceLinesSha256':hashlib.sha256((OUT/'szentes-local-lines.geojson').read_bytes()).hexdigest(),
 'assumptions':[
 {'id':'villogo-internal-stagger','sourceRole':'Continuity within source-named Villogó utca','chosenExistingRoadPathLengthM':vl,'chosenPathEdges':[SRC[e]for e in villogo],'qualification':'The contemporary named Villogó road is split by a stagger across Mátyás király utca. Existing road graph connector only; source does not explicitly name the intermediary modern segment.'},
 {'id':'river-arany','sourceRole':'Arany János to Kurca','chosenExistingRoadPathLengthM':ul,'chosenPathEdges':[SRC[e]for e in upper],'chosenPhysicalBridgeWayId':178546767,'qualification':'Source does not choose this southward river-adjacent path or current bridge. It is the shortest observed highway path to this nearby physical crossing. The direct text junction is absent from OSM by 37.54 m. This is a low-confidence local detour.'},
 {'id':'apponyi-square','sourceRole':'Deák–Apponyi tér–Baross','directSideLengthM':dl,'directSideEdges':[SRC[e]for e in direct],'aroundSquareLengthM':al,'aroundSquareEdges':[SRC[e]for e in around],'aroundSquareSearchExcludes':'Footways, paths, cycleways, steps and parking aisles excluded from this road alternative','qualification':'Two finite existing perimeter routes are tested. The source square reference does not determine which road traversal is intended. Neither is called observed.'},
 {'id':'attila-cadastral4697','sourceRole':'Attila–4697 cadastral road–Koszta','chosenExistingRoadPathLengthM':il1,'chosenPathEdges':[SRC[e]for e in inner1],'qualification':'The only shortest actual direct road connector is currently Nagyvölgy sor. Asset annex labels 4697 at Attila, without proving parcel-to-OSM identity. Current road geometry is a bounded inferred continuation, not a cadastral match.'},
 {'id':'szilfa-square','sourceRole':'Szilfa–Vásárhelyi','chosenExistingRoadPathLengthM':il2,'chosenPathEdges':[SRC[e]for e in inner2],'qualification':'Actual Lajos tér road joins the cited roads over about 70 m. Source does not explicitly name this intermediary square edge.'},
 {'id':'river-szentanna-cadastral5631','sourceRole':'Szent Anna–5631 cadastral road–Kurca','chosenExistingRoadPathLengthM':ll,'chosenPathEdges':[SRC[e]for e in lower],'chosenPhysicalBridgeWayId':370667751,'qualification':'The cadastral identity is unverified. Chosen current river-adjacent road/path closure to Eszperantó bridge is an explicit alternative, not a documentary match for 5631. The source-named street remains about 79.20 m from current Kurca centerline.'}],
 'alternatives':{'appOnyiCandidatesSymmetricDifferenceM2':A.symmetric_difference(B).area,'deakSideAreaM2':A.area,'aroundSquareAreaM2':B.area,'areaDeltaM2':B.area-A.area,'finiteAlternativeComparisonIsNotAbsoluteAccuracyBound':True},'candidates':outputs,'registryRecommendation':'Review candidates only. Independent source-map/cadastral review is still needed; if retained anywhere, only low-confidence inferred layer with all six assumptions and historical/current mismatch.', 'usableForAddressAssignment':False}
(OUT/'szentes-bounded-inference-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
# Diagnostic preview of the current source graph and both boundary alternatives.
bounds=unary_union(polys).bounds;scale=min(1000/(bounds[2]-bounds[0]),900/(bounds[3]-bounds[1]));W,H=1200,1120
img=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(img)
def px(c):return (90+(c[0]-bounds[0])*scale,130+(bounds[3]-c[1])*scale)
for f in F:
 l=transform(T,shape(f['geometry']))
 if l.intersects(unary_union(polys).envelope):
  d.line([px(c)for c in l.coords],fill='#d9dddf',width=1)
for idx,p in enumerate(polys):
 d.line([px(c)for c in p.exterior.coords],fill=['#005f9e','#d64016'][idx],width=[6,3][idx])
for n in names|{'Apponyi tér','Rákóczi Ferenc utca','Lajos tér','Nagyvölgy sor'}:
 ls=[transform(T,shape(f['geometry']))for f in F if f['properties']['name']==n]
 if not ls:continue
 l=unary_union(ls);q=l.representative_point();x,y=px((q.x,q.y))
 if 50<x<1150 and 100<y<1050:d.text((x,y),n,fill='#222222')
d.text((35,20),'Szentes Belvaros: LOW-CONFIDENCE inferred review alternatives',fill='black')
d.text((35,43),'Blue: Deak square side; orange: Apponyi/Rakoczi/Kossuth square perimeter.',fill='black')
d.text((35,66),'Current OSM lines only. Source boundary contour NOT observed. All six junction assumptions in proof JSON.',fill='black')
d.text((35,1090),'No address assignment. Not official/historical geometry. No synthetic connectors.',fill='black')
img.save(OUT/'szentes-belvaros-bounded-alternatives-preview.png')
print(json.dumps({'candidates':[{'key':x['key'],'areaM2':x['areaM2'],'vertices':x['vertices'],'faces':x['polygonFaces']}for x in outputs],'alternatives':proof['alternatives'],'upperClosureLengthM':ul,'lowerClosureLengthM':ll},ensure_ascii=False))
