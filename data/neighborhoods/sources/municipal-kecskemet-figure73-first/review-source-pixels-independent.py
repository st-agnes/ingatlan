#!/usr/bin/env python3
"""Independent original-JPEG and source-pixel review; no producer import.

Portable source/topology QA uses only this batch directory;
geographic registration and project geometry admission require the later audit.
"""
import argparse
from collections import deque
import hashlib
import json
import math
from pathlib import Path
import sys
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
SOURCE=OUT/'figure73-p143-xref172.jpeg'
PDF=OUT/'source-pages143-144-147-153.pdf'
EXCERPT_SHA='0429326bfe7fa4d04e70e6a45c39d142d06c5cdb80665ca958f2bb22da768b41'
PDF_SHA='83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939'
IMAGE_SHA='59cbd060c8010a396511cdec69848410b4fee8d6bd8e628500894b5e27565e9c'
STEPS=[(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encode(d):return(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def point_segment_distance(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
    if not den:return math.dist(p,a)
    t=min(1,max(0,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den))
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)


def review(check):
    import fitz
    import numpy as np
    from PIL import Image
    from shapely.geometry import Polygon,LineString,Point
    from shapely.validation import explain_validity
    if sha(PDF)!=EXCERPT_SHA or sha(SOURCE)!=IMAGE_SHA:raise ValueError('Original PDF/JPEG changed')
    doc=fitz.open(PDF);source_page=doc[0]
    if source_page.get_xobjects():raise ValueError('Expected raster-only source page changed')
    image_refs=[i[0]for i in source_page.get_images()if i[2:4]==(1014,1434)]
    if len(image_refs)!=1 or doc.extract_image(image_refs[0])['image']!=SOURCE.read_bytes():raise ValueError('Source JPEG is not byte-identical original embedded image172')
    trace=json.loads((OUT/'source-pixel-trace.json').read_text())
    if trace['sourceImageSha256']!=IMAGE_SHA or trace['maxRgbThreshold']!=45:raise ValueError('Trace source/threshold differs')
    rgb=np.asarray(Image.open(SOURCE).convert('RGB'));v=rgb.max(axis=2);h,w=v.shape
    if [w,h]!=[1014,1434]or trace['sourceImageSize']!=[w,h]:raise ValueError('Original source dimensions differ')
    black=v<=45
    rings={name:[tuple(p)for p in ring]for name,ring in trace['rings'].items()}
    if set(rings)!={'Árpádváros','Kossuthváros'}:raise ValueError('Unexpected source fine-name set')
    # Recompute the connected component from an actual archived ring pixel;
    # no copy of the producer graph-search/anchor algorithm is imported.
    seed=rings['Árpádváros'][0];component={seed};todo=deque([seed])
    while todo:
        x,y=todo.popleft()
        for dx,dy in STEPS:
            p=x+dx,y+dy
            if 0<=p[0]<w and 0<=p[1]<h and black[p[1],p[0]]and p not in component:
                component.add(p);todo.append(p)
    if len(component)!=trace['literalBlackComponentPixelCount']:raise ValueError('Original black connected-component count differs')
    for x,y in component:
        if not black[y,x]:raise ValueError('Component selection added a source pixel')
    anchor={tuple(a['manual']):tuple(a['actualBlackSourcePixel'])for a in trace['actualSourceAnchors']}
    for manual,actual in anchor.items():
        if actual not in component or max(abs(manual[0]-actual[0]),abs(manual[1]-actual[1]))>9:raise ValueError('Invalid original-source anchor selection')
    for key,path in trace['sections'].items():
        points=[tuple(p)for p in path]
        if any(p not in component for p in points):raise ValueError('Source section leaves literal black component')
        if any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(points,points[1:])):raise ValueError('Source section has a non-neighbor edge')
        guide=[anchor[tuple(p)]for p in trace['manualGuideSeeds'][key]]
        positions=[];start=0
        for p in guide:
            position=points.index(p,start);positions.append(position);start=position
        if positions[0]!=0 or positions[-1]!=len(points)-1:raise ValueError('A section does not match its ordered source anchors')
        for a,b,first,last in zip(guide,guide[1:],positions,positions[1:]):
            if any(point_segment_distance(p,a,b)>14+1e-12 for p in points[first:last+1]):raise ValueError('Source section leaves documented guide corridor')
    polygons={};rows=[]
    label_points={'Árpádváros':(280,1065),'Kossuthváros':(463,1100)}
    for name,points in rings.items():
        if points[0]!=points[-1]:raise ValueError('Source ring is not closed')
        if any(not isinstance(x,int)or not isinstance(y,int)or not(0<=x<w and 0<=y<h)for x,y in points):raise ValueError('Ring contains a nonliteral source pixel coordinate')
        if any(p not in component for p in points):raise ValueError('Ring leaves the unmodified actual black source component')
        if any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(points,points[1:])):raise ValueError('Ring contains a non-neighbor closing/gap edge')
        polygon=Polygon(points)
        if not polygon.is_valid or len(polygon.interiors):raise ValueError('Invalid source-only polygon: '+explain_validity(polygon))
        frame_distance=min(min(x,y,w-1-x,h-1-y)for x,y in points)
        if frame_distance<=0:raise ValueError('Source ring uses image frame')
        if not polygon.covers(Point(*label_points[name])):raise ValueError('Source name label does not belong to the traced source cell')
        polygons[name]=polygon
        rows.append({'name':name,'denseSourceVertexCountIncludingClosure':len(points),
                     'maxRgbOnEveryDenseSourceVertex':max(int(v[y,x])for x,y in points),
                     'everyPointOriginalIntegerSourcePixel':True,'everyEdge8Neighbor':True,
                     'closed':True,'shapelyValid':True,'holes':0,'sourcePixelArea':polygon.area,
                     'minimumDistanceFromSourceFramePixels':frame_distance,'sourceLabelCenterInsideOwnCell':True,
                     'blueLabelOverprintInterpreted':False,'introducedClosingOrBridgeEdgeCount':0})
    intersection=polygons['Árpádváros'].intersection(polygons['Kossuthváros'])
    if intersection.area!=0:raise ValueError('The two source fine cells overlap in area')
    shared=LineString(trace['sections']['DA'])
    if not intersection.equals(shared):raise ValueError('Two source rings do not share precisely the archived DA divider')
    arpad=' '.join(doc[2].get_text().split());kossuth=' '.join(doc[3].get_text().split());summary=' '.join(doc[1].get_text().split())
    if not all(s in arpad for s in ['ÁRPÁDVÁROS','Batthyány utcai társasházak mögötti parkoló utca','Tizedes utca','Petőfi Sándor utca']):raise ValueError('Explicit source-era Árpádváros definition missing')
    if not all(s in kossuth for s in ['KOSSUTHVÁROS','Kossuth körút - Tizedes utca - Magyar utca - Batthyány utca','Horváth Döme körút - Mezei']):raise ValueError('Explicit source-era Kossuthváros definition missing')
    if 'Erzsébet- és Kossuthváros északi része'not in summary:raise ValueError('Source summary scope caution missing')
    files=[SOURCE,OUT/'trace-source-pixels.py',OUT/'source-pixel-trace.json',OUT/'source-pixel-preview.png',Path(__file__).resolve()]
    result={'schemaVersion':1,'status':'SOURCE_PIXEL_AND_SOURCE_NAME_SCOPE_PASS_GEOGRAPHIC_REVIEW_PENDING',
            'independentCodeDoesNotImportProducer':True,'sourcePdfPath':str(PDF.relative_to(ROOT)),
            'originalPublisherPdfSha256':PDF_SHA,'archivedPdfExcerptSha256':EXCERPT_SHA,'sourceFigure':73,'sourcePdfPageOneBased':143,'printedPage':141,
            'publisherEmbeddedImageXref':172,'sourceImageSha256':IMAGE_SHA,
            'originalEmbeddedJpegBytesExactlyPreserved':True,'sourceImageSize':[w,h],
            'inputsSha256':{str(p.relative_to(ROOT)):sha(p)for p in files},
            'componentSelection':{'originalImageBlackThresholdMaxRgb':45,'allOriginalImageBlackPixelCount':int(black.sum()),
                                  'independentlyRecomputedBoundaryBlackComponentPixelCount':len(component),
                                  'selectionAddsPixelsOrFillsGaps':False,'anchorLookupUsesOnlySubsetOfOriginalBlackPixels':True,
                                  'detachedPhotographicSpecksAreExcludedFromAnchorLookup':True},
            'sourceRingChecks':rows,'pairwiseAreaOverlapPixelsSquared':float(intersection.area),
            'sharedBoundaryExactlyEqualsOriginalDaSection':True,'sharedBoundaryPixelLength':shared.length,
            'sourceCurveRoleVisualReview':'The independently inspected original JPEG and colored preview show both traces following the printed black municipal cell outlines. Their labels lie inside the correct separately drawn cells; no source label obscures a traced boundary. This is a source-contour interpretation, not a road-center replacement.',
            'sourceSemantics':{'fineSourceNames':['Árpádváros','Kossuthváros'],
                               'arpadDefinitionPdfPageOneBased':147,'kossuthDefinitionPdfPageOneBased':153,
                               'arpadSourceBoundaryQuote':'Dobó István krt., Batthyány utcai társasházak mögötti parkoló utca, Magyar utca, Tizedes utca, Árpád krt., Petőfi Sándor utca.',
                               'kossuthSourceBoundaryQuote':'Kossuth körút - Tizedes utca - Magyar utca - Batthyány utca – Horváth Döme körút - Mezei utca',
                               'summaryScopeCautionPdf144Quote':'A Belvárosi terület több városrész (Városközpont, Árpádváros, Homoki-domb, Bethlenváros, Rákócziváros, Erzsébet- és Kossuthváros északi része) egységéből épül fel.',
                               'decision':'These are separately named and explicitly bounded 2021 source cells. Preserve that exact source-era scope. The summary refers to a northern-part relationship for Erzsébet-/Kossuthváros, while the later dedicated KOSSUTHVÁROS section gives a concrete boundary; do not claim an independently verified complete broader historical Kossuthváros extent.',
                               'arpadNotKülsoArpadvaros':True,'compoundGroupCopiedUnderFineNames':False,
                               'currentExactNameUseOrCurrentBoundaryExtentVerifiedHere':False},
            'georeferencingReviewed':False,'projectValidateGeometryAdmissionReviewed':False,
            'laterGeographicAuditMustCallActualProjectValidator':True,'absoluteAccuracyMeters':None,
            'usableForAddressAssignment':False,'existingFrozenBatchesOrGlobalRegistriesModified':False}
    target=OUT/'independent-source-pixel-review.json';data=encode(result)
    if check:
        if not target.exists()or target.read_bytes()!=data:raise ValueError('Independent source review stale')
    else:target.write_bytes(data)
    print(json.dumps({'mode':'check'if check else'build','sourcePixelQa':'PASS','sourceNames':['Árpádváros','Kossuthváros'],'denseSourceVertexCounts':[r['denseSourceVertexCountIncludingClosure']for r in rows],'georeferenceAndProjectAdmission':'pending'},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');review(p.parse_args().check)
