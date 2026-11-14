#!/usr/bin/env python3
"""Index completed independent reviews without changing data or source snapshots."""
from pathlib import Path
import json,hashlib,sys
P=Path(__file__).resolve().parent
read=lambda n:json.loads((P/n).read_text())
sha=lambda n:hashlib.sha256((P/n).read_bytes()).hexdigest()
enc=lambda d:json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
fc=read('source-inferred.geojson');nameqa=read('independent-name-review.json');px=read('independent-pixel-review.json');missing=read('unresolved-name-review.json');first=read('first-cohort-exclusions.json');old=read('recovered-name-cell-review.json');new={f['properties']['name']:f for f in fc['features']};frozen={r['sourceName']:r for r in first['records']};unresolved={r['sourceName']:r for r in missing['records']}
assert len(new)==27 and len(frozen)==33 and len(unresolved)==7 and len(set(new)|set(frozen)|set(unresolved))==67
assert not(set(new)&set(frozen)or set(new)&set(unresolved)or set(frozen)&set(unresolved))
assert len({f['properties']['sourceCellId']for f in fc['features']})==27 and not({f['properties']['sourceCellId']for f in fc['features']}&{r['sourceCellId']for r in first['records']})
assert px['strictJsValidCount']==27 and px['candidateFineNames']==27 and px['primaryApprovedCount']==0 and px['restoredExactOriginalPixelCount']==422
rows=[]
for r in old['records']:
 n=r['sourceName'];base={'sourceName':n}
 if n in frozen:base.update({'status':'existing_frozen_first_cohort','sourceCellId':frozen[n]['sourceCellId'],'historicalFrozenSemanticKind':frozen[n]['semanticKind'],'includedInNewOutput':False})
 elif n in new:base.update({'status':'new_completed_inferred_candidate','sourceCellId':new[n]['properties']['sourceCellId'],'newFeatureId':new[n]['id'],'candidateBoundaryKind':new[n]['properties']['candidateBoundaryKind'],'includedInNewOutput':True})
 else:base.update({'status':'unresolved_original_source_extent','sourceCellIdsRelevant':unresolved[n]['originalMaskComponentsRelevant'],'reason':unresolved[n]['observation'],'includedInNewOutput':False})
 if n=='Déli gazdasági terület':base['separateUnappliedSemanticRecommendation']='first-cohort-semantic-recommendation.json'
 rows.append(base)
inventory={'schemaVersion':1,'sourcePdfSha256':'995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1','sourceTable':{'originalPdfPagesOneBased':[47,48],'printedPages':[40,41],'number':8,'title':'Pécs városrészei'},'sourceNameCount':67,'frozenFirstCohortCount':33,'additionalCompletedSourceNames':27,'sourceNamesWithCompleteReviewedContoursAcrossBothCohorts':60,'remainingUnresolvedSourceNames':7,'newPrimaryApprovedCount':0,'newCohortGeographicPlacementVerified':False,'claimedAbsoluteAccuracy':None,'sourceRomanNumbersAreNotUsedAsAutomaticCrossFigureKeys':True,'records':rows}
summary={'schemaVersion':1,'reviewDate':'2026-11-14','verdict':'pass_inferred_only_27_additional_source_quarters_zero_primary','scope':'Combined index of independent literal-name/semantics and pixel/transform/topology reviews; does not assert new geographic control or supersede the frozen first cohort.','sourceRecordCount':27,'candidateFineNames':27,'candidatePlanningUnits':0,'candidateLocalAreas':0,'primaryApprovedCount':0,'geographicPlacementVerified':False,'claimedAbsoluteAccuracy':None,'usableForAddressAssignment':False,'firstCohortSourceCellIdsAndPublishedNamesExcluded':True,'sourceNameAndCellMappingIndependentReview':'independent-name-review.json','functionalNameSemanticsReviewedAgainstSourceHierarchy':'semantic-source-review.json','sourcePixelAndProjectionIndependentReview':'independent-pixel-review.json','sourceRawCellsAndGeometriesRetained':'raw-pixel-cells.json','exactCartographicRestoration':{'holeCount':37,'originalPixelCount':422,'allExplicitlyReviewed':True,'externalSourceFacesChanged':0},'strictJsValidCount':27,'strictJsRejectedCount':0,'maximumNewNewWorldOverlapDegreesSquared':0.0,'maximumNewFrozenWorldOverlapDegreesSquared':0.0,'unresolvedExactNames':missing['missingExactList'],'unresolvedEvidence':'unresolved-name-review.json','all67NameAccounting':'source-table-name-inventory.json','frozenFirstGeometrySha256':first['frozenFirstGeometrySha256'],'separateUnappliedFirstCohortSemanticRecommendation':'first-cohort-semantic-recommendation.json','frozenFirstCohortChanged':False,'rootRegistriesOrExportsChanged':False,'registryEntryApplied':False,'networkUsed':False,'independentReviewHashes':[{'path':n,'sha256':sha(n)}for n in ['independent-name-review.json','semantic-source-review.json','independent-pixel-review.json','unresolved-name-review.json','first-cohort-semantic-recommendation.json']]}
for n,d in [('source-table-name-inventory.json',inventory),('independent-review.json',summary)]:
 s=enc(d)
 if '--check'in sys.argv:assert(P/n).read_text()==s,n
 else:(P/n).write_text(s)
print(json.dumps({'newInferredSourceQuarters':27,'primary':0,'sourceNamesAccounted':67,'completeContoursAcrossBothCohorts':60,'missingExactNames':missing['missingExactList'],'check':'--check'in sys.argv},ensure_ascii=False))
