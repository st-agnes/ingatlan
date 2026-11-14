"""Read literal local OSM linear features; acquisition extent is never a neighborhood."""
import json,sys,tempfile,hashlib,time
from pathlib import Path
sys.dont_write_bytecode=True
import osmium
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
PBF=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
BBOX=(20.23,46.61,20.32,46.69)
features=[]
class Extract(osmium.SimpleHandler):
 def way(self,w):
  tags=dict(w.tags)
  if not any(n.location.valid() and BBOX[0]<=n.lon<=BBOX[2] and BBOX[1]<=n.lat<=BBOX[3] for n in w.nodes):return
  if any(not n.location.valid() for n in w.nodes):raise ValueError('Missing source node')
  coords=[[n.lon,n.lat] for n in w.nodes]
  features.append({'type':'Feature','id':f'osm:way:{w.id}','properties':{'name':tags.get('name:hu',tags.get('name','')),'source':{'provider':'openstreetmap','osmType':'way','osmId':w.id,'tags':tags,'nodeRefs':[n.ref for n in w.nodes],'objectVersion':w.version,'objectTimestamp':str(w.timestamp),'geometryUnmodified':True,'url':f'https://www.openstreetmap.org/way/{w.id}','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}},'geometry':{'type':'LineString','coordinates':coords}})
start=time.monotonic()
with tempfile.TemporaryDirectory(prefix='szentes-source-roads-') as tmp:
 Extract().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway','waterway')])
path=OUT/'szentes-local-lines.geojson'
path.write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,indent=2)+'\n')
proof={'sourcePbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','sourcePbfHashProvenance':'Pinned parent-task source snapshot, hash not re-computed by this script','acquisitionExtentOnly':BBOX,'wholeSourceWaysPreserved':True,'bboxUsedAsNeighborhood':False,'ways':len(features),'elapsedSeconds':time.monotonic()-start,'outputSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'usableForAddressAssignment':False}
(OUT/'szentes-local-lines-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof))
