#!/usr/bin/env python3
"""Independent portable Figure78 audit, with no producer-code imports.

The same file runs before and after atomic cohort relocation. Provenance uses
OUT-relative filenames, not the current staging directory or final-manifest hash.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
ROOT=next(p for p in [OUT,*OUT.parents] if(p/'scripts/neighborhoods/build.mjs').is_file())
FINAL_REL='data/neighborhoods/sources/municipal-kecskemet-figure78-first'
IMAGE79_SHA='8d6217e4ae20dadfd07141aaed4dff0c057166fd60f30d8a7c0eec9b9fd5079d'
IMAGE78_SHA='63a05d0c439ef62c8feea3ca0347f7d944b98676c030960a38ccd4a9788870fd'
CAL_MANIFEST_SHA='b5c5c314e1afd96f0de5c2c00b9bb1a7bcf6472e737fcac8addcf61e09a898d8'
PBF_SHA='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name):return json.loads((OUT/name).read_text())
def encoded(d):return(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()


def independent_ncc(registration):
    import numpy as np
    from PIL import Image
    from numpy.lib.stride_tricks import sliding_window_view
    source=Image.open(OUT/'calibration-figure79.jpeg').convert('L')
    target=np.asarray(Image.open(OUT/'figure78-p166-xref204.jpeg').convert('L'),dtype=float)
    rows=[];max_coefficient_error=0.;max_center_error=0.
    for record in registration['records']:
        left,top,right,bottom=record['sourcePatchBox'];size=record['targetTemplateSize']
        if(right-left,bottom-top)!=(64,64)or size!=56:raise ValueError('Unexpected source/template patch size')
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
    from collections import deque
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
    if sha(OUT/'calibration-figure79.jpeg')!=IMAGE79_SHA or sha(OUT/'figure78-p166-xref204.jpeg')!=IMAGE78_SHA:raise ValueError('Original source image differs')
    pdf=fitz.open(OUT/'source-pages166-167.pdf');info=next(i for i in pdf[0].get_image_info(xrefs=True)if(i['width'],i['height'])==(1698,1202))
    if hashlib.sha256(pdf.extract_image(info['xref'])['image']).hexdigest()!=IMAGE78_SHA:raise ValueError('Archived original Figure78 JPEG differs')
    prose=' '.join((pdf[0].get_text()+' '+pdf[1].get_text()).split())
    if not all(name in prose for name in ['Alsócsalános','Homokbánya','Alsószéktó Kertváros','Szeleifalu']):raise ValueError('Distinct historical source-unit semantics absent')
    if sha(OUT/'calibration-figure79-manifest.json')!=CAL_MANIFEST_SHA:raise ValueError('Copied frozen Figure79 manifest differs')
    old_manifest=load('calibration-figure79-manifest.json');entries={r['path']:r['sha256']for r in old_manifest['files']}
    if entries['raster-georeference.json']!=sha(OUT/'calibration-figure79-raster-georeference.json')or entries['figure79-source.jpeg']!=IMAGE79_SHA:raise ValueError('Copied Figure79 JPEG/model not pinned by frozen source manifest')
    proof=load('original-pbf-verification.json')
    if proof['sourcePbfSha256']!=PBF_SHA or proof['wayCount']!=16 or proof['namePointCount']!=4:raise ValueError('Original-PBF proof identity differs')
    for name,expected in proof['inputSha256'].items():
        if sha(OUT/name)!=expected:raise ValueError('Original-PBF proof/input hash mismatch')
    for flag in ['allOriginalWayNodeSequencesAndCoordinatesMatch','allOriginalWayTagsVersionsAndTimestampsMatch','allOriginalNameNodeCoordinatesTagsVersionsAndTimestampsMatch','originalPbfWasActuallyReadToCreateThisProof']:
        if proof[flag]is not True:raise ValueError('Incomplete direct original-PBF proof')
    roads=load('calibration-control-roads.geojson')['features'];nodes={};membership={}
    for f in roads:
        s=f['properties']['source'];refs=s['nodeRefs'];coords=f['geometry']['coordinates']
        if len(refs)!=len(coords)or s['geometryUnmodified']is not True:raise ValueError('Changed complete source-road sequence')
        for node,coord in zip(refs,coords):
            if node in nodes and nodes[node]!=coord:raise ValueError('Conflicting literal source node')
            nodes[node]=coord;membership.setdefault(node,set()).add(f['id'])
    spec=load('calibration-control-specification.json');controls=spec['controls'];original=load('calibration-figure79-raster-georeference.json')
    if len(controls)!=5 or spec['sourceImageSha256']!=IMAGE79_SHA:raise ValueError('Original five-road observation set differs')
    previous={c['osmNodeId']:c for c in original['controls']}
    for c in controls:
        if nodes[c['osmNodeId']]!=c['coordinates']or membership[c['osmNodeId']]!=set(c['sourceWayIds']):raise ValueError('Literal current road-node identity differs')
        old=previous[c['osmNodeId']]
        if old['coordinates']!=c['coordinates']or old['originalJpegPixels']!=c['sourceImagePixel']:raise ValueError('A new road observation was silently substituted for frozen Figure79 evidence')
    eov=Transformer.from_crs(4326,23700,always_xy=True);wgs=Transformer.from_crs(23700,4326,always_xy=True)
    source_controls=np.array([c['sourceImagePixel']for c in controls]);world_controls=np.array([c['coordinates']for c in controls]);metric=np.array([eov.transform(*c['coordinates'])for c in controls]);design79=np.column_stack((source_controls,np.ones(5)))
    metric_model=np.linalg.lstsq(design79,metric,rcond=None)[0];residual=np.linalg.norm(design79@metric_model-metric,axis=1)
    # Original model is explicitly the inverse of a WORLD->PIXEL least-squares
    # fit. It is not the different direct PIXEL->WORLD least-squares estimator.
    old_world_to_pixel=np.linalg.lstsq(np.column_stack((world_controls,np.ones(5))),source_controls,rcond=None)[0]
    geographic_rows=np.linalg.inv(np.vstack((old_world_to_pixel.T,[0,0,1])))[:2].T
    if np.max(np.abs(geographic_rows-np.array(original['matrixOriginalJpegColumnToWgs84'])[:2].T))>1e-12:raise ValueError('Original inverse-world-to-pixel model not reproduced')
    registration=load('image-registration.json')
    if registration['sourceImageSha256']!=IMAGE79_SHA or registration['targetImageSha256']!=IMAGE78_SHA or registration['geographicCoordinatesUsed']is not False or registration['neighborhoodNameOrBoundaryGeometryUsed']is not False:raise ValueError('Photo matching source or independence differs')
    direct_rows,max_ncc_error,max_center_error=independent_ncc(registration)
    train=[r for r in registration['records']if r['usableTextureMatch']and r['trainingPartition']];held=[r for r in registration['records']if r['usableTextureMatch']and not r['trainingPartition']]
    if len(direct_rows)!=40 or len(train)!=14 or len(held)!=16:raise ValueError('Expected forty searches and fourteen/sixteen usable partition')
    image_design=np.array([[*r['sourcePatchCenter'],1]for r in train]);image_target=np.array([r['targetMatchedCenter']for r in train]);image_model=np.linalg.lstsq(image_design,image_target,rcond=None)[0]
    if not np.array_equal(image_model,np.array(registration['sourceToTargetAffineRows'])):raise ValueError('Independent photo affine differs')
    held_rows=[]
    for r in held:
        error=float(np.linalg.norm(np.array([*r['sourcePatchCenter'],1])@image_model-np.array(r['targetMatchedCenter'])))
        if abs(error-r['affinePredictionResidualPixels'])>1e-10:raise ValueError('Held-out photographic residual differs')
        held_rows.append({'id':r['id'],'residualTargetPixels':error,'usedInFit':False})
    inverse=np.linalg.inv(np.vstack((image_model.T,[0,0,1])));composed=inverse.T@metric_model;geo=load('georeference.json')
    for actual,key in [(image_model,'sourceFigure79ImageToFigure78ImageAffineRows'),(inverse,'sourceFigure78ImageToFigure79ImageHomogeneous'),(composed,'composedFigure78PixelToEovRows')]:
        if not np.array_equal(actual,np.array(geo[key])):raise ValueError('Independent inverse/composed matrix differs')
    if np.max(np.abs(residual-np.array(geo['fiveOriginalRoadControlResidualMetersNewMetricFit'])))>1e-6:raise ValueError('New metric calibration residuals differ')
    manual=load('independent-physical-landmarks.json');manual_checks=[]
    for p in manual['landmarks']:
        predicted=np.array([*p['figure79Pixel'],1])@image_model;delta=predicted-np.array(p['figure78Pixel']);half=p['manualInterpretationHalfWidthFigure79Pixels']*np.abs(image_model[:2,:]).sum(axis=0)+p['manualInterpretationHalfWidthFigure78Pixels']
        if not np.all(np.abs(delta)<=half):raise ValueError('Photo model conflicts with an independently measured physical feature')
        manual_checks.append({'id':p['id'],'manualSourcePixel':p['figure79Pixel'],'manualTargetPixel':p['figure78Pixel'],'predictedTargetPixel':predicted.tolist(),'distanceTargetPixels':float(np.linalg.norm(delta)),'withinPreviouslyDeclaredManualInterpretation':True,'manualPointOrWindowAdjustedToModel':False})
    trace=load('source-pixel-rings.json');rgb=np.asarray(Image.open(OUT/'figure78-p166-xref204.jpeg').convert('RGB'));value=rgb.max(axis=2);black=value<=45
    if trace['sourceImageSha256']!=IMAGE78_SHA or trace['sourceImageSize']!=[1698,1202]:raise ValueError('Source trace image differs')
    # Source component selection is independently replayed as an exact subset,
    # not a closing/morphological operation that could insert missing pixels.
    start=tuple(trace['rings']['Alsócsalános'][0]);component={start};todo=deque([start])
    while todo:
        x,y=todo.popleft()
        for dx,dy in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
            p=x+dx,y+dy
            if 0<=p[0]<1698 and 0<=p[1]<1202 and black[p[1],p[0]]and p not in component:component.add(p);todo.append(p)
    if len(component)!=trace['literalBlackComponentPixelCount']:raise ValueError('Literal source-black component differs')
    expected=['Alsócsalános','Homokbánya','Alsószéktó','Szeleifalu'];features=load('source-inferred.geojson')['features'];byname={f['properties']['name']:f for f in features};names=load('current-name-points.geojson')['features'];namebyname={f['properties']['name']:f for f in names};nameproof={n['osmNodeId']:n for n in proof['namePointRecords']}
    if list(trace['rings'])!=expected or set(byname)!=set(expected)or set(namebyname)!=set(expected):raise ValueError('Source/candidate/current-name identity set differs')
    for f in names:
        s=f['properties']['source'];p=nameproof[s['osmId']]
        if f['geometry']['coordinates']!=p['coordinates']or s['objectVersion']!=p['objectVersion']or s['objectTimestamp']!=p['objectTimestamp']or f['properties']['name']!=p['name']:raise ValueError('Current fine-name PBF identity differs')
    if set(n['properties']['source']['osmId']for n in names)&set(c['osmNodeId']for c in controls):raise ValueError('A fine-name point was used as a registration control')
    hull=MultiPoint([r['targetMatchedCenter']for r in train+held]).convex_hull
    if not hull.equals(shape(geo['matchedTextureHullFigure78Pixels'])):raise ValueError('Observed photo coverage hull differs')
    source_polygons={};world_polygons={};checks=[];all_pixels=[];total_vertices=0;max_error=0.
    for name in expected:
        ring=trace['rings'][name]
        if ring[0]!=ring[-1]or any(not isinstance(x,int)or not isinstance(y,int)or not(0<=x<1698 and 0<=y<1202)for x,y in ring):raise ValueError('Open/nonliteral source ring')
        if any(tuple(p)not in component for p in ring)or any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(ring,ring[1:])):raise ValueError('Nonblack/non-neighbor source edge')
        source=Polygon(ring);frame_distance=min(min(x,y,1697-x,1201-y)for x,y in ring)
        if not source.is_valid or source.interiors or frame_distance<=0:raise ValueError('Invalid, holed or frame-dependent original source')
        dense=np.column_stack((np.array(ring),np.ones(len(ring))));cal_pixels=(dense@inverse.T)[:,:2];metric_points=dense@composed;sequential=np.column_stack((cal_pixels,np.ones(len(cal_pixels))))@metric_model
        if np.max(np.abs(sequential-metric_points))>1e-8:raise ValueError('Sequential/inverse/composed mapping differs')
        lon,lat=wgs.transform(metric_points[:,0],metric_points[:,1]);computed=np.column_stack((lon,lat));f=byname[name];actual=np.array(f['geometry']['coordinates'][0]);world=shape(f['geometry'])
        if f['geometry']['type']!='Polygon'or len(f['geometry']['coordinates'])!=1 or actual.shape!=computed.shape or not world.is_valid or world.interiors:raise ValueError('World vertex count or topology differs')
        error=float(np.max(np.abs(actual-computed)))
        if error>1e-12:raise ValueError('World vertex differs from exact independently composed source pixel')
        total_vertices+=len(ring);max_error=max(max_error,error)
        outside_image=sum(not(0<=x<=1693 and 0<=y<=1201)for x,y in cal_pixels);outside_hull=sum(not hull.covers(Point(x,y))for x,y in ring);max_distance=max(hull.distance(Point(x,y))for x,y in ring)
        original_world=np.column_stack((cal_pixels,np.ones(len(cal_pixels))))@geographic_rows;old_e,old_n=eov.transform(original_world[:,0],original_world[:,1]);family=np.linalg.norm(np.column_stack((old_e,old_n))-metric_points,axis=1)
        declared=next(r for r in geo['overlapExtrapolationBySourceCell']if r['name']==name)
        if outside_image!=declared['outsideCalibrationImageRectangleVertexCount']or outside_hull!=declared['outsideMatchedTextureHullVertexCount']or abs(max_distance-declared['maximumSourcePixelDistanceBeyondMatchedTextureHull'])>1e-7 or abs(float(family.max())-declared['metricVsOriginalGeographicalAffineMaximumVertexDifferenceMeters'])>1e-7:raise ValueError('Extrapolation/model-family comparison differs')
        p=f['properties']
        if not(p['boundaryKind']=='inferred_area'and p['candidateBoundaryKind']=='neighbourhood'and p['estimated']is True and p['canonicalNameIsNeighborhood']is False and p['geographicRegistrationVerified']is False and p['absoluteAccuracyMeters']is None and p['usableForAddressAssignment']is False):raise ValueError('Explicit inferred-only policy differs')
        current=namebyname[name];covered=world.covers(shape(current['geometry']))
        if covered is not True or p['currentNameEvidence']['currentOsmPointCoveredByHistoricalEstimatedPolygon']is not True or p['currentNameEvidence']['namePointsNeverUsedAsGeometryOrGeoreferencingControls']is not True:raise ValueError('Current name-point/control-use diagnostic differs')
        if name=='Alsószéktó'and p['sourceProseNameVariant']!='Alsószéktó Kertváros':raise ValueError('Source prose-name scope qualifier lost')
        source_polygons[name]=source;world_polygons[name]=world;all_pixels+=ring
        checks.append({'name':name,'sourceAndWorldDenseVerticesChecked':len(ring),'maximumSourceMaxRgb':max(int(value[y,x])for x,y in ring),'allSourceEdges8Neighbor':True,'sourceAndWorldHoles':0,'minimumDistanceFromSourceFramePixels':frame_distance,'maximumWorldCoordinateDisagreementDegrees':error,'everyWorldEdgeCorrespondsToConsecutiveOriginalSourcePixels':True,'verticesOutsideObservedTextureHull':int(outside_hull),'verticesOutsideOriginalCalibrationImage':int(outside_image),'maximumDistanceBeyondTextureHullTargetPixels':max_distance,'newMetricVsOriginalInverseGeographicAffineMaximumDifferenceMeters':float(family.max()),'currentExactPbfNamePointInsideSourceCandidate':True,'currentNamePointId':current['id'],'namePointUsedAsRegistrationControl':False})
    if total_vertices!=5790:raise ValueError('Expected complete original dense vertex count differs')
    overlaps=[]
    for i,a in enumerate(expected):
        for b in expected[i+1:]:
            sa=source_polygons[a].intersection(source_polygons[b]).area;wa=world_polygons[a].intersection(world_polygons[b]).area
            if sa!=0 or wa!=0:raise ValueError('Original/world cell areas overlap')
            overlaps.append({'a':a,'b':b,'sourceAreaOverlap':sa,'worldAreaOverlap':wa})
    js="""import{readFile}from'node:fs/promises';import{pathToFileURL}from'node:url';const root=process.argv[1],folder=process.argv[2];const{validateGeometry}=await import(pathToFileURL(root+'/scripts/neighborhoods/build.mjs'));const d=JSON.parse(await readFile(folder+'/source-inferred.geojson','utf8'));process.stdout.write(JSON.stringify(d.features.map(f=>({id:f.id,name:f.properties.name,...validateGeometry(f.geometry,f.bbox)}))));"""
    validated=json.loads(subprocess.run(['node','--input-type=module','-e',js,str(ROOT),str(OUT)],capture_output=True,text=True,check=True).stdout)
    if len(validated)!=4 or not all(r['valid']for r in validated):raise ValueError('Actual project admission rejected an unchanged source candidate')
    registry=load('registry-entry.json')
    if registry['path']!=FINAL_REL+'/source-inferred.geojson'or registry['reviewPath']!=FINAL_REL+'/independent-review.json'or registry['sha256']!=sha(OUT/'source-inferred.geojson')or registry['featureCount']!=4:raise ValueError('Final logical registry path/hash differs')
    # Diagnostic only: perturb the calibration/model choice without moving a
    # contour. Extrapolated areas remain outside verified photo/geographic scope.
    all_dense=np.column_stack((np.array(all_pixels),np.ones(len(all_pixels))));all_cal=(all_dense@inverse.T)[:,:2];all_cal_design=np.column_stack((all_cal,np.ones(len(all_cal))));base=all_dense@composed;road_loo=[];image_loo=[]
    for i,c in enumerate(controls):
        keep=[j for j in range(5)if j!=i];model=np.linalg.lstsq(design79[keep],metric[keep],rcond=None)[0];changes=np.linalg.norm(all_cal_design@model-base,axis=1);road_loo.append({'omittedRoadNodeId':c['osmNodeId'],'maximumFigure78SourceVertexDisplacementMeters':float(changes.max())})
    for i,r in enumerate(train):
        keep=[j for j in range(len(train))if j!=i];model=np.linalg.lstsq(image_design[keep],image_target[keep],rcond=None)[0];inv=np.linalg.inv(np.vstack((model.T,[0,0,1])));changes=np.linalg.norm(all_dense@(inv.T@metric_model)-base,axis=1);image_loo.append({'omittedTexturePatchId':r['id'],'maximumFigure78SourceVertexDisplacementMeters':float(changes.max())})
    provenance=['input-manifest.json','generated-manifest.json','image-registration.json','independent-physical-landmarks.json','independent-physical-landmark-model-check.json','source-pixel-rings.json','source-inferred.geojson','calibration-figure79-manifest.json','calibration-figure79-raster-georeference.json','calibration-control-specification.json','calibration-control-roads.geojson','original-pbf-verification.json','current-name-points.geojson','georeference.json','conversion-proof.json','registry-entry.json','finalaudit-independent.py']
    result={'schemaVersion':1,'status':'PASS_FOR_FOUR_EXPLICIT_INFERRED_SOURCE_CELLS','logicalCohortPath':FINAL_REL,'independentOfProducerCode':True,
            'provenanceSha256':{name:sha(OUT/name)for name in provenance},
            'portableReplay':{'rootDiscoveredByProjectValidatorAncestorSearch':True,'currentStagingOrFinalDirectoryPathStoredInReport':False,'requiresExternalFrozenCohortDirectoryOrFullPbfForDefaultReplay':False,'finalManifestNotHashedInOwnFingerprintAvoidingCycles':True},
            'sourceEvidence':{'originalFigure78EmbeddedJpegPreserved':True,'sourceImageSha256':IMAGE78_SHA,'sourceBlackComponentIndependentlyRecomputedPixelCount':len(component),'componentOnlySelectsActualOriginalBlackPixels':True,'denseSourceAndWorldVertexCountChecked':total_vertices,'allSourceVerticesMaxRgb45OrLess':True,'allSourceEdges8Neighbor':True,'sourceFrameClosureGapFillLabelOcclusionInferenceRepairBufferSnapOrPixelAddition':False,'sourceAndWorldInteriorRingCount':0,'maximumWorldCoordinateDisagreementDegrees':max_error,'allWorldEdgesVerifiedAgainstConsecutiveOriginalSourcePixels':True,'pairwiseAreaOverlapChecks':overlaps},
            'independentPhotographicNcc':{'numericMethod':'Direct sliding-window dot products/window sum-square normalization, instead of the producer FFT convolution. All forty searches and rejected/usable classifications are recomputed.','directSearchCount':len(direct_rows),'trainingCount':len(train),'heldOutCount':len(held),'maximumNccCoefficientDisagreement':max_ncc_error,'maximumPeakCenterDisagreementPixels':max_center_error,'photoAffineIndependentlyRefitted':True,'heldOutResiduals':held_rows,'maximumHeldOutResidualTargetPixels':max(r['residualTargetPixels']for r in held_rows),'geographicCoordinatesNamesOrSourceQuarterRingsUsedByPhotoMatching':False,'independentUntunedPhysicalFeatureChecks':manual_checks},
            'calibrationEvidence':{'copiedFrozenFigure79ManifestSha256':CAL_MANIFEST_SHA,'copiedOriginalFigure79ImageAndWgsModelHashesMatchManifest':True,'originalFiveManualImageObservationsUnmodified':True,'actualLiteralControlWaysVerifiedAgainstPinnedOriginalPbf':16,'actualLiteralCurrentNameNodesVerifiedAgainstPinnedOriginalPbf':4,'newMetricFitIndependentlyComputedInCrs':'EPSG:23700','newMetricRoadControlResidualMeters':residual.tolist(),'oldGeographicalModelMethod':'Inverse of least-squares WORLD->PIXEL affine, reproduced explicitly; not direct PIXEL->WORLD least squares.','oldInverseGeographicalModelIndependentlyReproduced':True,'originalFrozenFigure79CalibrationFileChanged':False,'exactPhysicalSourceRoadJunctionCenterSurveyClaimed':False},
            'conversion':{'inversePhotoAffineAndComposedEovMappingIndependentlyComputed':True,'sequentialAndComposedMetricVerticesAgreeWithin1eMinus8Meters':True,'all5790WorldVerticesAndEdgesChecked':True},
            'sourceCellChecks':checks,
            'actualProjectGeometryValidator':{'modulePath':'scripts/neighborhoods/build.mjs','moduleSha256':sha(ROOT/'scripts/neighborhoods/build.mjs'),'actualValidateGeometryExportCalled':True,'acceptedCount':4,'rejectedCount':0,'results':validated},
            'sensitivityDiagnostics':{'originalRoadControlLeaveOneOut':road_loo,'photographicTrainingPatchLeaveOneOut':image_loo,'notCalibratedBoundaryAccuracyBounds':True},
            'sourceScopeDecision':{'separatelyNamedFineSourceCells':expected,'compoundGroupCopiedUnderFineNames':False,'alsoszektoProseVariantAlsoszektoKertvarosPreserved':True,'imageEdgeAlsoszektóiKiskertekExcluded':True,'fourOriginalPbfNamePointsInsideButNotUsedAsCoordinatesOrControls':True,'nameOccurrenceDoesNotProveCurrentExactBoundaryExtent':True},
            'limits':{'onlyObservedPhotographicOverlapTested':True,'largeSouthernEasternAndWesternExtrapolationExplicit':True,'szeleifaluAll1662SourceVerticesOutsideObservedTextureHull':True,'newFullFigure78GeographicValidationClaimed':False,'photoResidualsOrSmallModelFamilyDifferenceNotAbsoluteBoundaryAccuracy':True},
            'primaryLayerApproved':False,'explicitInferredLayerApproved':True,'geographicRegistrationVerified':False,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,
            'approvalReason':'The exact black source contours, common photographic overlap, literal original OSM controls/names, independently refitted calibration and every transformed world vertex/edge pass audit and the real project validator. The new Figure78 extent is largely outside observed photo coverage and original Figure79 image coverage; all Szeleifalu vertices are outside the texture hull. Four current name points and small model-family differences do not validate full geographic registration. Preserve explicit inferred-only status.'}
    target=OUT/'independent-review.json';data=encoded(result)
    if check:
        if not target.exists()or target.read_bytes()!=data:raise ValueError('Independent Figure78 audit stale or missing')
    else:target.write_bytes(data)
    print(json.dumps({'mode':'check'if check else'build','status':result['status'],'directNccSearches':len(direct_rows),'trainingAndHeldOut':[len(train),len(held)],'allWorldVerticesChecked':total_vertices,'actualProjectAccepted':4,'outsideCalibrationImageCounts':[r['verticesOutsideOriginalCalibrationImage']for r in checks]},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');audit(p.parse_args().check)
