#!/usr/bin/env python3
"""Source-only isolated-island pixel-mask experiment; no geographic transform."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely.geometry import box, mapping
from shapely.ops import unary_union

P = Path(__file__).resolve().parent
S = P.parent / 'municipal-pecs-first-inferred'
ISLANDS = [
    ('arpadteto', 'Árpádtető', (325, 84), (315, 66, 337, 95), (550, 168, 590, 208)),
    ('petofi-akna', 'Petőfi-akna', (499, 26), (489, 12, 512, 38), (838, 72, 873, 110)),
    ('m-utca', 'M utca', (500, 41), (492, 34, 510, 52), (846, 108, 870, 132)),
]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'

def build(write_images):
    source = Image.open(S / 'pecs-p48-names.jpeg').convert('RGB')
    density = Image.open(S / 'pecs-p63-density.jpeg').convert('RGB')
    rgb = np.asarray(source).astype(int)
    r, g, b = rgb.transpose(2, 0, 1)
    purple = (np.minimum(r, b) - g >= 25) & (b - r >= -30)
    records = []
    pixels = []
    for threshold in (150, 170, 190):
        # The criterion and labelling cover the COMPLETE original image.
        # Crops never enter the selection, component closure or geometry.
        labels, _ = ndimage.label(purple | (rgb.max(2) < threshold))
        for slug, name, seed, crop_box, density_box in ISLANDS:
            cid = int(labels[seed[1], seed[0]])
            assert cid != 0
            ys, xs = np.where(labels == cid)
            points = sorted([[int(x), int(y)] for x, y in zip(xs, ys)])
            assert all(crop_box[0] < x < crop_box[2]-1 and crop_box[1] < y < crop_box[3]-1 for x, y in points)
            geom = unary_union([box(x-.5, y-.5, x+.5, y+.5) for x, y in points])
            assert geom.geom_type == 'Polygon' and geom.is_valid
            assert geom.area == len(points)
            ring = list(geom.exterior.coords)
            assert ring[0] == ring[-1]
            ident = slug + '-T' + str(threshold)
            records.append({
                'id': ident, 'sourceName': name, 'threshold': threshold,
                'sourceSeedPixel': list(seed), 'sourcePixelCount': len(points),
                'sourcePixelSetSha256': hashlib.sha256(json.dumps(points,separators=(',',':')).encode()).hexdigest(),
                'sourcePixelBoundsInclusive': [int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())],
                'globalOriginalImageComponent': True, 'componentTouchesOriginalImageEdge': False,
                'componentTouchesEvidenceCropEdge': False,
                'pixelUnionValidSinglePolygon': True, 'exactUnitPixelArea': geom.area,
                'interiorRingCount': len(geom.interiors), 'exteriorRingVertexCount': len(ring),
                'closedExteriorRing': True,
                'morphologicalClosingOrFill': False, 'repairBufferSnapOrGeographicFit': False,
                'nominalExploratoryScenario': threshold == 170,
                'sourceContourSemanticsAutomaticallyApproved': False,
                'geographicApproval': False, 'claimedAbsoluteAccuracy': None,
            })
            pixels.append({'id': ident, 'sourcePixels': points, 'rawPixelUnionGeometry': mapping(geom)})
            if write_images:
                mask = Image.new('L', source.size)
                arr = np.zeros((source.height,source.width),dtype=np.uint8)
                arr[ys,xs] = 255
                mask = Image.fromarray(arr)
                mask.crop(crop_box).save(P / ('islands-' + ident + '-mask-native.png'))
                preview = source.crop(crop_box).resize(((crop_box[2]-crop_box[0])*24,(crop_box[3]-crop_box[1])*24), Image.Resampling.NEAREST)
                draw = ImageDraw.Draw(preview)
                selected = set(map(tuple,points))
                for x,y in points:
                    for dx,dy,coords in [(-1,0,(0,0,0,24)),(1,0,(24,0,24,24)),(0,-1,(0,0,24,0)),(0,1,(0,24,24,24))]:
                        if (x+dx,y+dy) not in selected:
                            xx=(x-crop_box[0])*24; yy=(y-crop_box[1])*24
                            draw.line((xx+coords[0],yy+coords[1],xx+coords[2],yy+coords[3]), fill=(0,255,255),width=2)
                preview.save(P / ('islands-' + ident + '-pixel-edge-preview.png'))
    if write_images:
        for slug,name,seed,crop_box,density_box in ISLANDS:
            source.crop(crop_box).save(P / ('islands-' + slug + '-figure9-native.png'))
            density.crop(density_box).save(P / ('islands-' + slug + '-figure12-native.png'))
    proof = {
        'schemaVersion':1, 'status':'source_pixel_extraction_experiment_only',
        'sourceImage':'../municipal-pecs-first-inferred/pecs-p48-names.jpeg',
        'sourceImageSha256':sha(S/'pecs-p48-names.jpeg'),
        'densityImageSha256':sha(S/'pecs-p63-density.jpeg'),
        'maskCriterion':'(min(R,B)-G>=25 and B-R>=-30) OR max(R,G,B)<T',
        'thresholds':[150,170,190],
        'componentMethod':'scipy 4-connected components over the whole original Figure9 image; retain the component containing each manually read source seed.',
        'geometryMethod':'Exact union of unit squares centered on all and only selected source pixels; retain every resulting interior ring. No pixel added, removed or restored.',
        'coordinateSpace':'Original Figure9 pixel centers, zero-based x right/y down; NOT geographic coordinates.',
        'cropBoxes': [{'sourceName':n,'figure9':list(c),'figure12':list(d)}for _,n,_,c,d in ISLANDS],
        'records':records,
        'geographicTransformUsed':False, 'newGeographicPolygons':0,
        'absoluteAccuracyClaimed':None, 'automaticPrimaryApproval':False,
    }
    return proof, {'coordinateSpace':proof['coordinateSpace'],'records':pixels}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    proof,pixels=build(not args.check)
    for name,value in [('islands-extraction-proof.json',proof),('islands-source-pixel-candidates.json',pixels)]:
        expected=encode(value)
        if args.check: assert (P/name).read_text()==expected,name
        else:(P/name).write_text(expected)
    print(encode({'check':args.check,'sourcePixelCandidates':9,'geographicPolygons':0,'automaticApproval':False}))

if __name__=='__main__':main()
