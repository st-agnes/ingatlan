#!/usr/bin/env python3
"""Independent portable Figure73 final audit; does not import derive.py.

Replays source-only QA, verifies the original-PBF proof bindings, independently
fits geographic controls, checks every source/output vertex and edge, reruns
the actual project validator, and preserves failed/outside diagnostics.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
IMAGE_SHA='59cbd060c8010a396511cdec69848410b4fee8d6bd8e628500894b5e27565e9c'
PBF_SHA='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name):return json.loads((OUT/name).read_text())
def encoded(d):return(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()


def audit(check):
    import fitz
    import numpy as np
    import pyproj
    from pyproj import Transformer
    from PIL import Image
    from shapely.geometry import Polygon,Point,shape
    pyproj.network.set_network_enabled(False)
    if check and(OUT/'manifest.json').exists():
        final=load('manifest.json');files=final['frozenFilesSha256']
        if final['frozenFileCountExcludingManifest']!=len(files):raise ValueError('Final manifest file count differs')
        for name,expected in files.items():
            if sha(OUT/name)!=expected:raise ValueError('Changed final frozen file '+name)
    for manifest in ['input-manifest.json','generated-manifest.json']:
        for name,expected in load(manifest)['sha256'].items():
            if sha(OUT/name)!=expected:raise ValueError('Changed producer artifact '+name)
    source_result=subprocess.run([sys.executable,str(OUT/'review-source-pixels-independent.py'),'--check'],capture_output=True,text=True,check=True)
    source_review=load('independent-source-pixel-review.json')
    trace=load('source-pixel-trace.json');spec=load('control-specification.json');controls=spec['controls'];excluded=spec['excludedPriorComparisonCandidate']
    if len(controls)!=6 or spec['geographicRegistrationVerified']is not False:raise ValueError('Control design/status differs')
    if sha(OUT/'figure73-p143-xref172.jpeg')!=IMAGE_SHA or spec['sourceImageSha256']!=IMAGE_SHA:raise ValueError('Source-image identity differs')
    rgb=np.asarray(Image.open(OUT/'figure73-p143-xref172.jpeg').convert('RGB'));black=rgb.max(axis=2)<=45
    roads=load('control-roads.geojson')['features'];names=load('current-name-points.geojson')['features'];proof=load('original-pbf-verification.json')
    if proof['sourcePbfSha256']!=PBF_SHA or proof['wayCount']!=23 or proof['namePointCount']!=2:raise ValueError('Original PBF proof identity differs')
    for name,expected in proof['inputSha256'].items():
        if sha(OUT/name)!=expected:raise ValueError('PBF proof not bound to current source input')
    for key in ['allOriginalWayNodeSequencesAndCoordinatesMatch','allOriginalWayTagsVersionsAndTimestampsMatch','allOriginalNameNodeCoordinatesTagsVersionsAndTimestampsMatch','originalPbfWasActuallyReadToCreateThisProof']:
        if proof[key]is not True:raise ValueError('Incomplete original-PBF verification')
    nodes={};membership={}
    for f in roads:
        s=f['properties']['source'];refs=s['nodeRefs'];coords=f['geometry']['coordinates']
        if len(refs)!=len(coords)or s['geometryUnmodified']is not True:raise ValueError('Control source-way sequence differs')
        for node,coord in zip(refs,coords):
            if node in nodes and nodes[node]!=coord:raise ValueError('Inconsistent literal OSM control node')
            nodes[node]=coord;membership.setdefault(node,set()).add(f['id'])
    for c in controls+[excluded]:
        if nodes[c['osmNodeId']]!=c['coordinates']or membership[c['osmNodeId']]!=set(c['sourceWayIds']):raise ValueError('Control/source-road identity differs')
        if c['historicalToCurrentPhysicalPointIdentityIndependentlyVerified']is not False:raise ValueError('Unsupported historical physical identity claim')
    nameproof={r['osmNodeId']:r for r in proof['namePointRecords']}
    for f in names:
        s=f['properties']['source'];p=nameproof[s['osmId']]
        if not(f['geometry']['coordinates']==p['coordinates']and s['objectVersion']==p['objectVersion']and s['objectTimestamp']==p['objectTimestamp']and f['properties']['name']==p['name']):raise ValueError('Current-name source identity differs')
    # Independently validate the same-source image transfer. The earlier
    # manual observations are page-render pixels, not a reused map transform.
    doc=fitz.open(OUT/'source-pages143-144-147-153.pdf');page=doc[0]
    info=next(i for i in page.get_image_info(xrefs=True)if(i['width'],i['height'])==(1014,1434))
    if hashlib.sha256(doc.extract_image(info['xref'])['image']).hexdigest()!=IMAGE_SHA:raise ValueError('Archived PDF/source JPEG differs')
    old=np.asarray(Image.open(OUT/'prior-page143-render.png').convert('RGB'))
    pix=page.get_pixmap(matrix=fitz.Matrix(2,2));current=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,pix.n)
    x0,y0,x1,y1=info['bbox'];bounds=[int(np.ceil(x0*2))+1,int(np.ceil(y0*2))+1,int(np.floor(x1*2))-1,int(np.floor(y1*2))-1]
    l,t,r,b=bounds
    if old.shape!=current.shape or not np.array_equal(old[t:b,l:r],current[t:b,l:r]):raise ValueError('Earlier page-render observations do not share byte-identical displayed image pixels')
    archived_box=spec['sameImageControlTransferProof']['sourceImagePlacementPageBox']
    if max(abs(a-b)for a,b in zip(info['bbox'],archived_box))>1e-4:raise ValueError('Publisher page-image placement differs')
    prior=load('prior-same-image-comparison.json')
    if prior['source']['figure']!=73 or prior['source']['originalPdfPageOneBased']!=143 or prior['source']['sourcePdfSha256']!='83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939':raise ValueError('Prior observations refer to another source')
    old_controls=prior['comparisonMethod']['controls'];transferred=[]
    for c in controls+[excluded]:
        match=[o for o in old_controls if o[:2]==c['coordinates']]
        if not match:continue
        if len(match)!=1:raise ValueError('Ambiguous old manual observation')
        _,_,px,py=match[0]
        transferred_point=np.array([(px/2-94.4)/406.47*1014,(py/2-197.47802734375)/574.8499755859375*1434])
        error=float(np.max(np.abs(transferred_point-np.array(c['sourceImagePixel']))))
        if error>1e-9:raise ValueError('Same-image manual point transfer differs')
        transferred.append({'osmNodeId':c['osmNodeId'],'oldPageRenderPixel':[px,py],'sourceImagePixel':transferred_point.tolist(),'maximumCoordinateTransferDisagreementPixels':error,'usedInFit':c in controls})
    if sum(r['usedInFit']for r in transferred)!=4 or len(transferred)!=5:raise ValueError('Expected four prior fitted observations plus one excluded observation')
    # Refit geographical placement from source observations and literal nodes.
    eov=Transformer.from_crs(4326,23700,always_xy=True);wgs=Transformer.from_crs(23700,4326,always_xy=True)
    observed=np.array([c['sourceImagePixel']for c in controls]);metric=np.array([eov.transform(*c['coordinates'])for c in controls]);design=np.column_stack((observed,np.ones(len(observed))))
    affine=np.linalg.lstsq(design,metric,rcond=None)[0];reg=load('georeference.json')
    if np.max(np.abs(affine-np.array(reg['affineImagePixelToEovRows'])))>1e-7:raise ValueError('Independently fitted geographic transform differs')
    residual=np.linalg.norm(design@affine-metric,axis=1)
    if np.max(np.abs(residual-np.array(reg['controlResidualMeters'])))>1e-6:raise ValueError('Fitted residuals differ')
    inverse=np.linalg.inv(np.vstack([affine.T,[0,0,1]]));ep=(np.array([*eov.transform(*excluded['coordinates']),1])@inverse.T)[:2]
    ew=excluded['sourceImageInterpretationWindow'];inside=all(ew[k][0]<=ep[i]<=ew[k][1]for i,k in enumerate(['x','y']))
    diagnostic=reg['excludedPriorComparisonDiagnostic']
    if inside or diagnostic['insideOriginalInterpretationWindow']is not False or diagnostic['usedInFit']is not False or diagnostic['sourceFeatureIdentityUnconfirmed']is not True or np.max(np.abs(ep-np.array(diagnostic['newModelPredictedSourcePixel'])))>1e-7:raise ValueError('Excluded failed same-source candidate was not preserved faithfully')
    features=load('source-inferred.geojson')['features']
    if len(features)!=2 or {f['properties']['name']for f in features}!={'Árpádváros','Kossuthváros'}:raise ValueError('Output fine-source cell set differs')
    byname={f['properties']['name']:f for f in features};namepoints={f['properties']['name']:f for f in names};checks=[];world_polygons={};all_source=[];maximum_error=0.
    for name,ring in trace['rings'].items():
        pixels=np.array(ring,dtype=int)
        if ring[0]!=ring[-1]or any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(ring,ring[1:])):raise ValueError('Source circuit is open/non-neighbor')
        if any(not black[y,x]for x,y in ring):raise ValueError('Source circuit leaves actual JPEG black pixels')
        source=Polygon(ring)
        if not source.is_valid or source.interiors:raise ValueError('Original source circuit topology differs')
        fitted=np.column_stack((pixels,np.ones(len(pixels))))@affine;lon,lat=wgs.transform(fitted[:,0],fitted[:,1]);expected=np.column_stack((lon,lat))
        feature=byname[name];actual=np.array(feature['geometry']['coordinates'][0])
        if feature['geometry']['type']!='Polygon'or len(feature['geometry']['coordinates'])!=1 or actual.shape!=expected.shape:raise ValueError('Source vertices/rings missing or added')
        error=float(np.max(np.abs(expected-actual)))
        if error>1e-12:raise ValueError('An output vertex differs from its exact independently transformed source pixel')
        maximum_error=max(maximum_error,error);geo=shape(feature['geometry'])
        if not geo.is_valid or geo.interiors:raise ValueError('Output geometry topology differs')
        p=feature['properties']
        if not(p['boundaryKind']=='inferred_area'and p['candidateBoundaryKind']=='neighbourhood'and p['estimated']is True and p['canonicalNameIsNeighborhood']is False and p['geographicRegistrationVerified']is False and p['absoluteAccuracyMeters']is None and p['usableForAddressAssignment']is False):raise ValueError('Explicit inferred-only policy differs')
        if name=='Kossuthváros'and 'PDF144'not in p['sourceScopeNote']:raise ValueError('Northern-part/broader historical name scope caveat lost')
        point=namepoints[name];point_metric=eov.transform(*point['geometry']['coordinates']);point_image=(np.array([*point_metric,1])@inverse.T)[:2]
        pixel_distance=source.distance(Point(*point_image));metric_distance=Polygon(fitted).distance(Point(*point_metric));covered=geo.covers(shape(point['geometry']))
        if covered is not False or p['currentNameEvidence']['currentOsmPointCoveredByHistoricalEstimatedPolygon']is not False:raise ValueError('Outside modern name point was hidden or shifted into historical cell')
        checks.append({'name':name,'allDenseSourceAndOutputVerticesChecked':len(ring),'maxVertexCoordinateDisagreementDegrees':error,
                       'everyOutputEdgeJoinsExactlyTheCorrespondingConsecutiveSourcePixels':True,
                       'sourceAndWorldHoleCount':0,'noSourceFrameClosingEdgeOrGeometryRepair':True,
                       'modernNamePoint':{'osmPointId':point['id'],'coordinates':point['geometry']['coordinates'],
                                          'currentNameExistsInOriginalPbf':True,'coveredByHistoricalInferredSourceCell':False,
                                          'predictedSourceImagePixel':point_image.tolist(),'distanceOutsideSourcePolygonPixels':pixel_distance,
                                          'distanceOutsideSourcePolygonInEovMeters':metric_distance,'usedAsRegistrationControl':False,
                                          'nameOccurrenceDoesNotProveExtentCorrespondence':True}})
        world_polygons[name]=geo;all_source+=ring
    if world_polygons['Árpádváros'].intersection(world_polygons['Kossuthváros']).area!=0:raise ValueError('Output source-cell areas overlap')
    all_design=np.column_stack((np.array(all_source),np.ones(len(all_source))));base=all_design@affine;loo=[]
    for i,c in enumerate(controls):
        keep=[j for j in range(len(controls))if j!=i];model=np.linalg.lstsq(design[keep],metric[keep],rcond=None)[0];delta=np.linalg.norm(all_design@model-base,axis=1)
        result={'omittedControlId':c['id'],'omittedControlPredictionErrorMeters':float(np.linalg.norm(design[i]@model-metric[i])),
                'maximumSourceVertexDisplacementMeters':float(delta.max()),'meanSourceVertexDisplacementMeters':float(delta.mean())}
        stated=reg['modelSensitivity']['leaveOneControlOut'][i]
        if any(abs(result[k]-stated[k])>1e-6 for k in ['omittedControlPredictionErrorMeters','maximumSourceVertexDisplacementMeters','meanSourceVertexDisplacementMeters']):raise ValueError('Independent LOO sensitivity differs')
        loo.append(result)
    sd=[];st=[]
    for(x,y),(east,north)in zip(observed,metric):sd.extend([[x,y,1,0],[-y,x,0,1]]);st.extend([east,north])
    a,b,tx,ty=np.linalg.lstsq(np.array(sd),np.array(st),rcond=None)[0];similarity=np.array([[a,b],[b,-a],[tx,ty]]);delta=np.linalg.norm(all_design@similarity-base,axis=1)
    if abs(float(delta.max())-reg['modelSensitivity']['similarityVsAffineMaximumSourceVertexDisplacementMeters'])>1e-6:raise ValueError('Independent transform-family sensitivity differs')
    # Actual admission policy, in addition to Shapely/source-pixel validity.
    node_code="""import{readFile}from'node:fs/promises';import{pathToFileURL}from'node:url';const root=process.argv[1],folder=process.argv[2];const{validateGeometry}=await import(pathToFileURL(root+'/scripts/neighborhoods/build.mjs'));const d=JSON.parse(await readFile(folder+'/source-inferred.geojson','utf8'));process.stdout.write(JSON.stringify(d.features.map(f=>({id:f.id,name:f.properties.name,...validateGeometry(f.geometry,f.bbox)}))));"""
    validated=json.loads(subprocess.run(['node','--input-type=module','-e',node_code,str(ROOT),str(OUT)],capture_output=True,text=True,check=True).stdout)
    if len(validated)!=2 or not all(r['valid']for r in validated):raise ValueError('Actual project geometry admission failed: '+str(validated))
    registry=load('registry-entry.json')
    if registry['sha256']!=sha(OUT/'source-inferred.geojson')or registry['featureCount']!=2 or registry['propertyOverrides']['boundaryKind']!='inferred_area'or registry['propertyOverrides']['usableForAddressAssignment']is not False:raise ValueError('Registry draft geometry/status binding differs')
    for f in load('parking-full-graph-subset.geojson')['features']:
        s=f['properties']['source']
        if len(s['nodeRefs'])!=len(f['geometry']['coordinates'])or s['geometryUnmodified']is not True:raise ValueError('Research graph source-way geometry was clipped')
    provenance=['input-manifest.json','generated-manifest.json','source-pixel-trace.json','source-inferred.geojson','control-specification.json','control-roads.geojson','current-name-points.geojson','original-pbf-verification.json','independent-source-pixel-review.json','georeference.json','conversion-proof.json','registry-entry.json','audit-independent.py']
    result={'schemaVersion':1,'status':'PASS_FOR_TWO_EXPLICIT_INFERRED_SOURCE_CELLS','independentOfProducerCode':True,
            'provenanceSha256':{name:sha(OUT/name)for name in provenance},
            'portableReplay':{'requiresOriginalFullPdfOrPbfForDefaultReplay':False,'usesOnlyFrozenBatchAndProjectValidator':True,'finalManifestExcludedFromOwnReportFingerprint':True,
                              'directPbfRevalidationCommand':'PYTHONPATH=.local/geodata python3 verify-original-pbf.py --check','originalPbfWasDirectlyReadWhenProofWasCreated':True},
            'sourceEvidence':{'originalEmbeddedJpegBytesPreserved':True,'sourceImageSha256':IMAGE_SHA,'sourcePixelIndependentReview':'independent-source-pixel-review.json',
                              'actualBlackConnectedComponentIsSourcePixelSubsetOnly':True,'noGapFillingPixelAdditionFrameClosureOrRepair':True,
                              'denseSourceAndOutputVerticesChecked':len(all_source),'maximumVertexDisagreementDegrees':maximum_error,'allOutputEdgesVerified':True,
                              'sourceHoleCount':0,'worldHoleCount':0,'pairwiseSourceAndWorldAreaOverlap':0},
            'originalOsmIdentity':{'sourcePbfSha256':PBF_SHA,'completeControlWayCount':23,'currentFineNameNodeCount':2,
                                  'everyOriginalNodeCoordinateNodeSequenceTagVersionTimestampMatched':True,
                                  'directPbfObjectProof':'original-pbf-verification.json'},
            'sameSourceManualObservationTransfer':{'archivedPdfImageRectangleMatchesPriorPageRenderPixelForPixel':True,
                                                 'checkedRenderRectangle':bounds,'pixelMismatchCount':0,
                                                 'oldManualObservationsTransferred':transferred,'fittedOldObservationCount':4,'fittedNewObservationCount':2,
                                                 'otherFigureOrOtherBasemapTransformReused':False,'noOldGeographicTransformUsedToProduceOutput':True},
            'geographicFit':{'independentlyRefittedInCrs':'EPSG:23700','controlResidualMeters':residual.tolist(),
                             'rmsControlResidualMeters':float(np.sqrt(np.mean(residual**2))),
                             'exactHistoricalToCurrentPhysicalJunctionIdentitiesIndependentlyVerified':False,
                             'residualsDoNotVerifyIdentityOrBoundaryAccuracy':True},
            'excludedFailedPriorSameImageCandidate':{'osmNodeId':excluded['osmNodeId'],'originalSourceImagePixel':excluded['sourceImagePixel'],
                                                    'independentlyPredictedSourceImagePixel':ep.tolist(),'insideOriginalInterpretationWindow':inside,
                                                    'sourceFeatureIdentityUnconfirmed':True,'usedInFit':False,'acceptedAsIndependentValidationControl':False},
            'modelSensitivity':{'leaveOneControlOut':loo,'similarityVsAffineMaximumSourceVertexDisplacementMeters':float(delta.max()),
                                'similarityVsAffineMeanSourceVertexDisplacementMeters':float(delta.mean()),'diagnosticNotCalibratedErrorBound':True},
            'featureChecks':checks,
            'actualProjectGeometryValidator':{'modulePath':'scripts/neighborhoods/build.mjs','moduleSha256':sha(ROOT/'scripts/neighborhoods/build.mjs'),
                                              'actualValidateGeometryExportCalled':True,'results':validated,'acceptedCount':2,'rejectedCount':0},
            'sourceScopeDecision':{'fineSourceNames':['Árpádváros','Kossuthváros'],'arpadNotKülsoArpadvaros':True,
                                   'kossuthSourceCellDefinitionPdf153Preserved':True,'pdf144NorthernPartCautionPreserved':True,
                                   'broaderHistoricalOrCurrentKossuthExtentEquivalenceAsserted':False,
                                   'bothModernNamePointsOutsideTheHistoricalSourceCells':True,
                                   'neitherFitNorContourShiftedToModernNamePoints':True},
            'parkingRoadGraph':{'usedToGenerateBoundaryCoordinates':False,'historicalParkingZigzagTakenFromActualClosedSourceContour':True,
                                'unresolvedModernGraphChainNotReplacedWithShortestPathOrInventedConnector':True},
            'primaryLayerApproved':False,'explicitInferredLayerApproved':True,'geographicRegistrationVerified':False,
            'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,
            'approvalReason':'The exact source-image contours, same-image observation transfer, complete OSM inputs, all transformed output vertices/edges and actual project admission are verified. Six historical-to-modern road-center identities remain manually interpreted, and the excluded older candidate fails its original interpretation window. Both current name nodes lie outside their respective historical source cells. Preserve these concrete scope/registration uncertainties in the inferred layer; no current/full historical extent or address assignment is approved.'}
    target=OUT/'independent-review.json';data=encoded(result)
    if check:
        if not target.exists()or target.read_bytes()!=data:raise ValueError('Independent final review stale or missing')
    else:target.write_bytes(data)
    print(json.dumps({'mode':'check'if check else'build','status':result['status'],'outputVertices':len(all_source),'actualProjectAccepted':2,'outsideCurrentNamePoints':2,'excludedOldCandidatePass':False,'maximumLooVertexDisplacementMeters':max(r['maximumSourceVertexDisplacementMeters']for r in loo)},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');audit(p.parse_args().check)
