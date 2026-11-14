#!/usr/bin/env python3
"""Freeze recovered Pecs evidence into this distinct batch; never overwrite prior files."""
from pathlib import Path
import json,hashlib,shutil,unicodedata
P=Path(__file__).resolve().parent;ROOT=P.parents[3];FIRST=P.parent/'municipal-pecs-first-inferred';OLD=P.parent/'municipal-pecs-next'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,o):
 p=P/n;s=json.dumps(o,ensure_ascii=False,indent=2)+'\n'
 if p.exists():assert p.read_text()==s
 else:p.write_text(s)
def copy(src,n=None):
 dst=P/(n or src.name)
 if dst.exists():assert dst.read_bytes()==src.read_bytes()
 else:shutil.copyfile(src,dst)
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.lower())if c.isalnum())
for n in ['pecs-p48-names.jpeg','pecs-p63-density.jpeg','pecs-image-alignment.json','pecs-registration-northwest-only-diagnostic.json','pecs-source-selected-pages.pdf','pecs-source-selected-pages.txt','pecs-source-extraction-proof.json','strict-validator-snapshot.mjs']:copy(FIRST/n)
copy(OLD/'pecs-independent-name-cell-review.json','recovered-name-cell-review.json')
copy(OLD/'pecs-review-name-more-anchors.json','recovered-additional-label-anchors.json')
copy(OLD/'pecs-name-review-label-anchors.json','recovered-first-label-anchors.json')
a=json.loads((FIRST/'assignments.json').read_text());geo=FIRST/'source-inferred.geojson';assert sha(geo)=='3de4d89461e243563c5bd99d2bc33914f6ca059bdc97548e8f7ee0b41c968a95'
write('first-cohort-exclusions.json',{'frozenFirstGeometrySha256':sha(geo),'frozenAssignmentSha256':sha(FIRST/'assignments.json'),'records':[{'sourceName':r['sourceName'],'sourceCellId':r['reviewedSourceComponentId'],'semanticKind':r['semanticKind']}for r in a['records']],'sourceCellIdsAndNamesBothExcluded':True})
inputs=[];published=[]
for n in ['neighborhoods.geojson','estimated-candidates.geojson','planning-units.geojson']:
 q=ROOT/'data/neighborhoods'/n
 if not q.exists():continue
 inputs.append({'path':str(q.relative_to(ROOT)),'sha256':sha(q)})
 for f in json.loads(q.read_text())['features']:
  r=f['properties']
  if r.get('municipality')=='Pécs' or r.get('city')=='Pécs':published.append({'sourceName':r['name'],'normalizedName':norm(r['name']),'featureId':f.get('id'),'publishedLayer':n})
write('published-name-exclusions.json',{'snapshotScope':'Read-only existing source exports at start of remaining batch; root exports are not written and are not future reproduction dependencies.','inputs':inputs,'records':published,'aliasesInferredFromNames':False})
review=json.loads((P/'recovered-name-cell-review.json').read_text());excluded={norm(r['sourceName'])for r in a['records']}|{r['normalizedName']for r in published};ids={r['reviewedSourceComponentId']for r in a['records']};remaining=[r for r in review['records']if norm(r['sourceName'])not in excluded]
assert len(remaining)==34
supported=[r for r in remaining if r.get('canUseUnchangedSourceCell')];assert len(supported)==27 and all(r['reviewedSourceComponentId']not in ids for r in supported)
write('provisional-remaining-assignments.json',{'status':'recovered_pairs_pending_new_independent_QA','records':supported})
write('unresolved-name-inventory.json',{'sourceTableNamesTotal':len(review['records']),'frozenFirstCohortCount':len(a['records']),'remainingSupportedBeforeNewQA':len(supported),'unresolvedCount':len(remaining)-len(supported),'records':[r for r in remaining if not r.get('canUseUnchangedSourceCell')],'scope':'These source names do not yet have a complete independently supported unchanged raster cell. No polygons or guessed closures are created here.'})
print(json.dumps({'copiedSources':len(list(P.glob('*.jpeg'))),'sourceNames':len(review['records']),'excludedFrozen':len(a['records']),'additionalPublishedExclusions':len(published)-len(a['records']),'remainingPairs':len(supported),'unresolved':len(remaining)-len(supported)}))
