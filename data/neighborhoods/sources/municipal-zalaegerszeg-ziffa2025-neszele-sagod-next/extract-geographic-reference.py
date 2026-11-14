"""Select complete archived OSM roads and name evidence without modifying geometry."""
from pathlib import Path
import argparse,hashlib,json
from shapely.geometry import shape,box
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
ROAD=ROOT/'data/neighborhoods/sources/municipal-local-map-next/zalaegerszeg-road-controls.geojson'
NAMES=ROOT/'.local/neighborhoods/country-associated/named-nodes.geojson'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(x):return json.dumps(x,ensure_ascii=False,indent=2)+'\n'
pa=argparse.ArgumentParser();pa.add_argument('--check',action='store_true');a=pa.parse_args()
assert sha(ROAD)=='c1f79adeb5d94f8b32620f6a0fa90a3840e5dad3ea996f247e72e003bcc30c83'
assert sha(NAMES)=='05c02b8ac8f32df2d917e01f6de81c6133c5e7dd527114f67000b43467a3a048'
# Filter bounds select reference objects only, never create a contour or clip geometry.
x=json.loads(ROAD.read_text());selected=[f for f in x['features'] if shape(f['geometry']).intersects(box(16.816,46.852,16.843,46.892))]
x=json.loads(NAMES.read_text());names=[f for f in x['features'] if f['properties']['municipality']=='Zalaegerszeg' and f['properties']['name'] in ['Neszele','Ságod']]
for f in names:f['properties']['usedForGeoreferencing']=False;f['properties']['establishesSourceBoundary']=False
out={'road-geographic-reference.geojson':enc({'type':'FeatureCollection','features':selected}),'current-name-evidence.geojson':enc({'type':'FeatureCollection','features':names})}
for n,t in out.items():
 if a.check:assert (P/n).read_text()==t,n
 else:(P/n).write_text(t)
print(json.dumps({'check':a.check,'completeRoadWays':len(selected),'nameEvidencePoints':len(names),'roadArchiveSha256':sha(ROAD),'nameArchiveSha256':sha(NAMES)}))
