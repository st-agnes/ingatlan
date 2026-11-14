#!/usr/bin/env python3
"""Portable independent Figure76 final audit; no producer imports.

Direct sliding-window photographic NCC verifies the producer's FFT match data.
Independent fits, inverse/composed transforms, every source/output vertex and
edge, extrapolation counts and the real project admission policy are checked.
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
IMAGE73_SHA='59cbd060c8010a396511cdec69848410b4fee8d6bd8e628500894b5e27565e9c'
IMAGE76_SHA='9afccf14486eb5ed86581d07f9a588da4b53df6fa0c47cdbcaf6f667659055cd'
CAL_MANIFEST_SHA='ccb04d4774e71a3cc3d3d35f9ce5050214134875dbc406236738bebdcd6363fc'
PBF_SHA='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name):return json.loads((OUT/name).read_text())
def encoded(d):return(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()


def independent_ncc(registration):
    import numpy as np
    from PIL import Image
    from numpy.lib.stride_tricks import sliding_window_view
    source=Image.open(OUT/'figure73-p143-xref172.jpeg').convert('L')
    target=np.asarray(Image.open(OUT/'figure76-p161-xref184.jpeg').convert('L'),dtype=float)
    rows=[];max_coefficient_error=0.;max_center_error=0.
    for record in registration['records']:
        left,top,right,bottom=record['sourcePatchBox'];size=record['targetTemplateSize']
        if(right-left,bottom-top)!=(64,64)or size!=69:raise ValueError('Unexpected source/template patch size')
        center=[(left+right-1)/2,(top+bottom-1)/2]
        if center!=record['sourcePatchCenter']:raise ValueError('Source patch center differs')
        template=np.asarray(source.crop((left,top,right,bottom)).resize((size,size),Image.Resampling.BICUBIC),dtype=float)
        template=template-template.mean();template_norm=np.sqrt(np.sum(template*template))
        lx,ly,rx,ry=record['targetSearchBox'];region=target[ly:ry,lx:rx]
        # A direct, strided-window dot product and direct window sums provide
        # an independent numeric implementation of normalized correlation.
        windows=sliding_window_view(region,(size,size))
        sums=windows.sum(axis=(-1,-2));squares=np.einsum('ijxy,ijxy->ij',windows,windows,optimize=False)
        variance=np.maximum(squares-sums*sums/(size*size),0)
        numerator=np.einsum('ijxy,xy->ij',windows,template,optimize=False)
        ncc=numerator/np.maximum(np.sqrt(variance)*template_norm,1e-9)
        py,px=np.unravel_index(np.argmax(ncc),ncc.shape);coefficient=float(ncc[py,px])
        def delta(before,middle,after):
            denominator=before-2*middle+after
            return float(np.clip(.5*(before-after)/denominator,-.5,.5))if abs(denominator)>1e-12 else 0.
        dx=delta(*ncc[py,px-1:px+2])if 0<px<ncc.shape[1]-1 else 0.
        dy=delta(*ncc[py-1:py+2,px])if 0<py<ncc.shape[0]-1 else 0.
        match=np.array([lx+px+dx+(size-1)/2,ly+py+dy+(size-1)/2])
        coefficient_error=abs(coefficient-record['normalizedCrossCorrelation'])
        center_error=float(np.max(np.abs(match-np.array(record['targetMatchedCenter']))))
        if coefficient_error>1e-9 or center_error>1e-6:raise ValueError('Independent direct NCC disagrees with archived match '+record['id'])
        usable=coefficient>=registration['usabilityThresholdNcc']
        if usable!=record['usableTextureMatch']:raise ValueError('NCC threshold selection differs')
        row,col=[int(v)for v in record['id'][1:].split('c')]
        if record['trainingPartition']!=((row+col)%2==0):raise ValueError('Image-only train/holdout partition differs')
        max_coefficient_error=max(max_coefficient_error,coefficient_error);max_center_error=max(max_center_error,center_error)
        rows.append({'id':record['id'],'directNcc':coefficient,'directMatchedCenter':match.tolist(),'usable':usable,
                     'training':record['trainingPartition'],'maximumCenterDisagreementPixels':center_error})
    return rows,max_coefficient_error,max_center_error


def audit(check):
    import fitz
    import numpy as np
    import pyproj
    from pyproj import Transformer
    from PIL import Image
    from shapely.geometry import Polygon,Point,MultiPoint,shape
    pyproj.network.set_network_enabled(False)
    if check and(OUT/'manifest.json').exists():
        final=load('manifest.json');files=final['frozenFilesSha256']
        if final['frozenFileCountExcludingManifest']!=len(files):raise ValueError('Final manifest file count differs')
        for name,expected in files.items():
            if sha(OUT/name)!=expected:raise ValueError('Changed final frozen file '+name)
    for manifest in ['input-manifest.json','generated-manifest.json']:
        for name,expected in load(manifest)['sha256'].items():
            if sha(OUT/name)!=expected:raise ValueError('Changed producer input/output '+name)
    if sha(OUT/'figure73-p143-xref172.jpeg')!=IMAGE73_SHA or sha(OUT/'figure76-p161-xref184.jpeg')!=IMAGE76_SHA:raise ValueError('Source JPEG identity differs')
    pdf=fitz.open(OUT/'source-pages161-162.pdf');info=next(i for i in pdf[0].get_image_info(xrefs=True)if(i['width'],i['height'])==(1702,1204))
    if hashlib.sha256(pdf.extract_image(info['xref'])['image']).hexdigest()!=IMAGE76_SHA:raise ValueError('Archived PDF does not preserve exact publisher JPEG')
    prose=' '.join((pdf[0].get_text()+' '+pdf[1].get_text()).split())
    if 'A városrész három meghatározó egységre osztható: Külső Árpádváros, Mezeiváros és Ürgés.'not in prose:raise ValueError('Three distinct source units lack archived explicit prose')
    if sha(OUT/'calibration-figure73-manifest.json')!=CAL_MANIFEST_SHA:raise ValueError('Copied frozen calibration manifest differs')
    prior_manifest=load('calibration-figure73-manifest.json')
    copy_map={'georeference.json':'calibration-figure73-georeference.json','control-specification.json':'calibration-figure73-control-specification.json',
              'control-roads.geojson':'calibration-figure73-control-roads.geojson','original-pbf-verification.json':'calibration-figure73-original-pbf-verification.json',
              'figure73-p143-xref172.jpeg':'figure73-p143-xref172.jpeg'}
    for old,copied in copy_map.items():
        if sha(OUT/copied)!=prior_manifest['frozenFilesSha256'][old]:raise ValueError('Copied calibration input differs from frozen Figure73 '+old)
    proof=load('original-pbf-verification.json')
    if proof['sourcePbfSha256']!=PBF_SHA or proof['wayCount']!=23 or proof['namePointCount']!=1:raise ValueError('New original-PBF proof identity differs')
    for name,expected in proof['inputSha256'].items():
        if sha(OUT/name)!=expected:raise ValueError('PBF proof binding differs')
    for flag in ['allOriginalWayNodeSequencesAndCoordinatesMatch','allOriginalWayTagsVersionsAndTimestampsMatch','allOriginalNameNodeCoordinatesTagsVersionsAndTimestampsMatch','originalPbfWasActuallyReadToCreateThisProof']:
        if proof[flag]is not True:raise ValueError('Incomplete original-PBF source verification')
    roads=load('calibration-figure73-control-roads.geojson')['features'];nodes={};membership={}
    for f in roads:
        s=f['properties']['source'];refs=s['nodeRefs'];coordinates=f['geometry']['coordinates']
        if len(refs)!=len(coordinates)or s['geometryUnmodified']is not True:raise ValueError('A full control source-way sequence differs')
        for n,c in zip(refs,coordinates):
            if n in nodes and nodes[n]!=c:raise ValueError('Conflicting original control node')
            nodes[n]=c;membership.setdefault(n,set()).add(f['id'])
    specification=load('calibration-figure73-control-specification.json');controls=specification['controls'];excluded=specification['excludedPriorComparisonCandidate']
    if len(controls)!=6:raise ValueError('Inherited six-control design differs')
    for c in controls+[excluded]:
        if nodes[c['osmNodeId']]!=c['coordinates']or membership[c['osmNodeId']]!=set(c['sourceWayIds']):raise ValueError('Inherited control/source node identity differs')
        if c['historicalToCurrentPhysicalPointIdentityIndependentlyVerified']is not False:raise ValueError('Unsupported historical physical-point identity claim')
    eov=Transformer.from_crs(4326,23700,always_xy=True);wgs=Transformer.from_crs(23700,4326,always_xy=True)
    control_points=np.array([c['sourceImagePixel']for c in controls]);metric=np.array([eov.transform(*c['coordinates'])for c in controls]);design73=np.column_stack((control_points,np.ones(6)))
    calibration=np.linalg.lstsq(design73,metric,rcond=None)[0];prior=load('calibration-figure73-georeference.json')
    if not np.array_equal(calibration,np.array(prior['affineImagePixelToEovRows'])):raise ValueError('Independent inherited geographic calibration fit differs')
    residuals=np.linalg.norm(design73@calibration-metric,axis=1)
    if np.max(np.abs(residuals-np.array(prior['controlResidualMeters'])))>1e-6:raise ValueError('Inherited fit residuals differ')
    cal_inverse=np.linalg.inv(np.vstack((calibration.T,[0,0,1])))
    excluded_prediction=(np.array([*eov.transform(*excluded['coordinates']),1])@cal_inverse.T)[:2]
    ew=excluded['sourceImageInterpretationWindow'];excluded_inside=all(ew[k][0]<=excluded_prediction[i]<=ew[k][1]for i,k in enumerate(['x','y']))
    if excluded_inside or prior['excludedPriorComparisonDiagnostic']['usedInFit']is not False or prior['excludedPriorComparisonDiagnostic']['sourceFeatureIdentityUnconfirmed']is not True:raise ValueError('Inherited failed candidate/status not retained')
    registration=load('image-registration.json')
    if registration['sourceImageSha256']!=IMAGE73_SHA or registration['targetImageSha256']!=IMAGE76_SHA or registration['geographicCoordinatesUsed']is not False or registration['neighborhoodNameOrBoundaryGeometryUsed']is not False:raise ValueError('Image relation mixes geographic/semantic inputs')
    correlation_rows,max_coefficient_error,max_center_error=independent_ncc(registration)
    train=[r for r in registration['records']if r['usableTextureMatch']and r['trainingPartition']]
    held=[r for r in registration['records']if r['usableTextureMatch']and not r['trainingPartition']]
    if len(train)!=10 or len(held)!=10:raise ValueError('Expected ten fitted plus ten held-out image matches')
    # Refit directly from independently revalidated frozen match pairs, never
    # from the producer's affine coefficients or a geographic prediction.
    image_design=np.array([[*r['sourcePatchCenter'],1]for r in train]);image_target=np.array([r['targetMatchedCenter']for r in train])
    image_affine=np.linalg.lstsq(image_design,image_target,rcond=None)[0]
    if not np.array_equal(image_affine,np.array(registration['sourceToTargetAffineRows'])):raise ValueError('Independent image-pair affine fit differs')
    image_holdout=[]
    for r in held:
        error=float(np.linalg.norm(np.array([*r['sourcePatchCenter'],1])@image_affine-np.array(r['targetMatchedCenter'])))
        if abs(error-r['affinePredictionResidualPixels'])>1e-10:raise ValueError('Independent held-out image prediction differs')
        image_holdout.append({'id':r['id'],'residualTargetPixels':error,'usedInImageFit':False})
    inverse=np.linalg.inv(np.vstack((image_affine.T,[0,0,1])));composed=inverse.T@calibration
    geo_registration=load('georeference.json')
    for actual,key in [(image_affine,'sourceFigure73ImageToFigure76ImageAffineRows'),(inverse,'sourceFigure76ImageToFigure73ImageHomogeneous'),(composed,'composedFigure76PixelToEovRows')]:
        if not np.array_equal(actual,np.array(geo_registration[key])):raise ValueError('Inverse/composed source-pixel mapping differs')
    # Previously measured physical-feature points were not fitted/tuned to NCC.
    manual=load('independent-physical-landmarks.json');manual_check=[]
    for point in manual['landmarks']:
        predicted=np.array([*point['figure73Pixel'],1])@image_affine;delta=predicted-np.array(point['figure76Pixel'])
        half=point['manualInterpretationHalfWidthPixels73']*np.abs(image_affine[:2,:]).sum(axis=0)+point['manualInterpretationHalfWidthPixels76']
        if not np.all(np.abs(delta)<=half):raise ValueError('Independently measured physical landmark conflicts with image model')
        manual_check.append({'id':point['id'],'manualSourcePixel':point['figure73Pixel'],'manualTargetPixel':point['figure76Pixel'],
                             'predictedTargetPixel':predicted.tolist(),'distanceTargetPixels':float(np.linalg.norm(delta)),
                             'withinPreviouslyDeclaredCombinedManualInterpretation':True,'manualPointAdjustedToModel':False})
    trace=load('source-pixel-rings.json');rgb=np.asarray(Image.open(OUT/'figure76-p161-xref184.jpeg').convert('RGB'));value=rgb.max(axis=2)
    if trace['sourceImageSha256']!=IMAGE76_SHA or trace['sourceImageSize']!=[1702,1204]:raise ValueError('Source-pixel trace image identity differs')
    features=load('source-inferred.geojson')['features'];byname={f['properties']['name']:f for f in features};expected=['Külső Árpádváros','Mezeiváros','Ürgés']
    if list(trace['rings'])!=expected or set(byname)!=set(expected)or len(features)!=3:raise ValueError('Fine-source cell set differs')
    hull=MultiPoint([r['targetMatchedCenter']for r in train+held]).convex_hull
    if not hull.equals(shape(geo_registration['matchedTextureHullFigure76Pixels'])):raise ValueError('Observed texture coverage hull differs')
    names=load('current-name-points.geojson')['features']
    if len(names)!=1 or names[0]['id']!='osm:node:984225142'or names[0]['properties']['name']!='Ürgés':raise ValueError('An unsupported name point/alias appeared')
    nameproof=proof['namePointRecords'][0];s=names[0]['properties']['source']
    if names[0]['geometry']['coordinates']!=nameproof['coordinates']or s['objectVersion']!=nameproof['objectVersion']or s['objectTimestamp']!=nameproof['objectTimestamp']:raise ValueError('Ürgés source name-point metadata differs')
    polygons={};world_polygons={};records=[];all_pixels=[];vertex_count=0;maximum_error=0.
    for name in expected:
        ring=trace['rings'][name]
        if ring[0]!=ring[-1]or any(not isinstance(x,int)or not isinstance(y,int)or not(0<=x<1702 and 0<=y<1204)for x,y in ring):raise ValueError('Open or nonliteral source circuit')
        if any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(ring,ring[1:]))or any(value[y,x]>45 for x,y in ring):raise ValueError('A nonblack or non-neighbor source segment appears')
        frame=min(min(x,y,1701-x,1203-y)for x,y in ring)
        if frame<=0:raise ValueError('Source-frame-dependent circuit')
        source=Polygon(ring)
        if not source.is_valid or source.interiors:raise ValueError('Invalid original source topology')
        pixels=np.array(ring);dense=np.column_stack((pixels,np.ones(len(ring))));cal_pixels=(dense@inverse.T)[:,:2]
        metric_points=dense@composed;sequential_metric=np.column_stack((cal_pixels,np.ones(len(ring))))@calibration
        if np.max(np.abs(metric_points-sequential_metric))>1e-8:raise ValueError('Sequential/composed geographic mapping differs')
        lon,lat=wgs.transform(metric_points[:,0],metric_points[:,1]);computed=np.column_stack((lon,lat));f=byname[name]
        if f['geometry']['type']!='Polygon'or len(f['geometry']['coordinates'])!=1:raise ValueError('Output rings were added or removed')
        actual=np.array(f['geometry']['coordinates'][0]);world=shape(f['geometry'])
        if actual.shape!=computed.shape or not world.is_valid or world.interiors:raise ValueError('Output source vertices/topology differs')
        error=float(np.max(np.abs(actual-computed)))
        if error>1e-12:raise ValueError('A world vertex does not match its independently composed source pixel')
        maximum_error=max(maximum_error,error);vertex_count+=len(ring)
        outside_image=sum(not(0<=x<=1013 and 0<=y<=1433)for x,y in cal_pixels)
        outside_hull=sum(not hull.covers(Point(x,y))for x,y in ring);max_distance=max(hull.distance(Point(x,y))for x,y in ring)
        claimed=next(r for r in geo_registration['overlapExtrapolationBySourceCell']if r['name']==name)
        if outside_image!=claimed['outsideCalibrationImageRectangleVertexCount']or outside_hull!=claimed['outsideMatchedTextureHullVertexCount']or abs(max_distance-claimed['maximumSourcePixelDistanceBeyondMatchedTextureHull'])>1e-7:raise ValueError('Extrapolated source extent was not faithfully recorded')
        p=f['properties']
        if not(p['boundaryKind']=='inferred_area'and p['estimated']is True and p['canonicalNameIsNeighborhood']is False and p['absoluteAccuracyMeters']is None and p['geographicRegistrationVerified']is False and p['usableForAddressAssignment']is False):raise ValueError('Inferred-only status changed')
        current=names[0]if name=='Ürgés'else None
        covered=world.covers(shape(current['geometry']))if current else None
        if name=='Ürgés'and(covered is not True or p['currentNameEvidence']['currentNameIndependentlyConfirmed']is not True):raise ValueError('Ürgés name-point diagnostic differs')
        if current is None and(p['currentNameEvidence']['osmPointId']is not None or p['currentNameEvidence']['currentNameIndependentlyConfirmed']is not False):raise ValueError('Unknown exact current fine name was silently promoted')
        polygons[name]=source;world_polygons[name]=world;all_pixels+=ring
        records.append({'name':name,'allOriginalAndWorldVerticesChecked':len(ring),'everyDenseVertexMaxRgb':max(int(value[y,x])for x,y in ring),
                        'closedActualBlack8NeighborCircuit':True,'minimumDistanceFromImageFramePixels':frame,'sourceAndWorldHoles':0,
                        'maxIndependentWorldCoordinateDisagreementDegrees':error,'allWorldEdgesMatchConsecutiveOriginalSourcePixels':True,
                        'verticesOutsideOriginalFigure73Image':int(outside_image),'verticesOutsideObservedTextureHull':int(outside_hull),
                        'maximumDistanceBeyondObservedTextureHullTargetPixels':max_distance,
                        'currentExactNamePointStatus':'original PBF Ürgés point inside; not used in registration'if current else'unknown exact current name point; no alias invented',
                        'currentNamePointInsideHistoricalEstimatedCell':covered})
    if vertex_count!=4635:raise ValueError('Original dense vertex count differs')
    overlaps=[]
    for i,a in enumerate(expected):
        for b in expected[i+1:]:
            source_area=polygons[a].intersection(polygons[b]).area;world_area=world_polygons[a].intersection(world_polygons[b]).area
            if source_area!=0 or world_area!=0:raise ValueError('Source/world cell interiors overlap')
            overlaps.append({'a':a,'b':b,'sourceIntersectionArea':source_area,'worldIntersectionArea':world_area})
    js="""import{readFile}from'node:fs/promises';import{pathToFileURL}from'node:url';const root=process.argv[1],folder=process.argv[2];const{validateGeometry}=await import(pathToFileURL(root+'/scripts/neighborhoods/build.mjs'));const d=JSON.parse(await readFile(folder+'/source-inferred.geojson','utf8'));process.stdout.write(JSON.stringify(d.features.map(f=>({id:f.id,name:f.properties.name,...validateGeometry(f.geometry,f.bbox)}))));"""
    validated=json.loads(subprocess.run(['node','--input-type=module','-e',js,str(ROOT),str(OUT)],capture_output=True,text=True,check=True).stdout)
    if len(validated)!=3 or not all(r['valid']for r in validated):raise ValueError('Actual project geometry admission failed')
    registry=load('registry-entry.json')
    if registry['featureCount']!=3 or registry['sha256']!=sha(OUT/'source-inferred.geojson')or registry['propertyOverrides']['boundaryKind']!='inferred_area':raise ValueError('Registry draft not bound to exact inferred geometry')
    # Sensitivity is diagnostic only, especially outside measured image overlap.
    all_dense=np.column_stack((np.array(all_pixels),np.ones(len(all_pixels))));all_cal=(all_dense@inverse.T)[:,:2];cal_design=np.column_stack((all_cal,np.ones(len(all_cal))));base=all_dense@composed
    metric_loo=[]
    for i,c in enumerate(controls):
        keep=[j for j in range(6)if j!=i];model=np.linalg.lstsq(design73[keep],metric[keep],rcond=None)[0]
        changes=np.linalg.norm(cal_design@model-base,axis=1)
        metric_loo.append({'omittedRoadControlId':c['id'],'maximumFigure76SourceVertexDisplacementMeters':float(changes.max())})
    image_loo=[]
    for i,r in enumerate(train):
        keep=[j for j in range(len(train))if j!=i];model=np.linalg.lstsq(image_design[keep],image_target[keep],rcond=None)[0]
        inv=np.linalg.inv(np.vstack((model.T,[0,0,1])));changes=np.linalg.norm(all_dense@(inv.T@calibration)-base,axis=1)
        image_loo.append({'omittedTexturePatchId':r['id'],'maximumFigure76SourceVertexDisplacementMeters':float(changes.max())})
    provenance=['input-manifest.json','generated-manifest.json','image-registration.json','independent-physical-landmarks.json','independent-physical-landmark-model-check.json','source-pixel-rings.json','source-inferred.geojson','calibration-figure73-manifest.json','calibration-figure73-georeference.json','calibration-figure73-control-specification.json','calibration-figure73-control-roads.geojson','original-pbf-verification.json','current-name-points.geojson','georeference.json','conversion-proof.json','registry-entry.json','finalaudit-independent.py']
    result={'schemaVersion':1,'status':'PASS_FOR_THREE_EXPLICIT_INFERRED_SOURCE_CELLS','independentOfProducerCode':True,
            'provenanceSha256':{name:sha(OUT/name)for name in provenance},
            'portableReplay':{'requiresExternalFrozen73Or77Directory':False,'requiresFullOriginalPdfOrPbfForDefaultAudit':False,
                              'usesCopiedPinnedCalibrationInputsAndProof':True,'finalManifestNotHashedInOwnReportAvoidingCycles':True},
            'originalSourceEvidence':{'figure':76,'originalImageSha256':IMAGE76_SHA,'archivedPublisherEmbeddedJpegBytesExactlyPreserved':True,
                                      'threeSeparateNamedFineUnitsExplicitInArchivedPdf161':True,'groupNotDuplicatedAsEachFineName':True,
                                      'everyDensePointActualBlackMaxRgb45OrLess':True,'everySourceEdge8Neighbor':True,
                                      'noFrameClosureGapFillLabelCrossingPixelAdditionRepairBufferOrSimplification':True,
                                      'sourceAndWorldInteriorRingCount':0,'allSourceAndWorldVerticesChecked':vertex_count,
                                      'maximumCoordinateDisagreementDegrees':maximum_error,'pairwiseAreaOverlapChecks':overlaps},
            'independentPhotographicNcc':{'numericMethod':'Direct strided-window dot products and window sum/square normalization, independently implemented instead of the producer FFT convolution.',
                                         'allSearchPatchCountDirectlyRecomputed':len(correlation_rows),'usableMatchCount':len(train)+len(held),
                                         'trainingCount':len(train),'heldOutCount':len(held),'usableNccThreshold':registration['usabilityThresholdNcc'],
                                         'maximumNccCoefficientDisagreement':max_coefficient_error,'maximumPeakCenterDisagreementPixels':max_center_error,
                                         'affineIndependentlyFittedFromRevalidatedImagePairs':True,'heldOutResiduals':image_holdout,
                                         'maximumHeldOutResidualTargetPixels':max(r['residualTargetPixels']for r in image_holdout),
                                         'geographicCoordinatesNamesAndBoundaryRingsUsedByImageMatch':False,
                                         'independentManualPhysicalFeatureChecks':manual_check},
            'inheritedMetricCalibration':{'copiedFrozenFigure73ManifestSha256':CAL_MANIFEST_SHA,'copiedCalibrationFileHashesMatchFrozenSourceManifest':True,
                                         'sixLiteralOsmRoadNodeControlsIndependentlyRefittedInCrs':'EPSG:23700','controlResidualMeters':residuals.tolist(),
                                         'originalControlWayPbfVerificationCount':23,'newCurrentNamePointPbfVerificationCount':1,
                                         'exactHistoricalToModernPhysicalPointIdentityVerified':False,
                                         'geographicRegistrationVerified':False,
                                         'excludedFailedPriorCandidate':{'osmNodeId':excluded['osmNodeId'],'predictedSource73Pixel':excluded_prediction.tolist(),
                                                                         'insideOriginalInterpretationWindow':excluded_inside,'sourceFeatureIdentityUnconfirmed':True,'usedInFitOrAsValidatedControl':False}},
            'conversion':{'inverseImageAffineIndependentlyRecomputed':True,'composedFigure76PixelToEovIndependentlyRecomputed':True,
                          'sequentialAndComposedCoordinatesAgreeWithin1eMinus8Meters':True,'all4635WorldVerticesAndEdgesChecked':True},
            'sourceCellChecks':records,
            'actualProjectGeometryValidator':{'modulePath':'scripts/neighborhoods/build.mjs','moduleSha256':sha(ROOT/'scripts/neighborhoods/build.mjs'),
                                              'actualValidateGeometryExportCalled':True,'acceptedCount':3,'rejectedCount':0,'results':validated},
            'sensitivityDiagnostics':{'inheritedRoadControlLeaveOneOut':metric_loo,'imageTrainingMatchLeaveOneOut':image_loo,'notCalibratedAbsoluteErrorBounds':True},
            'limits':{'photographicImageAgreementValidatesOnlyObservedOverlap':True,'fullFrameOrGeographicValidationClaimed':False,
                      'largeSouthernWesternEasternExtrapolationExplicit':True,'unknownCurrentMezeivarosAndKulsoArpadvarosExactOsmNamePointsPreserved':True,
                      'urgesNamePointNotUsedAsControlOrBoundaryGeometry':True,'inheritedSource73PhysicalControlUncertaintyNotRemovedByImageMatching':True},
            'primaryLayerApproved':False,'explicitInferredLayerApproved':True,'geographicRegistrationVerified':False,
            'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,
            'approvalReason':'Original source contours, observed common photographic texture, copied calibration provenance, every composed world vertex/edge and actual project admission are verified. The inherited Figure73 physical road-point identities remain unvalidated and its failed excluded candidate remains failed. Thousands of source vertices lie outside the observed texture hull and many outside the Figure73 image itself. This is an explicit inferred extension, with no full geographic registration or address-assignment approval.'}
    target=OUT/'independent-review.json';data=encoded(result)
    if check:
        if not target.exists()or target.read_bytes()!=data:raise ValueError('Final independent Figure76 audit stale or missing')
    else:target.write_bytes(data)
    print(json.dumps({'mode':'check'if check else'build','status':result['status'],'directlyRecomputedNccSearches':len(correlation_rows),'imageFitAndHeldout':[len(train),len(held)],'worldVerticesChecked':vertex_count,'actualProjectAccepted':3,'outsideCalibrationImageVertices':[r['verticesOutsideOriginalFigure73Image']for r in records]},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');audit(p.parse_args().check)
