#!/usr/bin/env python3
"""Two historical fine source footprints; inferred registration, no address use."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer
from scipy.ndimage import binary_fill_holes, label
from shapely.affinity import affine_transform
from shapely.geometry import LineString, MultiPoint, Point, box, mapping, shape
from shapely.ops import transform, unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROJECT = Transformer.from_crs(4326, 23700, always_xy=True)
UNPROJECT = Transformer.from_crs(23700, 4326, always_xy=True)
PINS = {
    'ksh27-native.jpeg': 'aa83d4115d7073416088f8e192879ddf2592c5384b5e1b34877074bc232285c8',
    'ivs11-native.jpeg': 'c7b8fbcad8445cb3520d01a19b1fe8d0e8e32441428e20dcd3aa8b7fa7d28177',
    'current-municipality-reference.geojson': 'fcc56f1deda0b0454aac02b9664004c2847c3520db60a6fddd8a7dd621c7f373',
    'current-name-point-evidence.geojson': '10d35d10886deafcb9b942dd016c80261688cb57b49c9680a3ddb9c23201c300',
    'control-specification.json': 'a39a19138e8fa06b24b8f15e2972685886c00f54a1ccf3f410b5ac4cbc9924dd',
}
UNITS = [
    {'id': 'erkert', 'name': 'Érkert', 'upperSeed': [438, 429],
     'lowerSeed': [438, 435], 'lowerUnitNumber': 2,
     'pointIds': [984100890], 'candidateBoundaryKind': 'local_area',
     'scope': 'Historical housing-estate-class footprint. Name assignment is inferred across the upper27/lower11 statistical schemas; whole Érkert quarter identity is unverified.'},
    {'id': 'orokosfold-estate', 'name': 'Örökösföld lakótelep',
     'upperSeed': [522, 368], 'lowerSeed': [518, 362], 'lowerUnitNumber': 3,
     'pointIds': [7966635459, 984100891], 'candidateBoundaryKind': 'neighbourhood',
     'scope': 'Estimated historical neighborhood candidate supported by the strong upper-component/lower-unit3 source-map correspondence. The lower legend does not directly label the upper27 map.'},
]
IMAGE_PAIRS = [
    ([7, 542], [10, 538]), ([371, 823], [378, 817]),
    ([621, 795], [625, 788]), ([825, 491], [827, 487]),
    ([773, 200], [777, 196]), ([426, 108], [429, 102]),
    ([249, 12], [254, 7]),
]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def load(name):
    return json.loads((HERE / name).read_text())


def runs(mask):
    result = []
    for y, row in enumerate(mask):
        xs = np.flatnonzero(row)
        if not len(xs):
            continue
        first = previous = int(xs[0])
        for x in xs[1:]:
            x = int(x)
            if x != previous + 1:
                result.append([y, first, previous + 1])
                first = x
            previous = x
        result.append([y, first, previous + 1])
    return result


def mask_shape(classified, seed):
    components, _ = label(classified)
    selected_id = components[seed[1], seed[0]]
    assert selected_id
    selected = components == selected_id
    filled = binary_fill_holes(selected)
    geometry = unary_union([box(a - .5, y - .5, b - .5, y + .5)
                            for y, a, b in runs(filled)])
    simple = geometry.simplify(0, preserve_topology=True)
    assert simple.geom_type == 'Polygon' and simple.is_valid
    assert simple.area == filled.sum() and simple.symmetric_difference(geometry).area == 0
    return selected, filled, simple


def affine_from_beta(beta):
    return [beta[0, 0], beta[1, 0], beta[0, 1], beta[1, 1], beta[2, 0], beta[2, 1]]


def blue_class(hsv, settings=(135, 190, 65, 45)):
    h0, h1, s, v = settings
    return ((hsv[:, :, 0] > h0) & (hsv[:, :, 0] < h1)
            & (hsv[:, :, 1] > s) & (hsv[:, :, 2] > v))


def point_summary(point, world, eov, beta):
    xy = point['geometry']['coordinates']
    projected = Point(PROJECT.transform(*xy))
    native = (np.array(projected.coords[0]) - beta[2]) @ np.linalg.inv(beta[:2].T).T
    return {
        'name': point['properties']['name'],
        'osmNodeId': point['properties']['source']['osmId'], 'wgs84': xy,
        'withinHistoricalCandidate': bool(world.covers(Point(xy))),
        'distanceToHistoricalCandidateMetres': projected.distance(eov),
        'nativeImageCoordinateUnderFit': native.tolist(),
        'usedAsRegistrationControl': False,
        'interpretation': 'A current named point supports existence of the name, not historical or current extent. Outside does not disqualify an explicitly historical estimated footprint and is not corrected by moving the fit.',
    }


def build():
    for filename, expected in PINS.items():
        assert sha((HERE / filename).read_bytes()) == expected, filename
    inventory = load('source-inventory.json')
    pdf_raw = (ROOT / inventory['localPdfPath']).read_bytes()
    assert sha(pdf_raw) == inventory['pdfSha256']
    doc = fitz.open(stream=pdf_raw, filetype='pdf')
    assert '2008. MÁRCIUS' in doc[0].get_text()
    assert 'A KSH 27' in doc[40].get_text()
    assert '11 városrészt határoltunk le' in doc[41].get_text()
    for entry in inventory['maps']:
        assert doc.extract_image(entry['xref'])['image'] == (HERE / entry['path']).read_bytes()
    upper = Image.open(HERE / 'ksh27-native.jpeg').convert('RGB')
    lower = Image.open(HERE / 'ivs11-native.jpeg').convert('RGB')
    upper_hsv = np.array(upper.convert('HSV'))
    lower_rgb = np.array(lower)
    lower_hsv = np.array(lower.convert('HSV'))
    municipality = load('current-municipality-reference.geojson')['features'][0]
    municipal_world = shape(municipality['geometry'])
    municipal_eov = transform(PROJECT.transform, municipal_world)
    main_ring = max(municipal_world.geoms, key=lambda part: part.area).exterior.coords
    controls = load('control-specification.json')['controls']
    for control in controls:
        assert list(main_ring[control['targetOriginalExteriorVertexIndex']]) == control['targetWgs84']
        assert np.linalg.norm(np.array(PROJECT.transform(*control['targetWgs84'])) - control['targetEov']) < 1e-7
    fit = [control for control in controls if control['role'] == 'fit']
    beta = np.linalg.lstsq(np.array([[*c['sourcePixel'], 1] for c in fit]),
                           np.array([c['targetEov'] for c in fit]), rcond=None)[0]
    coefficients = affine_from_beta(beta)
    residuals = []
    for control in controls:
        prediction = np.array([*control['sourcePixel'], 1]) @ beta
        residuals.append(control | {'predictionEov': prediction.tolist(),
                                    'residualMetres': float(np.linalg.norm(prediction - control['targetEov']))})
    image_beta = np.linalg.lstsq(np.array([[*a, 1] for a, b in IMAGE_PAIRS]),
                                 np.array([b for a, b in IMAGE_PAIRS]), rcond=None)[0]
    image_coefficients = affine_from_beta(image_beta)
    image_fit_residuals = np.linalg.norm(np.array([[*a, 1] for a, b in IMAGE_PAIRS]) @ image_beta
                                        - np.array([b for a, b in IMAGE_PAIRS]), axis=1)
    point_features = load('current-name-point-evidence.geojson')['features']
    features, pixel_records, identities = [], [], []
    native_geometries = []
    hull = MultiPoint([control['sourcePixel'] for control in fit]).convex_hull
    for unit in UNITS:
        selected, filled, geometry = mask_shape(blue_class(upper_hsv), unit['upperSeed'])
        x0, y0, x1, y1 = geometry.bounds
        assert x0 > 0 and y0 > 0 and x1 < upper.width - 1 and y1 < upper.height - 1
        sensitivity = []
        for settings in [(130, 195, 50, 40), (140, 185, 85, 65)]:
            _, alternative_mask, alternative = mask_shape(blue_class(upper_hsv, settings), unit['upperSeed'])
            sensitivity.append({'hsvSettings': list(settings), 'filledPixelCount': int(alternative_mask.sum()),
                                'boundaryHausdorffPixels': geometry.boundary.hausdorff_distance(alternative.boundary),
                                'notGeographicAccuracy': True})
        if unit['lowerUnitNumber'] == 3:
            lower_class = ((lower_rgb[:, :, 0] > 70) & (lower_rgb[:, :, 0] < 180)
                           & (lower_rgb[:, :, 1] < 40) & (lower_rgb[:, :, 2] < 40))
        else:
            lower_class = ((lower_hsv[:, :, 0] > 80) & (lower_hsv[:, :, 0] < 130)
                           & (lower_hsv[:, :, 1] > 30) & (lower_hsv[:, :, 2] > 15))
        _, lower_filled, lower_geometry = mask_shape(lower_class, unit['lowerSeed'])
        comparison = affine_transform(lower_geometry, image_coefficients)
        iou = comparison.intersection(geometry).area / comparison.union(geometry).area
        identities.append({
            'name': unit['name'], 'upperSeedPixel': unit['upperSeed'],
            'upperMapRole': 'One finer KSH27 housing-estate-class component; the class is not a name.',
            'lowerIvsNumber': unit['lowerUnitNumber'], 'lowerPrintedLegendName': unit['name'],
            'lowerSeedPixel': unit['lowerSeed'],
            'identityBasis': 'Explicit numbered name in the lower legend, corresponding small footprint in the same city sector, and upper/lower source-map comparison. Source text says the 11 units merge KSH 27 units. The lower11 key does not directly label the upper27 components; cross-schema name assignment remains an inference. No class color is assigned one name globally.',
            'candidateBoundaryKind': unit['candidateBoundaryKind'],
            'scope': unit['scope'],
            'lowerLegendDirectlyLabelsUpperComponent': False,
            'comparisonIntersectionOverUnion': iou,
            'comparisonModel': 'Affine between maps from seven paired municipal-outline corners, separate from geographic fit.',
            'exactPixelGeometryEqualityClaimed': False,
            'lowerGeometryUsedToConstructUpperCandidate': False,
            'wholeHistoricalSourceUnitIdentityRequiresIndependentVisualReview': True,
        })
        eov = affine_transform(geometry, coefficients)
        world = transform(UNPROJECT.transform, eov)
        assert world.is_valid and eov.is_valid
        points = [point_summary(point, world, eov, beta) for point in point_features
                  if point['properties']['source']['osmId'] in unit['pointIds']]
        extrapolation = max(Point(c).distance(hull) for c in geometry.exterior.coords)
        pixel_records.append({
            'id': unit['id'], 'name': unit['name'], 'coordinateSpace': 'NATIVE_IMAGE_PIXELS_NOT_GEOGRAPHIC',
            'sourceImage': 'ksh27-native.jpeg', 'sourceImageSha256': PINS['ksh27-native.jpeg'],
            'seedPixel': unit['upperSeed'], 'seedRgb': np.array(upper)[unit['upperSeed'][1], unit['upperSeed'][0]].tolist(),
            'hsvSettings': [135, 190, 65, 45], 'hsvConvention': 'Pillow H/S/V on 0–255; H strictly between endpoints, S/V strictly above thresholds.',
            'rawSelectedPixelCount': int(selected.sum()), 'enclosedHolePixelCount': int((filled & ~selected).sum()),
            'filledPixelCount': int(filled.sum()), 'pixelArea': geometry.area,
            'selectedPixelRowRuns': runs(selected), 'enclosedHoleRowRuns': runs(filled & ~selected),
            'rowRunConvention': '[y, first_x_inclusive, last_x_exclusive]',
            'geometry': mapping(geometry), 'thresholdSensitivity': sensitivity,
            'literalBlackStrokeTracingClaimed': False, 'estimatedColorFillFootprint': True,
            'imageFrameClosureOrManualCapsUsed': False,
        })
        properties = {
            'name': unit['name'], 'municipality': 'Nyíregyháza',
            'estimated': True, 'boundaryKind': 'inferred_area', 'candidateBoundaryKind': unit['candidateBoundaryKind'],
            'canonicalNameIsNeighborhood': False, 'usableForAddressAssignment': False,
            'sourceIsHardBoundary': False, 'sourceIsOfficial': False,
            'confidence': 'low', 'sourcePeriod': 'KSH 2003 division / 2001 census, reproduced in March 2008 municipal IVS',
            'historicalGeometryOnly': True, 'currentWholeExtentValidated': False,
            'sourceScope': unit['scope'],
            'nameAssignmentInferredAcrossStatisticalSchemas': True,
            'lowerLegendDirectlyLabelsUpperComponent': False,
            'wholeHistoricalQuarterIdentityVerified': False,
            'currentExactNameObservedInPbf': True, 'currentNamePointEvidence': points,
            'pointLocationUsedAsRegistrationControl': False,
            'sourceFineMapUnnumberedComponent': True, 'identityNamedLowerIvsUnit': unit['lowerUnitNumber'],
            'sourcePdfSha256': inventory['pdfSha256'], 'sourcePdfPage': 43, 'sourceImageXref': 139,
            'sourceUrl': inventory['sourceUrl'], 'georeferenceStatus': 'inferred_georeference',
            'georeferenceValidated': False, 'independentInteriorPhysicalHoldoutCount': 0,
            'claimedAbsoluteAccuracyMetres': None,
            'modelExtrapolationBeyondFitControlHullPixels': extrapolation,
            'hullDistanceIsAccuracyClaim': False,
            'method': 'Actual upper KSH 27 map component, four-neighbour HSV color mask and pixel-cell boundary. Only fully enclosed raster ink/noise holes filled; only collinear cell-edge vertices removed. Inferred affine from 11 municipal-outline corner correspondences to current OSM relation 1447608; 10 outline corners withheld. Current name points are diagnostic only. No class-to-name cloning, lower-group geometry substitution, buffers, hull boundary, missing-edge cap, frame closure or current-municipality clipping.',
            'sourceControlAndAgeUncertainty': 'The underlying 2003 quarter outlines are historical; source map generalization and equivalence of 2003/2008 versus 2026 municipal corners are unverified. Manual corner residuals and withheld same-outline points do not validate internal quarter positions. Exact current named points can lie outside the historical source footprint and the fit is not shifted to them.',
            'areaSquareMetresEov': eov.area, 'perimeterMetresEov': eov.length,
            'outsideCurrentMunicipalityAreaM2Diagnostic': eov.difference(municipal_eov).area,
            'municipalityClippingApplied': False,
            'license': 'Municipal/KSH map open-reuse rights unverified; ODbL-1.0 for OSM references.',
        }
        features.append({'type': 'Feature', 'id': 'nyiregyhaza-ksh2003-' + unit['id'],
                         'properties': properties, 'geometry': mapping(world)})
        native_geometries.append((unit, geometry))
    summaries = {}
    for role in ['fit', 'held_out']:
        values = [c['residualMetres'] for c in residuals if c['role'] == role]
        summaries[role] = {'count': len(values), 'medianMetres': float(np.median(values)),
                           'p95Metres': float(np.percentile(values, 95)), 'maximumMetres': float(max(values)),
                           'isAbsoluteAccuracyBound': False}
    georef = {
        'schemaVersion': 1, 'fitModel': 'Affine native image pixels to EPSG:23700, then WGS84',
        'affineBetaRowsX_Y_Offset': beta.tolist(), 'shapelyAffineCoefficients': coefficients,
        'controlsAndResiduals': residuals, 'summary': summaries,
        'sameMunicipalOutlineHoldoutsAreNotIndependentInteriorControls': True,
        'independentInteriorPhysicalHoldoutCount': 0, 'claimedAbsoluteAccuracyMetres': None,
        'manualCornerIdentificationAndHistoricalBoundaryChangeUncertaintyQuantified': False,
        'placeNamePointsUsedAsControls': False, 'fitAdjustedToPointPositions': False,
        'sourceMunicipalityNorthernTipTouchesImageEdge': True,
        'northImageFrameClosureUsed': False,
        'explanation': 'Only explicitly selected visible boundary-corner coordinates enter the fit. No closed image-frame polygon is fitted or emitted. Candidate footprints are internal and do not touch the image frame.',
        'imageToImageIdentityComparison': {
            'pairedMunicipalOutlinePixelsLowerThenUpper': IMAGE_PAIRS,
            'affineBetaRowsX_Y_Offset': image_beta.tolist(),
            'pairedCornerResidualPixels': image_fit_residuals.tolist(),
            'usedAsWorldGeoreference': False,
        },
    }
    identity = {'schemaVersion': 1, 'sourceSchemeCounts': {'upperKsh': 27, 'lowerIvs': 11},
                'sourceTextEvidence': {'pdfPage41': 'KSH identified 27 quarters based on 2001 census data.',
                                      'pdfPage42': 'The IVS formed 11 quarters by merging KSH units.'},
                'candidateNames': identities,
                'unkeyedOtherUpperComponentsAdmitted': False,
                'allSameColorComponentsAssignedSameName': False}
    registration_preview = upper.copy()
    draw = ImageDraw.Draw(registration_preview)
    inverse = np.linalg.inv(beta[:2].T)
    for part in municipal_eov.geoms:
        coords = [(np.array(c) - beta[2]) @ inverse.T for c in part.exterior.coords]
        draw.line([tuple(c) for c in coords], fill=(255, 0, 0), width=2)
    for control in controls:
        x, y = control['sourcePixel']
        color = (0, 0, 255) if control['role'] == 'fit' else (180, 0, 180)
        draw.ellipse([x-3, y-3, x+3, y+3], outline=color, width=2)
    for unit, geometry in native_geometries:
        draw.line(list(geometry.exterior.coords), fill=(255, 255, 255), width=1)
    for point in point_features:
        xy = (np.array(PROJECT.transform(*point['geometry']['coordinates'])) - beta[2]) @ inverse.T
        x, y = xy
        draw.ellipse([x-3, y-3, x+3, y+3], fill=(255, 0, 255))
    buffer = io.BytesIO(); registration_preview.save(buffer, format='PNG')
    # Actual source crops provide a legible name key. They are not redrawn maps.
    upper_crop = upper.crop((390, 305, 560, 458)).resize((510, 459), Image.Resampling.NEAREST)
    lower_crop = lower.crop((390, 310, 560, 463)).resize((510, 459), Image.Resampling.NEAREST)
    legend = lower.crop((837, 420, 1129, 510)).resize((876, 270), Image.Resampling.NEAREST)
    comparison_preview = Image.new('RGB', (1040, 810), 'white')
    comparison_preview.paste(upper_crop, (10, 35)); comparison_preview.paste(lower_crop, (520, 35))
    comparison_preview.paste(legend, (15, 520)); labels = ImageDraw.Draw(comparison_preview)
    labels.text((10, 10), 'Upper: actual KSH27 source pixels', fill='black')
    labels.text((520, 10), 'Lower: actual numbered IVS11 source pixels', fill='black')
    labels.text((15, 500), 'Actual lower-map legend: unit 2 Erkert, unit 3 Orokosfold lakotelep', fill='black')
    identity_buffer = io.BytesIO(); comparison_preview.save(identity_buffer, format='PNG')
    return {
        'fine-historical-candidates.geojson': encoded({'type': 'FeatureCollection', 'features': features}),
        'native-pixel-contours.json': encoded({'schemaVersion': 1, 'coordinateSpace': 'NATIVE_IMAGE_PIXELS_NOT_GEOGRAPHIC', 'units': pixel_records}),
        'georeference-proof.json': encoded(georef), 'source-name-key-proof.json': encoded(identity),
        'registration-review.png': buffer.getvalue(), 'source-name-key-review.png': identity_buffer.getvalue(),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    outputs = build()
    for filename, raw in outputs.items():
        if args.check:
            assert (HERE / filename).read_bytes() == raw, (filename, 'reproduction mismatch')
        else:
            (HERE / filename).write_bytes(raw)
    proof = json.loads(outputs['georeference-proof.json'])
    print(json.dumps({'historicalInferredCandidates': 2, 'neighborhoodCandidates': 1,
                      'localAreaCandidates': 1, 'primaryFeatures': 0,
                      'addressAssignmentAllowed': False, 'outlineResidualsNotAccuracy': proof['summary']}))
