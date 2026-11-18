#!/usr/bin/env python3
"""Independent archive/pixel/plan-crossing readback, never a fit or writer."""
from pathlib import Path
import json,hashlib,os,math
os.environ['PROJ_NETWORK']='OFF'
from PIL import Image
from shapely.geometry import LineString
from pyproj import Transformer
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
m=read(P/'manifest.json')
for r in m['artifacts']+m['protectedInputFiles']:
 q=ROOT/r['path'];assert q.is_file()and q.stat().st_size==r['bytes']and sha(q)==r['sha256'],r['path']
frozen=P.parent/'municipal-pecs-first-inferred/source-inferred.geojson'
assert sha(frozen)=='3de4d89461e243563c5bd99d2bc33914f6ca059bdc97548e8f7ee0b41c968a95'
r=read(P/'independent-source-image-review.json');im=Image.open(P.parent/'municipal-pecs-grounded-next/source-name-map.jpeg').convert('RGB')
for v in r['checkedInputHashes']:assert sha(P/v['path'])==v['sha256']
for c in r['crops']:
 actual=Image.open(P/c['path']).convert('RGB');expected=im.crop(c['sourcePixelBox']);s=c['nearestNeighbourScale'];expected=expected.resize((expected.width*s,expected.height*s),Image.Resampling.NEAREST)
 assert actual.size==expected.size and actual.tobytes()==expected.tobytes();assert sha(P/c['path'])==c['sha256']
for z in r['sourceOnlyObservations']:
 for v in z.get('samplePixels',[]):assert list(im.getpixel(tuple(v['pixel'])))==v['rgb']
p=read(P/'source-target-topology-proof.json');assert len(p['rawMemberAndCandidateWays'])==37 and len(p['rawReferencedNodes'])==715
ns={n['osmNodeId']:n['coordinates']for n in p['rawReferencedNodes']};t=Transformer.from_crs(4326,23700,always_xy=True);u=Transformer.from_crs(23700,4326,always_xy=True);maxdiff=0.0
for q in p['sourceInputs']:assert sha(ROOT/q['path'])==q['sha256']
for w in p['rawMemberAndCandidateWays']:assert all(n in ns for n in w['nodeRefs'])
for c in p['computedFeatureCrossings']:
 segs=[c[k]for k in ['roadSegment','railSegment','boundarySegment']if k in c];assert len(segs)==2
 for s in segs:
  assert s['wgs84']==[ns[n]for n in s['nodeRefs']]
  for a,b in zip(s['wgs84'],s['eov']):assert math.dist(t.transform(*a),b)<1e-8
 z=LineString(segs[0]['eov']).intersection(LineString(segs[1]['eov']));assert z.geom_type=='Point'
 diff=math.dist(list(z.coords)[0],c['computedIntersection']['eov']);assert diff<1e-8;maxdiff=max(maxdiff,diff)
d=read(P/'decision.json');assert d['result']=={'newDirectlyObservedEasternFeatureCrossings':2,'newApprovedGroundControls':0,'newFittedGeoreferenceModels':0,'newQuarterGeometries':0,'primaryRecordsAdded':0}
for c in d['easternCrossingCandidates']:assert math.dist(u.transform(*c['currentTargetEov']),c['currentTargetWgs84'])<1e-11;assert not c['geographicControlApproved']and not c['usedInFit']
assert d['claimedAbsoluteAccuracy']is None and not d['georeferenceModelApproved']and not d['automaticPrimaryApproval']
assert not any(P.glob('*model*.json'))and not any(P.glob('*inferred*.geojson'))
print(json.dumps({'status':'PASS','artifactHashesChecked':len(m['artifacts']),'protectedInputHashesChecked':len(m['protectedInputFiles']),'sourceCropsPixelExact':len(r['crops']),'originalRawWays':37,'originalRawNodes':715,'independentShapelyPlanCrossingsChecked':len(p['computedFeatureCrossings']),'maximumIntersectionMethodDifferenceMetres':maxdiff,'frozen33GeometryHashMatchesKnownBaseline':True,'newPrimaryRecords':0,'claimedAbsoluteAccuracy':None},ensure_ascii=False))
