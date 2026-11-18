#!/usr/bin/env python3
"""Frozen Figure73 literal-source contours; geographic placement stays inferred."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
URL='https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf'
PDF_SHA='83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939'
IMAGE_SHA='59cbd060c8010a396511cdec69848410b4fee8d6bd8e628500894b5e27565e9c'
METHOD=('Every boundary vertex is an original maxRGB<=45 black pixel on the exact embedded municipal Figure73 JPEG. '
        'Dense rings follow only 8-neighbor source-pixel paths guided by manually inspected stroke corridors. '
        'A literal black connected-component subset excludes detached photographic specks; no pixel is added, '
        'no missing edge is filled and no image-frame closure, buffer, snap, simplification or repair is used. '
        'The complete original apartment-back parking zigzag is retained instead of replacing it by an unresolved modern road-node chain. '
        'Six approximate historical source-junction observations fit an affine transform to literal current OSM nodes in EPSG:23700. '
        'Four old observations are transferred through the exact PDF page-image placement on the same byte-identical Figure73 image; '
        'two southern observations are new. A failed earlier same-image Jókai/Piaristák candidate is preserved outside the fit. '
        'Exact historical-to-current physical point identity has not been independently validated, so all geographic output remains inferred.')
LICENSE='Municipal source-map reuse rights unverified; ODbL-1.0 for OSM geographical controls and name points.'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encode(v):return(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()

def build(check=False):
    import fitz
    import numpy as np
    import pyproj
    from pyproj import Transformer,Geod
    from PIL import Image
    from shapely.geometry import Polygon,mapping,shape
    pyproj.network.set_network_enabled(False)
    generated={}
    def save(name,value):
        payload=encode(value);generated[name]=hashlib.sha256(payload).hexdigest()
        if check:
            if not(OUT/name).exists()or(OUT/name).read_bytes()!=payload:raise ValueError('Stale artifact '+name)
        else:(OUT/name).write_bytes(payload)
    inputs=json.loads((OUT/'input-manifest.json').read_text())
    for name,expected in inputs['sha256'].items():
        if sha(OUT/name)!=expected:raise ValueError('Frozen input changed '+name)
    if sha(OUT/'figure73-p143-xref172.jpeg')!=IMAGE_SHA:raise ValueError('Changed original JPEG')
    doc=fitz.open(OUT/'source-pages143-144-147-153.pdf')
    image_info=next(i for i in doc[0].get_image_info(xrefs=True)if(i['width'],i['height'])==(1014,1434))
    if hashlib.sha256(doc.extract_image(image_info['xref'])['image']).hexdigest()!=IMAGE_SHA:
        raise ValueError('Archive does not preserve exact original source image')
    rendered=doc[0].get_pixmap(matrix=fitz.Matrix(2,2))
    render_rgb=np.frombuffer(rendered.samples,dtype=np.uint8).reshape(rendered.height,rendered.width,rendered.n)
    old_rgb=np.asarray(Image.open(OUT/'prior-page143-render.png').convert('RGB'))
    # insert_pdf preserves the image and placement exactly; independently
    # embedded text outside the image can rasterize differently after copying
    # PDF resources. All transferred observations lie inside this exact common
    # image rectangle, so compare that rectangle, not unrelated page glyphs.
    x0,y0,x1,y1=image_info['bbox']
    left,top,right,bottom=int(np.ceil(x0*2))+1,int(np.ceil(y0*2))+1,int(np.floor(x1*2))-1,int(np.floor(y1*2))-1
    if not np.array_equal(render_rgb[top:bottom,left:right],old_rgb[top:bottom,left:right]):
        raise ValueError('Prior manual observations do not share the identical rendered source-image rectangle')
    spec=json.loads((OUT/'control-specification.json').read_text())
    controls=spec['controls'];excluded=spec['excludedPriorComparisonCandidate']
    roads=json.loads((OUT/'control-roads.geojson').read_text())['features']
    nodes={};membership={}
    for road in roads:
        refs=road['properties']['source']['nodeRefs'];coords=road['geometry']['coordinates']
        if len(refs)!=len(coords):raise ValueError('Changed literal road source sequence')
        for node,coord in zip(refs,coords):
            if node in nodes and nodes[node]!=coord:raise ValueError('Inconsistent original road node')
            nodes[node]=coord;membership.setdefault(node,set()).add(road['id'])
    for control in controls+[excluded]:
        node=control['osmNodeId']
        if nodes[node]!=control['coordinates']or set(control['sourceWayIds'])!=membership[node]:
            raise ValueError('Control differs from its literal original source node')
    metric_transform=Transformer.from_crs(4326,23700,always_xy=True)
    world_transform=Transformer.from_crs(23700,4326,always_xy=True)
    pixels=np.array([c['sourceImagePixel']for c in controls]);metric=np.array([metric_transform.transform(*c['coordinates'])for c in controls])
    design=np.c_[pixels,np.ones(len(pixels))];affine=np.linalg.lstsq(design,metric,rcond=None)[0]
    residuals=np.linalg.norm(design@affine-metric,axis=1)
    if len(controls)!=6 or max(residuals)>20:raise ValueError('Unexpected image control fit')
    inverse=np.linalg.inv(np.vstack([affine.T,[0,0,1]]))
    ep=(np.array([*metric_transform.transform(*excluded['coordinates']),1])@inverse.T)[:2]
    ew=excluded['sourceImageInterpretationWindow']
    excluded_inside=all(ew[k][0]<=ep[i]<=ew[k][1]for i,k in enumerate(['x','y']))
    trace=json.loads((OUT/'source-pixel-trace.json').read_text());rgb=np.asarray(Image.open(OUT/'figure73-p143-xref172.jpeg').convert('RGB'))
    value=rgb.max(axis=2);pixel_polygons={};world_polygons={};all_pixels=[]
    for name,ring in trace['rings'].items():
        if ring[0]!=ring[-1]or any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(ring,ring[1:])):
            raise ValueError('Non-source circuit')
        if any(value[y,x]>45 for x,y in ring):raise ValueError('Non-black source pixel')
        if any(x in(0,1013)or y in(0,1433)for x,y in ring):raise ValueError('Source ring reaches image frame')
        source=Polygon(ring)
        if not source.is_valid or source.interiors:raise ValueError('Invalid original source-pixel circuit')
        m=np.c_[np.array(ring),np.ones(len(ring))]@affine;lon,lat=world_transform.transform(m[:,0],m[:,1]);geo=Polygon(np.c_[lon,lat])
        if not geo.is_valid or geo.interiors:raise ValueError('Invalid transformed original source circuit')
        pixel_polygons[name]=source;world_polygons[name]=geo;all_pixels+=ring
    if list(pixel_polygons)!=['Árpádváros','Kossuthváros']:raise ValueError('Changed intended fine source cells')
    if pixel_polygons['Árpádváros'].intersection(pixel_polygons['Kossuthváros']).area!=0:raise ValueError('Source cell overlap')
    all_design=np.c_[np.array(all_pixels),np.ones(len(all_pixels))];full=all_design@affine;loo=[]
    for omit,c in enumerate(controls):
        keep=[i for i in range(len(controls))if i!=omit];other=np.linalg.lstsq(design[keep],metric[keep],rcond=None)[0]
        changes=np.linalg.norm(all_design@other-full,axis=1)
        loo.append({'omittedControlId':c['id'],'omittedControlPredictionErrorMeters':float(np.linalg.norm(design[omit]@other-metric[omit])),
                    'maximumSourceVertexDisplacementMeters':float(max(changes)),'meanSourceVertexDisplacementMeters':float(np.mean(changes))})
    sd=[];st=[]
    for(x,y),(east,north)in zip(pixels,metric):sd.extend([[x,y,1,0],[-y,x,0,1]]);st.extend([east,north])
    aa,bb,tx,ty=np.linalg.lstsq(np.array(sd),np.array(st),rcond=None)[0];similarity=np.array([[aa,bb],[bb,-aa],[tx,ty]])
    simchanges=np.linalg.norm(all_design@similarity-full,axis=1)
    name_points=json.loads((OUT/'current-name-points.geojson').read_text())['features'];features=[];records=[];geod=Geod(ellps='WGS84')
    for name in pixel_polygons:
        source=pixel_polygons[name];geo=world_polygons[name];current=next(p for p in name_points if p['properties']['name']==name)
        area,perimeter=geod.geometry_area_perimeter(geo)
        scope=('The complete separate source cell named Árpádváros on Figure73, with the parking-street perimeter described on PDF147.'if name=='Árpádváros'else
               'The separate source-period KOSSUTHVÁROS cell delimited on Figure73 and PDF153. PDF144 mentions the northern part when describing the larger Belváros composition; equivalence to any broader historical Kossuthváros extent is not asserted.')
        properties={'name':name,'municipality':'Kecskemét','boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood',
                    'canonicalNameIsNeighborhood':False,'estimated':True,'sourceNativeContourVerified':False,'sourceRasterContourVerified':True,
                    'sourceScopeNote':scope,'method':METHOD,'evidenceUrls':[URL],'license':LICENSE,
                    'sourceDocuments':[{'url':URL,'sha256':PDF_SHA,'pdfPageOneBased':143,'printedPage':141,'figure':73,'imageXref':172,'originalImageSha256':IMAGE_SHA},
                                       {'url':URL,'sha256':PDF_SHA,'pdfPageOneBased':147 if name=='Árpádváros' else 153,'printedPage':145 if name=='Árpádváros' else 151}],
                    'sourcePeriod':'2021 May municipal consultation draft; original orthoimage capture date unknown.',
                    'sourceIsOfficial':False,'sourceIsHardBoundary':False,'claimedAbsoluteAccuracyMetres':None,'absoluteAccuracyMeters':None,
                    'usableForAddressAssignment':False,'geographicRegistrationVerified':False,
                    'geometryVerificationStatus':'literal_black_source_pixel_contour_verified_geographic_placement_inferred',
                    'reviewStatus':'estimated_candidate_not_verified',
                    'sourceRaster':{'sha256':IMAGE_SHA,'width':1014,'height':1434,'denseVertexCountIncludingClosure':len(trace['rings'][name]),'maxRgbThreshold':45,'pixelCoordinateConvention':'Integer source-image pixel indices; x right/y down; no half-pixel offset.'},
                    'currentNameEvidence':{'status':'exact_current_osm_name_point','osmPointId':current['id'],'currentNameIndependentlyConfirmed':True,
                                           'currentOsmPointCoveredByHistoricalEstimatedPolygon':geo.covers(shape(current['geometry'])),'namePointDoesNotVerifyBoundaryExtent':True},
                    'areaM2':abs(area),'perimeterM':perimeter,
                    'attribution':'Kecskemét MJV Megalapozó Vizsgálat II., May2021 consultation draft, Figure73; geographical controls ©OpenStreetMap contributors.',
                    'reviewNotes':['The full historical black source contour supplies the shared parking corridor, independently of unresolved modern road-graph interpretation.',
                                   'Only actual source black pixels occur on the ring. There is no label-occlusion inference, invented connecting segment or image-frame closure.',
                                   'The excluded older same-image point is retained as a failed diagnostic, not hidden or accepted as a registration validation.',
                                   'Current exact physical control identities, current/legal boundary extent, absolute accuracy and address assignment are unverified.']}
        features.append({'type':'Feature','id':'manual:kecskemet-figure73:'+('arpadvaros'if name=='Árpádváros'else'kossuthvaros'),
                         'properties':properties,'geometry':mapping(geo)})
        records.append({'name':name,'denseVertexCountIncludingClosure':len(trace['rings'][name]),'sourceHoleCount':0,'worldHoleCount':0,
                        'sourceAreaPixelSquared':source.area,'everyDenseVertexIsActualOriginalBlackPixel':True,'sourceFrameTouched':False})
    # The real project validator must approve every import candidate in addition
    # to source-pixel and Shapely checks. Never modify geometry to force admission.
    js="""import {validateGeometry} from './scripts/neighborhoods/build.mjs';let data='';for await(const p of process.stdin)data+=p;console.log(JSON.stringify(JSON.parse(data).map(f=>({id:f.id,...validateGeometry(f.geometry)}))));"""
    validated=json.loads(subprocess.run(['node','--input-type=module','-e',js],input=json.dumps(features),text=True,capture_output=True,cwd=ROOT,check=True).stdout)
    if not all(r['valid']for r in validated):raise ValueError('Project validator rejected an original source circuit: '+str(validated))
    save('source-inferred.geojson',{'type':'FeatureCollection','features':features})
    save('georeference.json',{'schemaVersion':1,'fitCrs':'EPSG:23700','outputCrs':'EPSG:4326','affineImagePixelToEovRows':affine.tolist(),
                             'controlCount':len(controls),'controlResidualMeters':residuals.tolist(),'maximumControlResidualMeters':float(max(residuals)),
                             'rmsControlResidualMeters':float(np.sqrt(np.mean(residuals**2))),
                             'sameImagePriorPageImageRectanglePixelsExactlyEqualArchivedPdfRender':True,
                             'sourceImageRectangleCheckPageRenderBounds':[left,top,right,bottom],
                             'sourceImageRectanglePixelMismatchCount':0,'otherFigureTransformReused':False,
                             'excludedPriorComparisonDiagnostic':{'osmNodeId':excluded['osmNodeId'],'originalSourcePixel':excluded['sourceImagePixel'],
                                                                   'newModelPredictedSourcePixel':ep.tolist(),'insideOriginalInterpretationWindow':excluded_inside,
                                                                   'sourceFeatureIdentityUnconfirmed':True,'usedInFit':False,'identityCaution':excluded['identityCaution']},
                             'modelSensitivity':{'leaveOneControlOut':loo,'similarityVsAffineMaximumSourceVertexDisplacementMeters':float(max(simchanges)),
                                                 'similarityVsAffineMeanSourceVertexDisplacementMeters':float(np.mean(simchanges)),
                                                 'diagnosticNotCalibratedBoundaryErrorBound':True},
                             'geographicRegistrationVerified':False,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False})
    save('conversion-proof.json',{'schemaVersion':1,'sourceImageSha256':IMAGE_SHA,'records':records,'outputVertexCountIncludingClosures':len(all_pixels),
                                 'sourcePixelCellIntersectionArea':0.0,'projectValidatorResults':validated,
                                 'allSourceVertices8NeighborBlackPixels':True,'noFrameClosureInventedEdgeRepairBufferSnapOrPixelAddition':True,
                                 'geographicPlacementInferredOnly':True,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False})
    save('registry-entry.json',{'id':'kecskemet-figure73-source-pixel-inferred','path':str((OUT/'source-inferred.geojson').relative_to(ROOT)),
                               'sha256':generated['source-inferred.geojson'],'municipality':'Kecskemét','featureCount':2,'method':METHOD,
                               'evidenceUrls':[URL],'license':LICENSE,'reviewPath':str((OUT/'independent-review.json').relative_to(ROOT)),
                               'propertyOverrides':{'boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','estimated':True,
                                                     'canonicalNameIsNeighborhood':False,'usableForAddressAssignment':False},
                               'rightsStatus':'Public municipal consultation draft; open reuse rights not independently established.'})
    save('generated-manifest.json',{'schemaVersion':1,'sha256':generated.copy()})
    print(json.dumps({'mode':'check'if check else'build','inferredFeatureCount':len(features),'denseSourceVertices':len(all_pixels),
                      'projectValidatorAccepted':len(validated),'maximumControlResidualMeters':float(max(residuals)),
                      'excludedPriorCandidateInsideWindow':excluded_inside},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');build(parser.parse_args().check)
