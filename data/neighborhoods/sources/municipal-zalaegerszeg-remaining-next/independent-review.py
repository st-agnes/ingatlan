#!/usr/bin/env python3
"""Independent offline source/registration audit; never edits producer geometries."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

import fitz
import numpy as np
from PIL import Image
from scipy import ndimage
import shapely
from shapely.geometry import shape, mapping, LineString, box
from shapely.ops import transform, polygonize, unary_union
from pyproj import Transformer

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
FROZEN = ROOT / 'data/neighborhoods/sources/municipal-local-map-next'
NAMES = {6: 'Iparterület', 10: 'Zalabesenyő', 11: 'Botfa', 12: 'Bazita', 13: 'Ebergény', 14: 'Szenterzsébethegy'}
REGIONS = {6: [42, 64], 10: [77], 11: [83, 87], 12: [80, 91, 92], 13: [60, 68, 70], 14: [44, 47]}
LABELS = {6: [46, 73], 10: [81], 11: [88], 12: [89], 13: [66], 14: [53]}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1048576), b''):
            h.update(part)
    return h.hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def verify_registration(blue, frozen_matrix, parent):
    """Refit from recomputed original connected components, without saved anchors."""
    components, count = ndimage.label(blue, np.ones((3, 3), dtype=bool))
    boxes = ndimage.find_objects(components)
    sizes = np.bincount(components.ravel())
    ids = [i for i, b in enumerate(boxes, 1) if b is not None and 15 <= sizes[i] <= 230
           and max(b[0].stop-b[0].start, b[1].stop-b[1].start) <= 32]
    centers_yx = ndimage.center_of_mass(blue, components, ids)
    centers = np.asarray([(x, y) for y, x in centers_yx])
    metric = Transformer.from_crs(4326, 23700, always_xy=True)
    metric_parent = transform(metric.transform, parent)
    polygons = list(metric_parent.geoms) if hasattr(metric_parent, 'geoms') else [metric_parent]
    perimeter = max(polygons, key=lambda g: g.area).exterior
    ys, xs = np.where(blue)
    pixels = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    x0, y0, x1, y1 = pixels
    e0, n0, e1, n1 = perimeter.bounds
    xscale, yscale = (e1-e0)/(x1-x0), (n1-n0)/(y1-y0)
    matrix = np.asarray([[xscale, 0], [0, -yscale], [e0-x0*xscale, n1+y0*yscale]])
    design = np.column_stack((centers, np.ones(len(centers))))
    keep = shapely.distance(shapely.points(design @ matrix), perimeter) < 180
    design = design[keep]
    for iteration in range(80):
        predicted = design @ matrix
        fractions = shapely.line_locate_point(perimeter, shapely.points(predicted))
        nearest = shapely.get_coordinates(shapely.line_interpolate_point(perimeter, fractions))
        distances = np.linalg.norm(predicted-nearest, axis=1)
        selected = distances < min(100, np.quantile(distances, .9))
        updated = np.linalg.lstsq(design[selected], nearest[selected], rcond=None)[0]
        if np.max(np.abs(updated-matrix)) < 1e-6:
            break
        matrix = updated
    registration = json.loads((OUT / 'zalaegerszeg-registration.json').read_text())
    actual_anchors = design[:, :2]
    saved_anchors = np.asarray(registration['dashComponentCentersPixels'])
    residuals = shapely.distance(shapely.points(design @ frozen_matrix), perimeter)
    return {
        'sourceMaskComponentsEightNeighbor': count,
        'smallSourceDashComponentCount': len(ids),
        'initialNearPerimeterCount': int(keep.sum()),
        'initialPixelBounds': pixels, 'iterations': iteration,
        'recomputedMatrixPixelToEov': matrix.tolist(),
        'maximumMatrixCoefficientDifference': float(np.max(np.abs(matrix-frozen_matrix))),
        'allSavedAnchorsMatchRecomputedSourceComponents': bool(np.allclose(actual_anchors, saved_anchors, atol=1e-10, rtol=0)),
        'maximumResidualDifferenceMetres': float(np.max(np.abs(residuals-np.asarray(registration['residualsM'])))),
        'perimeterResidualPercentilesMetres': {str(p): float(np.percentile(residuals, p)) for p in [0, 50, 90, 100]},
        'independentInteriorControlCount': 0, 'absoluteBoundaryAccuracyMetres': None,
        'perimeterResidualsAreIndependentAccuracy': False,
        'currentNamePointsUsedAsControls': False,
    }


def exposed_faces(mask):
    """Every included source cell exposes four axis-aligned half-pixel faces."""
    result = set()
    ys, xs = np.where(mask)
    height, width = mask.shape
    for x, y in zip(xs, ys):
        if y == 0 or not mask[y-1, x]:
            result.add(((2*x-1, 2*y-1), (2*x+1, 2*y-1)))
        if y == height-1 or not mask[y+1, x]:
            result.add(((2*x-1, 2*y+1), (2*x+1, 2*y+1)))
        if x == 0 or not mask[y, x-1]:
            result.add(((2*x-1, 2*y-1), (2*x-1, 2*y+1)))
        if x == width-1 or not mask[y, x+1]:
            result.add(((2*x+1, 2*y-1), (2*x+1, 2*y+1)))
    return result


def geometry_faces(g):
    faces = set()
    non_grid = []
    polygons = list(g.geoms) if g.geom_type == 'MultiPolygon' else [g]
    for p in polygons:
        for ring in [p.exterior, *p.interiors]:
            coords = list(ring.coords)
            for a, b in zip(coords, coords[1:]):
                a2, b2 = np.asarray(a)*2, np.asarray(b)*2
                length = abs(b[0]-a[0])+abs(b[1]-a[1])
                if not (np.allclose(a2, np.rint(a2)) and np.allclose(b2, np.rint(b2))
                        and all(int(round(v)) % 2 for v in [*a2, *b2])
                        and (a[0] == b[0] or a[1] == b[1]) and length == int(length)):
                    non_grid.append([list(a), list(b)])
                    continue
                count = int(length)
                delta = (b2-a2)/count if count else np.zeros(2)
                for step in range(count):
                    start = tuple(int(round(v)) for v in a2+step*delta)
                    end = tuple(int(round(v)) for v in a2+(step+1)*delta)
                    faces.add(tuple(sorted((start, end))))
    return faces, non_grid


def adjacent_teal(face, blue):
    a, b = face
    x, y = (a[0]+b[0])/4, (a[1]+b[1])/4
    if a[0] == b[0]:
        neighbors = [(int(x-.5), int(y)), (int(x+.5), int(y))]
    else:
        neighbors = [(int(x), int(y-.5)), (int(x), int(y+.5))]
    return any(0 <= yy < blue.shape[0] and 0 <= xx < blue.shape[1] and blue[yy, xx] for xx, yy in neighbors)


def geometry_from_exposed_faces(mask):
    """Polygonize independently enumerated cell faces, with no row-run union."""
    faces = exposed_faces(mask)
    lines = [LineString([(x/2, y/2) for x, y in face]) for face in faces]
    selected = []
    for polygon in polygonize(lines):
        point = polygon.representative_point()
        x, y = int(np.floor(point.x+.5)), int(np.floor(point.y+.5))
        if 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1] and mask[y, x]:
            selected.append(polygon)
    g = unary_union(selected)
    if not g.is_valid or abs(g.area-int(mask.sum())) > 1e-9:
        raise ValueError('Independent exposed-face polygonization failed')
    return g


def candidate_audit(free, blue, literal_masks, matrix, parent):
    required = ['remaining-literal-source-pixels.geojson', 'remaining-literal-world.geojson',
                'remaining-manual-source-pixels.geojson', 'remaining-manual-world.geojson',
                'remaining-manual-reconstruction-proof.json']
    if not all((OUT / name).exists() for name in required):
        return {'status': 'producer_candidates_not_yet_available'}
    source_features = [f for name in [required[0], required[2]] for f in json.loads((OUT / name).read_text())['features']]
    world_features = [f for name in [required[1], required[3]] for f in json.loads((OUT / name).read_text())['features']]
    worlds = {f['properties']['sourceUnitNumber']: f for f in world_features}
    proofs = {f['sourceUnitNumber']: f for f in json.loads((OUT / required[4]).read_text())['records']}
    alternatives_path = OUT / 'remaining-manual-cap-alternatives-source-pixels.geojson'
    alternatives = json.loads(alternatives_path.read_text())['features'] if alternatives_path.exists() else []
    names_path = OUT / 'current-name-evidence.geojson'
    name_features = json.loads(names_path.read_text())['features'] if names_path.exists() else []
    frozen_features = json.loads((FROZEN / 'zalaegerszeg-import.geojson').read_text())['features']
    to_world = Transformer.from_crs(23700, 4326, always_xy=True)
    to_eov = Transformer.from_crs(4326, 23700, always_xy=True)
    def geographic(x, y, z=None):
        x, y = np.asarray(x), np.asarray(y)
        e = x*matrix[0, 0]+y*matrix[1, 0]+matrix[2, 0]
        n = x*matrix[0, 1]+y*matrix[1, 1]+matrix[2, 1]
        return to_world.transform(e, n)
    strict = json.loads(subprocess.check_output([
        'node', str(OUT / 'independent-strict-validator.mjs'), required[1], required[3]], cwd=ROOT, text=True))
    strict_by_number = {r['sourceUnitNumber']: r for r in strict['records']}
    records = []
    overlaps = []
    for source in source_features:
        p = source['properties']; number = p['sourceUnitNumber']
        pixel = shape(source['geometry'])
        world = shape(worlds[number]['geometry'])
        expected_world = transform(geographic, pixel)
        eov = transform(to_eov.transform, world)
        outside = transform(to_eov.transform, world.difference(parent)).area
        record = {'sourceUnitNumber': number, 'name': p['name'],
                  'sourceGeometryValid': pixel.is_valid, 'worldGeometryValid': world.is_valid,
                  'sourceGeometryBounds': list(pixel.bounds),
                  'sourceBoundsWithinOriginalRaster': bool(pixel.bounds[0] >= -.5 and pixel.bounds[1] >= -.5 and pixel.bounds[2] <= 1662.5 and pixel.bounds[3] <= 2359.5),
                  'worldCoordinateBounds': list(world.bounds),
                  'worldMatchesFrozenTransformationExactly': expected_world.equals_exact(world, 0),
                  'worldSymmetricDifferenceDegreesSquared': expected_world.symmetric_difference(world).area,
                  'outsideCurrentMunicipalityAreaM2': outside,
                  'municipalityOverlapFraction': 1-outside/eov.area,
                  'estimatedFlag': p.get('estimated'),
                  'strictValidator': strict_by_number[number]}
        current_names = [f for f in name_features if f['properties']['requestedName'] == p['name'] and f['properties']['nameRole'] == 'named_place']
        record['currentNameStatus'] = 'same_city_exact_osm_name_observed' if current_names else 'not_independently_confirmed'
        record['currentNameEvidenceIsGeoreferenceControl'] = False
        record['currentNameEvidence'] = [{'id': f['id'], 'name': f['properties']['name'],
                                          'insideHistoricalSourceGeometry': world.covers(shape(f['geometry'])),
                                          'distanceFromHistoricalSourceGeometryMetres': eov.distance(transform(to_eov.transform, shape(f['geometry']))),
                                          'sourceUrl': f['properties']['sourceUrl']}
                                         for f in current_names]
        if number == 6:
            expected_mask = literal_masks[42] | literal_masks[64]
            expected_faces = exposed_faces(expected_mask)
            actual_faces, nongrid = geometry_faces(pixel)
            record.update({'independentLiteralIncludedCellCount': int(expected_mask.sum()),
                           'independentLiteralBoundaryFaceCount': len(expected_faces),
                           'sourceBoundaryFaceMismatchCount': len(actual_faces.symmetric_difference(expected_faces)),
                           'nonGridSegments': nongrid,
                           'allSourceFacesAdjacentOriginalTeal': all(adjacent_teal(face, blue) for face in expected_faces),
                           'sourceAreaEqualsIncludedCells': pixel.area == int(expected_mask.sum()),
                           'sourcePartsCount': len(pixel.geoms) if hasattr(pixel, 'geoms') else 1,
                           'literalGeometryExact': actual_faces == expected_faces and not nongrid,
                           'estimatedFalseAppropriateForLiteralSource': p.get('estimated') is False})
        else:
            proof = proofs[number]
            ids = proof['sourceComponents']
            original = geometry_from_exposed_faces(np.isin(free, ids))
            window = shape(proof['windowGeometry']) if 'windowGeometry' in proof else box(*proof['windowPixels'])
            expected_outside = original.difference(window)
            actual_outside = pixel.difference(window)
            outside_difference = expected_outside.symmetric_difference(actual_outside).area
            patch = shape(proof['inferredPatchGeometry'])
            cap_geom = shape(proof['capGeometry'])
            record.update({'sourceComponentsIncluded': ids,
                           'observedOutsideAnnotationWindowSymmetricDifferencePixelsSquared': outside_difference,
                           'observedOutsideWindowExact': outside_difference < 1e-8,
                           'inferredPatchWithinAnnotationWindow': window.buffer(1e-9).covers(patch),
                           'inferredPatchAreaPixelsSquared': patch.area,
                           'annotationAndInferenceAreaDeltaFromRawLobesPixelsSquared': pixel.area-original.area,
                           'inferredBoundaryLengthPixels': cap_geom.length,
                           'inferredPerimeterFraction': cap_geom.length/pixel.length,
                           'removedObservedAndAnnotationBoundaryLengthPixels': original.boundary.intersection(window).length,
                           'sourceWindowBounds': list(window.bounds),
                           'inferredBoundaryConfinedToWindow': window.buffer(1e-9).covers(cap_geom),
                           'reconstructionFlagAppropriate': p.get('estimated') is True,
                           'boundaryReconstructionConfidence': p.get('boundaryReconstructionConfidence'),
                           'unlabelledComponentAssignmentConcern': 'Detached unnumbered92 must remain unassigned' if number == 12 else 'Southwest70 requires alternate assignment excluding this lobe' if number == 13 else None})
            local_alternatives = [f for f in alternatives if f['properties']['sourceUnitNumber'] == number]
            record['capAlternativeCount'] = len(local_alternatives)
            record['allAlternativesFlaggedUnobservedAndLowConfidence'] = bool(local_alternatives) and all(
                f['properties'].get('observed') is False and f['properties'].get('confidence') == 'low' for f in local_alternatives)
            record['allCapAlternativesWithinAnnotationWindow'] = bool(local_alternatives) and all(
                window.buffer(1e-9).covers(shape(f['geometry'])) for f in local_alternatives)
        for old in frozen_features:
            area = world.intersection(shape(old['geometry'])).area
            if area > 1e-16:
                overlaps.append({'newUnit': number, 'frozenPrimaryName': old['properties']['name'], 'areaDegreesSquared': area})
        records.append(record)
    for index, first in enumerate(world_features):
        for second in world_features[:index]:
            area = shape(first['geometry']).intersection(shape(second['geometry'])).area
            if area > 1e-16:
                overlaps.append({'firstNewUnit': first['properties']['sourceUnitNumber'], 'secondNewUnit': second['properties']['sourceUnitNumber'], 'areaDegreesSquared': area})
    inferred6 = {}
    inferred_source_path = OUT / 'remaining-iparterulet-one-pixel-inferred-source-pixels.geojson'
    inferred_world_path = OUT / 'remaining-iparterulet-one-pixel-inferred-world.geojson'
    if inferred_source_path.exists() and inferred_world_path.exists():
        raw = shape(next(f for f in source_features if f['properties']['sourceUnitNumber'] == 6)['geometry'])
        source = json.loads(inferred_source_path.read_text())['features'][0]
        pixel = shape(source['geometry'])
        world = shape(json.loads(inferred_world_path.read_text())['features'][0]['geometry'])
        difference = pixel.symmetric_difference(raw)
        unchanged_exteriors = all(a.exterior.equals(b.exterior) for a, b in zip(pixel.geoms, raw.geoms))
        geometry_check = json.loads(subprocess.check_output([
            'node', str(OUT / 'independent-strict-validator.mjs'), inferred_world_path.name], cwd=ROOT, text=True))['records'][0]
        source_pixel = blue[1224, 931]
        inferred6 = {'variant': 'separate_explicit_one_pixel_inference',
                     'sourceGeometryFile': inferred_source_path.name, 'worldGeometryFile': inferred_world_path.name,
                     'literalRawPreservedSeparately': True,
                     'strictValidator': geometry_check,
                     'sourceGeometryValid': pixel.is_valid, 'worldGeometryValid': world.is_valid,
                     'estimatedTrue': source['properties'].get('estimated') is True,
                     'changedAreaPixelsSquared': difference.area,
                     'changedPixelBounds': list(difference.bounds),
                     'onlyChangeIsRecordedOnePixel': difference.equals(box(930.5, 1223.5, 931.5, 1224.5)),
                     'filledPixelIsOriginalTealSourceMask': bool(source_pixel),
                     'sourceInterpretationIsLiteral': False,
                     'exteriorRingsUnchanged': unchanged_exteriors,
                     'worldMatchesFrozenTransformationExactly': transform(geographic, pixel).equals_exact(world, 0),
                     'removedAreaPixelsSquared': raw.difference(pixel).area,
                     'remainingSourceHolesCount': sum(len(part.interiors) for part in pixel.geoms),
                     'alternative': 'Retain the exact literal contour in quarantine with original hole_outside_shell reason.'}
    export_review = {}
    export_path = OUT / 'remaining-inferred-import.geojson'
    if export_path.exists():
        export = json.loads(export_path.read_text())['features']
        validation = json.loads(subprocess.check_output([
            'node', str(OUT / 'independent-strict-validator.mjs'), export_path.name], cwd=ROOT, text=True))
        rows = []
        for f in export:
            p = f['properties']; number = p['sourceUnitNumber']
            expected = (json.loads(inferred_world_path.read_text())['features'][0] if number == 6 else worlds[number])
            rows.append({'sourceUnitNumber': number, 'name': p['name'],
                         'geometryUnchangedFromReviewedInterpretation': f['geometry'] == expected['geometry'],
                         'estimatedTrue': p.get('estimated') is True,
                         'boundaryKindIsInferredArea': p.get('boundaryKind') == 'inferred_area',
                         'canonicalNeighborhoodFlagFalse': p.get('canonicalNameIsNeighborhood') is False,
                         'sourceContourObservedFlagFalse': p.get('sourceContourIsObserved') is False,
                         'addressAssignmentDisabled': p.get('usableForAddressAssignment') is False,
                         'sourceHardBoundaryFalse': p.get('sourceIsHardBoundary') is False,
                         'absoluteAccuracyClaimNull': p.get('claimedAbsoluteAccuracyMetres') is None,
                         'independentInteriorControlsZero': p.get('independentInteriorControlCount') == 0})
        export_review = {'path': export_path.name, 'sha256': sha(export_path), 'featureCount': len(export),
                         'sourceUnitNumbers': sorted(f['properties']['sourceUnitNumber'] for f in export),
                         'records': rows, 'strictValidatorRecords': validation['records'],
                         'strictPassCount': sum(r['valid'] for r in validation['records']),
                         'newPrimaryFeatureCount': 0, 'newInferredFeatureCount': len(export)}
        export_overlaps = []
        for index, f in enumerate(export):
            first = shape(f['geometry'])
            for other in [*export[:index], *frozen_features]:
                area = first.intersection(shape(other['geometry'])).area
                if area > 1e-16:
                    export_overlaps.append({'name': f['properties']['name'], 'otherName': other['properties']['name'], 'areaDegreesSquared': area})
        export_review['positiveAreaOverlapsAmongFinalExportOrFrozenPrimary'] = export_overlaps
        quarantine_path = OUT / 'remaining-validator-quarantine.geojson'
        if quarantine_path.exists():
            quarantine = json.loads(quarantine_path.read_text())['features']
            raw = next(f for f in world_features if f['properties']['sourceUnitNumber'] == 6)
            export_review['rawLiteralQuarantineFeatureCount'] = len(quarantine)
            export_review['rawLiteralQuarantineGeometryUnchanged'] = len(quarantine) == 1 and quarantine[0]['geometry'] == raw['geometry']
    extra_inputs = ['remaining-manual-caps-source-pixels.geojson', 'remaining-manual-cap-alternatives-source-pixels.geojson',
                    'remaining-unassigned-source-pixels.geojson', 'remaining-ebergeny-omit-lobe70-source-pixels.geojson',
                    'remaining-iparterulet-one-pixel-inferred-source-pixels.geojson', 'remaining-iparterulet-one-pixel-inferred-world.geojson',
                    'remaining-iparterulet-one-pixel-inference-proof.json', 'current-name-evidence.geojson', 'current-name-evidence.json']
    extra_inputs += ['remaining-inferred-import.geojson', 'remaining-registry-entry.json', 'remaining-conversion-proof.json',
                     'remaining-validator-passing.geojson', 'remaining-validator-quarantine.geojson']
    fingerprints = [{'path': name, 'sha256': sha(OUT / name)} for name in required+extra_inputs if (OUT / name).exists()]
    return {'status': 'independently_checked_producer_candidates',
            'method': 'Original RGB/four-neighbor mask recomputation; every exposed literal cell face independently enumerated and compared. Manual lobes independently polygonized from exposed faces, then compared outside the declared annotation mask. Producer row-run union is never called.',
            'inputFingerprints': fingerprints, 'records': records,
            'explicitOnePixelIparteruletVariant': inferred6,
            'finalInferredExportReview': export_review,
            'strictValidator': strict['validator'],
            'positiveAreaOverlaps': overlaps,
            'allGeometryCoordinatesRecomputedFromFrozenAffine': all(r['worldMatchesFrozenTransformationExactly'] for r in records),
            'strictValidatorPassCount': sum(r['strictValidator']['valid'] for r in records),
            'strictValidatorFailureCount': sum(not r['strictValidator']['valid'] for r in records)}


def assert_review(result):
    if not (result['originalEmbeddedImageByteIdenticalToExcerpt'] and result['originalFullPdfHashMatchesArchivedOfficialSource']
            and result['originalFullPdfPage12HasExpectedImageXref105'] and result['originalFullPdfImageByteIdentical']):
        raise ValueError('Archived source raster is not the original excerpt image')
    if not all(r['legendNumberAndNameMatch'] and not r['selectedInteriorTouchesRasterFrame'] for r in result['sourceRecords']):
        raise ValueError('Source semantics or raster-frame check failed')
    registration = result['georeferencing']
    if registration['maximumMatrixCoefficientDifference'] != 0 or not registration['allSavedAnchorsMatchRecomputedSourceComponents']:
        raise ValueError('Frozen registration was not independently reproduced exactly')
    candidates = result['candidateReview']
    if candidates['status'] != 'independently_checked_producer_candidates':
        return
    if candidates['positiveAreaOverlaps']:
        raise ValueError('Reviewed source units have a positive-area overlap')
    for record in candidates['records']:
        if not (record['sourceGeometryValid'] and record['worldGeometryValid'] and record['sourceBoundsWithinOriginalRaster']
                and record['worldMatchesFrozenTransformationExactly']):
            raise ValueError('Candidate coordinate/source-bound check failed: ' + record['name'])
        if record['sourceUnitNumber'] == 6:
            if not record['literalGeometryExact'] or record['strictValidator'].get('reason') != 'hole_outside_shell':
                raise ValueError('Literal6 exact-source/quarantine check failed')
        elif not (record['strictValidator']['valid'] and record['observedOutsideWindowExact']
                  and record['inferredPatchWithinAnnotationWindow'] and record['inferredBoundaryConfinedToWindow']
                  and record['reconstructionFlagAppropriate'] and record['allCapAlternativesWithinAnnotationWindow']
                  and record['allAlternativesFlaggedUnobservedAndLowConfidence']):
            raise ValueError('Manual interpretation/alternatives check failed: ' + record['name'])
    variant = candidates['explicitOnePixelIparteruletVariant']
    if variant and not (variant['strictValidator']['valid'] and variant['onlyChangeIsRecordedOnePixel']
                        and variant['estimatedTrue'] and variant['exteriorRingsUnchanged']
                        and variant['worldMatchesFrozenTransformationExactly'] and variant['remainingSourceHolesCount'] == 1):
        raise ValueError('Explicit one-pixel6 inference check failed')
    export = candidates['finalInferredExportReview']
    if export:
        flags = ['geometryUnchangedFromReviewedInterpretation', 'estimatedTrue', 'boundaryKindIsInferredArea',
                 'canonicalNeighborhoodFlagFalse', 'sourceContourObservedFlagFalse', 'addressAssignmentDisabled',
                 'sourceHardBoundaryFalse', 'absoluteAccuracyClaimNull', 'independentInteriorControlsZero']
        if export['sourceUnitNumbers'] != [6, 10, 11, 12, 13, 14] or export['strictPassCount'] != 6:
            raise ValueError('Final six-inferred export membership/strict check failed')
        if not all(all(r[flag] for flag in flags) for r in export['records']):
            raise ValueError('Final inferred export changed reviewed geometry or metadata restrictions')
        if export['positiveAreaOverlapsAmongFinalExportOrFrozenPrimary'] or not export.get('rawLiteralQuarantineGeometryUnchanged'):
            raise ValueError('Final inferred export overlap or raw-quarantine preservation check failed')


def baseline():
    image_path = OUT / 'zalaegerszeg-p12-image0.jpeg'
    rgb = np.asarray(Image.open(image_path).convert('RGB'), dtype=np.int32)
    blue = (rgb[:, :, 0] < 135) & (rgb[:, :, 1]-rgb[:, :, 0] > 30) & (rgb[:, :, 2]-rgb[:, :, 0] > 30) & (rgb[:, :, 1] > 65)
    free, count = ndimage.label(~blue)
    boxes = ndimage.find_objects(free)
    sizes = np.bincount(free.ravel())
    document = fitz.open(OUT / 'zalaegerszeg-source-pages12-13.pdf')
    extracted = document.extract_image(document[0].get_images(full=True)[0][0])['image']
    original_path = ROOT / '.local/neighborhoods/nationwide-docs/originals/zalaegerszeg-its.pdf'
    original = fitz.open(original_path)
    original_extracted = original.extract_image(105)['image']
    original_image_on_page12 = any(record[0] == 105 for record in original[11].get_images(full=True))
    legend = document[1].get_text()
    matrix = np.asarray(json.loads((OUT / 'zalaegerszeg-registration.json').read_text())['matrixPixelToEov'])
    parent = shape(json.loads((FROZEN / 'zalaegerszeg-calibration-municipality.geojson').read_text())['geometry'])
    records = []
    literal_masks = {}
    for number, name in NAMES.items():
        parts = []
        for cid, lid in zip(REGIONS[number], LABELS[number]) if number == 6 else [(None, LABELS[number][0])]:
            region = free == cid if cid else np.isin(free, REGIONS[number])
            excluded_enclosures = ndimage.binary_fill_holes(region) & ~region
            hole_labels, _ = ndimage.label(excluded_enclosures)
            label_pixels = np.argwhere(free == lid)
            y, x = label_pixels[len(label_pixels)//2]
            enclosed_id = int(hole_labels[y, x])
            graphic = hole_labels == enclosed_id if enclosed_id else np.zeros(region.shape, dtype=bool)
            if cid:
                literal_masks[cid] = region | graphic
            parts.append({'freeComponentId': cid, 'numericFreeComponentId': lid,
                          'numericGraphicWhollyEnclosedBySelectedInterior': bool(enclosed_id),
                          'restorableWhollyEnclosedGraphicPixelCount': int(graphic.sum())})
        components = []
        for cid in [*REGIONS[number], *LABELS[number]]:
            b = boxes[cid-1]
            components.append({'freeComponentId': cid, 'pixelCount': int(sizes[cid]),
                               'bboxPixelsInclusive': [b[1].start, b[0].start, b[1].stop-1, b[0].stop-1]})
        selected = np.isin(free, REGIONS[number])
        records.append({'sourceUnitNumber': number, 'name': name,
                        'legendNumberAndNameMatch': bool(re.search(r'\b'+str(number)+r'\.\s*'+re.escape(name), legend)),
                        'sourceComponents': components,
                        'selectedInteriorTouchesRasterFrame': bool(selected[0].any() or selected[-1].any() or selected[:, 0].any() or selected[:, -1].any()),
                        'numericGraphics': parts,
                        'unassignedOrUncertainComponents': [92] if number == 12 else [70] if number == 13 else [],
                        'completionCategory': 'literal_inside_source_stroke' if number == 6 else 'requires_explicit_hidden_boundary_interpretation',
                        'recommendedEstimated': number != 6})
    output = {'schemaVersion': 1, 'reviewer': 'independent sibling source-cell reviewer',
              'reviewDate': '2026-11-14', 'networkUsed': False,
              'originalEmbeddedImageByteIdenticalToExcerpt': hashlib.sha256(extracted).hexdigest() == sha(image_path),
              'originalFullPdfSha256': sha(original_path),
              'originalFullPdfHashMatchesArchivedOfficialSource': sha(original_path) == '4534775c49466eba0460e583aa45a12127f0a46cd8c0e768ed689b830e4eb035',
              'originalFullPdfPage12HasExpectedImageXref105': original_image_on_page12,
              'originalFullPdfImageByteIdentical': hashlib.sha256(original_extracted).hexdigest() == sha(image_path),
              'sourceImagePixels': [int(rgb.shape[1]), int(rgb.shape[0])],
              'sourceSemantics': '2014 municipal ITS statistical city-quarter division used to compare 2009 and 2011 data; the figure and numbered table establish the historical unit names.',
              'numericDisksAreAnnotationRatherThanGeographicHoles': True,
              'sourceMaskRule': 'R<135 and G-R>30 and B-R>30 and G>65; original JPEG RGB',
              'recomputedFreeComponentCountFourNeighbor': count,
              'sourceRecords': records,
              'georeferencing': verify_registration(blue, matrix, parent),
              'admissionPrinciple': 'Unknown absolute placement accuracy alone is the same limitation as the frozen five literal source candidates. Unit6 may retain estimated=false only if its exact two source-cell footprints pass strict import checks. Any cap completing units10–14 is an actual inferred boundary choice and must retain estimated=true, low confidence and alternatives.',
              'usableForAddressAssignment': False, 'sourceIsHardBoundary': False,
              'sourceGeometriesEditedByReviewer': False}
    baseline_inputs = [image_path, original_path, OUT / 'zalaegerszeg-source-pages12-13.pdf', OUT / 'zalaegerszeg-registration.json',
                       FROZEN / 'zalaegerszeg-calibration-municipality.geojson', FROZEN / 'zalaegerszeg-import.geojson']
    output['baselineInputFingerprints'] = [{'path': str(path.relative_to(ROOT)), 'sha256': sha(path)} for path in baseline_inputs]
    output['frozenPrimaryImportFeatureCount'] = len(json.loads((FROZEN / 'zalaegerszeg-import.geojson').read_text())['features'])
    output['frozenPrimaryImportHashMatchesPreexistingInput'] = sha(FROZEN / 'zalaegerszeg-import.geojson') == '70b502949fcc8333ead5ffc0d404cbdd6198ec0a1f09241f88bd3509fc056b6a'
    return output, free, blue, literal_masks, matrix, parent


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result, free, blue, literal_masks, matrix, parent = baseline()
    result['candidateReview'] = candidate_audit(free, blue, literal_masks, matrix, parent)
    assert_review(result)
    result['admissionRecommendation'] = {
        'newPrimaryFeatures': 0, 'newInferredFeatures': 6,
        'literalUnit6': 'Keep exact raw two-part source contour quarantined with original hole_outside_shell error.',
        'inferredUnit6': 'Admit only the explicitly estimated one-pixel-fill interpretation, whose exterior rings are unchanged and whose one-pixel delta is recorded.',
        'units10Through14': 'Admit only as estimated, low-confidence source-based interpretations with local hidden-edge caps, bounded alternatives and semantic caveats retained.',
        'placementAccuracy': 'Zero independent interior controls; absolute accuracy remains unknown. Measured cap lengths and perimeter residuals are not positional-accuracy claims.',
        'currentNames': 'Five current exact named-place matches retained as evidence only. Iparterület current exact name remains unconfirmed; the official historical source table establishes its source unit identity.'}
    content = encode(result)
    destination = OUT / 'independent-source-registration-review.json'
    if args.check:
        if destination.read_text() != content:
            raise ValueError('Independent source/registration audit changed')
    else:
        destination.write_text(content)
    print(json.dumps({'sourceRecords': len(result['sourceRecords']),
                      'matrixMaximumDifference': result['georeferencing']['maximumMatrixCoefficientDifference'],
                      'check': args.check}))
