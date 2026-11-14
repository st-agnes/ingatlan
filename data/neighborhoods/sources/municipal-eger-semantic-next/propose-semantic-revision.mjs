/** Offline, geometry-preserving semantic proposal. Does not edit a global registry. */
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {dirname,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {validateGeometry} from '../../../../scripts/neighborhoods/build.mjs';
const P=dirname(fileURLToPath(import.meta.url));
const sha=x=>createHash('sha256').update(x).digest('hex');
const sourcePath='data/neighborhoods/sources/municipal-east/eger-planning-units.geojson';
const sourceBytes=await readFile(join(P,'../municipal-east/eger-planning-units.geojson'));
if(sha(sourceBytes)!=='c3619e702df579b23776b977daf62c0ee1aafb9f629a8b447fb29b64f558011b')throw Error('Frozen Eger source changed');
const source=JSON.parse(sourceBytes),proposed=structuredClone(source);
const decisions=JSON.parse(await readFile(join(P,'semantic-decisions.json'),'utf8'));
const evidence=JSON.parse(await readFile(join(P,'web-evidence.json'),'utf8'));
const native=JSON.parse(await readFile(join(P,'native-source-records.json'),'utf8'));
if(source.features.length!==32||decisions.decisions.length!==32)throw Error('Expected32 source records');
const rows=[];
for(let i=0;i<32;i++){
 const before=source.features[i],f=proposed.features[i],p=f.properties,d=decisions.decisions.find(d=>d.featureIndex===i),n=native.records.find(r=>r.featureIndex===i);
 if(!d||!n||n.sourceFeatureId!==f.id)throw Error('Per-record source identity mismatch');
 const hash=sha(JSON.stringify(before.geometry)),validation=validateGeometry(before.geometry);
 if(!validation.valid)throw Error('Frozen source geometry does not pass strict validator');
 const fine=d.decision==='propose_qualified_quarter';
 const scope=fine?`Complete native source base-unit footprint labelled ${p.name} (${p.sourcePlanId}) on the2016-08 HÉSZ/SZT overview; base reference year${d.basePlanYear}. Current ordinary whole-quarter, ITS, legal and cadastral extents are not asserted.`:d.reason;
 Object.assign(p,{boundaryKind:fine?'neighbourhood':'planning_unit',canonicalNameIsNeighborhood:fine,
  sourceBoundarySchema:'Eger2016-08 mixed HÉSZ/SZT overview; individual historical statutory source-unit schema',
  sourceSchemaDate:'2016-08',sourceBasePlanReferenceYear:d.basePlanYear??null,
  candidateBoundarySchema:fine?'historical_source_defined_statutory_quarter_base_plan':'historical_regulatory_group_partial_or_other_unit',
  currentQuarterIdentityVerified:false,currentNameStatus:'unknown_not_independently_current_name_audited',
  priorManualNameAuditApplies:false,manualNameReviewScope:'The earlier89-name audit is a frozen previous cohort; it provides no current-name or extent corroboration for this revision.',reviewStatus:'unreviewed',
  sourceUnitScope:d.scope,sourceWholeNamedBaseUnitSupported:fine,
  currentOrdinaryWholeQuarterExtentAsserted:false,currentItsExtentMatches:null,currentLegalExtentMatches:null,
  boundaryScopeNote:scope,semanticReviewPath:'data/neighborhoods/sources/municipal-eger-semantic-next/semantic-audit.json',
  semanticReviewDecision:d.decision,semanticReviewReason:d.reason,semanticReviewEvidenceIds:d.evidence,
  semanticRevisionStatus:'proposal_requires_root_review_not_applied',originalBoundaryKind:'planning_unit',
  sourceGeometryUnmodified:true,sourceGeometrySha256:hash,
  georeferencingIsApproximate:true,independentInteriorControlCount:0,claimedAbsoluteAccuracyMetres:null,
  perimeterFitResidualsAreAccuracy:false,sourceDocumentIsOfficialMunicipalPublication:true,sourceIsOfficial:false,
  sourceIsHardBoundary:false,usableForAddressAssignment:false});
 if(d.qualification)p.semanticExtentQualification=d.qualification;
 if(d.blocker)p.semanticPromotionBlocker=d.blocker;
 p.quality={...p.quality,semanticExtent:scope,referenceYear:2016,independentInteriorControlVerified:false};
 const afterHash=sha(JSON.stringify(f.geometry));if(hash!==afterHash)throw Error('Semantic proposal changed a geometry');
 rows.push({...d,name:p.name,sourceFeatureId:f.id,sourcePlanId:p.sourcePlanId,sourcePdfDrawingIndex:p.sourcePdfDrawingIndex,
  currentEffectiveKind:'planning_unit',proposedBoundaryKind:p.boundaryKind,proposedCanonicalNameIsNeighborhood:p.canonicalNameIsNeighborhood,
  sourceNativeCrop:n.sourceCrop,sourceNativeLabels:n.nativePathContainedText,geometrySha256Before:hash,geometrySha256After:afterHash,
  geometryUnchanged:true,validator:validation,sourceDate:'2016-08',currentCommonOrItsExtentEstablished:false,
  evidence:d.evidence.map(id=>({id,url:evidence.sources[id].url})),globalChangeApplied:false});
}
const write=async(name,x)=>writeFile(join(P,name),JSON.stringify(x,null,2)+'\n');
proposed.name='Eger historical source units; qualified per-record semantic proposal, geometry unchanged';
await write('proposed-semantic-revision.geojson',proposed);
const digest=sha(await readFile(join(P,'proposed-semantic-revision.geojson')));
const originalEntry=JSON.parse(await readFile(join(P,'existing-admission-comparison.json'),'utf8')).entries.find(e=>e.id==='eger-historical-planning-units');
const entry={...originalEntry,path:'data/neighborhoods/sources/municipal-eger-semantic-next/proposed-semantic-revision.geojson',sha256:digest,
 propertyOverrides:{usableForAddressAssignment:false},
 semanticReclassificationNote:'PROPOSAL ONLY: per-record historical source-quarter scope review. Replace existing dataset rather than append; preserve all32 IDs/geometry hashes. Source schema/date and unknown current/ITS/legal extent remain explicit. No blanket quarter override.',
 semanticReviewPath:'data/neighborhoods/sources/municipal-eger-semantic-next/semantic-audit.json',
 reviewPath:'data/neighborhoods/sources/municipal-eger-semantic-next/root-native-geometry-audit.json',registryEntryAppliedByThisBatch:false};
await write('proposed-registry-entry.json',entry);
const counts={};for(const r of rows)counts[r.decision]=(counts[r.decision]??0)+1;
await write('semantic-audit.json',{schemaVersion:1,reviewDate:'2026-11-14',status:'qualified_individual_proposal_root_review_required',sourcePath,sourceGeojsonSha256:sha(sourceBytes),sourcePdfSha256:'7db28b2b5922e6dea7bde9dc3263087534b26e9cd1e52b63335249265df6febe',admissionMeaning:decisions.admissionMeaning,
 comparisonPath:'existing-admission-comparison.json',nativeGeometryAuditPath:'root-native-geometry-audit.json',webEvidencePath:'web-evidence.json',
 summary:{sourceRecords:32,existingFine:0,existingPlanning:32,proposedQualifiedHistoricalQuarters:rows.filter(r=>r.proposedBoundaryKind==='neighbourhood').length,proposedRetainedPlanning:rows.filter(r=>r.proposedBoundaryKind==='planning_unit').length,allGeometryHashesUnchanged:true,allGeometryValidatorPass:true,decisionCounts:counts,globalRegistryOrExportChangesApplied:0},
 changesFromPriorAudit:[{featureIndex:7,name:'Galagonyás-dűlő',finding:'The actual selected2004 base path is distinct from its2012 small amendment; the prior partial reasoning cited the amendment as if it defined this base geometry.'},{featureIndex:10,name:'Volt kemping',finding:'Conflicting quarter-language and direct Rác-hóstya subarea evidence require retention as planning pending scope resolution.'},{featureIndex:30,name:'Északnyugati külterület',finding:'Contemporaneous2016 law and supporting report restrict M1.23 to a road24 operational-site plan, not the entire northwest quarter.'}],
 globalSafety:{applyOnlyAfterRootReview:true,replaceExistingDatasetDoNotAppend:true,featureIdsPreserved:true,frozenSourceFilesModified:false,frozenZalaModified:false,noCurrentItsCoincidenceRequirementInvented:true,usableForAddressAssignment:false,absoluteAccuracyMetres:null,independentInteriorControlCount:0},
 features:rows});
await write('geometry-unchanged-check.json',{sourcePath,sourceFileSha256:sha(sourceBytes),proposalPath:'proposed-semantic-revision.geojson',proposalFileSha256:digest,hashDefinition:'SHA-256 of project JavaScript JSON.stringify(feature.geometry)',featureCount:32,allIdsUnchanged:source.features.every((f,i)=>f.id===proposed.features[i].id),allGeometryHashesUnchanged:rows.every(r=>r.geometryUnchanged),allStrictValidatorPass:rows.every(r=>r.validator.valid),features:rows.map(r=>({sourceFeatureId:r.sourceFeatureId,name:r.name,sourcePdfDrawingIndex:r.sourcePdfDrawingIndex,geometrySha256Before:r.geometrySha256Before,geometrySha256After:r.geometrySha256After,geometryUnchanged:r.geometryUnchanged,validation:r.validator}))});
console.log(JSON.stringify({proposalFeatures:32,qualifiedQuarters:rows.filter(r=>r.proposedBoundaryKind==='neighbourhood').length,retainedPlanning:rows.filter(r=>r.proposedBoundaryKind==='planning_unit').length,geometryChanged:0,sha256:digest}));
