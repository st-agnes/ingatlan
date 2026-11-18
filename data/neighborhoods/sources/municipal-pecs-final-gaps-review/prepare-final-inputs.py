#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,shutil
P=Path(__file__).resolve().parent;ROOT=P.parents[3];FIRST=P.parent/'municipal-pecs-first-inferred';MORE=P.parent/'municipal-pecs-remaining-next'
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
def cp(src,name):
 dst=P/name
 if dst.exists():assert dst.read_bytes()==src.read_bytes()
 else:shutil.copyfile(src,dst)
for n in ['pecs-p48-names.jpeg','pecs-p63-density.jpeg','pecs-image-alignment.json','pecs-registration-northwest-only-diagnostic.json','pecs-source-selected-pages.pdf','pecs-source-selected-pages.txt']:cp(MORE/n,n)
for source,prefix in [(FIRST,'first'),(MORE,'remaining')]:
 for n in ['source-inferred.geojson','assignments.json','conversion-proof.json']:cp(source/n,prefix+'-'+n)
cp(MORE/'unresolved-name-review.json','previous-unresolved-review.json')
records=[]
for prefix in ['first','remaining']:
 g=json.loads((P/(prefix+'-source-inferred.geojson')).read_text());a=json.loads((P/(prefix+'-assignments.json')).read_text())
 for r in a['records']:records.append({'sourceName':r['sourceName'],'sourceCellId':r['reviewedSourceComponentId'],'admittedCohort':prefix})
assert len(records)==60 and len({r['sourceCellId']for r in records})==60 and len({r['sourceName']for r in records})==60
out={'schemaVersion':1,'purpose':'Exclude all60 already admitted actual source contours/names. Source copies are immutable references, not outputs of the gap batch.','records':records,'frozenSourceGeometryInputs':[{'path':prefix+'-source-inferred.geojson','sha256':sha(P/(prefix+'-source-inferred.geojson'))}for prefix in ['first','remaining']],'newGeographicModelAllowed':False,'claimedAbsoluteAccuracy':None}
q=P/'admitted-cohort-exclusions.json';s=json.dumps(out,ensure_ascii=False,indent=2)+'\n'
if q.exists():assert q.read_text()==s
else:q.write_text(s)
print(json.dumps({'admittedExcluded':len(records),'firstSha256':out['frozenSourceGeometryInputs'][0]['sha256'],'remainingSha256':out['frozenSourceGeometryInputs'][1]['sha256']}))
