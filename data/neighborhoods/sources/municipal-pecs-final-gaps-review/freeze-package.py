#!/usr/bin/env python3
from pathlib import Path
import argparse,json,hashlib
P=Path(__file__).resolve().parent
load=lambda n:json.loads((P/n).read_text())
sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
def build():
 obs=load('source-inferred.geojson');caps=load('reconstructed-cap-inferred.geojson');cov=load('source-coverage-accounting.json');qa=load('independent-final-gap-review.json');cq=load('independent-cap-review.json')
 assert len(obs['features'])==qa['strictJsValidCount']==5 and len(caps['features'])==cq['strictReconstructionValidCount']==2
 assert cov['observedSourceContoursTotal']==65 and cov['separatelyIdentifiedLowConfidenceReconstructedCandidates']==2 and cov['are67VerifiedOrCurrentBoundaries']is False
 assert all(f['properties']['sourceContourIsObserved']is True for f in obs['features'])and all(f['properties']['sourceContourIsObserved']is False and f['properties']['reconstructionConfidence']=='low'for f in caps['features'])
 for reg in ['registry-entry.json','registry-entry-caps.json']:
  r=load(reg);assert r['registryEntryAppliedByThisBatch']is False;assert r['sha256']==sha(P/Path(r['path']).name)
 known={'first-source-inferred.geojson':'3de4d89461e243563c5bd99d2bc33914f6ca059bdc97548e8f7ee0b41c968a95','remaining-source-inferred.geojson':'cfdd86a7dc73d6f6a76ebf9a2377a0e7e077992761f3b23fd675abf102c8826a','source-inferred.geojson':'a27535ffae4e4549f76200e207fa80fc6796dfbe394740eacce57b7df7693acc'}
 for n,h in known.items():assert sha(P/n)==h,n
 assert cq['observedFiveGeometrySha256Unchanged']==known['source-inferred.geojson']and cq['newCapsMaximumOverlapWithAll65ObservedDegreesSquared']==0 and qa['newAdmitted60WorldMaximumOverlapDegreesSquared']==0
 files=[{'path':str(q.relative_to(P)),'bytes':q.stat().st_size,'sha256':sha(q)}for q in sorted(P.rglob('*'))if q.is_file()and q.name!='artifact-manifest.json'and '__pycache__'not in q.parts and q.suffix!='.pyc']
 return {'schemaVersion':1,'reviewDate':'2026-11-14','status':'frozen_five_observed_source_contours_plus_two_low_confidence_reconstructions_inferred_only','artifactCount':len(files),'artifacts':files,'newObservedSourceContours':5,'newLowConfidenceReconstructedCandidates':2,'sourceDocumentCoverage':{'observedSourceContours':65,'separatelyReconstructedCandidates':2,'verifiedCurrentBoundariesClaimed':False},'observedSourceGeojsonSha256':sha(P/'source-inferred.geojson'),'reconstructedCapGeojsonSha256':sha(P/'reconstructed-cap-inferred.geojson'),'priorObservedCohortGeometryHashes':known,'primaryApprovedCount':0,'geographicPlacementVerified':False,'claimedAbsoluteAccuracy':None,'usableForAddressAssignment':False,'newGeographicModelFitted':False,'globalRegistryOrExportsWrittenByThisBatch':False,'localRegistrySuggestionsApplied':False,'finalProducerAndIndependentAuditorDataDependenciesAreLocalSnapshotFiles':True}
a=argparse.ArgumentParser();a.add_argument('--check',action='store_true');args=a.parse_args();d=build();s=json.dumps(d,ensure_ascii=False,indent=2)+'\n';q=P/'artifact-manifest.json'
if args.check:assert q.read_text()==s,'Frozen artifact inventory, hashes or interpretation changed'
else:q.write_text(s)
print(json.dumps({'check':args.check,'artifacts':d['artifactCount'],'newObserved':5,'newReconstructed':2,'coverageObserved':65,'coverageReconstructed':2,'primary':0,'claimedAbsoluteAccuracy':None,'observedSourceSha256':d['observedSourceGeojsonSha256'],'reconstructedSourceSha256':d['reconstructedCapGeojsonSha256']}))
