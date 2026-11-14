#!/usr/bin/env python3
"""Independent literal-pixel BFS and face audit; no source extractor imports."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image

P = Path(__file__).resolve().parent
SOURCE = P.parent / 'municipal-pecs-remaining-next' / 'pecs-p48-names.jpeg'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    image = Image.open(SOURCE).convert('RGB')
    width, height = image.size
    author_path = P / 'islands-source-pixel-candidates.json'
    author = {r['id']: r for r in json.loads(author_path.read_text())['records']}

    def selected(x, y, threshold):
        r, g, b = image.getpixel((x, y))
        return (min(r, b) - g >= 25 and b - r >= -30) or max(r, g, b) < threshold

    def component(seed, threshold):
        assert selected(*seed, threshold)
        found, todo = {tuple(seed)}, [tuple(seed)]
        while todo:
            x, y = todo.pop()
            for xx, yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if 0 <= xx < width and 0 <= yy < height and (xx,yy) not in found and selected(xx,yy,threshold):
                    found.add((xx,yy))
                    todo.append((xx,yy))
        return found

    def faces(pixels, threshold):
        boundary = set()
        outgoing_count = 0
        for x, y in pixels:
            assert selected(x,y,threshold)
            corners = [(2*x-1,2*y-1),(2*x+1,2*y-1),(2*x+1,2*y+1),(2*x-1,2*y+1)]
            for a,b in zip(corners,corners[1:]+corners[:1]):
                if (b,a) in boundary:
                    boundary.remove((b,a))
                else:
                    boundary.add((a,b))
            for xx,yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if (xx,yy) not in pixels:
                    assert 0 <= xx < width and 0 <= yy < height
                    assert not selected(xx,yy,threshold)
                    outgoing_count += 1
        next_vertex, incoming = defaultdict(list), defaultdict(list)
        for a,b in boundary:
            next_vertex[a].append(b)
            incoming[b].append(a)
        assert all(len(v)==1 for v in next_vertex.values())
        assert all(len(v)==1 for v in incoming.values())
        assert set(next_vertex)==set(incoming)
        remaining, rings = set(boundary), []
        while remaining:
            start = min(remaining)[0]
            ring, u = [start], start
            while True:
                v = next_vertex[u][0]
                assert (u,v) in remaining
                remaining.remove((u,v))
                ring.append(v)
                u = v
                if u == start:
                    break
            rings.append([[x/2,y/2] for x,y in ring])
        areas = [sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]))/2 for ring in rings]
        assert abs(sum(areas)-len(pixels)) < 1e-8
        assert outgoing_count == len(boundary)
        return boundary, rings, areas

    def author_faces(geometry):
        assert geometry['type']=='Polygon'
        result = set()
        for ring in geometry['coordinates']:
            assert ring[0]==ring[-1]
            for a,b in zip(ring,ring[1:]):
                x,y = (int(round(v*2)) for v in a)
                end_x,end_y = (int(round(v*2)) for v in b)
                assert (x==end_x) != (y==end_y)
                dx = 0 if x==end_x else (2 if end_x>x else -2)
                dy = 0 if y==end_y else (2 if end_y>y else -2)
                while (x,y)!=(end_x,end_y):
                    following = (x+dx,y+dy)
                    result.add(tuple(sorted(((x,y),following))))
                    x,y = following
        return result

    records = []
    for name,slug,seed,anchor in [('Árpádtető','arpadteto',[325,82],[343,80]),('Petőfi-akna','petofi-akna',[499,25],[515,23]),('M utca','m-utca',[501,42],[514,43])]:
        sensitivity = []
        nominal = None
        for threshold in (150,170,190):
            pixels = component(seed,threshold)
            boundary,rings,areas = faces(pixels,threshold)
            source = author[f'{slug}-T{threshold}']
            assert pixels=={tuple(v) for v in source['sourcePixels']}
            assert author_faces(source['rawPixelUnionGeometry'])=={tuple(sorted(edge)) for edge in boundary}
            bounds = [min(x for x,y in pixels),min(y for x,y in pixels),max(x for x,y in pixels),max(y for x,y in pixels)]
            sensitivity.append({'darkThresholdExclusive':threshold,'rawPixelCount':len(pixels),'ringCount':len(rings),'sourcePixelCenterBounds':bounds,'isGeographicErrorBound':False})
            if threshold==170:
                assert len(rings)==1
                assert not any(x in (0,width-1) or y in (0,height-1) for x,y in pixels)
                nominal = {'sourceName':name,'sourceInteriorSeedPixel':seed,'sourceLabelAnchorPixel':anchor,'includedSourcePixelCount':len(pixels),'sourcePixelCenterBounds':bounds,'pixelSetSha256':hashlib.sha256(json.dumps(sorted(map(list,pixels)),separators=(',',':')).encode()).hexdigest(),'allIncludedPixelsPassExplicitMask':True,'allOutgoingFacesHaveUnselectedOppositePixel':True,'outgoingFaceCount':len(boundary),'ringCount':1,'ringSignedAreasPixelsSquared':areas,'externalPixelEdgeRing':rings[0],'notAtImageEdge':True,'authorRawPixelSetExactlyMatches':True,'authorPixelGeometryExactlyMatchesAllUnitFaces':True}
        nominal.update({'thresholdRenderingSensitivity':sensitivity,'sourceFineUnitIdentitySupported':True,'sourceFineUnitIdentityMeaning':'Both original quarter maps depict the named complete isolated fine-unit island at this position; it is not a text glyph or generic land-use proxy. This does not certify that this threshold-selected subset is the complete island.','rawComponentArithmeticPassed':True,'completeLiteralSourceContourCertified':False,'approvedForNewInferredQuarterPolygon':False,'geographicRegistrationEvaluated':False,'claimedAbsoluteAccuracy':None,'usableForAddressAssignment':False})
        if name=='Petőfi-akna':
            nominal['specificCompletenessBlocker']='The pale northern cap pixels[500,19] RGB223/211/235 and[500,20] RGB234/217/251 are excluded at170and190, giving a visible notch. A valid one-ring component does not establish the whole mapped cap.'
        else:
            nominal['specificCompletenessBlocker']='Mixed gray/color antialias pixels at the tiny outer stroke remain threshold-dependent. This audit confirms literal mask arithmetic, not a uniquely complete original outer boundary.'
        records.append(nominal)
    return {'schemaVersion':1,'reviewDate':'2026-11-14','status':'raw_pixel_arithmetic_passes_whole_footprint_certification_withheld','reviewScope':'Independent whole-image source-pixel BFS and exact face audit for three isolated original Figure9 fine units. No author extractor imported/invoked.','sourceImage':{'path':'../municipal-pecs-remaining-next/pecs-p48-names.jpeg','sha256':sha(SOURCE),'width':width,'height':height},'authorOutputInput':{'path':author_path.name,'sha256':sha(author_path)},'sourceMask':'((min(R,B)-G>=25) and (B-R>=-30)) or (max(R,G,B)<170)','connectivity':4,'independentMethod':'Python stack BFS over full original image with direct PIL pixel values; exact oriented square-pixel face cancellation and ring walking. Author output geometry is independently expanded to unit faces. No Shapely, morphology, fill, closing, repair, snap, crop closure or geographic transform.','authorExtractorImportedOrInvoked':False,'records':records,'sourcePixelCandidates':3,'newApprovedWholeFootprints':0,'source9NegativeOtherNames':['Murom','Köztemető'],'otherNameEvidence':'murom-cemetery-source9-continuity-review.json','thresholdSensitivityMeaning':'150/190 are alternate literal raster classifications, not geographic uncertainty,error radii,probability or alternate geographic fits.170includes actual observed gray pixels directly; no pixel is fabricated or filled.','georeferenceModelApproved':False,'automaticPrimaryApproval':False,'claimedAbsoluteAccuracy':None,'usableForAddressAssignment':False,'newWorldGeometriesCreated':0,'networkUsed':False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    report = build()
    expected = json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    path = P/'independent-islands-pixel-review.json'
    if args.check:
        assert path.read_text()==expected
    else:
        path.write_text(expected)
    print(json.dumps({'independentRawPixelAuditPassed':True,'sourcePixelCandidates':3,'newApprovedWholeFootprints':0,'check':args.check}))


if __name__=='__main__':
    main()
