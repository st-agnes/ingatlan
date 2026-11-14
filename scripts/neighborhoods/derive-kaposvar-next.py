#!/usr/bin/env python3
"""Offline Kaposvár street/rail source acquisition and explicitly reviewed boundary construction."""
import argparse,hashlib,json,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/neighborhoods/sources/municipal-kaposvar-next'
PBF=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
BBOX=(17.76,46.34,17.83,46.385)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def extract():
 import osmium
 OUT.mkdir(parents=True,exist_ok=True);features=[];stats={'filteredWays':0,'selectedWays':0};xmin,ymin,xmax,ymax=BBOX;t0=time.monotonic()
 class Collector(osmium.SimpleHandler):
  def way(self,obj):
   stats['filteredWays']+=1
   if not any(n.location.valid() and xmin<=n.lon<=xmax and ymin<=n.lat<=ymax for n in obj.nodes):return
   tags=dict(obj.tags)
   features.append({'type':'Feature','id':f'osm:way:{obj.id}','properties':{'name':tags.get('name:hu',tags.get('name','')),'source':{'provider':'openstreetmap','osmType':'way','osmId':obj.id,'url':f'https://www.openstreetmap.org/way/{obj.id}','tags':tags,'nodeRefs':[n.ref for n in obj.nodes],'objectVersion':obj.version,'objectTimestamp':str(obj.timestamp),'geometryUnmodified':True,'geometryProcessing':'Actual complete source way node sequence; bbox is acquisition only.','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}},'geometry':{'type':'LineString','coordinates':[[n.lon,n.lat] for n in obj.nodes]}});stats['selectedWays']+=1
 with tempfile.TemporaryDirectory(prefix='kaposvar-node-locations-') as temp:
  Collector().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(temp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway')])
 path=OUT/'all-local-roads-rails.geojson';write(path,{'type':'FeatureCollection','features':features})
 write(OUT/'extraction-proof.json',{'schemaVersion':1,'sourcePbfSha256':sha(PBF),'bboxAcquisitionOnly':BBOX,'statistics':stats,'outputSha256':sha(path),'nativeFilter':'KeyFilter(highway,railway) after actual node location cache','includesUnnamedWays':True,'elapsedSeconds':round(time.monotonic()-t0,3)})
 print(json.dumps(stats))

# Audit is intentionally separate from polygon admission: a boundary description
# does not authorize connecting today's disconnected or renamed road corridors.
def audit():
 from shapely.geometry import shape
 from shapely.ops import unary_union,nearest_points,polygonize
 from pyproj import Geod
 features=json.loads((OUT/'all-local-roads-rails.geojson').read_text())['features'];geod=Geod(ellps='WGS84')
 excluded={'steps','footway','path','cycleway','corridor','platform','pedestrian','service','proposed','construction'}
 chains=[{'id':'ivs-2009','sourceUrl':'https://kph.kaposvar.hu/eloterjesztesek/et20090226/doku/e28m01.pdf','printedPage':27,
  'names':['Áchim András utca','Petőfi Sándor tér','Budai Nagy Antal utca','Baross Gábor utca','Hársfa utca','Virág utca','48-as ifjúság útja','rail41']},
 {'id':'law-2026','sourceUrl':'https://kph.kaposvar.hu/authorized/laws/2005_70.pdf','printedPage':2,
  'names':['Áchim András utca','rail36','Kanizsai utca','Füredi út','48-as ifjúság útja','Virág utca','Hársfa utca','Baross Gábor utca','Budai Nagy Antal utca']}]
 results=[]
 for case in chains:
  groups={}
  for name in case['names']:
   if name.startswith('rail'):
    refs=[f for f in features if f['properties']['source']['tags'].get('railway')=='rail' and f['properties']['source']['tags'].get('ref')==name[4:]]
   else:refs=[f for f in features if f['properties']['name']==name and f['properties']['source']['tags'].get('highway') not in excluded and f['properties']['source']['tags'].get('area')!='yes']
   groups[name]=unary_union([shape(f['geometry']) for f in refs])
  pairs=[]
  for a,b in zip(case['names'],case['names'][1:]+case['names'][:1]):
   p,q=nearest_points(groups[a],groups[b]);pairs.append({'from':a,'to':b,'minimumGeodesicGapM':geod.inv(p.x,p.y,q.x,q.y)[2],'nearestSourcePoints':[list(p.coords[0]),list(q.coords[0])],'diagnosticOnly':True})
  cells=list(polygonize(unary_union(list(groups.values()))));complete=[p for p in cells if all(p.boundary.intersection(g).length>1e-10 for g in groups.values())]
  results.append({**case,'rawSourcePdfAcquired':False,'rawSourcePdfSha256':None,'sourceEvidenceMethod':'Public web search extraction of official municipal PDF factual street names; no raw PDF body was downloaded.','adjacentFeatureGaps':pairs,'closedLiteralSourceCircuits':len(complete)})
 write(OUT/'boundary-obstacles.json',{'schemaVersion':1,'municipality':'Kaposvár','name':'Belváros','status':'not_admitted_unresolved_source_corridors','actualNewQuarterPolygons':0,'roadInput':{'path':str((OUT/'all-local-roads-rails.geojson').relative_to(ROOT)),'sha256':sha(OUT/'all-local-roads-rails.geojson')},'cases':results,
  'notes':['The2009 and2026 western limits are different source descriptions; do not silently substitute the Fonyód railway for the2009 Gyékényes wording.','Current Újpiac tér lies between Áchim András utca and Petőfi Sándor tér/Budai Nagy Antal utca. It was already an official name in2007, so a rename is not established.','The2023 FVS explicitly includes Árpád utca between Virág and48-as; this resolves one abbreviated northern name transition but does not close all remaining source gaps.','A source map must resolve all remaining corridors, rail/road crossings and divided-road junction choices before a quarter polygon can be admitted.','The raw2009 PDF is14,880,108bytes and the2008 municipal chapter20,264,583bytes; the available web reader rejected them for content size. No permission or shell network request was attempted.','Exploratory full-road polygonization produced no circuit containing every literal named component. No inferred closing edges, buffers or invented polygons were exported.'],
  'sourceUrls':['https://kph.kaposvar.hu/data/adattar/fvs21-27/fvs21-27.pdf','https://net.jogtar.hu/rendelet?council=kaposvar&dbnum=529&docid=A0700058.KAP','https://kph.kaposvar.hu/eloterjesztesek/et20080416/doku/e1vb3.pdf'],
  'usableForAddressAssignment':False})
 print(json.dumps({'admittedQuarterPolygons':0,'cases':[(r['id'],r['closedLiteralSourceCircuits']) for r in results]}))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--extract',action='store_true');parser.add_argument('--audit',action='store_true');args=parser.parse_args()
 if args.extract:extract()
 if args.audit:audit()
