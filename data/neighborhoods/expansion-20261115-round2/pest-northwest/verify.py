#!/usr/bin/env python3
"""Offline integrity checks; not a survey/official-boundary accuracy audit."""
from pathlib import Path
from collections import Counter
import hashlib,json,subprocess,sys
from shapely.geometry import shape
H=Path(__file__).resolve().parent
before=(H/'features.geojson').read_bytes()
subprocess.run([sys.executable,str(H/'build.py')],check=True)
assert before==(H/'features.geojson').read_bytes(),'rebuild changed features.geojson'
fc=json.loads(before);fs=fc['features']; keys=set();areas=[]
for f in fs:
 p=f['properties'];key=(p['municipality'],p['name']);assert key not in keys;keys.add(key)
 g=shape(f['geometry']);assert g.geom_type in ('Polygon','MultiPolygon') and g.is_valid and not g.is_empty
 assert p['sourceUrl'].startswith('https://') and p['supportingUrls'] and p['boundaryAnchors']
 assert p['estimated'] is True and p['lowConfidence'] is True and p['absoluteAccuracyEstablished'] is False
 assert len(g.exterior.coords)>4 and len(set(g.exterior.coords))>4
 assert p['namePoint']['insideEstimatedPolygon']
 for x,y in g.exterior.coords:assert 18<x<20 and 46<y<49
 areas.append(p['areaSquareMetres'])
summary=json.loads((H/'summary.json').read_text());assert len(fs)==29==summary['featureCount']
assert len(keys)==29 and len(summary['remainingNames'])==14
inputs={str(p.relative_to(H)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(H.rglob('*')) if p.is_file() and p.name not in {'features.geojson','summary.json','validation.json','source-manifest.json','README.md','unresolved.json'} and '__pycache__' not in p.parts}
(H/'source-manifest.json').write_text(json.dumps({'algorithm':'sha256','files':inputs},ensure_ascii=False,indent=2)+'\n')
report={'featureCount':len(fs),'municipalityCounts':dict(sorted(Counter(f['properties']['municipality'] for f in fs).items())),'validPolygonCount':len(fs),'deterministicRebuild':True,'estimatedCount':len(fs),'lowConfidenceCount':len(fs),'nativeCount':0,'pointInsideCount':len(fs),'circleCount':0,'voronoiCount':0,'aliasesProposed':0,'smallestAreaSquareMetres':min(areas),'largestAreaSquareMetres':max(areas),'featuresSha256':hashlib.sha256(before).hexdigest(),'absoluteAccuracyEstablished':False,'completeCityCoverageEstablished':False,'note':'All 29 priority names in the four selected municipalities now have estimated polygons in this packet or prior data. The name inventory is not authoritative or complete. This does not establish complete city, national, legal or address coverage.'}
(H/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
