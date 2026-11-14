#!/usr/bin/env python3
"""Concatenate the two frozen city batches without touching the root catalogue."""
from pathlib import Path
import json,hashlib
HERE=Path(__file__).resolve().parent
features=[]
for file in ['salgotarjan-features.geojson','gyula-features.geojson']:
    features.extend(json.loads((HERE/file).read_text())['features'])
assert len({(f['properties']['municipality'],f['properties']['name']) for f in features})==len(features)
content=json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n'
(HERE/'features.geojson').write_text(content)
print(json.dumps({'features':len(features),'sha256':hashlib.sha256(content.encode()).hexdigest()}))
