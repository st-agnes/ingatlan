#!/usr/bin/env python3
import json,hashlib,subprocess,sys
from pathlib import Path
from shapely.geometry import shape
P=Path(__file__).resolve().parent
names={'Belváros','Bartók Béla lakótelep','Kis Amerika','Rokkant telep','Tisztviselő telep','Vasúton túl'}
before=hashlib.sha256((P/'features.geojson').read_bytes()).hexdigest()
subprocess.run([sys.executable,str(P/'build.py')],check=True)
after=hashlib.sha256((P/'features.geojson').read_bytes()).hexdigest()
assert before==after,'Non-deterministic features'
fs=json.load(open(P/'features.geojson'))['features'];assert {f['properties']['name'] for f in fs}==names
city=shape(json.load(open(P/'municipality.geojson'))['features'][0]['geometry']);points=json.load(open(P/'source-named-points.geojson'))['features']
rows=[]
for f in fs:
 g=shape(f['geometry']);q=f['properties'];assert g.is_valid and not g.is_empty and g.geom_type=='Polygon'
 assert g.difference(city).area<1e-12
 matches=[x for x in points if x['properties']['name']==q['name']];assert len(matches)==1 and g.covers(shape(matches[0]['geometry']))
 assert q['estimated'] and q['lowConfidence'] and q['method'] and q['sourceUrl'] and q['approximationNote']
 rows.append(dict(name=q['name'],valid=True,insideMunicipality=True,containsKnownLabel=True,areaM2=q['areaM2']))
for i,f in enumerate(fs):
 for other in fs[i+1:]:assert not shape(f['geometry']).equals(shape(other['geometry']))
(P/'validation.json').write_text(json.dumps(dict(schemaVersion=1,featureCount=len(fs),allValid=True,allInsideMunicipality=True,allKnownLabelsContained=True,distinctGeometries=True,deterministicRebuild=True,featuresSha256=after,features=rows),ensure_ascii=False,indent=2)+'\n')
print('PASS:',len(fs),'quarters, deterministic',after)
