#!/usr/bin/env python3
"""Reproduce one native image-pixel footprint; emit no geographic polygon."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path

import fitz
import numpy as np
from PIL import Image
from scipy.ndimage import binary_fill_holes, label
from shapely.geometry import box, mapping
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PDF = ROOT / '.local/neighborhoods/quarter-map-batch/szolnok-foldi-ksh-map-2012.pdf'
PDF_SHA256 = 'a794b371c17810d421cf6bc6a9453d602fd964488ed674a2017cda6472d1f019'
SEED = (325, 347)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def runs(mask):
    result = []
    for y, row in enumerate(mask):
        xs = np.flatnonzero(row)
        if not len(xs):
            continue
        start = previous = int(xs[0])
        for x in xs[1:]:
            x = int(x)
            if x != previous + 1:
                result.append([y, start, previous + 1])
                start = x
            previous = x
        result.append([y, start, previous + 1])
    return result


def component(rgb, maximum_red, minimum_green, maximum_blue):
    classified = ((rgb[:, :, 0] < maximum_red) & (rgb[:, :, 1] > minimum_green)
                  & (rgb[:, :, 2] < maximum_blue))
    labels, _ = label(classified)  # Default connectivity is four-neighbour.
    value = labels[SEED[1], SEED[0]]
    assert value
    selected = labels == value
    filled = binary_fill_holes(selected)
    geometry = unary_union([box(x0 - 0.5, y - 0.5, x1 - 0.5, y + 0.5)
                            for y, x0, x1 in runs(filled)])
    # Zero-tolerance removal of collinear cell-edge vertices only.
    simplified = geometry.simplify(0, preserve_topology=True)
    assert geometry.equals_exact(simplified, 0) or geometry.symmetric_difference(simplified).area == 0
    assert geometry.geom_type == simplified.geom_type == 'Polygon'
    assert simplified.is_valid and simplified.area == int(filled.sum())
    return selected, filled, simplified


def build():
    raw = PDF.read_bytes()
    assert len(raw) == 3633854 and sha(raw) == PDF_SHA256
    document = fitz.open(stream=raw, filetype='pdf')
    assert len(document) == 235
    page = document[71]
    assert '9. ábra Szolnok város funkcionális tagozódása' in page.get_text()
    assert 'Pécs, 2012' in document[0].get_text()
    assert len(page.get_drawings()) == 0
    image = document.extract_image(153)
    assert image['width'] == 441 and image['height'] == 539
    assert image['ext'] == 'png'
    rgb = np.array(Image.open(io.BytesIO(image['image'])).convert('RGB'))
    selected, filled, geometry = component(rgb, 70, 180, 70)
    sensitivity = []
    for thresholds in [(50, 220, 50), (100, 140, 100)]:
        _, alternative_filled, alternative = component(rgb, *thresholds)
        sensitivity.append({
            'rgbThresholds': {'redLessThan': thresholds[0], 'greenGreaterThan': thresholds[1],
                              'blueLessThan': thresholds[2]},
            'filledPixelCount': int(alternative_filled.sum()),
            'boundaryHausdorffPixels': geometry.boundary.hausdorff_distance(alternative.boundary),
            'symmetricDifferencePixelArea': geometry.symmetric_difference(alternative).area,
            'interpretation': 'Color-threshold sensitivity only; not source boundary accuracy or geographic error.',
        })
    ys, xs = np.nonzero(filled)
    assert xs.min() > 0 and ys.min() > 0 and xs.max() < 440 and ys.max() < 538
    inventory = {
        'schemaVersion': 1, 'sourceUrl': 'https://ktk.pte.hu/sites/ktk.pte.hu/files/images/kepzes/phd/Foldi%20Katalin%20-%20disszertacio.pdf',
        'localRawPath': str(PDF.relative_to(ROOT)), 'pdfBytes': len(raw), 'pdfSha256': PDF_SHA256,
        'pdfPageCount': len(document), 'documentTitle': 'A fogyasztói üzletválasztási döntések az élelmiszerorientált kiskereskedelemben',
        'author': 'Földi Katalin', 'coverPlaceAndYear': 'Pécs, 2012',
        'pdfCreationMetadata': document.metadata['creationDate'],
        'underlyingSource': {'title': 'A nagyvárosok belső tagozódása – Szolnok', 'year': 2003,
                             'publisher': 'KSH Jász-Nagykun-Szolnok Megyei Igazgatósága',
                             'originalVolumeLocallyAcquired': False},
        'map': {
            'pdfPageOneBased': 72, 'printedPage': 72, 'figure': '9. ábra',
            'caption': 'Szolnok város funkcionális tagozódása', 'imageXref': 153,
            'nativeWidth': 441, 'nativeHeight': 539, 'sourceEncoding': 'PDF FlateDecode RGB image',
            'nativePdfVectorPathCountOnMapPage': 0,
            'artifact': 'figure9-native-pixels.png', 'artifactSha256': sha(image['image']),
            'decodedRgbSha256': sha(rgb.tobytes()),
            'originalCompressedImageStreamSha256': sha(document.xref_stream_raw(153)),
            'artifactEncodingNote': 'PyMuPDF decodes the PDF raster to a lossless PNG. Native pixels are preserved; PNG bytes are not claimed to be an original embedded PNG file.',
            'pdfPlacementRectangle': [list(rect) for rect in page.get_image_rects(153)],
            'pdfPlacementObservation': 'Native portrait raster is nonuniformly stretched to a landscape rectangle on the thesis page. Neither native image aspect nor PDF placement supplies geographic scale.',
        },
        'geographicProjectionOrScaleEstablished': False, 'rawPdfCommitted': False,
        'sourceOpenReuseLicenceEstablished': False, 'usableForAddressAssignment': False,
    }
    contour = {
        'schemaVersion': 1, 'coordinateSpace': 'NATIVE_IMAGE_PIXELS_NOT_GEOGRAPHIC',
        'image': 'figure9-native-pixels.png', 'imageSha256': sha(image['image']),
        'axisConvention': 'x right; y down; integer pixel centres, cell edges at ±0.5 pixels',
        'sourceLabelAsPrinted': 'Szanda-szőlős', 'labelLineBreak': ['Szanda-', 'szőlős'],
        'normalizedCandidateName': 'Szandaszőlős', 'currentCanonicalNameIndependentlyConfirmed': False,
        'semanticStatus': 'Named historical source footprint within a functional map; whole-quarter identity/current extent unverified.',
        'method': 'One actual four-connected bright-green source component selected by a manually identified interior seed. Only fully enclosed raster text/ink holes are filled; no separate colored components or exterior gaps are joined. Every contour edge follows the selected pixel-cell boundary; collinear cell-edge vertices alone are omitted.',
        'seedPixel': list(SEED), 'seedRgb': rgb[SEED[1], SEED[0]].tolist(),
        'rgbThresholds': {'redLessThan': 70, 'greenGreaterThan': 180, 'blueLessThan': 70},
        'rawSelectedPixelCount': int(selected.sum()), 'enclosedHolePixelsFilled': int((filled & ~selected).sum()),
        'filledPixelCount': int(filled.sum()), 'nativePixelArea': geometry.area,
        'rawSelectedPixelRowRuns': runs(selected), 'enclosedHolePixelRowRuns': runs(filled & ~selected),
        'rowRunConvention': '[y, first_x_inclusive, last_x_exclusive]',
        'geometry': mapping(geometry), 'validPolygon': True,
        'literalBlackStrokeTracingClaimed': False, 'estimatedColorFillFootprint': True,
        'imageFrameClosureUsed': False, 'manualCapsOrBridgingUsed': False,
        'sourceComponentClonedOntoOtherNames': False,
        'geographicTransformFitted': False, 'wgs84GeometryEmitted': False,
        'claimedAbsoluteAccuracyMetres': None, 'usableForAddressAssignment': False,
        'thresholdSensitivity': sensitivity,
    }
    preview = Image.fromarray(rgb.copy()).convert('RGB')
    from PIL import ImageDraw
    drawing = ImageDraw.Draw(preview)
    drawing.line(list(geometry.exterior.coords), fill=(255, 80, 0), width=1)
    buffer = io.BytesIO()
    preview.save(buffer, format='PNG')
    return {
        'figure9-native-pixels.png': image['image'],
        'source-inventory.json': encoded(inventory),
        'szandaszoelos-native-pixel-contour.json': encoded(contour),
        'native-contour-preview.png': buffer.getvalue(),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for filename, raw in build().items():
        if args.check:
            assert (HERE / filename).read_bytes() == raw, (filename, 'reproduction mismatch')
        else:
            (HERE / filename).write_bytes(raw)
    print('Szolnok native map and one closed pixel footprint reproduced; 0 geographic polygons emitted.')
