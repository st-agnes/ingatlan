#!/usr/bin/env python3
"""One full-map road-based estimated placement; no place-point fitting."""
from pathlib import Path
import hashlib
import json

import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer
from shapely.geometry import Point, shape, mapping
from shapely.ops import transform

HERE = Path(__file__).resolve().parent
PBF_SHA = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
DATASET = 'kiskunfelegyhaza-its2016-five'
NAME_NODES = {2: 1300486631, 3: 1300486634, 4: 1300486629,
              13: 10707051448, 14: 1300505896}
CONTROLS = [
    ('C1', [400, 653], 1843236649, ['Dr. Holló Lajos utca', 'Bercsényi utca']),
    ('C2', [343, 698], 1843235605, ['Mikszáth Kálmán utca', 'Árok utca']),
    ('C3', [430, 589], 1843237905, ['Kőrösi út', 'railway']),
    ('C4-north', [188.5, 285.5], 2208340620, ['route 5', 'Páka utca / Pintér dűlő junction']),
    ('C5-southeast', [551, 868], 2212985376,
     ['Mészöly Gyula utca', 'Péteri út', 'Móczár bekötőút', 'northwest road']),
]
HOLDOUTS = [
    ('H1', [360, 681], 1843236018, ['Bercsényi utca', 'Mikszáth Kálmán utca']),
    ('H2', [435, 633], 5914756408, ['Kőrösi utca', 'Tanyasori út']),
    ('H3a', [449, 648], 2139468150, ['Alpári út', 'Tanyasori út']),
    ('H3b-current-junction-alternative', [449, 648], 5914074516, ['Alpári út', 'Tanyasori út']),
]
METHOD = ('Literal source pixel-cell contour placed with one full-map six-parameter EOV affine '
          'model from five actual road/rail junction correspondences, then inverse projected to '
          'EPSG:4326. Source color barriers and actual pixel cells are retained; Petőfi alone has '
          'the separately recorded two-pixel cap under its numeric label. No name-point fitting, '
          'per-feature shift, clipping, snapping, repair, smoothing, buffers or frame closures.')
