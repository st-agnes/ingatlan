#!/usr/bin/env python3
"""Three literal Figure76 source contours, with explicitly inferred placement."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
URL='https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf'
PDF_SHA='83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939'
IMAGE_SHA='9afccf14486eb5ed86581d07f9a588da4b53df6fa0c47cdbcaf6f667659055cd'
CALIBRATION_IMAGE_SHA='59cbd060c8010a396511cdec69848410b4fee8d6bd8e628500894b5e27565e9c'
METHOD=('Literal original Figure76 maxRGB<=45 black-source-pixel circuits, every dense edge an 8-neighbor source step. '
        'Shared dividers are reused exactly; no source-frame closure, label crossing, invented connector, simplification, buffer, snap or repair. '
        'Actual photographic texture establishes a Figure73-to-Figure76 image affine relation: ten fitted and ten separately held-out NCC patches, '
        'with no world coordinates, names or boundary rings used by image matching. The inverse image relation is composed with the archived '
        'Figure73 EOV affine calibration, independently recomputed from its six approximate real-road-node correspondences. '
        'The Figure73 geographic placement remains unvalidated, and Figure76 contours partly extend beyond the observed common-image overlap. '
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
    if sha(OUT/'figure76-p161-xref184.jpeg')!=IMAGE_SHA or sha(OUT/'figure73-p143-xref172.jpeg')!=CALIBRATION_IMAGE_SHA:
        raise ValueError('Changed exact source image')
    doc=fitz.open(OUT/'source-pages161-162.pdf');info=next(i for i in doc[0].get_image_info(xrefs=True)if(i['width'],i['height'])==(1702,1204))
    if hashlib.sha256(doc.extract_image(info['xref'])['image']).hexdigest()!=IMAGE_SHA:raise ValueError('Archive JPEG bytes differ')
    previous_manifest=json.loads((OUT/'calibration-figure73-manifest.json').read_text())
    if previous_manifest['frozenFilesSha256']['georeference.json']!=sha(OUT/'calibration-figure73-georeference.json'):
        raise ValueError('Calibration model does not match its frozen source manifest')
    previous_geo=json.loads((OUT/'calibration-figure73-georeference.json').read_text())
    specification=json.loads((OUT/'calibration-figure73-control-specification.json').read_text());controls=specification['controls']
    roads=json.loads((OUT/'calibration-figure73-control-roads.geojson').read_text())['features'];nodes={};members={}
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
    if not np.array_equal(calibration,np.array(previous_geo['affineImagePixelToEovRows'])):raise ValueError('Frozen Figure73 calibration not reproduced')
    relation=json.loads((OUT/'image-registration.json').read_text())
    if relation['sourceImageSha256']!=CALIBRATION_IMAGE_SHA or relation['targetImageSha256']!=IMAGE_SHA:raise ValueError('Image relation source changed')
    training=[r for r in relation['records']if r['usableTextureMatch']and r['trainingPartition']];heldout=[r for r in relation['records']if r['usableTextureMatch']and not r['trainingPartition']]
    if len(training)!=10 or len(heldout)!=10:raise ValueError('Changed image relation split')
    image_matrix=np.linalg.lstsq(np.array([[*r['sourcePatchCenter'],1]for r in training]),np.array([r['targetMatchedCenter']for r in training]),rcond=None)[0]
    if not np.array_equal(image_matrix,np.array(relation['sourceToTargetAffineRows'])):raise ValueError('Image affine fit changed')
    image_homogeneous=np.vstack([image_matrix.T,[0,0,1]]);inverse=np.linalg.inv(image_homogeneous)
    composed=inverse.T@calibration
    matched_hull=MultiPoint([r['targetMatchedCenter']for r in training+heldout]).convex_hull
    trace=json.loads((OUT/'source-pixel-rings.json').read_text());rgb=np.asarray(Image.open(OUT/'figure76-p161-xref184.jpeg').convert('RGB'));value=rgb.max(2)
    expected=['Külső Árpádváros','Mezeiváros','Ürgés']
    if list(trace['rings'])!=expected:raise ValueError('Source unit set changed')
    name_points=json.loads((OUT/'current-name-points.geojson').read_text())['features'];geod=Geod(ellps='WGS84');features=[];records=[];source_polygons={};world_polygons={};all_pixels=[]
    for name in expected:
        ring=trace['rings'][name]
        if ring[0]!=ring[-1]or any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(ring,ring[1:])):raise ValueError('Not a closed source-pixel path')
        if any(value[y,x]>45 for x,y in ring):raise ValueError('Non-source black pixel')
        source=Polygon(ring)
        if not source.is_valid or source.interiors or any(x in(0,1701)or y in(0,1203)for x,y in ring):raise ValueError('Invalid or frame-dependent source ring')
        dense=np.c_[np.array(ring),np.ones(len(ring))];calibration_pixels=(dense@inverse.T)[:,:2];metric_points=dense@composed;lon,lat=world_transform.transform(metric_points[:,0],metric_points[:,1]);world=Polygon(np.c_[lon,lat])
        if not world.is_valid or world.interiors:raise ValueError('Invalid transformed source circuit')
        current=next((p for p in name_points if p['properties']['name']==name),None)
        outside_image=int(sum(not(0<=x<=1013 and 0<=y<=1433)for x,y in calibration_pixels))
        outside_hull=int(sum(not matched_hull.covers(Point(x,y))for x,y in ring));max_hull_distance=max(matched_hull.distance(Point(x,y))for x,y in ring)
        area,perimeter=geod.geometry_area_perimeter(world)
        props={'name':name,'municipality':'Kecskemét','boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','canonicalNameIsNeighborhood':False,'estimated':True,
               'sourceRasterContourVerified':True,'sourceScopeNote':'One of the three separately named constituent units expressly identified on PDF161 and described on PDF161–162; the broader Mezeiváros és környezete group is not duplicated under each fine name.',
               'method':METHOD,'evidenceUrls':[URL],'sourceDocuments':[{'url':URL,'sha256':PDF_SHA,'pdfPageOneBased':161,'printedPage':159,'figure':76,'imageXref':184,'originalImageSha256':IMAGE_SHA},{'url':URL,'sha256':PDF_SHA,'pdfPageOneBased':162,'printedPage':160}],
               'sourcePeriod':'2021 May municipal consultation draft; original orthophoto capture date unknown.','license':LICENSE,'sourceIsOfficial':False,'sourceIsHardBoundary':False,
               'claimedAbsoluteAccuracyMetres':None,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,'geographicRegistrationVerified':False,
               'geometryVerificationStatus':'literal_black_source_pixel_contour_verified_image_relation_supported_geographic_placement_inherited_inferred',
               'reviewStatus':'estimated_candidate_not_verified','sourceRaster':{'sha256':IMAGE_SHA,'width':1702,'height':1204,'denseVertexCountIncludingClosure':len(ring),'maxRgbThreshold':45,'coordinateConvention':'Integer exact original-image pixel centers, x right/y down, no extra half-pixel offset.'},
               'imageOverlapExtrapolation':{'sourceVerticesOutsideMatchedTextureHull':outside_hull,'sourceVerticesOutsideFigure73ImageRectangle':outside_image,'maximumDistanceBeyondMatchedTextureHullSourcePixels':max_hull_distance,'notAnAbsoluteBoundaryErrorBound':True},
               'currentNameEvidence':{'status':'exact_current_osm_name_point'if current else'2021_municipal_fine_source_name_only','currentNameIndependentlyConfirmed':current is not None,'osmPointId':current['id']if current else None,'currentOsmPointCoveredByHistoricalEstimatedPolygon':world.covers(shape(current['geometry']))if current else None,'namePointDoesNotVerifyBoundaryExtent':True,'namePointsNeverUsedAsGeometryOrGeoreferencingControls':True},
               'areaM2':abs(area),'perimeterM':perimeter,'attribution':'Kecskemét MJV Megalapozó Vizsgálat II., May2021 consultation draft, Figure76; geographical controls ©OpenStreetMap contributors.',
               'reviewNotes':['All source contour vertices and shared dividers are original black JPEG pixels; no missing source boundary is reconstructed.',
                              'Photographic texture supports a common Figure73/Figure76 image relation only within observed overlap. Southern, western and eastern contour portions extend beyond this observed overlap.',
                              'Figure73 geographic calibration is inherited as an unvalidated estimate, including its failed excluded physical-control candidate; image matching cannot make it a verified geographic registration.',
                              'Current exact name scope, current/legal boundaries, source-map reuse rights and address assignment remain unverified.']}
        slug={'Külső Árpádváros':'kulso-arpadvaros','Mezeiváros':'mezeivaros','Ürgés':'urges'}[name]
        features.append({'type':'Feature','id':'manual:kecskemet-figure76:'+slug,'properties':props,'geometry':mapping(world)})
        records.append({'name':name,'denseVertexCountIncludingClosure':len(ring),'maximumMaxRgb':max(int(value[y,x])for x,y in ring),'sourceHoleCount':0,'worldHoleCount':0,'outsideMatchedTextureHullVertexCount':outside_hull,'outsideCalibrationImageRectangleVertexCount':outside_image,'maximumSourcePixelDistanceBeyondMatchedTextureHull':max_hull_distance})
        source_polygons[name]=source;world_polygons[name]=world;all_pixels+=ring
    for i,a in enumerate(expected):
        for b in expected[i+1:]:
            if source_polygons[a].intersection(source_polygons[b]).area!=0:raise ValueError('Original source-cell overlap')
    js="""import {validateGeometry} from './scripts/neighborhoods/build.mjs';let d='';for await(const c of process.stdin)d+=c;console.log(JSON.stringify(JSON.parse(d).map(f=>({id:f.id,...validateGeometry(f.geometry)}))));"""
    validated=json.loads(subprocess.run(['node','--input-type=module','-e',js],input=json.dumps(features),text=True,capture_output=True,cwd=ROOT,check=True).stdout)
    if not all(v['valid']for v in validated):raise ValueError('Actual project validator rejected a candidate '+str(validated))
    save('source-inferred.geojson',{'type':'FeatureCollection','features':features})
    save('georeference.json',{'schemaVersion':1,'outputCrs':'EPSG:4326','metricCrs':'EPSG:23700','sourceFigure73ImageToFigure76ImageAffineRows':image_matrix.tolist(),
                             'sourceFigure76ImageToFigure73ImageHomogeneous':inverse.tolist(),'composedFigure76PixelToEovRows':composed.tolist(),
                             'calibrationFigure73GeoreferenceSha256':sha(OUT/'calibration-figure73-georeference.json'),'calibrationFigure73FrozenManifestSha256':sha(OUT/'calibration-figure73-manifest.json'),
                             'imageTextureTrainingMatches':len(training),'imageTextureHeldOutMatches':len(heldout),'maximumImageTextureHeldOutResidualTargetPixels':relation['maximumHeldOutResidualTargetPixels'],
                             'matchedTextureHullFigure76Pixels':mapping(matched_hull),'overlapExtrapolationBySourceCell':records,
                             'inheritedSixRoadControlMaximumResidualMeters':previous_geo['maximumControlResidualMeters'],
                             'inheritedGeographicCalibrationVerified':False,'inheritedExcludedPriorSourceFeatureIdentityUnconfirmed':True,'geographicRegistrationVerified':False,
                             'imageRelationUsesNoWorldCoordinatesNamesOrBoundaryRings':True,'georeferencingUsesNoNeighborhoodNamePoints':True,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False})
    save('conversion-proof.json',{'schemaVersion':1,'featureCount':3,'denseOriginalAndWorldVertexCountIncludingClosures':len(all_pixels),'records':records,'projectValidatorResults':validated,
                                 'sourcePixelInteriorOverlap':0.0,'allOriginalContoursLiteralBlack8NeighborCircuits':True,'noSourceFrameClosureGapFillInventedChordSnapRepairBufferOrSimplification':True,
                                 'estimatedPlacementOnly':True,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False})
    save('registry-entry.json',{'id':'kecskemet-figure76-source-pixel-inferred','path':str((OUT/'source-inferred.geojson').relative_to(ROOT)),'sha256':generated['source-inferred.geojson'],'municipality':'Kecskemét','featureCount':3,
                               'method':METHOD,'evidenceUrls':[URL],'license':LICENSE,'reviewPath':str((OUT/'independent-review.json').relative_to(ROOT)),
                               'propertyOverrides':{'boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','estimated':True,'canonicalNameIsNeighborhood':False,'usableForAddressAssignment':False},
                               'rightsStatus':'Public municipal consultation draft; open reuse rights not independently established.'})
    save('generated-manifest.json',{'schemaVersion':1,'sha256':generated.copy()})
    print(json.dumps({'mode':'check'if check else'build','inferredFeatures':3,'denseSourceVertices':len(all_pixels),'actualProjectAccepted':len(validated),'imageHeldOutMaxPixels':relation['maximumHeldOutResidualTargetPixels'],'records':records},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');build(p.parse_args().check)
