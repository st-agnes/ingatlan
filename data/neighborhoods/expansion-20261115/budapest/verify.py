#!/usr/bin/env python3
"""Packet-level geometry, source metadata and deterministic-build verification."""
from pathlib import Path
import hashlib,json,subprocess,sys,unicodedata
from shapely.geometry import shape
HERE=Path(__file__).resolve().parent
output=HERE/'features.geojson';before=output.read_bytes()
subprocess.run([sys.executable,str(HERE/'build.py')],check=True,capture_output=True)
assert output.read_bytes()==before,'Non-deterministic output'
fs=json.loads(before)['features'];names=[]
for f in fs:
 p=f['properties'];g=shape(f['geometry'])
 assert g.geom_type=='Polygon' and g.is_valid and not g.is_empty,p['name']
 assert p['municipality']=='Budapest' and p['estimated'] is True and p['lowConfidence'] is True,p['name']
 for key in ['method','sourceUrl','supportingUrls','approximationNote','boundaryAnchors','namePoint']:
  assert p[key],(p['name'],key)
 assert p['sourceUrl'].startswith('https://'),p['name']
 assert all(u.startswith('https://') for u in p['supportingUrls']),p['name']
 assert (HERE/p['contextImage']).is_file(),p['name']
 names.append(unicodedata.normalize('NFC',p['name']).casefold())
assert len(set(names))==len(names),'Duplicate names'
for p in HERE.glob('*-source-roads.geojson.gz'):assert p.stat().st_size<95_000_000
summary=json.loads((HERE/'summary.json').read_text())
assert summary['featureCount']==len(fs)
assert summary['circleCount']==summary['voronoiCount']==0
report={'date':'2026-11-15','featureCount':len(fs),'validPolygonCount':len(fs),'estimatedAndLowConfidenceCount':len(fs),'metadataComplete':True,'duplicateNames':0,'offlineByteIdenticalRebuild':True,'featuresSha256':hashlib.sha256(before).hexdigest(),'pointOutsideNames':summary['pointOutsideNames'],'note':'Geometry/reproducibility checks do not certify neighborhood boundary accuracy.'}
(HERE/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