UNCERTAINTY = ('Native 945×1364 JPEG; colored boundary bands and manual road picks are several '
               'pixels wide. Original map projection, cartographic generalization, boundary '
               'survey date and current whole-quarter extent are unestablished. Five-control '
               'fit residuals and manually picked road holdouts measure correspondence consistency '
               'only, not absolute ground accuracy. A separate full-map similarity model illustrates '
               'placement variation without defining a confidence envelope. Municipal 2014 '
               'submission, census 2011 statistics and ITS 2016 review periods are distinct. No current-name '
               'point is used to fit or correct any coordinate.')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def canonical_sha(geometry):
    return hashlib.sha256(json.dumps(geometry, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def main():
    source = json.loads((HERE / 'source-pixel-contours.geojson').read_text())
    roads = json.loads((HERE / 'source-road-rail-reference.geojson').read_text())
    names = json.loads((HERE / 'source-name-points.geojson').read_text())
    assert roads['sourcePbfSha256'] == names['sourcePbfSha256'] == PBF_SHA
    nodes = {}
    incident = {}
    for way in roads['features']:
        for ref, coordinate in zip(way['properties']['nodeRefs'], way['geometry']['coordinates']):
            if ref in nodes:
                assert nodes[ref] == coordinate
            nodes[ref] = coordinate
            incident.setdefault(ref, []).append(way['properties']['osmWayId'])
    to_eov = Transformer.from_crs(4326, 23700, always_xy=True)
    to_wgs = Transformer.from_crs(23700, 4326, always_xy=True)
    X = np.array([c[1] for c in CONTROLS], dtype=float)
    Y = np.array([to_eov.transform(*nodes[c[2]]) for c in CONTROLS])
    design = np.column_stack([X, np.ones(len(X))])
    coefficients = np.linalg.lstsq(design, Y, rcond=None)[0]
    matrix, offset = coefficients[:2].T, coefficients[2]
    assert np.linalg.det(matrix) < 0  # Native image y points down.
    affine_errors = np.linalg.norm(design @ coefficients - Y, axis=1)
    sd, sy = [], []
    for (x, y), (e, n) in zip(X, Y):
        sd.extend([[x, y, 1, 0], [-y, x, 0, 1]])
        sy.extend([e, n])
    a, b, tx, ty = np.linalg.lstsq(sd, sy, rcond=None)[0]
    smatrix, soffset = np.array([[a, b], [b, -a]]), np.array([tx, ty])
    similarity_errors = np.linalg.norm(X @ smatrix.T + soffset - Y, axis=1)

    def place(geometry, model_matrix=matrix, model_offset=offset):
        def op(x, y, z=None):
            pixels = np.column_stack([np.asarray(x), np.asarray(y)])
            eov = pixels @ model_matrix.T + model_offset
            return to_wgs.transform(eov[:, 0], eov[:, 1])
        return transform(op, geometry)

    controls = []
    for index, (cid, pixel, node, road_names) in enumerate(CONTROLS):
        controls.append({'id': cid, 'sourcePixel': pixel, 'targetOsmNodeId': node,
                         'targetWgs84': nodes[node], 'actualIncidentWayIds': incident[node],
                         'physicalCorrespondence': road_names, 'role': 'fit',
                         'sourcePickingIsManual': True, 'sourcePickUncertaintyPixels': None,
                         'affineResidualMetresDiagnosticOnly': float(affine_errors[index]),
                         'similarityResidualMetresDiagnosticOnly': float(similarity_errors[index])})
    heldouts = []
    for cid, pixel, node, road_names in HOLDOUTS:
        target = np.array(to_eov.transform(*nodes[node]))
        heldouts.append({'id': cid, 'sourcePixel': pixel, 'targetOsmNodeId': node,
                         'targetWgs84': nodes[node], 'actualIncidentWayIds': incident[node],
                         'physicalCorrespondence': road_names, 'role': 'not_used_for_fit',
                         'sourcePickingIsManual': True,
                         'affineResidualMetresDiagnosticOnly': float(np.linalg.norm(np.array(pixel) @ matrix.T + offset - target)),
                         'similarityResidualMetresDiagnosticOnly': float(np.linalg.norm(np.array(pixel) @ smatrix.T + soffset - target))})
    write('road-registration.json', {
        'schemaVersion': 1, 'sourceCrs': 'Native image pixels, x right/y down',
        'fitWorldCrs': 'EPSG:23700', 'outputCrs': 'EPSG:4326',
        'mainModel': 'Full-map affine; five actual road/rail junctions; no per-feature model',
        'pixelToEovMatrix': matrix.tolist(), 'pixelToEovOffset': offset.tolist(),
        'singularScalesMetresPerPixel': np.linalg.svd(matrix)[1].tolist(),
        'fitRmsMetresDiagnosticOnly': float(np.sqrt(np.mean(affine_errors ** 2))),
        'claimedAbsoluteAccuracyMetres': None, 'controls': controls,
        'heldOutManualRoadChecks': heldouts, 'sourceNamePointsUsedForFit': False,
        'alternative': {'model': 'Full-map four-parameter similarity using the same five controls',
                        'pixelToEovMatrix': smatrix.tolist(), 'pixelToEovOffset': soffset.tolist(),
                        'fitRmsMetresDiagnosticOnly': float(np.sqrt(np.mean(similarity_errors ** 2)))},
        'uncertainty': UNCERTAINTY, 'georeferencingIsApproximate': True,
        'sourceRoadReferencePath': 'source-road-rail-reference.geojson',
        'sourceRoadReferenceSha256': sha(HERE / 'source-road-rail-reference.geojson')})

    names_by_node = {f['properties']['osmNodeId']: f for f in names['features']}
    first, scout, alternatives, diagnostics = [], [], [], []
    for f in source['features']:
        unit = f['properties']['sourceUnitNumber']
        g = shape(f['geometry'])
        world, other = place(g), place(g, smatrix, soffset)
        assert world.is_valid and other.is_valid
        evidence = names_by_node[NAME_NODES[unit]]
        point = shape(evidence['geometry'])
        eov_world = transform(to_eov.transform, world)
        eov_point = transform(to_eov.transform, point)
        eov_other = transform(to_eov.transform, other)
        item = {'sourceUnitNumber': unit, 'literalSourceName': f['properties']['name'],
                'actualOsmName': evidence['properties']['name'], 'actualOsmNodeId': NAME_NODES[unit],
                'matchRule': 'literal_exact' if evidence['properties']['name'] == f['properties']['name'] else 'explicit_space_hyphen_spelling_variant_only',
                'pointInside': world.contains(point),
                'pointOutsideDistanceMetresDiagnosticOnly': float(eov_world.distance(eov_point)),
                'usedForFitOrCorrection': False,
                'affineSimilarityHausdorffMetresDiagnosticOnly': float(eov_world.hausdorff_distance(eov_other)),
                'affineSimilaritySymmetricDifferenceSquareMetres': float(eov_world.symmetric_difference(eov_other).area),
                'wholeCurrentQuarterExtentProven': False}
        diagnostics.append(item)
        props = {'name': f['properties']['name'], 'municipality': 'Kiskunfélegyháza',
                 'municipalityId': 'city:Kiskunfélegyháza', 'sourceUnitNumber': unit,
                 'sourceSchemaId': f'kiskunfelegyhaza-its2016-table4-unit{unit}',
                 'sourcePeriod': 'ITS 2016 review, municipal 2014 boundary submission; census 2011 statistics. Original survey/backdrop date unknown.',
                 'sourceContourIsObserved': unit != 3, 'observedSourceContour': unit != 3,
                 'sourceContourObserved': unit != 3, 'completeSourceContourObserved': unit != 3,
                 'sourceContourHasObservedSections': True, 'estimatedContour': unit == 3,
                 'sourceContourMethod': ('Observed RGB outline component and exact free pixel interior; no inferred source edges.'
                                         if unit != 3 else 'Observed green boundary sections with one explicit two-pixel inferred cap beneath numeric label 3; the complete ring is not fully observed.'),
                 'inferredSourceGapCapCount': 1 if unit == 3 else 0,
                 'inferredSourceGapBarrierCells': 2 if unit == 3 else 0,
                 'estimatedPlacement': True, 'estimated': True,
                 'boundaryKind': 'inferred_area', 'candidateBoundaryKind': 'neighbourhood',
                 'canonicalNameIsNeighborhood': False, 'sourceIsOfficial': False,
                 'sourceDocumentIsOfficialMunicipalPublication': True,
                 'sourceIsHardBoundary': False, 'usableForAddressAssignment': False,
                 'wholeOrdinaryQuarterExtentVerified': False,
                 'georeferencingIsApproximate': True, 'claimedAbsoluteAccuracyMetres': None,
                 'confidence': 'low', 'reviewStatus': 'estimated_source_candidate_pending_independent_review',
                 'method': METHOD, 'placementUncertainty': UNCERTAINTY,
                 'sourcePixelGeometrySha256': canonical_sha(f['geometry']),
                 'sourcePixelArea': f['properties']['sourcePixelArea'],
                 'sourceNameEvidence': dict(item, sourceObjectVersion=evidence['properties']['objectVersion'],
                                            sourceObjectTimestamp=evidence['properties']['objectTimestamp'],
                                            sourcePbfSha256=PBF_SHA),
                 'evidenceUrls': [json.loads((HERE / 'source-facts.json').read_text())['sourceUrl']],
                 'sourceDocuments': [{'url': json.loads((HERE / 'source-facts.json').read_text())['sourceUrl'],
                                      'sha256': json.loads((HERE / 'source-facts.json').read_text())['sourcePdfSha256'],
                                      'pdfPagesOneBased': [24, 25], 'mapNumber': 2, 'imageXref': 365}],
                 'license': 'Municipal map reuse rights unestablished; ODbL-1.0 for OSM controls and identity evidence.',
                 'rightsStatus': 'Public official publication is not an independently established unrestricted redistribution licence.'}
        feature = {'type': 'Feature', 'id': f'manual:kiskunfelegyhaza-its2016:unit{unit}',
                   'properties': props, 'geometry': mapping(world)}
        (first if unit in [2, 3, 4] else scout).append(feature)
        alternatives.append({'type': 'Feature', 'id': f'alternative:kiskunfelegyhaza-its2016:unit{unit}',
                             'properties': {'name': props['name'], 'sourceUnitNumber': unit,
                                            'alternativeOnly': True, 'countsAsAdditionalQuarter': False},
                             'geometry': mapping(other)})
    write('kiskunfelegyhaza-inferred-import.geojson', {'type': 'FeatureCollection', 'features': first + scout})
    write('outlying-world-scouts.geojson', {'type': 'FeatureCollection',
                                          'registeredAsSeparateDataset': False,
                                          'sameGeometryIncludedInMainFive': True,
                                          'countsAsAdditionalQuarters': False,
                                          'features': scout})
    write('placement-similarity-alternative.geojson', {'type': 'FeatureCollection',
                                                      'countsAsAdditionalQuarters': False,
                                                      'features': alternatives})
    alternate_contour = json.loads((HERE / 'petofi-cap-alternative-source-pixels.geojson').read_text())['features'][0]
    write('petofi-contour-alternative-world.geojson', {
        'type': 'FeatureCollection', 'countsAsAdditionalQuarter': False,
        'features': [{'type': 'Feature', 'properties': alternate_contour['properties'],
                      'geometry': mapping(place(shape(alternate_contour['geometry'])))}]})
    write('name-and-model-diagnostics.json', {'schemaVersion': 1, 'sourcePbfSha256': PBF_SHA,
                                             'sourceNamePointsUsedForFit': False,
                                             'automaticAliasesAdopted': False,
                                             'records': diagnostics})
    write('inferred-registry-entry.json', {
        'id': DATASET, 'path': str((HERE / 'kiskunfelegyhaza-inferred-import.geojson').relative_to(HERE.parents[3])),
        'sha256': sha(HERE / 'kiskunfelegyhaza-inferred-import.geojson'),
        'municipality': 'Kiskunfélegyháza', 'method': METHOD,
        'evidenceUrls': [json.loads((HERE / 'source-facts.json').read_text())['sourceUrl']],
        'propertyOverrides': {'estimated': True, 'boundaryKind': 'inferred_area',
                              'candidateBoundaryKind': 'neighbourhood', 'canonicalNameIsNeighborhood': False,
                              'sourceIsOfficial': False, 'sourceIsHardBoundary': False,
                              'usableForAddressAssignment': False, 'claimedAbsoluteAccuracyMetres': None,
                              'estimatedPlacement': True, 'georeferencingIsApproximate': True},
        'reviewPath': str((HERE / 'independent-parent-review.json').relative_to(HERE.parents[3])),
        'uncertainties': [UNCERTAINTY, 'Petőfi contains the explicit bounded two-pixel source cap; its alternative is retained separately.'],
        'license': 'Municipal map reuse rights unestablished; ODbL-1.0 controls and identity evidence.',
        'newPrimaryFeatures': 0, 'newEstimatedFineCandidates': len(first + scout), 'globalRegistryApplied': False})
    # Exact current roads over the source image are a placement diagnostic only.
    im = Image.open(HERE / 'source-map-p25-xref365.jpeg').convert('RGB')
    dr = ImageDraw.Draw(im)
    inv = np.linalg.inv(matrix)
    for f in roads['features']:
        tags = f['properties']['tags']
        if not (tags.get('name') in ['Dr. Holló Lajos utca', 'Bercsényi utca', 'Mikszáth Kálmán utca', 'Árok utca', 'Kőrösi út', 'Tanyasori út', 'Alpári út'] or tags.get('railway') == 'rail'):
            continue
        xy = np.array([to_eov.transform(*c) for c in f['geometry']['coordinates']])
        pixels = (xy - offset) @ inv.T
        dr.line([tuple(p) for p in pixels], fill=(0, 80, 255), width=1)
    for c in controls:
        x, y = c['sourcePixel']; dr.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 0, 0))
    im.save(HERE / 'registration-road-overlay.png')
    print(json.dumps({'firstCandidates': len(first), 'outlyingScouts': len(scout),
                      'affineRmsDiagnosticMetres': float(np.sqrt(np.mean(affine_errors ** 2))),
                      'similarityRmsDiagnosticMetres': float(np.sqrt(np.mean(similarity_errors ** 2))) }))

if __name__ == '__main__':
    main()
