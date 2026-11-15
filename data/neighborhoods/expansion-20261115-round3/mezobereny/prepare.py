#!/usr/bin/env python3
"""Copy already archived local road/administrative evidence; no network or PBF pass."""
import gzip,json,hashlib
from pathlib import Path
from shapely.geometry import box,shape
H=Path(__file__).resolve().parent;R=H.parents[3];D=R/'data/neighborhoods'
def load(p):
 b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def write(n,o):(H/n).write_text(json.dumps(o,ensure_ascii=False,separators=(',',':'))+'\n')
b=box(21.0,46.81,21.05,46.84)
p=D/'expansion-20261115/national-cells/source-barriers.geojson'
roads=[f for f in load(p)['features'] if shape(f['geometry']).intersects(b)]
write('source-roads.geojson',{'type':'FeatureCollection','features':roads})
m=[f for f in load(D/'sources/country-osm/municipalities.geojson.gz')['features'] if f['properties'].get('name')=='Mezőberény']
write('source-municipality.geojson',{'type':'FeatureCollection','features':m})
t=[q for q in load(D/'expansion-20261114/inventory/known-names.json')['names'] if q['municipality']=='Mezőberény' and q['name']=='Városközpont']
write('baseline-target.json',t[0])
write('source-manifest.json',{'sourcePath':str(p.relative_to(R)),'sourceSha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','snapshotDate':'2026-11-12T21:23:05Z','localRoadCount':len(roads),'municipalityCount':len(m),'bounds':[21.0,46.81,21.05,46.84],'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'})
print('Archived local roads:',len(roads))
