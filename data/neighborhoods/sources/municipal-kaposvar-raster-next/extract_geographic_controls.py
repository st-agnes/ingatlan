"""Acquire only literal local PBF roads/rails/place points; no network or geometry."""
import sys,json,hashlib,tempfile,time
from pathlib import Path
sys.dont_write_bytecode=True
import osmium
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
PBF=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
BBOX=(17.73,46.28,17.91,46.46)
ways=[];places=[];count=0;started=time.monotonic()
class Extract(osmium.SimpleHandler):
 def node(self,node):
  tags=dict(node.tags)
  if 'place' not in tags or not node.location.valid() or not(BBOX[0]<=node.lon<=BBOX[2]and BBOX[1]<=node.lat<=BBOX[3]):return
  places.append({'type':'Feature','id':f'osm:node:{node.id}','properties':{'name':tags.get('name',''),'source':{'provider':'openstreetmap','osmType':'node','osmId':node.id,'tags':tags,'objectVersion':node.version,'objectTimestamp':str(node.timestamp),'geometryUnmodified':True,'url':f'https://www.openstreetmap.org/node/{node.id}'}},'geometry':{'type':'Point','coordinates':[node.lon,node.lat]}})
 def way(self,way):
  global count
  tags=dict(way.tags)
  if not('highway'in tags or'railway'in tags):return
  count+=1
  if not any(n.location.valid()and BBOX[0]<=n.lon<=BBOX[2]and BBOX[1]<=n.lat<=BBOX[3]for n in way.nodes):return
  if any(not n.location.valid()for n in way.nodes):raise ValueError('Missing literal source way node')
  ways.append({'type':'Feature','id':f'osm:way:{way.id}','properties':{'name':tags.get('name:hu',tags.get('name','')),'source':{'provider':'openstreetmap','osmType':'way','osmId':way.id,'tags':tags,'nodeRefs':[n.ref for n in way.nodes],'objectVersion':way.version,'objectTimestamp':str(way.timestamp),'geometryUnmodified':True,'url':f'https://www.openstreetmap.org/way/{way.id}','license':'ODbL-1.0','attribution':'©OpenStreetMap contributors'}},'geometry':{'type':'LineString','coordinates':[[n.lon,n.lat]for n in way.nodes]}})
with tempfile.TemporaryDirectory(prefix='kaposvar-source-controls-')as temp:
 Extract().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(temp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway','place')])
for filename,features in [('all-city-roads-rails.geojson',ways),('local-place-controls.geojson',places)]:
 (OUT/filename).write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,indent=2)+'\n')
proof={'sourcePbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','sourcePbfHashProvenance':'Previously independently hashed frozen source PBF; this extraction does not re-hash the large file.','acquisitionBboxOnly':BBOX,'ways':len(ways),'placeNodes':len(places),'filteredWays':count,'fullWaysPreservedWithoutClipping':True,'bboxNeverUsedAsNeighborhoodBoundary':True,'outputSha256':{f:hashlib.sha256((OUT/f).read_bytes()).hexdigest()for f in ['all-city-roads-rails.geojson','local-place-controls.geojson']},'elapsedSeconds':round(time.monotonic()-started,3),'usableForAddressAssignment':False}
(OUT/'geographic-source-extraction.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps(proof))
