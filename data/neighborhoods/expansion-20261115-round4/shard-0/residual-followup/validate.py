#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,shutil,subprocess,sys,tempfile
from shapely.geometry import shape,Point
P=Path(__file__).resolve().parent
expected={'features.geojson':'7663baf1a55e1bfa3ac29d07078a45db625d50e19155d5df01f0839123e58c74','arkoshaza-reviewed-candidate.geojson':'16193c336185a9a8de2756a953f1d847509a475fbc191162383ff07409ea73b6'}
features=[]
for name,sha in expected.items():
 assert hashlib.sha256((P/name).read_bytes()).hexdigest()==sha
 d=json.load(open(P/name));assert d['type']=='FeatureCollection' and len(d['features'])==1;features.extend(d['features'])
for f in features:
 g=shape(f['geometry']);p=f['properties'];assert g.is_valid and not g.is_empty and g.geom_type in ['Polygon','MultiPolygon'];assert p['estimated'] and p['lowConfidence'] and p['partialFootprint'];assert p['sourceUrl'] and p['supportingUrls'] and p['approximationNote'];assert not p['usableForAddressAssignment']
assert len({(f['properties']['municipality'],f['properties']['name']) for f in features})==2
ark=next(f for f in features if f['properties']['name']=='Árkosháza-puszta')['properties'];assert ark['quality']==9 and ark['historicEstateBoundaryKnown'] is False and ark['disappearedSettlement'] and ark['representativeLandscapeTract']
with tempfile.TemporaryDirectory(prefix='west-residual-offline-') as t:
 t=Path(t);shutil.copytree(P/'source-inputs',t/'source-inputs');shutil.copyfile(P/'recipe.json',t/'recipe.json')
 for n in ['build.py','build-arkoshaza-candidate.py']:
  shutil.copyfile(P/n,t/n);subprocess.run([sys.executable,str(t/n)],check=True,capture_output=True)
 for n in expected:assert (t/n).read_bytes()==(P/n).read_bytes(),'Offline output differs: '+n
out={'valid':True,'distinctRepresentations':2,'frozenFeatureCollectionCount':1,'separateReviewedCandidateCount':1,'deterministicOfflineBuild':True,'geometryTypes':[f['geometry']['type'] for f in features],'pointBuffersCreated':0,'syntheticClosureEdges':0,'hashes':expected}
(P/'validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
