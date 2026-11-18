#!/usr/bin/env python3
"""Exact local artifact inventory; does not touch root registries or prior snapshots."""
from pathlib import Path
import argparse,json,hashlib
P=Path(__file__).resolve().parent
read=lambda n:json.loads((P/n).read_text())
sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
def build():
 source=read('source-inferred.geojson');summary=read('independent-review.json');reg=read('registry-entry.json');name=read('independent-name-review.json');pixel=read('independent-pixel-review.json');inventory=read('source-table-name-inventory.json');missing=read('unresolved-name-review.json');recommend=read('first-cohort-semantic-recommendation.json');a=read('assignments.json')
 assert reg['sha256']==sha(P/'source-inferred.geojson')and reg['registryEntryNotAppliedByThisBatch']is True
 assert len(source['features'])==len(a['records'])==27 and summary['candidateFineNames']==pixel['candidateFineNames']==27 and pixel['strictJsValidCount']==27
 assert all(f['properties']['candidateBoundaryKind']=='neighbourhood'and f['properties']['estimated']and f['properties']['claimedAbsoluteAccuracy']is None for f in source['features'])
 assert a['sourceNameReviewSha256']==sha(P/'independent-name-review.json')
 assert {r['sourceName']for r in name['records']}=={f['properties']['name']for f in source['features']}
 assert inventory['sourceNameCount']==67 and inventory['sourceNamesWithCompleteReviewedContoursAcrossBothCohorts']==60 and len(missing['records'])==7
 assert sha(P/'first-cohort-geometry-reference.geojson')==recommend['frozenSourceGeojsonSha256']=='3de4d89461e243563c5bd99d2bc33914f6ca059bdc97548e8f7ee0b41c968a95'
 assert recommend['appliedByThisReview']is False and summary['rootRegistriesOrExportsChanged']is False
 artifacts=[{'path':str(q.relative_to(P)),'bytes':q.stat().st_size,'sha256':sha(q)}for q in sorted(P.rglob('*'))if q.is_file()and q.name!='artifact-manifest.json'and '__pycache__'not in q.parts and q.suffix!='.pyc']
 return {'schemaVersion':1,'reviewDate':'2026-11-14','status':'frozen_27_additional_observed_source_quarters_inferred_placement_only','artifactCount':len(artifacts),'artifacts':artifacts,'sourceGeojsonSha256':reg['sha256'],'sourceRecordCount':27,'candidateFineNames':27,'candidatePlanningUnits':0,'candidateLocalAreas':0,'primaryApprovedCount':0,'geographicPlacementVerified':False,'claimedAbsoluteAccuracy':None,'rootRegistryOrExportsChanged':False,'registryEntryApplied':False,'allRuntimeConversionAndFinalAuditorInputsAreLocalSnapshotFiles':True,'missingExactNames':missing['missingExactList'],'separateFirstCohortSemanticRecommendationApplied':False}
ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();d=build();s=json.dumps(d,ensure_ascii=False,indent=2)+'\n';q=P/'artifact-manifest.json'
if args.check:assert q.read_text()==s,'Artifact bytes, inventory or classification changed'
else:q.write_text(s)
print(json.dumps({'check':args.check,'artifacts':d['artifactCount'],'sourceRecords':27,'candidateFineNames':27,'primary':0,'sourceGeojsonSha256':d['sourceGeojsonSha256'],'missingExactNames':d['missingExactNames'],'claimedAbsoluteAccuracy':None},ensure_ascii=False))
