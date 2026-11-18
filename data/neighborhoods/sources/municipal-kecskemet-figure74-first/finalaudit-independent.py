#!/usr/bin/env python3
"""Independent source/geotransformation audit, with no source/derive producer imports.

Photo registration was produced by this reviewing agent; that limitation is
explicit. Root-relative source files and matrices are independently recomputed.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np
import pyproj
from pyproj import Transformer
from PIL import Image
from shapely.geometry import Polygon,Point,MultiPoint,shape
OUT=Path(__file__).resolve().parent
ROOT=next(p for p in [OUT,*OUT.parents]if(p/'scripts/neighborhoods/build.mjs').is_file())
FINAL_REL='data/neighborhoods/sources/municipal-kecskemet-figure74-first'
PBF_SHA='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
sys.dont_write_bytecode=True

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(n):return json.loads((OUT/n).read_text())
def encode(v):return(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def close(a,b,tolerance=1e-9):
 if np.array(a).shape!=np.array(b).shape or np.max(np.abs(np.array(a)-np.array(b)))>tolerance:raise ValueError('independent numeric arrays disagree')

def audit(check=False):
 pyproj.network.set_network_enabled(False)
 if check and(OUT/'manifest.json').is_file():
  frozen=load('manifest.json');files=frozen['frozenFilesSha256'];actual={p.relative_to(OUT).as_posix()for p in OUT.rglob('*')if p.is_file()and p.name!='manifest.json'}
  if set(files)!=actual or frozen['frozenFileCountExcludingManifest']!=len(files):raise ValueError('final manifest exact membership differs')
  for n,digest in files.items():
   if sha(OUT/n)!=digest:raise ValueError('changed final file '+n)
   if'frozenFileBytes'in frozen and(OUT/n).stat().st_size!=frozen['frozenFileBytes'][n]:raise ValueError('changed final bytes '+n)
 for n in ['input-manifest.json','generated-manifest.json']:
  for name,digest in load(n)['sha256'].items():
   if sha(OUT/name)!=digest:raise ValueError('changed pinned input/output '+name)
 # Execute only separately authored audit paths, never the source or geographic
 # derivation producer. These are portable checks with their own pinned reports.
 subprocess.run([sys.executable,str(OUT/'source-independent-review.py'),'--check'],check=True,capture_output=True,text=True)
 subprocess.run([sys.executable,str(OUT/'image-registration-work/verify-image-registration-direct.py'),'--check'],check=True,capture_output=True,text=True)
 source_review=load('source-independent-review.json');photo_review=load('image-registration-work/direct-verification.json')
 photo_files=load('image-registration-work/work-manifest.json')['files'];photo_actual={p.relative_to(OUT/'image-registration-work').as_posix()for p in(OUT/'image-registration-work').rglob('*')if p.is_file()and p.name!='work-manifest.json'}
 if photo_actual!={r['path']for r in photo_files}:raise ValueError('photo archive membership differs')
 for f in photo_files:
  path=OUT/'image-registration-work'/f['path']
  if sha(path)!=f['sha256']or path.stat().st_size!=f['bytes']:raise ValueError('photo archive differs')
 prior=load('calibration-figure73-manifest.json')['frozenFilesSha256'];calibration_files=[('calibration-figure73.jpeg','figure73-p143-xref172.jpeg'),('calibration-figure73-georeference.json','georeference.json'),('calibration-figure73-control-specification.json','control-specification.json'),('calibration-figure73-control-roads.geojson','control-roads.geojson'),('calibration-figure73-original-pbf-verification.json','original-pbf-verification.json'),('calibration-figure73-current-name-points.geojson','current-name-points.geojson'),('calibration-figure73-prior-same-image-comparison.json','prior-same-image-comparison.json')]
 for local,original in calibration_files:
  if sha(OUT/local)!=prior[original]:raise ValueError('copied frozen Figure73 file differs '+local)
 proof=load('calibration-figure73-original-pbf-verification.json')
 if proof['sourcePbfSha256']!=PBF_SHA or proof['wayCount']!=23 or proof['namePointCount']!=2:raise ValueError('inherited PBF proof identity differs')
 for flag in ['allOriginalWayNodeSequencesAndCoordinatesMatch','allOriginalWayTagsVersionsAndTimestampsMatch','allOriginalNameNodeCoordinatesTagsVersionsAndTimestampsMatch','originalPbfWasActuallyReadToCreateThisProof']:
  if proof[flag]is not True:raise ValueError('inherited PBF proof incomplete')
 for original,local in [('control-roads.geojson','calibration-figure73-control-roads.geojson'),('current-name-points.geojson','calibration-figure73-current-name-points.geojson')]:
  if proof['inputSha256'][original]!=sha(OUT/local):raise ValueError('inherited PBF proof not bound to exact copied input')
 roads=load('calibration-figure73-control-roads.geojson')['features'];nodes={};membership={};wayproof={r['osmWayId']:r for r in proof['wayRecords']}
 for f in roads:
  s=f['properties']['source'];refs=s['nodeRefs'];coords=f['geometry']['coordinates'];q=wayproof[s['osmId']]
  if len(refs)!=len(coords)or len(refs)!=q['nodeCount']or s['geometryUnmodified']is not True:raise ValueError('source road sequence differs')
  for node,coordinate in zip(refs,coords):
   if node in nodes and nodes[node]!=coordinate:raise ValueError('source node coordinate conflict')
   nodes[node]=coordinate;membership.setdefault(node,set()).add(f['id'])
 spec=load('calibration-figure73-control-specification.json');controls=spec['controls'];original=load('calibration-figure73-georeference.json');previous=load('calibration-figure73-prior-same-image-comparison.json');oldobs=previous['comparisonMethod']['controls']
 if len(controls)!=6 or spec['sourceImageSha256']!=sha(OUT/'calibration-figure73.jpeg'):raise ValueError('six original control observation set differs')
 for c in controls:
  if nodes[c['osmNodeId']]!=c['coordinates']or membership[c['osmNodeId']]!=set(c['sourceWayIds']):raise ValueError('literal control identity differs')
  if c['historicalToCurrentPhysicalPointIdentityIndependentlyVerified']is not False:raise ValueError('unwarranted physical identity claim')
 # Four prior manual observations and excluded old candidate map through the
 # actual original image/page rectangle; two new southern points stay distinct.
 transfer=spec['sameImageControlTransferProof'];box=transfer['sourceImagePlacementPageBox'];manual_transfers=[];max_raw_pdf_float_box_vs_archived_decimal_transfer=0.
 for c in controls[:4]+[spec['excludedPriorComparisonCandidate']]:
  old=next(row for row in oldobs if row[:2]==c['coordinates']);raw_box_source=[(old[2]/2-box[0])/(box[2]-box[0])*1014,(old[3]/2-box[1])/(box[3]-box[1])*1434];source=[(old[2]/2-94.4)/406.47*1014,(old[3]/2-197.47802734375)/574.8499755859375*1434];max_raw_pdf_float_box_vs_archived_decimal_transfer=max(max_raw_pdf_float_box_vs_archived_decimal_transfer,float(np.max(np.abs(np.array(raw_box_source)-np.array(source)))));close(source,c['sourceImagePixel'],0);manual_transfers.append({'osmNodeId':c['osmNodeId'],'priorObservationRetainedExactlyThroughImagePlacement':True,'usedInNewFit':c in controls})
 eov=Transformer.from_crs(4326,23700,always_xy=True);wgs=Transformer.from_crs(23700,4326,always_xy=True);design=np.array([[*c['sourceImagePixel'],1]for c in controls]);metric=np.array([eov.transform(*c['coordinates'])for c in controls]);cal=np.linalg.lstsq(design,metric,rcond=None)[0];residual=np.linalg.norm(design@cal-metric,axis=1);close(cal,original['affineImagePixelToEovRows'],1e-8);close(residual,original['controlResidualMeters'],1e-8)
 excluded=spec['excludedPriorComparisonCandidate'];excluded_metric=np.array([*eov.transform(*excluded['coordinates']),1]);cal_h=np.vstack((cal.T,[0,0,1]));predicted_excluded=(np.linalg.inv(cal_h)@excluded_metric)[:2];excluded_report=original['excludedPriorComparisonDiagnostic'];close(predicted_excluded,excluded_report['newModelPredictedSourcePixel'],1e-7)
 if excluded['osmNodeId']in {c['osmNodeId']for c in controls}or excluded_report['usedInFit']is not False or excluded_report['insideOriginalInterpretationWindow']is not False or excluded_report['sourceFeatureIdentityUnconfirmed']is not True:raise ValueError('excluded prior physical candidate was silently promoted')
 relation=load('image-registration-work/image-registration.json')
 if relation['sourceImageSha256']!=sha(OUT/'calibration-figure73.jpeg')or relation['targetImageSha256']!=sha(OUT/'figure74-p154-xref176.jpeg')or relation['geographicCoordinatesUsed']is not False or relation['neighborhoodNameOrBoundaryGeometryUsed']is not False:raise ValueError('photo-only independence or identity differs')
 train=[q for q in relation['records']if q['usableTextureMatch']and q['trainingPartition']];held=[q for q in relation['records']if q['usableTextureMatch']and not q['trainingPartition']]
 if len(relation['records'])!=48 or(len(train),len(held))!=(13,10):raise ValueError('photo partition differs')
 photo=np.linalg.lstsq(np.array([[*q['sourcePatchCenter'],1]for q in train]),np.array([q['targetMatchedCenter']for q in train]),rcond=None)[0];close(photo,relation['sourceToTargetAffineRows'],0);held_errors=[float(np.linalg.norm(np.array([*q['sourcePatchCenter'],1])@photo-np.array(q['targetMatchedCenter'])))for q in held];close(max(held_errors),relation['maximumHeldOutResidualTargetPixels'],1e-12)
 inverse=np.linalg.inv(np.vstack((photo.T,[0,0,1])));composed=inverse.T@cal;geo=load('georeference.json')
 for actual,key in [(photo,'figure73ToFigure74PhotoAffineRows'),(inverse,'figure74ToFigure73Homogeneous'),(cal,'figure73PixelToEovRowsIndependentlyRefitted'),(composed,'composedFigure74PixelToEovRows')]:close(actual,geo[key],0)
 trace=load('source-pixel-trace.json');ring=trace['rings']['Hunyadiváros'];source=Polygon(ring);rgb=np.asarray(Image.open(OUT/'figure74-p154-xref176.jpeg').convert('RGB'));maxrgb=rgb.max(2);gap_paths=trace['sourceTextOverprintInferences'];inferred={tuple(q)for g in gap_paths for q in g['inferredPixelPath'][1:-1]};nonblack=[q for q in ring if maxrgb[q[1],q[0]]>45]
 if len(ring)!=2391 or len(nonblack)!=13 or any(tuple(q)not in inferred for q in nonblack)or any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(ring,ring[1:])):raise ValueError('source vertex/gap/edge audit differs')
 if source_review['sourceContourFullyObserved']is not False or source_review['nonBlackInferredVertexCount']!=13:raise ValueError('source audit inference scope differs')
 dense=np.column_stack((np.array(ring),np.ones(len(ring))));cal_pixels=(dense@inverse.T)[:,:2];metric_points=dense@composed;sequential=np.column_stack((cal_pixels,np.ones(len(cal_pixels))))@cal;close(metric_points,sequential,1e-8);lon,lat=wgs.transform(metric_points[:,0],metric_points[:,1]);computed=np.column_stack((lon,lat));collection=load('source-inferred.geojson')
 if len(collection['features'])!=1:raise ValueError('unexpected feature count')
 f=collection['features'][0];world=shape(f['geometry']);actual=np.array(f['geometry']['coordinates'][0])
 if f['properties']['name']!='Hunyadiváros'or f['geometry']['type']!='Polygon'or len(f['geometry']['coordinates'])!=1 or not world.is_valid or world.interiors or actual.shape!=computed.shape:raise ValueError('transformed cell identity/topology differs')
 close(actual,computed,0);world_error=float(np.max(np.abs(actual-computed)))
 hull=MultiPoint([q['targetMatchedCenter']for q in train+held]).convex_hull
 if not hull.equals(shape(geo['observedTextureHullFigure74Pixels'])):raise ValueError('observed image hull differs')
 outside_hull=sum(not hull.covers(Point(x,y))for x,y in ring);outside_image=sum(not(0<=x<=1013 and 0<=y<=1433)for x,y in cal_pixels);max_hull=max(hull.distance(Point(x,y))for x,y in ring)
 if outside_hull!=geo['sourceVerticesOutsideMatchedTextureHull']or outside_image!=geo['sourceVerticesOutsideFigure73ImageRectangle']:raise ValueError('extrapolation count differs')
 close(max_hull,geo['maximumDistanceBeyondMatchedTextureHullSourcePixels'],1e-10)
 alternatives=load('source-inference-alternatives.json');alternative_checks=[]
 if len(alternatives['gaps'])!=3 or alternatives['sourceAlternativesAreUnselectedHypotheses']is not True:raise ValueError('source hypotheses scope differs')
 for g in gap_paths:
  q=next(a for a in alternatives['gaps']if a['id']==g['id'])
  for key,value in g.items():
   if q[key]!=value:raise ValueError('source gap metadata altered in geographic alternatives')
  expected_rgb=[{'pixel':pixel,'rgb':rgb[pixel[1],pixel[0]].tolist()}for pixel in g['inferredPixelPath'][1:-1]]
  if q['sourceRgbOnChosenInferredInteriorPixels']!=expected_rgb or q['alternativesSelectedForRegistry']is not False:raise ValueError('gap colors or alternative selection differs')
  paths=[g['inferredPixelPath'],*g['alternativePixelPaths']];world_paths=[q['chosenWorldCoordinates'],*q['alternativeWorldPaths']]
  for path,world_path in zip(paths,world_paths):
   m=np.column_stack((np.array(path),np.ones(len(path))))@composed;x,y=wgs.transform(m[:,0],m[:,1]);close(np.column_stack((x,y)),world_path,1e-12)
  src_review_gap=next(a for a in source_review['sourceGaps']if a['id']==g['id'])
  if len(q['alternativeDiagnostics'])!=len(src_review_gap['alternativeDiagnostics']):raise ValueError('alternative replacement diagnostic count differs')
  for actual_diagnostic,review_diagnostic in zip(q['alternativeDiagnostics'],src_review_gap['alternativeDiagnostics']):
   for key in ['replacementSourcePolygonValid','replacementSourceAreaDifferenceSquarePixels','notAnAccuracyBoundOrChosenOutput']:
    if actual_diagnostic[key]!=review_diagnostic[key]:raise ValueError('unselected alternative validity diagnostic differs')
  alternative_checks.append({'id':g['id'],'chosenAndBothAlternativeWorldPathsChecked':True,'sourceNonBlackChosenVertexCount':src_review_gap['chosenPathNonBlackVertexCount'],'alternativeReplacementPolygonValidFlags':[r['replacementSourcePolygonValid']for r in src_review_gap['alternativeDiagnostics']],'alternativesAreUnselectedAndNotAccuracyBounds':True})
 current=load('current-name-points.geojson')['features'];nameproof=load('current-name-original-pbf-proof.json')
 if len(current)!=1 or current!=nameproof['namePoints']or nameproof['sourcePbfSha256']!=PBF_SHA or nameproof['actualOriginalPbfRead']is not True or nameproof['controlOrGeographicExtentValidation']is not False:raise ValueError('current name proof identity differs')
 n=current[0];name_inside=world.covers(shape(n['geometry']))
 if n['id']!='osm:node:984225130'or n['properties']['source']['osmId']in {c['osmNodeId']for c in controls}or n['properties']['source']['notUsedAsGeometryOrGeoreferencingControl']is not True or not name_inside:raise ValueError('current name/control/containment diagnostic differs')
 fresh=load('original-pbf-verification.json')
 if fresh['sourcePbfSha256']!=PBF_SHA or fresh['wayCount']!=23 or fresh['namePointCount']!=1 or fresh['uniqueComparedNodeCount']!=len(set(nodes)|{n['properties']['source']['osmId']}):raise ValueError('fresh original-PBF proof object counts differ')
 for name,digest in fresh['inputSha256'].items():
  if sha(OUT/name)!=digest:raise ValueError('fresh original-PBF proof/input hash differs')
 if set(fresh['inputSha256'])!={'calibration-figure73-control-roads.geojson','current-name-points.geojson'}:raise ValueError('fresh PBF proof input scope differs')
 for flag in ['allOriginalWayNodeSequencesAndCoordinatesMatch','allOriginalWayTagsVersionsAndTimestampsMatch','allOriginalNameNodeCoordinatesTagsVersionsAndTimestampsMatch','originalPbfWasActuallyReadToCreateThisProof']:
  if fresh[flag]is not True:raise ValueError('fresh original-PBF proof incomplete')
 fresh_way_records={r['osmWayId']:r for r in fresh['wayRecords']}
 for road in roads:
  source_metadata=road['properties']['source'];record=fresh_way_records[source_metadata['osmId']]
  if record['nodeCount']!=len(source_metadata['nodeRefs'])or record['objectVersion']!=source_metadata['objectVersion']or record['objectTimestamp']!=source_metadata['objectTimestamp']:raise ValueError('fresh literal road metadata differs')
  for flag in ['nodeReferenceSequenceMatches','everyNodeCoordinateMatches','tagsMatch','versionAndTimestampMatch']:
   if record[flag]is not True:raise ValueError('fresh literal road identity flag differs')
 fresh_name=fresh['namePointRecords'][0];source_metadata=n['properties']['source']
 if fresh_name['osmNodeId']!=source_metadata['osmId']or fresh_name['coordinates']!=n['geometry']['coordinates']or fresh_name['objectVersion']!=source_metadata['objectVersion']or fresh_name['objectTimestamp']!=source_metadata['objectTimestamp']or fresh_name['name']!=n['properties']['name']:raise ValueError('fresh literal name metadata differs')
 for flag in ['tagsMatch','coordinatesMatch','versionAndTimestampMatch']:
  if fresh_name[flag]is not True:raise ValueError('fresh name identity flag differs')
 p=f['properties']
 for k,expected in [('boundaryKind','inferred_area'),('candidateBoundaryKind','neighbourhood'),('estimated',True),('canonicalNameIsNeighborhood',False),('sourceRasterContourVerified',False),('sourceObservedContourVerifiedExceptExplicitOverprints',True),('geographicRegistrationVerified',False),('absoluteAccuracyMeters',None),('claimedAbsoluteAccuracyMetres',None),('usableForAddressAssignment',False)]:
  if p[k]!=expected:raise ValueError('explicit source/placement inference policy differs '+k)
 if p['sourceBoundaryInference']['gapCount']!=3 or p['sourceBoundaryInference']['inferredNonBlackVertexCount']!=13 or p['sourceBoundaryInference']['confidence']!='low'or p['sourceBoundaryInference']['alternativesPath']!=FINAL_REL+'/source-inference-alternatives.json':raise ValueError('source-inference policy differs')
 registry=load('registry-entry.json')
 if registry['path']!=FINAL_REL+'/source-inferred.geojson'or registry['reviewPath']!=FINAL_REL+'/independent-review.json'or registry['sha256']!=sha(OUT/'source-inferred.geojson')or registry['featureCount']!=1:raise ValueError('final registry path/hash differs')
 loo=[]
 for i,c in enumerate(controls):
  keep=[j for j in range(6)if j!=i];m=np.linalg.lstsq(design[keep],metric[keep],rcond=None)[0];movement=np.linalg.norm(np.column_stack((cal_pixels,np.ones(len(cal_pixels))))@m-metric_points,axis=1);row={'omittedControlId':c['id'],'maximumFigure74VertexDisplacementMeters':float(movement.max())};loo.append(row)
 close([q['maximumFigure74VertexDisplacementMeters']for q in loo],[q['maximumFigure74VertexDisplacementMeters']for q in geo['calibrationLeaveOneControlOut']],1e-8)
 js="""import{readFile}from'node:fs/promises';import{pathToFileURL}from'node:url';const{validateGeometry}=await import(pathToFileURL(process.argv[1]+'/scripts/neighborhoods/build.mjs'));const d=JSON.parse(await readFile(process.argv[2]+'/source-inferred.geojson','utf8'));process.stdout.write(JSON.stringify(d.features.map(f=>({id:f.id,...validateGeometry(f.geometry,f.bbox)}))));"""
 accepted=json.loads(subprocess.run(['node','--input-type=module','-e',js,str(ROOT),str(OUT)],check=True,capture_output=True,text=True).stdout)
 if len(accepted)!=1 or not accepted[0]['valid']:raise ValueError('actual project validator rejected cell')
 conversion=load('conversion-proof.json')
 if conversion['denseOriginalAndWorldVertexCountIncludingClosures']!=len(ring)or conversion['strictBlackSourceVertexCountIncludingClosure']!=2378 or conversion['inferredNonBlackSourceVertexCount']!=13 or conversion['allSourcePixelsBlack']is not False:raise ValueError('conversion evidence scope differs')
 provenance=['input-manifest.json','generated-manifest.json','source-pixel-trace.json','source-semantics.json','source-independent-review.py','source-independent-review.json','source-inferred.geojson','source-inference-alternatives.json','georeference.json','conversion-proof.json','registry-entry.json','calibration-figure73-manifest.json','calibration-figure73-georeference.json','calibration-figure73-control-specification.json','calibration-figure73-control-roads.geojson','calibration-figure73-original-pbf-verification.json','calibration-figure73-prior-same-image-comparison.json','current-name-points.geojson','current-name-original-pbf-proof.json','original-pbf-verification.json','verify-original-pbf.py','image-registration-work/work-manifest.json','image-registration-work/image-registration.json','image-registration-work/direct-verification.json','finalaudit-independent.py']
 result={'schemaVersion':1,'status':'PASS_FOR_ONE_EXPLICIT_SOURCE_GAP_AND_GEOGRAPHIC_INFERRED_CANDIDATE','logicalCohortPath':FINAL_REL,'independentOfSourceAndGeographicProducerCodeExecution':True,'producerSourceAndDeriveModulesImported':False,'photographicWorkProducedByThisReviewingAgent':True,'photographicNumericImplementationIndependentlyCrossCheckedButSeparateBlindVisualReviewer':False,'provenanceSha256':{n:sha(OUT/n)for n in provenance},'portableReplay':{'requiresExternalFrozenCohortDirectoryOrFullPbf':False,'requiresRepositoryProjectValidator':True,'allProvenancePathsRelativeToCohort':True,'finalManifestExcludedFromOwnFingerprintAvoidingCycles':True},'sourceContour':{'all2391SourceVerticesAnd2390EdgesChecked':True,'strictBlackVerticesIncludingClosure':2378,'explicitBlueTextOverprintNonBlackVertices':13,'gapCount':3,'sourceContourFullyObserved':False,'frameClosureOrUnlistedGapDetected':False,'sourceAndWorldHoles':0,'sourceScopeReview':'source-independent-review.json','allThreeGapWorldPathsAndSixUnselectedAlternativePathsChecked':True,'gapChecks':alternative_checks},'photographicRelation':{'all48SearchesDirectlyCrossCheckedBySeparateNumericImplementation':True,'trainingCount':13,'heldOutCount':10,'rejectedCount':25,'maximumHeldOutResidualTargetPixels':max(held_errors),'allFourProducerManualPreFitPhotoChecksInsideOriginalInterpretation':relation['allProducerPreFitManualChecksWithinOriginalInterpretation'],'separateBlindPhysicalReview':False,'geographicCoordinatesNamesOrQuarterGeometryUsed':False},'calibration':{'copiedFrozenFigure73EvidenceHashesMatch':True,'sixOriginalManualImageObservationsPreserved':True,'originalMetricAffineIndependentlyRefitted':True,'controlResidualMeters':residual.tolist(),'priorManualObservationTransfersChecked':manual_transfers,'priorTransferExactlyReproducedArchivedRoundedDecimalFormula':True,'rawPdfFloatBoxVsArchivedFormulaMaximumSourcePixelDifference':max_raw_pdf_float_box_vs_archived_decimal_transfer,'excludedOldSameImageCandidateNodeId':excluded['osmNodeId'],'excludedOldCandidatePredictedSourcePixelRecomputed':predicted_excluded.tolist(),'excludedOldCandidateStillUnconfirmedOutsideInterpretationAndNotUsedInFit':True,'inheritedPbfProofBoundToExactCopiedRoadAndNameInputs':True,'inheritedWayCount':23,'inheritedNamePointCount':2,'freshOriginalPbfProofBoundToExactCurrentInputs':True,'freshOriginalPbfProofWayCount':23,'freshOriginalPbfProofCurrentNameCount':1,'freshOriginalPbfProofUniqueNodeCount':fresh['uniqueComparedNodeCount'],'fullOriginalPbfRereadByThisAudit':False,'inheritedGeographicRegistrationVerified':False},'conversion':{'photoTrainingAffineAndInverseIndependentlyComputed':True,'metricCompositionAndSequentialConversionAgreeWithin1eMinus8Meters':True,'all2391WorldVerticesAndEveryEdgeChecked':True,'maximumWorldCoordinateDisagreementDegrees':world_error,'sourceVerticesOutsideObservedTextureHull':outside_hull,'sourceVerticesOutsideOriginalFigure73Image':outside_image,'maximumDistanceBeyondTextureHullTargetPixels':max_hull,'fullGeographicFootprintValidated':False},'currentNameEvidence':{'originalPbfProofContainsExactNode':'osm:node:984225130','pointInsideInferredCandidate':name_inside,'pointNotUsedAsControl':True,'nameOccurrenceProvesCurrentExactExtent':False,'originalPbfRereadByThisAudit':False},'sensitivityDiagnostics':{'leaveOneControlOut':loo,'notCalibratedAccuracyBounds':True},'actualProjectGeometryValidator':{'modulePath':'scripts/neighborhoods/build.mjs','moduleSha256':sha(ROOT/'scripts/neighborhoods/build.mjs'),'actualValidateGeometryExportCalled':True,'acceptedCount':1,'rejectedCount':0,'results':accepted},'sourceScope':{'properHunyadivarosSeparatedFromUmbrella':True,'otherThreeSourceCellsNotRejectedForFunctionalUse':True,'factoryMapProseNuanceRetained':True,'separateSouthernEconomicCellNotSubstitutedForPoultryFactory':True},'primaryLayerApproved':False,'explicitInferredLayerApproved':True,'sourceRasterContourFullyVerified':False,'geographicRegistrationVerified':False,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,'rightsStatus':'Municipal source-map reuse rights unverified; ODbL-1.0 applies to OSM controls and current name.','approvalReason':'All recorded source/gap coordinates, archived calibration evidence, independent numeric composition, all transformed vertices/edges and actual project admission pass. Three low-confidence source overprint continuations and extensive geographic extrapolation remain explicit inferences. The photo producer is this reviewing agent; no separate blind physical independence is claimed. Preserve inferred-only status.'}
 target=OUT/'independent-review.json';data=encode(result)
 if check:
  if target.read_bytes()!=data:raise ValueError('independent audit stale')
 else:target.write_bytes(data)
 print(json.dumps({'mode':'check'if check else'build','status':result['status'],'worldVerticesChecked':2391,'sourceBlackVertices':2378,'sourceGapNonBlackVertices':13,'actualProjectAccepted':1,'outsideObservedTextureHull':outside_hull,'outsideOriginalCalibrationImage':outside_image,'maximumBeyondTextureHullPixels':max_hull},ensure_ascii=False))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');audit(parser.parse_args().check)
