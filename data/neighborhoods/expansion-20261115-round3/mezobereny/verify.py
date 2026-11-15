#!/usr/bin/env python3
"""Check the frozen center, exact source-road edges and byte-identical offline rebuild."""
import hashlib,json,subprocess,sys
from pathlib import Path
from shapely.geometry import shape,Point
H=Path(__file__).resolve().parent
def read(n):return json.loads((H/n).read_bytes())
files=['features.geojson','boundary-route.geojson','boundary-route-audit.json','summary.json']
before={n:hashlib.sha256((H/n).read_bytes()).hexdigest() for n in files}
subprocess.run([sys.executable,str(H/'build.py')],check=True)
assert before=={n:hashlib.sha256((H/n).read_bytes()).hexdigest() for n in files}
fs=read('features.geojson')['features'];assert len(fs)==1
f=fs[0];g=shape(f['geometry']);assert g.geom_type=='Polygon' and g.is_valid
assert g.covers(Point(read('baseline-target.json')['pointCandidates'][0]['coordinates']))
route=read('boundary-route.geojson')['features'][0]['geometry']['coordinates'];assert route[0]==route[-1]
edges=set()
for road in read('source-roads.geojson')['features']:
 coords=road['geometry']['coordinates']
 for a,b in zip(coords,coords[1:]):edges.add(tuple(sorted((tuple(a),tuple(b)))))
assert all(tuple(sorted((tuple(a),tuple(b)))) in edges for a,b in zip(route,route[1:]))
audit=read('boundary-route-audit.json');assert len(audit['legs'])==17 and audit['rawRingValid']
assert all(a['sourceWayIds'] and a['lengthMetres']>0 for a in audit['legs'])
p=f['properties'];assert p['estimated'] and p['lowConfidence'] and not p['pointRadiusFallback']
report={'featureCount':1,'allValid':True,'sourceLabelCovered':True,'sourceRoadSegmentsOnly':True,'closedWithoutInventedSegment':True,'sourceDefinitionLegCount':17,'byteIdenticalOfflineRebuild':True,'exactParcelSidesReproduced':False,'geographicPrecisionReview':False,'sha256':before}
(H/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='sha256'}))
