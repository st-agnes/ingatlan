#!/usr/bin/env python3
"""One explicit inferred Figure74 source cell; retain source/placement limits."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
ROOT=next(p for p in OUT.parents if(p/'scripts/neighborhoods/build.mjs').is_file())
FINAL_REL='data/neighborhoods/sources/municipal-kecskemet-figure74-first'
URL='https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf'
PDF_SHA='83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939'
METHOD=('Manual Figure74 source-stroke guides trace original maxRGB<=45 JPEG pixels. '
        'Three explicitly enumerated blue-text-overprint intervals use low-confidence bounded manual continuations '
        'with unselected alternative paths; thirteen vertices are not strict source-black observations. '
        'No source-frame closure, buffer, repair, geographic snap or simplification is used. '
        'A photo-only Figure73-to-Figure74 affine uses thirteen fitted and ten held-out texture patches, '
        'with all twenty-five rejected searches and preliminary attempts retained. Its inverse is composed '
        'with the archived Figure73 metric EOV affine, independently refitted from its six original manual '
        'image observations and literal OSM road coordinates. The new footprint extends beyond the observed '
        'photo overlap and the original calibration image. Source-text overprints and full geographic '
        'placement remain explicit inferences; photographic residuals are not absolute boundary accuracy.')
LICENSE='Municipal source-map reuse rights unverified; ODbL-1.0 for OSM geographical controls and name point.'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name):return json.loads((OUT/name).read_text())
def encoded(v):return(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()

def build(check=False):
    import fitz,numpy as np,pyproj
    from PIL import Image
    from pyproj import Transformer,Geod
    from shapely.geometry import Polygon,Point,MultiPoint,mapping,shape
    pyproj.network.set_network_enabled(False)
    generated={}
    def save(name,value):
        data=encoded(value);generated[name]=hashlib.sha256(data).hexdigest()
        if check:
            if not(OUT/name).exists()or(OUT/name).read_bytes()!=data:raise ValueError('Stale artifact '+name)
        else:(OUT/name).write_bytes(data)
    for name,digest in load('input-manifest.json')['sha256'].items():
        if sha(OUT/name)!=digest:raise ValueError('Changed pinned input '+name)
    pdf=fitz.open(OUT/'source-pages154-156.pdf')
    image=next(i for i in pdf[0].get_image_info(xrefs=True)if(i['width'],i['height'])==(956,1348))
    if hashlib.sha256(pdf.extract_image(image['xref'])['image']).hexdigest()!=sha(OUT/'figure74-p154-xref176.jpeg'):raise ValueError('Original JPEG no longer matches archived PDF')
    prior=load('calibration-figure73-manifest.json')['frozenFilesSha256']
    for local,original in [('calibration-figure73.jpeg','figure73-p143-xref172.jpeg'),('calibration-figure73-georeference.json','georeference.json'),('calibration-figure73-control-specification.json','control-specification.json'),('calibration-figure73-control-roads.geojson','control-roads.geojson'),('calibration-figure73-original-pbf-verification.json','original-pbf-verification.json'),('calibration-figure73-current-name-points.geojson','current-name-points.geojson'),('calibration-figure73-prior-same-image-comparison.json','prior-same-image-comparison.json')]:
        if sha(OUT/local)!=prior[original]:raise ValueError('Changed frozen calibration evidence '+local)
    original_proof=load('calibration-figure73-original-pbf-verification.json')
    if original_proof['sourcePbfSha256']!='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a':raise ValueError('Calibration PBF identity differs')
    for original,local in [('control-roads.geojson','calibration-figure73-control-roads.geojson'),('current-name-points.geojson','calibration-figure73-current-name-points.geojson')]:
        if original_proof['inputSha256'][original]!=sha(OUT/local):raise ValueError('Archived original-PBF proof/input mismatch')
    roads=load('calibration-figure73-control-roads.geojson')['features'];nodes={};membership={}
    for road in roads:
        refs=road['properties']['source']['nodeRefs'];coords=road['geometry']['coordinates']
        if len(refs)!=len(coords):raise ValueError('Unpaired source road node')
        for node,coord in zip(refs,coords):
            if node in nodes and nodes[node]!=coord:raise ValueError('Inconsistent literal OSM node')
            nodes[node]=coord;membership.setdefault(node,set()).add(road['id'])
    controls=load('calibration-figure73-control-specification.json')['controls']
    if len(controls)!=6:raise ValueError('Changed calibration observation set')
    for c in controls:
        if nodes[c['osmNodeId']]!=c['coordinates']or membership[c['osmNodeId']]!=set(c['sourceWayIds']):raise ValueError('Changed original road control')
    eov=Transformer.from_crs(4326,23700,always_xy=True);wgs=Transformer.from_crs(23700,4326,always_xy=True)
    design=np.array([[*c['sourceImagePixel'],1]for c in controls]);metric=np.array([eov.transform(*c['coordinates'])for c in controls]);cal=np.linalg.lstsq(design,metric,rcond=None)[0]
    if np.max(np.abs(cal-np.array(load('calibration-figure73-georeference.json')['affineImagePixelToEovRows'])))>1e-8:raise ValueError('Frozen calibration does not independently reproduce')
    residual=np.linalg.norm(design@cal-metric,axis=1)
    relation=load('image-registration-work/image-registration.json')
    if relation['sourceImageSha256']!=sha(OUT/'calibration-figure73.jpeg')or relation['targetImageSha256']!=sha(OUT/'figure74-p154-xref176.jpeg'):raise ValueError('Photo source identity differs')
    train=[r for r in relation['records']if r['usableTextureMatch']and r['trainingPartition']];held=[r for r in relation['records']if r['usableTextureMatch']and not r['trainingPartition']]
    if(len(train),len(held),relation['rejectedSearchCount'])!=(13,10,25):raise ValueError('Photo split changed')
    photo=np.linalg.lstsq(np.array([[*r['sourcePatchCenter'],1]for r in train]),np.array([r['targetMatchedCenter']for r in train]),rcond=None)[0]
    if not np.array_equal(photo,np.array(relation['sourceToTargetAffineRows'])):raise ValueError('Photo affine differs')
    inverse=np.linalg.inv(np.vstack((photo.T,[0,0,1])));composed=inverse.T@cal
    trace=load('source-pixel-trace.json');ring=trace['rings']['Hunyadiváros'];source=Polygon(ring)
    if list(trace['rings'])!=['Hunyadiváros']or not source.is_valid or source.interiors or ring[0]!=ring[-1]:raise ValueError('Changed source cell topology')
    rgb=np.asarray(Image.open(OUT/'figure74-p154-xref176.jpeg').convert('RGB'));maxrgb=rgb.max(2)
    gaps=trace['sourceTextOverprintInferences'];inferred={tuple(q)for g in gaps for q in g['inferredPixelPath'][1:-1]}
    if len(gaps)!=3 or len(ring)!=2391:raise ValueError('Changed source trace/inference scope')
    if any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(ring,ring[1:])):raise ValueError('Non-neighbor source step')
    if any(maxrgb[y,x]>45 and(x,y)not in inferred for x,y in ring):raise ValueError('Unlisted source overprint')
    black_count=int(sum(maxrgb[y,x]<=45 for x,y in ring));nonblack=len(ring)-black_count
    if black_count!=2378 or nonblack!=13:raise ValueError('Changed source-black/inferred counts')
    dense=np.column_stack((np.array(ring),np.ones(len(ring))));cal_pixels=(dense@inverse.T)[:,:2];eov_points=dense@composed;lon,lat=wgs.transform(eov_points[:,0],eov_points[:,1]);world=Polygon(np.column_stack((lon,lat)))
    if not world.is_valid or world.interiors:raise ValueError('Invalid transformed source cell')
    hull=MultiPoint([r['targetMatchedCenter']for r in train+held]).convex_hull
    outside_hull=sum(not hull.covers(Point(x,y))for x,y in ring);outside_image=sum(not(0<=x<=1013 and 0<=y<=1433)for x,y in cal_pixels);max_distance=max(hull.distance(Point(x,y))for x,y in ring)
    current=load('current-name-points.geojson')['features'];nameproof=load('current-name-original-pbf-proof.json')
    if len(current)!=1 or current!=nameproof['namePoints']or not nameproof['actualOriginalPbfRead']:raise ValueError('Current name proof differs')
    if current[0]['properties']['source']['osmId']in {c['osmNodeId']for c in controls}:raise ValueError('Name point used as a control')
    name_inside=world.covers(shape(current[0]['geometry']));area,perimeter=Geod(ellps='WGS84').geometry_area_perimeter(world)
    alternatives=[]
    for g in gaps:
        chosen=g['inferredPixelPath'];start=next(i for i in range(len(ring)-len(chosen)+1)if ring[i:i+len(chosen)]==chosen)
        alternative_diagnostics=[]
        for path in g['alternativePixelPaths']:
            candidate=Polygon(ring[:start]+path+ring[start+len(chosen):])
            alternative_diagnostics.append({'replacementSourcePolygonValid':candidate.is_valid,'replacementSourceAreaDifferenceSquarePixels':candidate.area-source.area,'notAnAccuracyBoundOrChosenOutput':True})
        alternatives.append({**g,'alternativeDiagnostics':alternative_diagnostics,'sourceRgbOnChosenInferredInteriorPixels':[{'pixel':q,'rgb':rgb[q[1],q[0]].tolist()}for q in g['inferredPixelPath'][1:-1]],'chosenWorldCoordinates':[list(wgs.transform(*(np.array([*q,1])@composed)))for q in g['inferredPixelPath']],'alternativeWorldPaths':[[list(wgs.transform(*(np.array([*q,1])@composed)))for q in path]for path in g['alternativePixelPaths']],'alternativesSelectedForRegistry':False,'notAnAbsoluteAccuracyBound':True})
    props={'name':'Hunyadiváros','municipality':'Kecskemét','boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','canonicalNameIsNeighborhood':False,'estimated':True,'method':METHOD,'evidenceUrls':[URL],
           'sourceDocuments':[{'url':URL,'sha256':PDF_SHA,'pdfPagesOneBased':[154,155,156],'printedPages':[152,153,154],'figure':74,'imageXref':176,'originalImageSha256':sha(OUT/'figure74-p154-xref176.jpeg')}],
           'sourcePeriod':'2021 May municipal consultation draft; underlying orthophoto capture date unknown.','license':LICENSE,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'sourceRasterContourVerified':False,'sourceObservedContourVerifiedExceptExplicitOverprints':True,
           'sourceScopeNote':'The separately labeled Hunyadiváros proper source cell. PDF155 expressly distinguishes it from Ceglédi út, the southern economic source cell and the station-side development cell; the larger Hunyadiváros–Ceglédi út umbrella is not cloned under the fine name.',
           'sourceFactoryScopeCaution':load('source-semantics.json')['factoryScopeCaution'],
           'sourceRaster':{'sha256':sha(OUT/'figure74-p154-xref176.jpeg'),'width':956,'height':1348,'denseVertexCountIncludingClosure':2391,'strictBlackSourceVerticesIncludingClosure':2378,'inferredNonBlackSourceVertices':13,'blackMaxRgbThreshold':45,'coordinateConvention':'Integer original-image pixel centers, x right/y down, no extra half-pixel offset.'},
           'sourceBoundaryInference':{'used':True,'confidence':'low','reason':'Three short economic-divider intervals are overprinted by the blue source label. Manual continuations and unselected alternatives are explicit.','gapCount':3,'inferredNonBlackVertexCount':13,'endpointDistancesSourcePixels':[g['endpointDistancePixels']for g in gaps],'alternativesPath':FINAL_REL+'/source-inference-alternatives.json','notAnAbsoluteAccuracyBound':True},
           'imageOverlapExtrapolation':{'sourceVerticesOutsideMatchedTextureHull':outside_hull,'sourceVerticesOutsideFigure73ImageRectangle':outside_image,'maximumDistanceBeyondMatchedTextureHullSourcePixels':max_distance,'fullGeographicPlacementValidated':False,'notAnAbsoluteBoundaryErrorBound':True},
           'currentNameEvidence':{'status':'exact_current_osm_name_point','osmPointId':current[0]['id'],'currentNameIndependentlyConfirmed':True,'currentOsmPointCoveredByHistoricalEstimatedPolygon':name_inside,'namePointDoesNotVerifyBoundaryExtent':True,'namePointNeverUsedAsGeometryOrGeoreferencingControl':True},
           'claimedAbsoluteAccuracyMetres':None,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,'geographicRegistrationVerified':False,'geometryVerificationStatus':'mostly_literal_source_contour_with_three_explicit_low_confidence_text_overprint_inferences_and_extrapolated_geographic_placement','reviewStatus':'estimated_candidate_not_verified','areaM2':abs(area),'perimeterM':perimeter,'attribution':'Kecskemét MJV Megalapozó Vizsgálat II., May2021 consultation draft, Figure74; geographical controls and current name ©OpenStreetMap contributors.',
           'reviewNotes':['Thirteen source vertices across three short blue-text-overprint intervals are manual source-boundary inferences. All other vertices are original maxRGB<=45 black source pixels. No full black-contour claim is made.','The final source cell is preserved separately from the umbrella and the distinct southern economic/station-side cells. The factory map/prose scope nuance is retained without changing the pictured source boundary.','Only common photographic overlap is tested; most of the source contour extends beyond it. The inherited Figure73 geographical calibration remains inferred.','Current exact/legal extent, original photo date, open source-map reuse rights and address assignment remain unverified.']}
    feature={'type':'Feature','id':'manual:kecskemet-figure74:hunyadivaros','properties':props,'geometry':mapping(world)}
    save('source-inferred.geojson',{'type':'FeatureCollection','features':[feature]})
    js="""import{readFile}from'node:fs/promises';import{pathToFileURL}from'node:url';const{validateGeometry}=await import(pathToFileURL(process.argv[1]+'/scripts/neighborhoods/build.mjs'));const d=JSON.parse(await readFile(process.argv[2]+'/source-inferred.geojson','utf8'));process.stdout.write(JSON.stringify(d.features.map(f=>({id:f.id,...validateGeometry(f.geometry,f.bbox)}))));"""
    validated=json.loads(subprocess.run(['node','--input-type=module','-e',js,str(ROOT),str(OUT)],capture_output=True,text=True,check=True).stdout)
    if len(validated)!=1 or not validated[0]['valid']:raise ValueError('Actual project admission rejected source candidate '+str(validated))
    loo=[]
    for i,c in enumerate(controls):
        keep=[j for j in range(len(controls))if j!=i];model=np.linalg.lstsq(design[keep],metric[keep],rcond=None)[0];delta=np.linalg.norm(np.column_stack((cal_pixels,np.ones(len(cal_pixels))))@model-eov_points,axis=1)
        loo.append({'omittedControlId':c['id'],'maximumFigure74VertexDisplacementMeters':float(delta.max())})
    save('source-inference-alternatives.json',{'schemaVersion':1,'selectedSourceCell':'Hunyadiváros','confidence':'low','gaps':alternatives,'sourceAlternativesAreUnselectedHypotheses':True,'geographicCalibrationOfAlternativesIsAlsoInferred':True,'absoluteAccuracyMeters':None})
    save('georeference.json',{'schemaVersion':1,'metricCrs':'EPSG:23700','outputCrs':'EPSG:4326','figure73ToFigure74PhotoAffineRows':photo.tolist(),'figure74ToFigure73Homogeneous':inverse.tolist(),'figure73PixelToEovRowsIndependentlyRefitted':cal.tolist(),'composedFigure74PixelToEovRows':composed.tolist(),'originalSixControlResidualMeters':residual.tolist(),'originalMaximumControlResidualMeters':float(residual.max()),'originalFrozenFigure73CalibrationModified':False,'imageTextureTrainingMatches':13,'imageTextureHeldOutMatches':10,'maximumImageTextureHeldOutResidualTargetPixels':relation['maximumHeldOutResidualTargetPixels'],'observedTextureHullFigure74Pixels':mapping(hull),'sourceVerticesOutsideMatchedTextureHull':outside_hull,'sourceVerticesOutsideFigure73ImageRectangle':outside_image,'maximumDistanceBeyondMatchedTextureHullSourcePixels':max_distance,'calibrationLeaveOneControlOut':loo,'diagnosticsNotCalibratedAccuracyBounds':True,'geographicRegistrationVerified':False,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False})
    save('conversion-proof.json',{'schemaVersion':1,'featureCount':1,'denseOriginalAndWorldVertexCountIncludingClosures':2391,'strictBlackSourceVertexCountIncludingClosure':black_count,'inferredNonBlackSourceVertexCount':nonblack,'manualSourceTextOverprintGapCount':3,'sourceAndWorldHoleCount':0,'allSourceEdges8Neighbor':True,'allSourcePixelsBlack':False,'worldCoordinatesExactlyDerivedFromRecordedSourceTrace':True,'sourceVerticesOutsideMatchedTextureHull':outside_hull,'sourceVerticesOutsideFigure73ImageRectangle':outside_image,'maximumDistanceBeyondMatchedTextureHullSourcePixels':max_distance,'currentOriginalPbfNamePointInside':name_inside,'projectValidatorResults':validated,'estimatedPlacementOnly':True,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False})
    save('registry-entry.json',{'id':'kecskemet-figure74-source-overprint-inferred','path':FINAL_REL+'/source-inferred.geojson','sha256':sha(OUT/'source-inferred.geojson'),'municipality':'Kecskemét','featureCount':1,'method':METHOD,'evidenceUrls':[URL],'license':LICENSE,'reviewPath':FINAL_REL+'/independent-review.json','propertyOverrides':{'boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','estimated':True,'canonicalNameIsNeighborhood':False,'usableForAddressAssignment':False},'rightsStatus':'Public municipal consultation draft; open source-map reuse rights not independently established.'})
    data=encoded({'schemaVersion':1,'sha256':generated})
    if check:
        if(OUT/'generated-manifest.json').read_bytes()!=data:raise ValueError('Stale generated manifest')
    else:(OUT/'generated-manifest.json').write_bytes(data)
    print(json.dumps({'mode':'check'if check else'build','inferredFeatures':1,'denseVertices':2391,'strictBlackVertices':black_count,'inferredNonBlackVertices':nonblack,'actualProjectAccepted':1,'outsideTextureHull':outside_hull,'outsideCalibrationImage':outside_image,'maxBeyondHullPixels':max_distance,'currentNamePointInside':name_inside},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');build(parser.parse_args().check)
