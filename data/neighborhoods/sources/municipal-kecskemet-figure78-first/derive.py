#!/usr/bin/env python3
"""Four literal Figure78 source contours, with explicitly inferred placement."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
ROOT=next(p for p in OUT.parents if(p/'scripts/neighborhoods/build.mjs').exists())
FINAL_REL='data/neighborhoods/sources/municipal-kecskemet-figure78-first'
URL='https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf'
PDF_SHA='83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939'
IMAGE_SHA='63a05d0c439ef62c8feea3ca0347f7d944b98676c030960a38ccd4a9788870fd'
CALIBRATION_IMAGE_SHA='8d6217e4ae20dadfd07141aaed4dff0c057166fd60f30d8a7c0eec9b9fd5079d'
METHOD=('Literal original Figure78 maxRGB<=45 black-source-pixel circuits, every dense edge an 8-neighbor source step. '
        'Shared dividers are reused exactly; no source-frame closure, label crossing, invented connector, simplification, buffer, snap or repair. '
        'Actual photographic texture establishes a Figure79-to-Figure78 image affine relation: fourteen fitted and sixteen separately held-out NCC patches, '
        'with no world coordinates, names or boundary rings used by image matching. The inverse image relation is composed with the archived '
        'new EOV affine calibration, independently fitted from the five original Figure79 manual source-junction observations and literal OSM coordinates. '
        'The frozen Figure79 geographic-degree affine is retained as a model-family comparison and is never modified. '
        'Figure78 contours extend beyond the observed common-image overlap and the original calibration image; their full geographic placement is not independently validated. '
        'All output is therefore an explicit inferred geographic candidate; exact source contours are proved separately from placement.')
LICENSE='Municipal source-map reuse rights unverified; ODbL-1.0 for OSM geographical controls and name points.'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encode(v):return(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()

def build(check=False):
    import fitz,numpy as np,pyproj
    from PIL import Image
    from pyproj import Transformer,Geod
    from shapely.geometry import Polygon,Point,MultiPoint,mapping,shape
    pyproj.network.set_network_enabled(False)
    generated={}
    def save(name,value):
        data=encode(value);generated[name]=hashlib.sha256(data).hexdigest()
        if check:
            if not(OUT/name).exists()or(OUT/name).read_bytes()!=data:raise ValueError('Stale artifact '+name)
        else:(OUT/name).write_bytes(data)
    inputs=json.loads((OUT/'input-manifest.json').read_text())
    for name,expected in inputs['sha256'].items():
        if sha(OUT/name)!=expected:raise ValueError('Changed frozen input '+name)
    if sha(OUT/'figure78-p166-xref204.jpeg')!=IMAGE_SHA or sha(OUT/'calibration-figure79.jpeg')!=CALIBRATION_IMAGE_SHA:
        raise ValueError('Changed exact source image')
    doc=fitz.open(OUT/'source-pages166-167.pdf');info=next(i for i in doc[0].get_image_info(xrefs=True)if(i['width'],i['height'])==(1698,1202))
    if hashlib.sha256(doc.extract_image(info['xref'])['image']).hexdigest()!=IMAGE_SHA:raise ValueError('Archive JPEG bytes differ')
    previous_manifest=json.loads((OUT/'calibration-figure79-manifest.json').read_text())
    original_model_entry=next(f for f in previous_manifest['files']if f['path']=='raster-georeference.json')
    if original_model_entry['sha256']!=sha(OUT/'calibration-figure79-raster-georeference.json'):
        raise ValueError('Calibration model does not match its frozen source manifest')
    previous_geo=json.loads((OUT/'calibration-figure79-raster-georeference.json').read_text())
    specification=json.loads((OUT/'calibration-control-specification.json').read_text());controls=specification['controls']
    roads=json.loads((OUT/'calibration-control-roads.geojson').read_text())['features'];nodes={};members={}
    for road in roads:
        refs=road['properties']['source']['nodeRefs'];coordinates=road['geometry']['coordinates']
        if len(refs)!=len(coordinates):raise ValueError('Unpaired source road node')
        for node,coordinate in zip(refs,coordinates):
            if node in nodes and nodes[node]!=coordinate:raise ValueError('Inconsistent source node')
            nodes[node]=coordinate;members.setdefault(node,set()).add(road['id'])
    for c in controls:
        if nodes[c['osmNodeId']]!=c['coordinates']or members[c['osmNodeId']]!=set(c['sourceWayIds']):raise ValueError('Changed literal source control')
    metric_transform=Transformer.from_crs(4326,23700,always_xy=True);world_transform=Transformer.from_crs(23700,4326,always_xy=True)
    source_points=np.array([c['sourceImagePixel']for c in controls]);metric=np.array([metric_transform.transform(*c['coordinates'])for c in controls]);calibration=np.linalg.lstsq(np.c_[source_points,np.ones(len(source_points))],metric,rcond=None)[0]
    geographic_rows=np.array(previous_geo['matrixOriginalJpegColumnToWgs84'])[:2].T
    old_world_to_pixels=np.linalg.lstsq(np.array([[*c['coordinates'],1]for c in controls]),source_points,rcond=None)[0]
    recomputed_geographic_rows=np.linalg.inv(np.vstack([old_world_to_pixels.T,[0,0,1]]))[:2].T
    if np.max(np.abs(recomputed_geographic_rows-geographic_rows))>1e-12:raise ValueError('Original frozen Figure79 geographical calibration is not reproduced')
    calibration_residuals=np.linalg.norm(np.c_[source_points,np.ones(len(source_points))]@calibration-metric,axis=1)
    relation=json.loads((OUT/'image-registration.json').read_text())
    if relation['sourceImageSha256']!=CALIBRATION_IMAGE_SHA or relation['targetImageSha256']!=IMAGE_SHA:raise ValueError('Image relation source changed')
    training=[r for r in relation['records']if r['usableTextureMatch']and r['trainingPartition']];heldout=[r for r in relation['records']if r['usableTextureMatch']and not r['trainingPartition']]
    if len(training)!=14 or len(heldout)!=16:raise ValueError('Changed image relation split')
    image_matrix=np.linalg.lstsq(np.array([[*r['sourcePatchCenter'],1]for r in training]),np.array([r['targetMatchedCenter']for r in training]),rcond=None)[0]
    if not np.array_equal(image_matrix,np.array(relation['sourceToTargetAffineRows'])):raise ValueError('Image affine fit changed')
    image_homogeneous=np.vstack([image_matrix.T,[0,0,1]]);inverse=np.linalg.inv(image_homogeneous)
    composed=inverse.T@calibration
    matched_hull=MultiPoint([r['targetMatchedCenter']for r in training+heldout]).convex_hull
    trace=json.loads((OUT/'source-pixel-rings.json').read_text());rgb=np.asarray(Image.open(OUT/'figure78-p166-xref204.jpeg').convert('RGB'));value=rgb.max(2)
    expected=['Alsócsalános','Homokbánya','Alsószéktó','Szeleifalu']
    if list(trace['rings'])!=expected:raise ValueError('Source unit set changed')
    name_points=json.loads((OUT/'current-name-points.geojson').read_text())['features'];geod=Geod(ellps='WGS84');features=[];records=[];source_polygons={};world_polygons={};all_pixels=[]
    for name in expected:
        ring=trace['rings'][name]
        if ring[0]!=ring[-1]or any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(ring,ring[1:])):raise ValueError('Not a closed source-pixel path')
        if any(value[y,x]>45 for x,y in ring):raise ValueError('Non-source black pixel')
        source=Polygon(ring)
        if not source.is_valid or source.interiors or any(x in(0,1697)or y in(0,1201)for x,y in ring):raise ValueError('Invalid or frame-dependent source ring')
        dense=np.c_[np.array(ring),np.ones(len(ring))];calibration_pixels=(dense@inverse.T)[:,:2];metric_points=dense@composed;lon,lat=world_transform.transform(metric_points[:,0],metric_points[:,1]);world=Polygon(np.c_[lon,lat])
        if not world.is_valid or world.interiors:raise ValueError('Invalid transformed source circuit')
        current=next((p for p in name_points if p['properties']['name']==name),None)
        outside_image=int(sum(not(0<=x<=1693 and 0<=y<=1201)for x,y in calibration_pixels))
        outside_hull=int(sum(not matched_hull.covers(Point(x,y))for x,y in ring));max_hull_distance=max(matched_hull.distance(Point(x,y))for x,y in ring)
        area,perimeter=geod.geometry_area_perimeter(world)
        old_world_points=np.c_[calibration_pixels,np.ones(len(calibration_pixels))]@geographic_rows
        old_east,old_north=metric_transform.transform(old_world_points[:,0],old_world_points[:,1])
        family_difference=np.linalg.norm(np.c_[old_east,old_north]-metric_points,axis=1)
        props={'name':name,'municipality':'Kecskemét','boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','canonicalNameIsNeighborhood':False,'estimated':True,
               'sourceRasterContourVerified':True,'sourceScopeNote':'A separately named source cell on Figure78. PDF166–167 distinguishes the residential source quarters, Homokbánya former-barracks quarter and the named Alsócsalános area; the larger Alsószéktó–Homokbánya group is not copied under the four fine source names. The cut-off Alsószéktói kiskertek cell is excluded.',
               'sourceProseNameVariant':'Alsószéktó Kertváros'if name=='Alsószéktó'else name,
               'method':METHOD,'evidenceUrls':[URL],'sourceDocuments':[{'url':URL,'sha256':PDF_SHA,'pdfPageOneBased':166,'printedPage':164,'figure':78,'imageXref':204,'originalImageSha256':IMAGE_SHA},{'url':URL,'sha256':PDF_SHA,'pdfPageOneBased':167,'printedPage':165}],
               'sourcePeriod':'2021 May municipal consultation draft; original orthophoto capture date unknown.','license':LICENSE,'sourceIsOfficial':False,'sourceIsHardBoundary':False,
               'claimedAbsoluteAccuracyMetres':None,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,'geographicRegistrationVerified':False,
               'geometryVerificationStatus':'literal_black_source_pixel_contour_verified_image_relation_supported_geographic_placement_inherited_inferred',
               'reviewStatus':'estimated_candidate_not_verified','sourceRaster':{'sha256':IMAGE_SHA,'width':1698,'height':1202,'denseVertexCountIncludingClosure':len(ring),'maxRgbThreshold':45,'coordinateConvention':'Integer exact original-image pixel centers, x right/y down, no extra half-pixel offset.'},
               'imageOverlapExtrapolation':{'sourceVerticesOutsideMatchedTextureHull':outside_hull,'sourceVerticesOutsideFigure79ImageRectangle':outside_image,'maximumDistanceBeyondMatchedTextureHullSourcePixels':max_hull_distance,'notAnAbsoluteBoundaryErrorBound':True},
               'currentNameEvidence':{'status':'exact_current_osm_name_point'if current else'2021_municipal_fine_source_name_only','currentNameIndependentlyConfirmed':current is not None,'osmPointId':current['id']if current else None,'currentOsmPointCoveredByHistoricalEstimatedPolygon':world.covers(shape(current['geometry']))if current else None,'namePointDoesNotVerifyBoundaryExtent':True,'namePointsNeverUsedAsGeometryOrGeoreferencingControls':True},
               'areaM2':abs(area),'perimeterM':perimeter,'attribution':'Kecskemét MJV Megalapozó Vizsgálat II., May2021 consultation draft, Figure78; geographical controls ©OpenStreetMap contributors.',
               'reviewNotes':['All source contour vertices and shared dividers are original black JPEG pixels; no missing source boundary is reconstructed.',
                              'Photographic texture supports a common Figure79/Figure78 image relation only within observed overlap. Southern, western and eastern contour portions extend beyond this observed overlap.',
                              'The original Figure79 five manual road-junction observations support a new metric calibration, but no independent physical validation covers the full extrapolated Figure78 footprint. Image matching cannot establish absolute boundary accuracy.',
                              'Current exact name scope, current/legal boundaries, source-map reuse rights and address assignment remain unverified.']}
        slug={'Alsócsalános':'alsocsalanos','Homokbánya':'homokbanya','Alsószéktó':'alsoszekto','Szeleifalu':'szeleifalu'}[name]
        features.append({'type':'Feature','id':'manual:kecskemet-figure78:'+slug,'properties':props,'geometry':mapping(world)})
        records.append({'name':name,'denseVertexCountIncludingClosure':len(ring),'maximumMaxRgb':max(int(value[y,x])for x,y in ring),'sourceHoleCount':0,'worldHoleCount':0,'outsideMatchedTextureHullVertexCount':outside_hull,'outsideCalibrationImageRectangleVertexCount':outside_image,'maximumSourcePixelDistanceBeyondMatchedTextureHull':max_hull_distance,
                        'metricVsOriginalGeographicalAffineMaximumVertexDifferenceMeters':float(max(family_difference))})
        source_polygons[name]=source;world_polygons[name]=world;all_pixels+=ring
    for i,a in enumerate(expected):
        for b in expected[i+1:]:
            if source_polygons[a].intersection(source_polygons[b]).area!=0:raise ValueError('Original source-cell overlap')
    js="""import {validateGeometry} from './scripts/neighborhoods/build.mjs';let d='';for await(const c of process.stdin)d+=c;console.log(JSON.stringify(JSON.parse(d).map(f=>({id:f.id,...validateGeometry(f.geometry)}))));"""
    validated=json.loads(subprocess.run(['node','--input-type=module','-e',js],input=json.dumps(features),text=True,capture_output=True,cwd=ROOT,check=True).stdout)
    if not all(v['valid']for v in validated):raise ValueError('Actual project validator rejected a candidate '+str(validated))
    save('source-inferred.geojson',{'type':'FeatureCollection','features':features})
    save('georeference.json',{'schemaVersion':1,'outputCrs':'EPSG:4326','metricCrs':'EPSG:23700','sourceFigure79ImageToFigure78ImageAffineRows':image_matrix.tolist(),
                             'sourceFigure78ImageToFigure79ImageHomogeneous':inverse.tolist(),'composedFigure78PixelToEovRows':composed.tolist(),
                             'calibrationFigure79GeoreferenceSha256':sha(OUT/'calibration-figure79-raster-georeference.json'),'calibrationFigure79FrozenManifestSha256':sha(OUT/'calibration-figure79-manifest.json'),
                             'imageTextureTrainingMatches':len(training),'imageTextureHeldOutMatches':len(heldout),'maximumImageTextureHeldOutResidualTargetPixels':relation['maximumHeldOutResidualTargetPixels'],
                             'matchedTextureHullFigure78Pixels':mapping(matched_hull),'overlapExtrapolationBySourceCell':records,
                             'fiveOriginalRoadControlResidualMetersNewMetricFit':calibration_residuals.tolist(),
                             'maximumOriginalRoadControlResidualMetersNewMetricFit':float(max(calibration_residuals)),
                             'metricCalibrationIsExplicitNewFitFromOriginalObservations':True,'originalFigure79CalibrationFileChanged':False,
                             'fullFigure78GeographicPlacementIndependentlyValidated':False,'geographicRegistrationVerified':False,
                             'imageRelationUsesNoWorldCoordinatesNamesOrBoundaryRings':True,'georeferencingUsesNoNeighborhoodNamePoints':True,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False})
    save('conversion-proof.json',{'schemaVersion':1,'featureCount':4,'denseOriginalAndWorldVertexCountIncludingClosures':len(all_pixels),'records':records,'projectValidatorResults':validated,
                                 'sourcePixelInteriorOverlap':0.0,'allOriginalContoursLiteralBlack8NeighborCircuits':True,'noSourceFrameClosureGapFillInventedChordSnapRepairBufferOrSimplification':True,
                                 'estimatedPlacementOnly':True,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False})
    save('registry-entry.json',{'id':'kecskemet-figure78-source-pixel-inferred','path':FINAL_REL+'/source-inferred.geojson','sha256':generated['source-inferred.geojson'],'municipality':'Kecskemét','featureCount':4,
                               'method':METHOD,'evidenceUrls':[URL],'license':LICENSE,'reviewPath':FINAL_REL+'/independent-review.json',
                               'propertyOverrides':{'boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','estimated':True,'canonicalNameIsNeighborhood':False,'usableForAddressAssignment':False},
                               'rightsStatus':'Public municipal consultation draft; open reuse rights not independently established.'})
    save('generated-manifest.json',{'schemaVersion':1,'sha256':generated.copy()})
    print(json.dumps({'mode':'check'if check else'build','inferredFeatures':4,'denseSourceVertices':len(all_pixels),'actualProjectAccepted':len(validated),'imageHeldOutMaxPixels':relation['maximumHeldOutResidualTargetPixels'],'records':records},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');build(p.parse_args().check)
