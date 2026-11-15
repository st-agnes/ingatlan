#!/usr/bin/env python3
"""Offline integrity checks, not boundary accuracy certification."""
from pathlib import Path
import json,hashlib,subprocess,sys,gzip
from shapely.geometry import shape,Point
H=Path(__file__).resolve().parent
before=(H/'features.geojson').read_bytes();subprocess.run([sys.executable,str(H/'build.py')],check=True);assert before==(H/'features.geojson').read_bytes(),'rebuild differs'
fs=json.loads(before)['features'];targets=json.loads((H/'target-selection.json').read_text());expected={x['name'] for x in targets};assert len(fs)==8 and {f['properties']['name'] for f in fs}==expected
m=shape(json.loads((H/'source-municipalities.geojson').read_text())['features'][0]['geometry']);checks=[]
for f in fs:
 p=f['properties'];g=shape(f['geometry']);assert g.is_valid and not g.is_empty and g.geom_type=='Polygon'
 assert p['estimated'] and p['lowConfidence'] and not p['absoluteAccuracyEstablished'] and not p['partialSourceFootprint'] and p['geometryScope']=='whole_main_quarter_estimate'
 assert p['sourceUrl'].startswith('https://') and p['supportingUrls'] and p['boundaryAnchors'] and p['sourceContextSha256']
 assert g.covers(Point(p['namePoint']['coordinates']))
 assert len(set(g.exterior.coords))>4
 assert .7<g.intersection(m).area/g.area<=1.00001
 checks.append({'name':p['name'],'valid':True,'areaSquareMetres':p['areaSquareMetres'],'pointInside':True,'municipalOverlapFraction':round(g.intersection(m).area/g.area,6)})
r={'date':'2026-11-15','featureCount':8,'validPolygonCount':8,'estimatedCount':8,'lowConfidenceCount':8,'nativePolygonCount':0,'partialSourceFootprintCount':0,'pointInsideCount':8,'byteIdenticalOfflineRebuild':True,'featuresSha256':hashlib.sha256(before).hexdigest(),'circleCount':0,'voronoiCount':0,'aliasesProposed':0,'completeCityCoverageEstablished':False,'absoluteAccuracyEstablished':False,'checks':checks}
(H/'validation.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
manifest={str(p.relative_to(H)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(H.rglob('*')) if p.is_file() and p.name not in ['source-manifest.json','validation.json','features.geojson','summary.json']}
(H/'source-manifest.json').write_text(json.dumps({'algorithm':'sha256','files':manifest},ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False))
