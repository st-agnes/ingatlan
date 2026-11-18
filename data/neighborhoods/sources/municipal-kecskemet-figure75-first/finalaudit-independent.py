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
FINAL_REL='data/neighborhoods/sources/municipal-kecskemet-figure75-first'
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
  frozen=load('manifest.json');files=frozen['frozenFilesSha256'];actual={p.relative_to(OUT).as_posix()for p in OUT.rglob('*')if p.is_file()and p!=OUT/'manifest.json'}
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
 photo_archive_counts={}
 for folder in ['calibration-figure74-photo-work','image-registration-work']:
  subprocess.run([sys.executable,str(OUT/folder/'verify-image-registration-direct.py'),'--check'],check=True,capture_output=True,text=True)
  photo_files=load(folder+'/work-manifest.json')['files'];photo_actual={p.relative_to(OUT/folder).as_posix()for p in(OUT/folder).rglob('*')if p.is_file()and p.name!='work-manifest.json'}
  if photo_actual!={r['path']for r in photo_files}:raise ValueError('photo archive membership differs '+folder)
  for f in photo_files:
   path=OUT/folder/f['path']
   if sha(path)!=f['sha256']or path.stat().st_size!=f['bytes']:raise ValueError('photo archive differs '+folder)
  photo_archive_counts[folder]=len(photo_files)
 source_review=load('source-independent-review.json')
 prior74=load('calibration-figure74-manifest.json')['frozenFilesSha256']
 for local,original in [('calibration-figure74-georeference.json','georeference.json'),('calibration-figure74-independent-review.json','independent-review.json')]:
  if sha(OUT/local)!=prior74[original]:raise ValueError('copied frozen Figure74 evidence differs '+local)
 for path in (OUT/'calibration-figure74-photo-work').rglob('*'):
  if path.is_file():
   original='image-registration-work/'+path.relative_to(OUT/'calibration-figure74-photo-work').as_posix()
   if sha(path)!=prior74[original]:raise ValueError('copied Figure74 photographic archive not pinned by its frozen cohort '+original)
 prior74review=load('calibration-figure74-independent-review.json')
 if prior74review['primaryLayerApproved']is not False or prior74review['geographicRegistrationVerified']is not False:raise ValueError('inherited Figure74 inference policy differs')
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
 prior_relation=load('calibration-figure74-photo-work/image-registration.json')
 if prior_relation['sourceImageSha256']!=sha(OUT/'calibration-figure73.jpeg')or prior_relation['targetImageSha256']!=sha(OUT/'image-registration-work/figure74-p154-xref176.jpeg')or prior_relation['geographicCoordinatesUsed']is not False or prior_relation['neighborhoodNameOrBoundaryGeometryUsed']is not False:raise ValueError('inherited photographic image identity/independence differs')
 prior_train=[q for q in prior_relation['records']if q['usableTextureMatch']and q['trainingPartition']];prior_held=[q for q in prior_relation['records']if q['usableTextureMatch']and not q['trainingPartition']]
 if(len(prior_relation['records']),len(prior_train),len(prior_held))!=(48,13,10):raise ValueError('inherited photo partition differs')
 prior_photo=np.linalg.lstsq(np.array([[*q['sourcePatchCenter'],1]for q in prior_train]),np.array([q['targetMatchedCenter']for q in prior_train]),rcond=None)[0];close(prior_photo,prior_relation['sourceToTargetAffineRows'],0);prior_inverse=np.linalg.inv(np.vstack((prior_photo.T,[0,0,1])));old_geo=load('calibration-figure74-georeference.json');close(prior_inverse,old_geo['figure74ToFigure73Homogeneous'],0);close(prior_inverse.T@cal,old_geo['composedFigure74PixelToEovRows'],0)
 prior_held_errors=[float(np.linalg.norm(np.array([*q['sourcePatchCenter'],1])@prior_photo-np.array(q['targetMatchedCenter'])))for q in prior_held];close(max(prior_held_errors),prior_relation['maximumHeldOutResidualTargetPixels'],1e-12)
 relation=load('image-registration-work/image-registration.json')
 if relation['sourceImageSha256']!=sha(OUT/'image-registration-work/figure74-p154-xref176.jpeg')or relation['targetImageSha256']!=sha(OUT/'figure75-p158-xref180.jpeg')or relation['geographicCoordinatesUsed']is not False or relation['neighborhoodNameOrBoundaryGeometryUsed']is not False:raise ValueError('new photo-only identity/independence differs')
 train=[q for q in relation['records']if q['usableTextureMatch']and q['trainingPartition']];held=[q for q in relation['records']if q['usableTextureMatch']and not q['trainingPartition']]
 if len(relation['records'])!=27 or(len(train),len(held))!=(6,7):raise ValueError('new photo partition differs')
 if relation['manualPreNccOrBlindPhysicalObservationClaimed']is not False:raise ValueError('unwarranted blind/pre-NCC visual independence claim')
 photo=np.linalg.lstsq(np.array([[*q['sourcePatchCenter'],1]for q in train]),np.array([q['targetMatchedCenter']for q in train]),rcond=None)[0];close(photo,relation['sourceToTargetAffineRows'],0);held_errors=[float(np.linalg.norm(np.array([*q['sourcePatchCenter'],1])@photo-np.array(q['targetMatchedCenter'])))for q in held];close(max(held_errors),relation['maximumHeldOutResidualTargetPixels'],1e-12)
 inverse=np.linalg.inv(np.vstack((photo.T,[0,0,1])));combined_inverse=prior_inverse@inverse;composed=combined_inverse.T@cal;geo=load('georeference.json')
 for actual,key in [(photo,'figure74ToFigure75PhotoAffineRows'),(inverse,'figure75ToFigure74Homogeneous'),(combined_inverse,'figure75ToFigure73Homogeneous'),(prior_photo,'inheritedFigure73ToFigure74PhotoAffineRows'),(prior_inverse,'inheritedFigure74ToFigure73Homogeneous'),(cal,'figure73PixelToEovRowsIndependentlyRefitted'),(composed,'composedFigure75PixelToEovRows')]:close(actual,geo[key],0)
 trace=load('source-pixel-trace.json');ring=trace['rings']['Reptéri lakótelep'];source=Polygon(ring);rgb=np.asarray(Image.open(OUT/'figure75-p158-xref180.jpeg').convert('RGB'));maxrgb=rgb.max(2);gap_paths=trace['sourceTextOverprintInferences'];inferred={tuple(q)for g in gap_paths for q in g['inferredPixelPath'][1:-1]};nonblack=[q for q in ring if maxrgb[q[1],q[0]]>45]
 if len(ring)!=366 or len(nonblack)!=20 or any(tuple(q)not in inferred for q in nonblack)or any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(ring,ring[1:])):raise ValueError('source vertex/gap/edge audit differs')
 if source_review['sourceContourFullyObserved']is not False or source_review['nonBlackInferredVertexCount']!=20:raise ValueError('source audit inference scope differs')
 dense=np.column_stack((np.array(ring),np.ones(len(ring))));via74_pixels=(dense@inverse.T)[:,:2];cal_pixels=(dense@combined_inverse.T)[:,:2];close(np.column_stack((via74_pixels,np.ones(len(via74_pixels))))@prior_inverse.T,dense@combined_inverse.T,1e-10);metric_points=dense@composed;sequential=np.column_stack((cal_pixels,np.ones(len(cal_pixels))))@cal;close(metric_points,sequential,1e-8);lon,lat=wgs.transform(metric_points[:,0],metric_points[:,1]);computed=np.column_stack((lon,lat));collection=load('source-inferred.geojson')
 if len(collection['features'])!=1:raise ValueError('unexpected feature count')
 f=collection['features'][0];world=shape(f['geometry']);actual=np.array(f['geometry']['coordinates'][0])
 if f['properties']['name']!='Reptéri lakótelep'or f['geometry']['type']!='Polygon'or len(f['geometry']['coordinates'])!=1 or not world.is_valid or world.interiors or actual.shape!=computed.shape:raise ValueError('transformed cell identity/topology differs')
 close(actual,computed,0);world_error=float(np.max(np.abs(actual-computed)))
 hull=MultiPoint([q['targetMatchedCenter']for q in train+held]).convex_hull
 if not hull.equals(shape(geo['observedTextureHullFigure75Pixels'])):raise ValueError('observed image hull differs')
 outside_hull=sum(not hull.covers(Point(x,y))for x,y in ring);outside_image=sum(not(0<=x<=955 and 0<=y<=1347)for x,y in via74_pixels);outside_original73=sum(not(0<=x<=1013 and 0<=y<=1433)for x,y in cal_pixels);max_hull=max(hull.distance(Point(x,y))for x,y in ring)
 if outside_hull!=geo['sourceVerticesOutsideMatchedTextureHull']or outside_image!=geo['sourceVerticesOutsideFigure74ImageRectangle']or outside_original73!=geo['sourceVerticesOutsideOriginalFigure73ImageRectangle']:raise ValueError('extrapolation count differs')
 close(max_hull,geo['maximumDistanceBeyondMatchedTextureHullSourcePixels'],1e-10)
 alternatives=load('source-inference-alternatives.json');alternative_checks=[]
 if len(alternatives['gaps'])!=4 or alternatives['sourceAlternativesAreUnselectedHypotheses']is not True:raise ValueError('source hypotheses scope differs')
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
 if n['id']!='osm:node:14084145693'or n['properties']['source']['osmId']in {c['osmNodeId']for c in controls}or n['properties']['source']['notUsedAsGeometryOrGeoreferencingControl']is not True or not name_inside:raise ValueError('current name/control/containment diagnostic differs')
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
 if p['sourceBoundaryInference']['gapCount']!=4 or p['sourceBoundaryInference']['inferredNonBlackVertexCount']!=20 or p['sourceBoundaryInference']['confidence']!='low'or p['sourceBoundaryInference']['alternativesPath']!=FINAL_REL+'/source-inference-alternatives.json':raise ValueError('source-inference policy differs')
 registry=load('registry-entry.json')
 if registry['path']!=FINAL_REL+'/source-inferred.geojson'or registry['reviewPath']!=FINAL_REL+'/independent-review.json'or registry['sha256']!=sha(OUT/'source-inferred.geojson')or registry['featureCount']!=1:raise ValueError('final registry path/hash differs')
 loo=[]
 for i,c in enumerate(controls):
  keep=[j for j in range(6)if j!=i];m=np.linalg.lstsq(design[keep],metric[keep],rcond=None)[0];movement=np.linalg.norm(np.column_stack((cal_pixels,np.ones(len(cal_pixels))))@m-metric_points,axis=1);row={'omittedControlId':c['id'],'maximumFigure75VertexDisplacementMeters':float(movement.max())};loo.append(row)
 close([q['maximumFigure75VertexDisplacementMeters']for q in loo],[q['maximumFigure75VertexDisplacementMeters']for q in geo['calibrationLeaveOneControlOut']],1e-8)
 js="""import{readFile}from'node:fs/promises';import{pathToFileURL}from'node:url';const{validateGeometry}=await import(pathToFileURL(process.argv[1]+'/scripts/neighborhoods/build.mjs'));const d=JSON.parse(await readFile(process.argv[2]+'/source-inferred.geojson','utf8'));process.stdout.write(JSON.stringify(d.features.map(f=>({id:f.id,...validateGeometry(f.geometry,f.bbox)}))));"""
 accepted=json.loads(subprocess.run(['node','--input-type=module','-e',js,str(ROOT),str(OUT)],check=True,capture_output=True,text=True).stdout)
 if len(accepted)!=1 or not accepted[0]['valid']:raise ValueError('actual project validator rejected cell')
 conversion=load('conversion-proof.json')
 if conversion['denseOriginalAndWorldVertexCountIncludingClosures']!=len(ring)or conversion['strictBlackSourceVertexCountIncludingClosure']!=346 or conversion['inferredNonBlackSourceVertexCount']!=20 or conversion['allSourcePixelsBlack']is not False:raise ValueError('conversion evidence scope differs')
 # The bounded research is not an alias list or completeness claim. Its
 # historical registry references are not opened by portable cohort replay.
 inventory=load('source-semantics-work/bounded-remaining-source-gaps.json');sem_manifest=load('source-semantics-work/manifest.json')
 for entry in sem_manifest['files']:
  path=OUT/'source-semantics-work'/entry['path']
  if sha(path)!=entry['sha256']or path.stat().st_size!=entry['bytes']:raise ValueError('semantic/inventory archive differs')
 if inventory['conditionalNextSubset']['name']!='Reptéri lakótelep'or inventory['conditionalNextSubset']['count']!=1 or inventory['conditionalNextSubset']['KülsőRákóczivárosStillPending']is not True or inventory['allKecskemetNamesOrSourcesExhausted']is not False or inventory['nationwideCompletenessVerified']is not False:raise ValueError('bounded inventory scope differs')
 if len(inventory['remainingLocalSourceCandidates'])!=inventory['conditionalRemainingFigure72LabelCandidatesCount']:raise ValueError('bounded inventory count differs')
 research=load('current-city-place-node-research.json')
 if research['sourcePbfSha256']!=PBF_SHA:raise ValueError('bounded name research PBF identity differs')
 research_nodes={q['id']:q for q in research['records']};exact=research_nodes[14084145693]
 if exact['coordinates']!=n['geometry']['coordinates']or exact['tags']!=n['properties']['source']['tags']:raise ValueError('bounded exact residential-name record differs')
 distinct_airport_nodes=[]
 for node_id in [984225132,5899728724]:
  q=research_nodes[node_id]
  if node_id in {c['osmNodeId']for c in controls}or node_id==n['properties']['source']['osmId']:raise ValueError('airport/base node used as residential-name/control')
  distinct_airport_nodes.append({'osmNodeId':node_id,'name':q['tags']['name'],'insideInferredResidentialCandidate':world.covers(Point(*q['coordinates'])),'treatedAsAliasOrControl':False})
 for key,value in [('sourceVerticesOutsideMatchedTextureHull',outside_hull),('sourceVerticesOutsideFigure74ImageRectangle',outside_image),('sourceVerticesOutsideOriginalFigure73ImageRectangle',outside_original73)]:
  if p['imageOverlapExtrapolation'][key]!=value or conversion[key]!=value:raise ValueError('output extrapolation metadata differs')
 qualitative=load('image-registration-work/post-preliminary-qualitative-photo-review.json')
 if qualitative['registrationModelAlreadyAvailableAtReview']is not True or qualitative['manualPreNccObservationClaimed']is not False or qualitative['separateBlindPhysicalReviewer']is not False:raise ValueError('qualitative photographic review independence scope differs')
 provenance=['input-manifest.json','generated-manifest.json','source-pixel-trace.json','source-semantics.json','source-independent-review.py','source-independent-review.json','source-inferred.geojson','source-inference-alternatives.json','georeference.json','conversion-proof.json','registry-entry.json','calibration-figure73-manifest.json','calibration-figure73-georeference.json','calibration-figure73-control-specification.json','calibration-figure73-control-roads.geojson','calibration-figure73-original-pbf-verification.json','calibration-figure73-prior-same-image-comparison.json','calibration-figure74-manifest.json','calibration-figure74-georeference.json','calibration-figure74-independent-review.json','calibration-figure74-photo-work/work-manifest.json','calibration-figure74-photo-work/image-registration.json','calibration-figure74-photo-work/direct-verification.json','current-name-points.geojson','current-name-original-pbf-proof.json','current-city-place-node-research.json','original-pbf-verification.json','verify-original-pbf.py','image-registration-work/work-manifest.json','image-registration-work/image-registration.json','image-registration-work/direct-verification.json','image-registration-work/post-preliminary-qualitative-photo-review.json','source-semantics-work/manifest.json','source-semantics-work/source-semantics-review.json','source-semantics-work/bounded-remaining-source-gaps.json','finalaudit-independent.py']
 result={'schemaVersion':1,'status':'PASS_FOR_ONE_EXPLICIT_SOURCE_GAP_AND_GEOGRAPHIC_INFERRED_CANDIDATE','logicalCohortPath':FINAL_REL,'independentOfSourceAndGeographicProducerCodeExecution':True,'producerSourceAndDeriveModulesImported':False,'photographicWorkProducedByThisReviewingAgent':True,'separateBlindPhysicalReviewer':False,'provenanceSha256':{name:sha(OUT/name)for name in provenance},'portableReplay':{'requiresExternalFrozenCohortDirectoryOrFullPbf':False,'requiresRepositoryProjectValidator':True,'allAuditProvenancePathsRelativeToCohort':True,'finalManifestExcludedFromOwnFingerprintAvoidingCycles':True,'historicalInventoryExternalReferencesPreservedWithoutRequiringThoseDirectories':True},'sourceContour':{'sourceVertexCountIncludingClosure':366,'sourceEdgeCount':365,'allSourceVerticesAndEdgesChecked':True,'strictBlackVerticesIncludingClosure':346,'explicitBlueTextOverprintNonBlackVertices':20,'gapCount':4,'sourceContourFullyObserved':False,'frameClosureOrUnlistedGapDetected':False,'sourceAndWorldHoles':0,'sourceScopeReview':'source-independent-review.json','allFourChosenGapWorldPathsAndEightUnselectedAlternativePathsChecked':True,'gapChecks':alternative_checks},'photographicRelations':{'inheritedFigure73ToFigure74':{'all48SearchesDirectlyCrossChecked':True,'trainingCount':13,'heldOutCount':10,'rejectedCount':25,'maximumHeldOutResidualTargetPixels':max(prior_held_errors)},'newFigure74ToFigure75':{'all27SearchesDirectlyCrossChecked':True,'trainingCount':6,'heldOutCount':7,'rejectedCount':14,'maximumHeldOutResidualTargetPixels':max(held_errors)},'bothWorkManifestsAndOriginalImageIdentitiesVerified':True,'photoArchiveFileCounts':photo_archive_counts,'newQualitativePhysicalReviewAfterPreliminaryAndModelAvailable':True,'newPreNccOrBlindManualObservationsClaimed':False,'separateBlindPhysicalReview':False,'geographicCoordinatesNamesOrQuarterGeometryUsed':False},'calibration':{'copiedFrozenFigure73AndFigure74EvidenceHashesMatch':True,'sixOriginalManualFigure73ImageObservationsPreserved':True,'originalMetricAffineIndependentlyRefitted':True,'controlResidualMeters':residual.tolist(),'priorManualObservationTransfersChecked':manual_transfers,'priorTransferExactlyReproducedArchivedRoundedDecimalFormula':True,'rawPdfFloatBoxVsArchivedFormulaMaximumSourcePixelDifference':max_raw_pdf_float_box_vs_archived_decimal_transfer,'excludedOldSameImageCandidateNodeId':excluded['osmNodeId'],'excludedOldCandidatePredictedSourcePixelRecomputed':predicted_excluded.tolist(),'excludedOldCandidateStillUnconfirmedOutsideInterpretationAndNotUsedInFit':True,'inheritedPbfProofBoundToExactCopiedRoadAndNameInputs':True,'freshOriginalPbfProofBoundToExactCurrentInputs':True,'freshOriginalPbfProofWayCount':23,'freshOriginalPbfProofCurrentNameCount':1,'freshOriginalPbfProofUniqueNodeCount':fresh['uniqueComparedNodeCount'],'fullOriginalPbfRereadByThisAudit':False,'inheritedGeographicRegistrationVerified':False},'conversion':{'bothPhotoTrainingAffinesAndBothInversesIndependentlyComputed':True,'figure75To74To73MatrixProductIndependentlyChecked':True,'metricCompositionAndSequentialConversionAgreeWithin1eMinus8Meters':True,'all366WorldVerticesAnd365EdgesChecked':True,'maximumWorldCoordinateDisagreementDegrees':world_error,'sourceVerticesOutsideObservedTextureHull':outside_hull,'sourceVerticesOutsideOriginalFigure74Image':outside_image,'sourceVerticesOutsideOriginalFigure73Image':outside_original73,'entirePerimeterOutsidePhotoHullAndBothInheritedImageFootprints':outside_hull==outside_image==outside_original73==366,'maximumDistanceBeyondTextureHullTargetPixels':max_hull,'fullGeographicFootprintValidated':False},'currentNameEvidence':{'originalPbfProofContainsExactNode':'osm:node:14084145693','pointInsideInferredCandidate':name_inside,'pointNotUsedAsControl':True,'airportBaseNodeDiagnostics':distinct_airport_nodes,'nameOccurrenceProvesCurrentExactExtent':False,'originalPbfRereadByThisAudit':False,'boundedPlaceNodeResearchIsNotAliasOrQuarterInventory':True},'sensitivityDiagnostics':{'leaveOneControlOut':loo,'notCalibratedAccuracyBounds':True},'actualProjectGeometryValidator':{'modulePath':'scripts/neighborhoods/build.mjs','moduleSha256':sha(ROOT/'scripts/neighborhoods/build.mjs'),'actualValidateGeometryExportCalled':True,'acceptedCount':1,'rejectedCount':0,'results':accepted},'sourceScope':{'selectedSmallRepteriResidentialSourceCell':True,'airportBaseOrBroadSzolnokihegyNotSubstituted':True,'mukertvarosProseNotAssignedWholeSzolnokihegyBoundary':True,'otherEconomicCellsNotRejectedForFunctionalUse':True},'boundedInventory':{'historicalSnapshotAndConditionalRepteriOnlySubsetPreserved':True,'conditionalRemainingSourceLabelCandidates':inventory['conditionalRemainingFigure72LabelCandidatesCount'],'kulsoRakoczivarosStillPending':True,'allKecskemetNamesOrSourcesExhausted':False,'nationwideCompletenessVerified':False},'primaryLayerApproved':False,'explicitInferredLayerApproved':True,'sourceRasterContourFullyVerified':False,'geographicRegistrationVerified':False,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,'rightsStatus':'Municipal source-map reuse rights unverified; ODbL-1.0 applies to OSM controls and current name.','approvalReason':'The recorded source/gap coordinates, both archived/local photographic relations, six-control metric fit, composed chain, all transformed vertices/edges and actual project admission pass. Four low-confidence source overprint continuations remain explicit inferences. Every perimeter vertex lies beyond observed photographic overlap and both inherited image footprints; geographic placement remains unvalidated. The photo producer is this reviewing agent, and the new physical review was post-preliminary/model; no separate blind independence is claimed. Preserve inferred-only status.'}
 target=OUT/'independent-review.json';data=encode(result)
 if check:
  if target.read_bytes()!=data:raise ValueError('independent audit stale')
 else:target.write_bytes(data)
 print(json.dumps({'mode':'check'if check else'build','status':result['status'],'worldVerticesChecked':366,'sourceBlackVertices':346,'sourceGapNonBlackVertices':20,'actualProjectAccepted':1,'outsideObservedTextureHull':outside_hull,'outsideOriginalFigure74Image':outside_image,'outsideOriginalFigure73Image':outside_original73,'maximumBeyondTextureHullPixels':max_hull},ensure_ascii=False))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');audit(parser.parse_args().check)
