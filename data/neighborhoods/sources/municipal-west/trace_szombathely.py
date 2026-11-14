"""Reproduce manually reviewed municipal street circuits from real OSM geometry.
No artificial connector lines: junctions and source roads are traced through the input network.
"""
import json,heapq,math,hashlib
from pathlib import Path
from shapely.geometry import shape,Polygon,Point,LineString,box,mapping
from shapely.ops import unary_union,nearest_points
from shapely.strtree import STRtree
from pyproj import Geod
BASE=Path(__file__).resolve().parents[4]
OUTPUT=Path(__file__).resolve().parent
INPUT=BASE/'.local/neighborhoods/country/construction-lines.geojson'
DOC=BASE/'.local/neighborhoods/nationwide-docs/originals/szombathely-ivs.pdf'
URL='https://kbr.szombathely.hu/kbrfile/46469.pdf'
SPECS=[dict(name='Belváros',roads=['Zrínyi Ilona utca','Hunyadi János út','Szent Márton utca','Vörösmarty Mihály utca','Szelestey László utca','Petőfi Sándor utca','Sörház utca','Hollán Ernő utca','Kiskar utca','Mátyás király út'],bbox=[16.61,47.224,16.632,47.241])]
PENDING_SPECS=[dict(name='Derkovits lakótelep',roads=['Paragvári utca','Szűrcsapó utca','Bolyai János utca','Bartók Béla körút','Perintparti sétány','Váci Mihály utca'],bbox=[16.598,47.233,16.616,47.247])]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def length(a,b):return math.hypot((a[0]-b[0])*75500,(a[1]-b[1])*111000)
def make(spec,features):
 names=spec['roads'];extent=box(*spec['bbox']);lines=[];props=[]
 for f in features:
  p=f['properties'];t=p['source']['tags'];kind=t.get('highway');n=p['name'];g=shape(f['geometry'])
  if not kind or kind in ['proposed','construction']:continue
  if not g.intersects(extent):continue
  lines.append(g);props.append(p)
 tree=STRtree(lines);network=unary_union(lines);adj={}
 for line in network.geoms:
  cs=list(line.coords)
  for aa,bb in zip(cs,cs[1:]):
   a=tuple(aa);b=tuple(bb);mid=Point((a[0]+b[0])/2,(a[1]+b[1])/2);ix=int(tree.nearest(mid));sid=props[ix]['source']['osmId'];dist=length(a,b)
   if dist:adj.setdefault(a,[]).append((b,dist,ix));adj.setdefault(b,[]).append((a,dist,ix))
 byname={n:unary_union([g for g,p in zip(lines,props) if p['name']==n]) for n in names}
 # Junctions are existing vertices in the noded source line network.
 nodes=list(adj)
 def nearest_node(pt,name):
  allowed=[a for a in nodes if any(props[i]['name']==name for _,_,i in adj[a])]
  return min(allowed,key=lambda a:length(a,tuple(pt.coords[0])))
 junctions=[]
 for a,b in zip(names,names[1:]+names[:1]):
  p,q=nearest_points(byname[a],byname[b]);junctions.append((nearest_node(p,a),nearest_node(q,b)))
 def path(start,end,allowed):
  best={start:0};back={};todo=[(0,start)]
  while todo:
   d,a=heapq.heappop(todo)
   if d!=best.get(a):continue
   if a==end:break
   for b,dist,ix in adj[a]:
    p=props[ix];factor=1 if p['name'] in allowed else (2 if p['source']['tags'].get('junction')=='roundabout' else 100)
    nd=d+dist*factor
    if nd<best.get(b,float('inf')):best[b]=nd;back[b]=(a,ix,dist);heapq.heappush(todo,(nd,b))
  if end not in best:raise ValueError('Source network disconnected')
  cs=[end];ids=[];other=[];a=end;metres=0
  while a!=start:
   prev,ix,dist=back[a];p=props[ix];sid=p['source']['osmId'];ids.append(sid);cs.append(prev);metres+=dist
   if p['name'] not in allowed:other.append(dict(sourceLineId='way/'+str(sid),name=p['name'],lengthM=round(dist,3),junction=p['source']['tags'].get('junction')))
   a=prev
  return cs[::-1],dict(sourceLineIds=sorted(set(ids)),vertices=len(cs),lengthM=round(metres,3),otherNamedSegments=other)
 coords=[];proof=[]
 def append(cs,record):
  if coords and coords[-1]!=cs[0]:raise ValueError('Circuit discontinuity')
  coords.extend(cs if not coords else cs[1:]);proof.append(record)
 for i,n in enumerate(names):
  start=junctions[i-1][1];end=junctions[i][0];cs,record=path(start,end,[n]);record['boundaryRoad']=n;append(cs,record)
  a,b=junctions[i]
  if a!=b:
   cs,record=path(a,b,[n,names[(i+1)%len(names)]]);record['junctionBetween']=[n,names[(i+1)%len(names)]]
   if record['lengthM']>120:raise ValueError('Ambiguous source connector exceeds120m: '+str(record))
   append(cs,record)
 polygon=Polygon(coords)
 if not polygon.is_valid or not polygon.exterior.is_closed:raise ValueError('Invalid constructed polygon')
 ids=sorted({sid for s in proof for sid in s['sourceLineIds']});area=abs(Geod(ellps='WGS84').geometry_area_perimeter(polygon)[0])
 extra=[x for s in proof for x in s.get('otherNamedSegments',[])]
 print(spec['name'],len(coords),'vertices',round(area),'m2', 'connectors',extra)
 feature=dict(type='Feature',geometry=mapping(polygon),properties=dict(name=spec['name'],municipality='Szombathely',boundaryKind='neighbourhood',method='Manual official street-circuit interpretation; sourceOSMroads noded at2Dsegmentintersections and traced sequentially, preserving complete source vertices; junction connectors follow real source roads.',evidenceUrls=[URL],sourceDocuments=[dict(url=URL,sha256=sha(DOC),page=150,pdfPageZeroBased=149)],quality='manual-source-trace',reviewNotes=['Roadcentreline construction from2013 municipal boundary facts and2026 OSMgeometry; unsuitable for cadastral or automatic address assignment.','Actual road-junction connectors are separately recorded in traceproof; no artificial chords or buffers.','Derkovits source includes both sides of Váci Mihály utca; this polygon uses roadcentreline and therefore is approximate at that edge.' if spec['name'].startswith('Derkovits') else 'Zrínyi Ilona utca is joined through the actual Batthyány tér roundabout.'],sourceLineIds=['way/'+str(i) for i in ids],usableForAddressAssignment=False,areaM2=area,license='ODbL-1.0',attribution='© OpenStreetMap contributors; official boundary facts: Szombathely MJV IVS annex1,2013-06-06'))
 return feature,dict(name=spec['name'],segments=proof,closed=True,valid=True,areaM2=area)
