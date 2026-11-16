#!/usr/bin/env python3
from pathlib import Path
import json,sys,hashlib
H=Path(__file__).resolve().parent;name=sys.argv[1];D=H/'batches'/name;assert not D.exists(),name
known=set()
for p in (H/'batches').glob('*/features.geojson'):
 for f in json.loads(p.read_text())['features']:known.add((f['properties']['municipality'],f['properties']['name']))
fs=[f for f in json.loads((H/'features.geojson').read_text())['features'] if (f['properties']['municipality'],f['properties']['name']) not in known];assert fs
D.mkdir();b=(json.dumps({'type':'FeatureCollection','features':fs},ensure_ascii=False,separators=(',',':'))+'\n').encode();(D/'features.geojson').write_bytes(b)
s={'featureCount':len(fs),'newNameCount':len(fs),'sha256':hashlib.sha256(b).hexdigest(),'remainingAssignedNames':len(json.loads((H/'summary.json').read_text())['remainingNames']),'estimatedCount':sum(f['properties']['estimated'] for f in fs),'nativeCount':0,'completeCityCoverageEstablished':False}
(D/'summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n');print(json.dumps(s))
