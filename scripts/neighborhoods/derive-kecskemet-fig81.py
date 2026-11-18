#!/usr/bin/env python3
"""Offline source-pixel digitization of Kecskemét's 2021 Figure 81.

The two label-overprinted candidates are deliberately separate from the two
literal-black source outlines. No source-frame corner or missing extent is
reconstructed. --check compares deterministic artifacts without writing them.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/neighborhoods/sources/municipal-kecskemet-fig81'
IMAGE_SHA = '4d9d33cf34268d28653d0955b8619e515653b29cea59914397246eaa7589f1ec'
PDF_SHA = '83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939'
ROADS_SHA = '2b3222aa9c78e24c492a1b4e34c5f3ec551d5671d6f1a92a38bcd4e26f3fc0ff'
CONTROLS_SHA = '1781daafee14232f8afb94f29103262672dad366f5287001cdac6227d1690fb4'
EXTRACTION_SHA = 'ac1b1628baa580fbeb32118d7be5088953ea30e24a37f50a83b23aa3ecf7bcea'
FULL_ROADS_SHA = 'ee16b15f2dcc1379f5638abd8990151c8865065307331f0ee54b8c53bf2bd7f9'
URL = 'https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf'
PRIMARY_NAMES = {'Belső-Máriahegy', 'Széchenyiváros III.'}
EXPECTED_NONBLACK = {'Belső-Máriahegy': 0, 'Széchenyiváros III.': 0,
                     'Széchenyiváros II.': 4, 'Széchenyiváros I.': 16}
SLUGS = {'Belső-Máriahegy': 'belso-mariahegy', 'Széchenyiváros III.': 'szechenyivaros-3',
         'Széchenyiváros II.': 'szechenyivaros-2', 'Széchenyiváros I.': 'szechenyivaros-1'}
METHOD = (
    'Manual interpretation of separately labelled fine-quarter outlines on the exact original '
    'embedded JPEG of the 2021 consultation-draft municipal figure 81. Manually identified '
    'source-stroke seeds guide continuous 8-neighbor source-pixel paths. For the literal-source '
    'layer every dense vertex has maxRGB <= 45. Only exactly collinear vertices are removed. '
    'A metric affine fit in EOV/EPSG:23700 using five literal contemporary OSM-node coordinates '
    'and manually placed approximate old-image road junctions georeferences the source pixels; '
    'the result is converted to WGS84. No current-road replacement, source-frame closure, '
    'arbitrary chord, buffer, geometric snapping or geometry repair is used.'
)
INFERRED_METHOD = (
    METHOD + ' This candidate has narrowly bounded dark-blue source-label crossings: the '
    'underlying black outline is obscured, and its continuation through actual dark-blue '
    'source pixels is manually interpreted. It is an explicit estimate, not a literal-black '
    'boundary reconstruction; the exact affected pixels and lengths are archived.'
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def compress_collinear(ring, protected=frozenset()):
    points = list(ring[:-1])
    changed = True
    while changed:
        changed, result = False, []
        for index, middle in enumerate(points):
            before, after = points[index - 1], points[(index + 1) % len(points)]
            cross = ((middle[0] - before[0]) * (after[1] - middle[1])
                     - (middle[1] - before[1]) * (after[0] - middle[0]))
            dot = ((middle[0] - before[0]) * (after[0] - middle[0])
                   + (middle[1] - before[1]) * (after[1] - middle[1]))
            if tuple(middle) not in protected and cross == 0 and dot > 0:
                changed = True
            else:
                result.append(middle)
        points = result
    return points + [points[0]]


def build(check=False):
    import gzip
    import math
    import numpy as np
    import pyproj
    from PIL import Image, ImageDraw
    from pyproj import Geod, Transformer
    from shapely.geometry import Polygon, mapping, shape

    pyproj.network.set_network_enabled(False)
    generated = {}

    def save(filename, value):
        payload = encode(value)
        generated[filename] = hashlib.sha256(payload).hexdigest()
        path = OUT / filename
        if check:
            if not path.exists() or path.read_bytes() != payload:
                raise ValueError('Stale or missing artifact: ' + str(path))
        else:
            path.write_bytes(payload)

    for filename, expected in [('page175-xref216.jpeg', IMAGE_SHA),
                               ('control-roads.geojson', ROADS_SHA),
                               ('control-specification.json', CONTROLS_SHA),
                               ('source-extraction.json', EXTRACTION_SHA)]:
        if sha(OUT / filename) != expected:
            raise ValueError('Changed frozen input: ' + filename)
    extraction = json.loads((OUT / 'source-extraction.json').read_text())
    if (extraction['pdfSha256'] != PDF_SHA
            or extraction['originalExtractedImageSha256'] != IMAGE_SHA
            or extraction['bytesExactlyEqualPublisherEmbeddedImage'] is not True):
        raise ValueError('Publisher source-image identity not established')

    full_roads_path = ROOT / extraction['geographicControlFullWayArchivePath']
    if sha(full_roads_path) != FULL_ROADS_SHA:
        raise ValueError('Changed literal full control-way archive')
    full_roads = {feature['id']: feature for feature in json.loads(full_roads_path.read_text())['features']}
    roads = json.loads((OUT / 'control-roads.geojson').read_text())['features']
    actual_nodes, node_ways = {}, {}
    for road in roads:
        if road != full_roads.get(road['id']):
            raise ValueError('A control way differs from its literal original node sequence')
        refs = road['properties']['source']['nodeRefs']
        coords = road['geometry']['coordinates']
        if len(refs) != len(coords):
            raise ValueError('Unpaired control-way node references')
        for node, coord in zip(refs, coords):
            if node in actual_nodes and actual_nodes[node] != coord:
                raise ValueError('Inconsistent literal control-node coordinates')
            actual_nodes[node] = coord
            node_ways.setdefault(node, set()).add(road['id'])
    specification = json.loads((OUT / 'control-specification.json').read_text())
    controls = specification['controls']
    for control in controls + [specification['heldOutVisualControl']]:
        node = control['osmNodeId']
        if (actual_nodes.get(node) != control['coordinates']
                or not set(control['sourceWayIds']).issubset(node_ways.get(node, set()))):
            raise ValueError('A control is not the stated literal OSM road-junction node')
    if len(controls) != 5:
        raise ValueError('Exactly five manually reviewed geographical controls required')

    to_metric = Transformer.from_crs(4326, 23700, always_xy=True)
    to_wgs84 = Transformer.from_crs(23700, 4326, always_xy=True)
    pixels = np.array([control['sourceImagePixel'] for control in controls])
    metric_controls = np.array([to_metric.transform(*control['coordinates']) for control in controls])
    affine = np.linalg.lstsq(np.c_[pixels, np.ones(len(pixels))], metric_controls, rcond=None)[0]
    fitted = np.c_[pixels, np.ones(len(pixels))] @ affine
    residuals = np.linalg.norm(fitted - metric_controls, axis=1)
    affine_homogeneous = np.vstack([affine.T, [0, 0, 1]])
    inverse = np.linalg.inv(affine_homogeneous)
    fitted_pixels = (np.c_[metric_controls, np.ones(len(controls))] @ inverse.T)[:, :2]
    residual_pixels = np.linalg.norm(fitted_pixels - pixels, axis=1)
    if affine.shape != (3, 2) or not np.isfinite(affine).all() or max(residuals) > 20:
        raise ValueError('Invalid or inconsistent source-image affine control fit')

    def world(pixel_sequence):
        metric = np.c_[np.array(pixel_sequence), np.ones(len(pixel_sequence))] @ affine
        x, y = to_wgs84.transform(metric[:, 0], metric[:, 1])
        return np.c_[x, y]

    held_out = specification['heldOutVisualControl']
    hx, hy = to_metric.transform(*held_out['coordinates'])
    held_out_pixel = (np.array([hx, hy, 1]) @ inverse.T)[:2]
    held_out_window = held_out['sourceImagePixelWindow']
    held_out_within = (held_out_window['x'][0] <= held_out_pixel[0] <= held_out_window['x'][1]
                       and held_out_window['y'][0] <= held_out_pixel[1] <= held_out_window['y'][1])
    if not held_out_within:
        raise ValueError('Held-out junction falls outside independently inspected approximate image window')

    helper = OUT / 'trace-figure81-pixels.py'
    spec = importlib.util.spec_from_file_location('otthonra_figure81_source_pixels', helper)
    trace = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trace)
    image = Image.open(OUT / 'page175-xref216.jpeg').convert('RGB')
    rgb = np.asarray(image)
    max_rgb = rgb.max(axis=2)
    if image.size != (1259, 893) or set(trace.RINGS) != set(EXPECTED_NONBLACK):
        raise ValueError('Source dimensions or intended source-unit set changed')
    # Preserve every shared-section endpoint. Inverse projection is nonlinear:
    # dropping a three-way junction from just one neighbour could introduce a
    # tiny geographic sliver even though source-pixel areas remain identical.
    protected = {tuple(path[end]) for path in trace.paths.values() for end in [0, -1]}
    parent_path = ROOT / 'data/neighborhoods/sources/country-osm/municipalities.geojson.gz'
    parent_features = json.loads(gzip.decompress(parent_path.read_bytes()))['features']
    parent = shape(next(feature for feature in parent_features
                        if feature['properties']['name'] == 'Kecskemét'
                        and feature['properties'].get('usedForAssociation'))['geometry'])
    geod = Geod(ellps='WGS84')
    primary, inferred, records, pixel_geometries, world_geometries = [], [], [], {}, {}
    compressed_rings, overprint_details = {}, {}
    for name, ring in trace.RINGS.items():
        if (ring[0] != ring[-1]
                or any(max(abs(a[0] - b[0]), abs(a[1] - b[1])) != 1
                       for a, b in zip(ring, ring[1:]))):
            raise ValueError('Open or non-adjacent source-pixel trace: ' + name)
        if any(not trace.allowed[y, x] for x, y in ring):
            raise ValueError('Trace leaves documented actual-source-pixel mask: ' + name)
        nonblack = [index for index, (x, y) in enumerate(ring[:-1]) if max_rgb[y, x] > 45]
        if len(nonblack) != EXPECTED_NONBLACK[name]:
            raise ValueError('Changed label-overprint interpretation: ' + name)
        is_primary = name in PRIMARY_NAMES
        if is_primary and nonblack:
            raise ValueError('Inferred pixels cannot enter the literal-source layer')
        simple = compress_collinear(ring, protected)
        original, compressed = Polygon(ring), Polygon(simple)
        if (not original.is_valid or not compressed.is_valid or len(compressed.interiors)
                or original.symmetric_difference(compressed).area != 0):
            raise ValueError('Invalid or altered collinear-compressed source circuit: ' + name)
        geographic = Polygon(world(simple))
        if not geographic.is_valid or not parent.covers(geographic):
            raise ValueError('Invalid or outside-parent geographic circuit: ' + name)
        pixel_geometries[name], world_geometries[name] = compressed, geographic
        compressed_rings[name] = simple
        area, perimeter = geod.geometry_area_perimeter(geographic)

        # Exact non-black source vertices and every incident edge remain auditable.
        # We describe the interpreted continuation; these are not hidden black pixels.
        incident_edges = sorted({edge for index in nonblack
                                 for edge in [(index - 1) % (len(ring) - 1), index]})
        dense_world = world(ring)
        interpreted_length = sum(geod.inv(*dense_world[index], *dense_world[index + 1])[2]
                                 for index in incident_edges)
        interpreted_pixel_length = sum(math.dist(ring[index], ring[index + 1])
                                       for index in incident_edges)
        used_windows = []
        nonblack_records = []
        for index in nonblack:
            x, y = ring[index]
            windows = [window['id'] for window in trace.OVERPRINTS
                       if window['box'][0] <= x <= window['box'][2]
                       and window['box'][1] <= y <= window['box'][3]]
            if len(windows) != 1:
                raise ValueError('An interpreted source pixel has no unique bounded window')
            if windows[0] not in used_windows:
                used_windows.append(windows[0])
            nonblack_records.append({'ringIndex': index, 'pixel': [x, y],
                                     'rgb': [int(channel) for channel in rgb[y, x]],
                                     'maxRgb': int(max_rgb[y, x]),
                                     'luminance': float(trace.luminance[y, x]),
                                     'interpretationWindowId': windows[0]})
        interpretation = {
            'literalBlackPixelClosureEstablished': not nonblack,
            'darkBlueSourcePixelCount': len(nonblack),
            'boundedInterpretationWindowIds': used_windows,
            'nonblackSourcePixels': nonblack_records,
            'incidentSourceEdgeIndices': incident_edges,
            'incidentEdgeLengthSourcePixels': interpreted_pixel_length,
            'incidentEdgeLengthMetresApproximate': interpreted_length,
            'lengthMeaning': 'Boundary edges touching a non-black interpreted vertex, not an accuracy bound.',
            'underlyingBlackStrokeProvedWithinLabels': False if nonblack else None,
        }
        overprint_details[name] = interpretation
        properties = {
            'name': name, 'municipality': 'Kecskemét',
            'boundaryKind': 'neighbourhood' if is_primary else 'inferred_area',
            'canonicalNameIsNeighborhood': is_primary,
            'method': METHOD if is_primary else INFERRED_METHOD,
            'evidenceUrls': [URL],
            'sourceDocuments': [{'url': URL, 'sha256': PDF_SHA, 'pdfPageOneBased': 175,
                                 'printedPage': 173, 'figure': 81, 'imageXref': 216,
                                 'originalImageSha256': IMAGE_SHA}],
            'sourcePeriod': '2021 May municipal consultation draft; underlying orthophoto date unknown.',
            'sourceRaster': {'path': str((OUT / 'page175-xref216.jpeg').relative_to(ROOT)),
                             'sha256': IMAGE_SHA, 'width': 1259, 'height': 893,
                             'pixelCoordinateConvention': 'Integer source-pixel indices; x right, y down; top-left (0,0), no half-pixel offset.',
                             'denseSourcePixelCount': len(ring),
                             'collinearCompressedPixelCount': len(simple)},
            'estimated': not is_primary,
            'sourceIsOfficial': False, 'sourceIsHardBoundary': False,
            'usableForAddressAssignment': False, 'claimedAbsoluteAccuracyMetres': None,
            'geometryVerificationStatus': ('historical_source_black_outline_georeferencing_accuracy_unknown'
                                           if is_primary else 'source_label_occlusion_interpretation_not_verified'),
            'reviewStatus': ('source_based_historical_boundary_review_required' if is_primary
                             else 'estimated_candidate_not_verified'),
            'currentNameEvidence': {'status': '2021_municipal_fine_label_only',
                                    'currentNameIndependentlyConfirmed': False,
                                    'matchingExactCurrentOsmLabelVerified': False},
            'labelOcclusionInterpretation': {key: value for key, value in interpretation.items()
                                             if key != 'nonblackSourcePixels' and key != 'incidentSourceEdgeIndices'},
            'reviewNotes': [
                'These are separately labelled fine source outlines, not the combined Széchenyiváros–Máriahegy planning extent.',
                'Geographic output vertices derive from historical source pixels; they are not original OSM vertices.',
                'Literal contemporary OSM junction coordinates locate the image approximately; manually chosen old-image points and source line width have uncalibrated uncertainty.',
                'Control residuals and the held-out visual check do not establish absolute boundary accuracy.',
                'Current fine names, legal/cadastral status and address assignment are not independently established.',
            ],
            'areaM2': abs(area), 'perimeterM': perimeter,
            'license': 'Municipal source-map reuse rights not independently established; ODbL-1.0 applies to OSM georeferencing controls.',
            'attribution': 'Source: Kecskemét MJV Megalapozó Vizsgálat II, May 2021 consultation draft, Figure 81; geographical controls ©OpenStreetMap contributors.',
        }
        if not is_primary:
            properties['candidateBoundaryKind'] = 'neighbourhood'
            properties['reviewNotes'].append(
                'Dark-blue label pixels obscure a short source-boundary continuation. Their exact positions are preserved as an explicit estimate; no black source closure is claimed through the label.')
        feature = {'type': 'Feature', 'id': 'manual:kecskemet-figure81:' + SLUGS[name],
                   'properties': properties, 'geometry': mapping(geographic)}
        (primary if is_primary else inferred).append(feature)
        records.append({'name': name, 'layer': 'literal-source' if is_primary else 'estimated',
                        'valid': True, 'sourcePixelWalkClosed': True,
                        'allDenseSteps8Neighbor': True, 'allDensePixelsMaxRgbAtMost45': not nonblack,
                        'darkBlueInterpretedPixelCount': len(nonblack),
                        'densePixelCount': len(ring), 'compressedPixelCount': len(simple),
                        'sourcePixelArea': original.area, 'simplificationSymmetricDifferencePixelArea': 0,
                        'canonicalParentContained': True, 'areaM2': abs(area),
                        'absoluteBoundaryAccuracyMetres': None, 'geographicCoordinatesAreOsmVertices': False})

    overlaps = []
    names = list(pixel_geometries)
    for index, name in enumerate(names):
        for other in names[index + 1:]:
            pixel_overlap = pixel_geometries[name].intersection(pixel_geometries[other]).area
            geographic_overlap = world_geometries[name].intersection(world_geometries[other]).area
            if pixel_overlap != 0 or geographic_overlap > 1e-20:
                raise ValueError('Candidate interiors overlap: ' + name + ' / ' + other)
            overlaps.append({'names': [name, other], 'sourcePixelInteriorOverlapArea': pixel_overlap,
                             'geographicInteriorOverlapSquareDegrees': geographic_overlap})

    save('szechenyi-source-raster.geojson', {'type': 'FeatureCollection', 'features': primary})
    save('szechenyi-label-inferred.geojson', {'type': 'FeatureCollection', 'status': 'estimated_candidates_only',
                                           'usableForAddressAssignment': False, 'features': inferred})
    save('raster-pixel-trace.json', {
        'sourceImageSha256': IMAGE_SHA, 'literalBlackThresholdMaxRgb': 45,
        'manualSeeds': trace.SECTIONS,
        'snappedManualSeeds': [{'manualPixel': manual, 'actualSourceBlackPixel': snapped}
                              for manual, snapped in trace.snaps.items()],
        'manualSearchCorridorPixels': trace.PAD,
        'corridorMeaning': 'Search constraint only, never a geographic buffer or invented boundary.',
        'explicitDarkBlueLabelInterpretationWindows': trace.OVERPRINTS,
        'sourcePixelPaths': trace.paths, 'denseClosedPixelRings': trace.RINGS,
        'compressedClosedPixelRings': compressed_rings, 'labelOcclusionDetails': overprint_details,
        'protectedSharedSectionEndpointPixels': [list(point) for point in sorted(protected)],
        'unexportedSourceClipUnits': ['Külső-Máriahegy', 'Villanegyed'],
        'clippedTipsReconstructed': False,
    })
    save('raster-georeference.json', {
        'sourceImageSha256': IMAGE_SHA, 'actualControlRoadInputSha256': ROADS_SHA,
        'allControlCoordinatesMatchLiteralOsmNodes': True, 'controlWaysUnmodifiedFromOriginalArchive': True,
        'controlSpecificationSha256': CONTROLS_SHA, 'controls': controls,
        'fitMethod': 'Least squares [pixelX,pixelY,1] row vectors to EOV/EPSG:23700; inverse projection to WGS84.',
        'matrixSourcePixelRowToEov': affine.tolist(), 'fitResidualMetres': residuals.tolist(),
        'fitResidualSourcePixels': residual_pixels.tolist(),
        'heldOutControl': {**held_out, 'predictedSourcePixel': held_out_pixel.tolist(),
                           'insideIndependentApproximateVisualWindow': bool(held_out_within)},
        'metricProjection': 'EPSG:23700', 'outputCrs': 'EPSG:4326',
        'pyprojVersion': pyproj.__version__, 'projVersion': pyproj.proj_version_str,
        'wgs84ToMetricPipeline': to_metric.get_last_used_operation().definition,
        'metricToWgs84Pipeline': to_wgs84.get_last_used_operation().definition,
        'projectionOperationAccuracyMetresFromLibrary': {
            'wgs84ToMetric': to_metric.get_last_used_operation().accuracy,
            'metricToWgs84': to_wgs84.get_last_used_operation().accuracy,
            'meaning': 'Library datum-transformation metadata only; does not include source-map, manual-control or boundary uncertainty.'},
        'sourceMapProjectionKnown': False, 'claimedAbsoluteAccuracyMetres': None,
        'controlInterpretation': 'Literal geographical OSM nodes, with manually approximated source-image junction locations; no surveyed image control or absolute accuracy guarantee.',
    })
    save('conversion-proof.json', {
        'schemaVersion': 1, 'sourcePublisherPdfSha256': PDF_SHA, 'sourceImageSha256': IMAGE_SHA,
        'sourceExtractionProofSha256': EXTRACTION_SHA, 'pixelTraceHelperSha256': sha(helper),
        'literalSourceMethod': METHOD, 'estimatedMethod': INFERRED_METHOD,
        'records': records, 'pairwiseOverlapChecks': overlaps,
        'sharedSourceSectionsReusedIdentically': True, 'geometryRepairPerformed': False,
        'clippedSourceTipsExported': False,
        'unresolvedSourceUnits': [
            {'name': 'Külső-Máriahegy', 'reason': 'Source top tip clipped; black rays do not visibly close.'},
            {'name': 'Villanegyed', 'reason': 'Source bottom tip clipped; disjoint black rays at final photographic row.'},
        ],
        'primaryFeatureCount': 2, 'estimatedFeatureCount': 2,
        'primaryOutputSha256': generated['szechenyi-source-raster.geojson'],
        'estimatedOutputSha256': generated['szechenyi-label-inferred.geojson'],
        'canonicalMunicipalityInputSha256': sha(parent_path),
        'reproduce': 'PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-kecskemet-fig81.py --check',
        'usableForAddressAssignment': False,
    })
    for filename, dataset, geometry_file, method, overrides in [
        ('registry-entry.json', 'kecskemet-figure81-source-raster', 'szechenyi-source-raster.geojson', METHOD,
         {'boundaryKind': 'neighbourhood', 'canonicalNameIsNeighborhood': True, 'usableForAddressAssignment': False}),
        ('inferred-registry-entry.json', 'kecskemet-figure81-label-inference', 'szechenyi-label-inferred.geojson', INFERRED_METHOD,
         {'boundaryKind': 'inferred_area', 'candidateBoundaryKind': 'neighbourhood',
          'estimated': True, 'canonicalNameIsNeighborhood': False, 'usableForAddressAssignment': False}),
    ]:
        save(filename, {'id': dataset, 'path': str((OUT / geometry_file).relative_to(ROOT)),
                        'sha256': generated[geometry_file], 'municipality': 'Kecskemét',
                        'method': method, 'evidenceUrls': [URL],
                        'license': 'Municipal source-map reuse rights unverified; ODbL-1.0 for OSM georeferencing controls.',
                        'propertyOverrides': overrides,
                        'reviewPath': str((OUT / 'raster-independent-review.json').relative_to(ROOT)),
                        'rightsStatus': 'Publicly published municipal consultation draft; open-reuse license not independently established.'})
    save('generated-manifest.json', {
        'schemaVersion': 1, 'primaryFeatureCount': 2, 'estimatedFeatureCount': 2,
        'unexportedSourceUnitCount': 2,
        'inputs': {filename: sha(OUT / filename) for filename in [
            'page175-xref216.jpeg', 'source-extraction.json', 'control-roads.geojson',
            'control-specification.json', 'trace-figure81-pixels.py', 'visual-review.json']},
        'converterPath': str(Path(__file__).relative_to(ROOT)), 'converterSha256': sha(Path(__file__)),
        'generatedArtifactsSha256': dict(generated),
        'independentReviewPath': str((OUT / 'raster-independent-review.json').relative_to(ROOT)),
        'claimedAbsoluteAccuracyMetres': None, 'usableForAddressAssignment': False,
    })
    if not check:
        preview = image.copy()
        draw = ImageDraw.Draw(preview)
        for name, ring in trace.RINGS.items():
            draw.line(ring, fill='red' if name in PRIMARY_NAMES else 'orange', width=2)
        preview.save(OUT / 'raster-trace-preview.png')
    print(json.dumps({'primary': 2, 'estimated': 2, 'unresolvedClippedTips': 2,
                      'features': [{'name': record['name'], 'layer': record['layer'],
                                    'vertices': record['compressedPixelCount'],
                                    'areaM2': round(record['areaM2'])} for record in records],
                      'primarySha256': generated['szechenyi-source-raster.geojson'],
                      'estimatedSha256': generated['szechenyi-label-inferred.geojson'],
                      'check': check}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Compare generated artifacts without writing them.')
    build(parser.parse_args().check)