def main():
 allfeatures=json.loads(INPUT.read_text())['features'];features=[f for f in allfeatures if f['geometry']['type']=='LineString' and 'szombathely' in f['properties'].get('constructionAreaIds',[])]
 output=[];proof=[]
 for spec in SPECS:
  feature,trace=make(spec,features);output.append(feature);proof.append(trace)
 out=OUTPUT/'szombathely-manual.geojson';out.write_text(json.dumps(dict(type='FeatureCollection',features=output),ensure_ascii=False,indent=2)+'\n')
 (OUTPUT/'szombathely-trace-proof.json').write_text(json.dumps(dict(schemaVersion=1,sourceUrl=URL,sourcePdfSha256=sha(DOC),constructionGeometry=dict(path=str(INPUT.relative_to(BASE)),sha256=sha(INPUT)),algorithm='trace_szombathely.py: source network noding, ordered per-road traces and actual junction connectors.',features=proof),ensure_ascii=False,indent=2)+'\n')
 manifest_path=OUTPUT/'manifest.json'
 manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else dict(schemaVersion=1,files=[])
 manifest.update(generatedAt='2026-11-13',license='ODbL-1.0',attribution='© OpenStreetMap contributors')
 manifest['files']=[f for f in manifest.get('files',[]) if f['path']!=out.name]+[dict(path=out.name,sha256=sha(out),features=len(output),methodProof='szombathely-trace-proof.json',reproduce='PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-west/trace_szombathely.py')]
 manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
