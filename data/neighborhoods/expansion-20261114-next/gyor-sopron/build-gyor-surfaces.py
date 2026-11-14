#!/usr/bin/env python3
"""Rebuild the frozen Győr source-footprint subset from tracked raw surfaces."""
from pathlib import Path
import json,unicodedata
HERE=Path(__file__).resolve().parent
norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
raw=json.loads((HERE/'raw-surface-features.geojson').read_text())['features'];selected={}
for f in sorted(raw,key=lambda f:(f['properties']['sourceAreaSquareMetres'],f['id'])):
 p=f['properties']
 if p['municipality']!='Győr' or p['name']=='Kertváros':continue
 selected.setdefault((p['municipality'],norm(p['name'])),f)
(HERE/'gyor-surface-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':list(selected.values())},ensure_ascii=False,separators=(',',':'))+'\n')
print('Győr unchanged source-footprint estimates',len(selected))
