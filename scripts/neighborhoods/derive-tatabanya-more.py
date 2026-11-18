#!/usr/bin/env python3
"""Extract additional literal Tatabánya source cycles, without repairing the map.

All vector endpoints come from original PDF decimal operands and graphics CTMs.
Existing four quarter outputs are used only for comparison and are not exported.
Compound source areas remain a separate planning/group layer. --check is read-only.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'data/neighborhoods/sources/municipal-west'
OUT = ROOT / 'data/neighborhoods/sources/municipal-tatabanya-more'
PDF_SHA = '7a7ca9a8f70f0dcaad90deb3ce27a459a8b70610914c72cc7d9ec98eb2fb76d7'
GEOREF_SHA = 'e0debc1af65c71699403deaa786efbdfd63337d84d980c37c7128e2705c6aeb8'
OLD_FOUR_SHA = 'fd527b72165d5a50178f3eedfc0cb0498ee9c087bd7aa1727e1a4794a8c9100e'
URL = 'https://njt.jog.gov.hu/document/c5/c56aLL_EJR_13372578-H_SZ_3.mell_klet.pdf'
METHOD = (
    'Literal source-vector circuit extraction from the single-page Tatabánya Városrészek '
    'településrendezési szempontú lehatárolása map, annex 3 of municipal regulation 8/2018 '
    '(IV.19.). Original decimal PDF path operands and graphics matrices are evaluated '
    'exactly, rather than snapping MuPDF float32 endpoint approximations. Every exported '
    'edge is an actual selected source line item, possibly reversed. Explicit source '
    'subcircuits omit documented out-and-back nonboundary strokes; no buffer, make_valid, '
    'invented closing edge, smoothing, clipping or geographical snapping is used. '
    'The frozen earlier municipal-outline affine georegistration into EOV/EPSG:23700 '
    'is preserved and inverse-projected into WGS84. Historical source overlaps and '
    'small differences from the current OSM city boundary remain unmodified and recorded.'
)

# Each arc is [drawing index, first vertex, last vertex, reverse]. The indices
# address actual source vertices, not automatically repaired polygonized output.
UNITS = [
    {'name': 'Galla ipari övezet', 'slug': 'galla-ipari-ovezet', 'kind': 'neighbourhood',
     'labels': ['GALLA IPARI ÖVEZET'],
     'rings': [[[1815, 0, 366, False], [1815, 368, 517, False]]],
     'excluded': [{'drawing': 1815, 'vertices': [366, 367, 368],
                   'reason': 'Exact out-and-back spur: vertices 366 and 368 are identical. Both opposite traversals are nonboundary strokes; no replacement edge.'}]},
    {'name': 'Észak-Vértes', 'slug': 'eszak-vertes', 'kind': 'neighbourhood',
     'labels': ['ÉSZAK-VÉRTES'],
     'rings': [[[1286, 0, 745, False]], [[6325, 0, 470, False]]],
     'excluded': [],
     'interpretation': 'Outer green source ring 1286 and explicit opposite-winding green inner ring 6325; the latter is exactly the existing separate Síkvölgy ring 5531. The source visibly renders Síkvölgy orange inside the green forest quarter.'},
    {'name': 'Nyugat-Gerecse', 'slug': 'nyugat-gerecse', 'kind': 'neighbourhood',
     'labels': ['NYUGAT-GERECSE'],
     'rings': [[[4557, 0, 894, False], [4558, 0, 140, False], [4851, 95, 96, True]]],
     'excluded': [],
     'interpretation': 'The final shared closing edge is actual Felsőgalla source item 95, followed in reverse. It is not an automatically generated endpoint chord.'},
    {'name': 'Bánhida – Dózsakert', 'slug': 'banhida-dozsakert-group', 'kind': 'planning_unit',
     'labels': ['BÁNHIDA', 'DÓZSAKERT'], 'rings': [[[5528, 0, 366, False]]], 'excluded': [],
     'interpretation': 'One literal outline contains both labels. No source-supported internal divider establishes two independent fine polygons.'},
    {'name': 'Szőlőhegy – Újváros – Sárberek', 'slug': 'szolohegy-ujvaros-sarberek-group', 'kind': 'planning_unit',
     'labels': ['SZŐLŐHEGY', 'ÚJVÁROS', 'SÁRBEREK'],
     'rings': [[[3277, 20, 308, False], [3267, 0, 65, False], [3696, 0, 203, False]]],
     'excluded': [{'drawings': [3277, 3696], 'vertexRanges': [[0, 20], [203, 223]],
                   'reason': 'These are exactly the same shared internal road-side source chain in opposite directions. The outer source subcircuit closes at vertices 3277:20 and 3696:203. The remaining A–B internal divider is not supplied by an exact named-area source circuit.'}],
     'interpretation': 'The three actual outer source arcs close one combined area. It is not copied under any constituent fine name.'},
    {'name': 'VI-os telep – Felsőgalla', 'slug': 'vi-os-telep-felsogalla-group', 'kind': 'planning_unit',
     'labels': ['VI-OS TELEP', 'FELSŐGALLA'],
     'rings': [[[4836, 5, 223, False], [4851, 13, 235, True], [4851, 5, 11, True]]],
     'excluded': [{'drawing': 4851, 'vertices': [11, 12, 13],
                   'reason': 'Exact out-and-back spur, identical endpoints; no replacement edge.'},
                  {'drawings': [4836, 4851], 'vertexRanges': [[0, 5], [0, 5]],
                   'reason': 'Leading source stems and their tiny 0.54 PDF-square-point loop are internal to the selected combined source cycle, not its outer boundary. No source-supported complete internal highway divider is invented.'}],
     'interpretation': 'Two differently colored but open fine outlines supply one literal combined outer circuit. Fine VI-os telep and Felsőgalla remain unresolved separately.'},
    {'name': 'Nyugati ipari park – Erőmű ltp.', 'slug': 'nyugati-ipari-park-eromu-ltp-group', 'kind': 'planning_unit',
     'labels': ['NYUGATI IPARI PARK', 'ERŐMŰ LTP.'],
     'rings': [[[5527, 0, 336, False]]],
     'excluded': [{'drawing': 5527, 'vertices': [336, 337, 338, 339],
                   'reason': 'A tiny 0.0216 PDF-square-point interior triangle repeats the beginning of the already closed large source cycle. It lies entirely inside that cycle; no extent is removed and no fine split is guessed.'}],
     'interpretation': 'One large source circuit includes both labels. Turquoise source path 6326 is a lake footprint, not an Erőmű lakótelep boundary.'},
]
OLD_UNITS = {'Kertváros': 4284, 'Alsógalla': 5529, 'Óváros': 5530, 'Síkvölgy': 5531}
LABELS = ['KERTVÁROS', 'BÁNHIDA', 'SZŐLŐHEGY', 'ALSÓGALLA', 'ÓVÁROS', 'VI-OS TELEP',
          'SÍKVÖLGY', 'NYUGAT-GERECSE', 'GALLA IPARI ÖVEZET', 'DÓZSAKERT', 'ÚJVÁROS',
          'ÉSZAK-VÉRTES', 'SÁRBEREK', 'ERŐMŰ LTP.', 'FELSŐGALLA', 'NYUGATI IPARI PARK']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def build(check=False):
    import math
    from decimal import Decimal
    import numpy as np
    import pyproj
    from PIL import Image, ImageDraw
    from pyproj import Transformer, Geod
    from shapely.geometry import Polygon, Point, shape, mapping
    from shapely.ops import transform, nearest_points

    pyproj.network.set_network_enabled(False)
    artifacts = {}

    def save(filename, document):
        content = encode(document)
        artifacts[filename] = hashlib.sha256(content).hexdigest()
        path = OUT / filename
        if check:
            if not path.exists() or path.read_bytes() != content:
                raise ValueError('Stale or missing generated artifact: ' + str(path))
        else:
            path.write_bytes(content)

    for filename, expected in [('tatabanya-map.source.pdf', PDF_SHA),
                               ('tatabanya-georeference-proof.json', GEOREF_SHA),
                               ('tatabanya-manual.geojson', OLD_FOUR_SHA)]:
        if sha(OLD / filename) != expected:
            raise ValueError('Changed frozen original input: ' + filename)
    helper = OUT / 'parse_exact_pdf.py'
    spec = importlib.util.spec_from_file_location('tatabanya_original_decimal_paths', helper)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    parsed = parser.read_paths(OLD / 'tatabanya-map.source.pdf')
    paths = parsed['paths']
    source_points = {}

    def points(index):
        if index in source_points:
            return source_points[index]
        items = paths[index]['items']
        if (not items or any(item[0] != 'l' for item in items)
                or any(a[2] != b[1] for a, b in zip(items, items[1:]))):
            raise ValueError('Selected source outline is not one continuous literal line path')
        values = [items[0][1]] + [item[2] for item in items]
        source_points[index] = values
        return values

    def joined(arcs):
        ring, origins = [], []
        for index, start, end, reverse in arcs:
            part = points(index)[start:end + 1]
            if len(part) != end - start + 1:
                raise ValueError('Source arc index exceeds original source path')
            if reverse:
                part = part[::-1]
            if ring and ring[-1] != part[0]:
                raise ValueError('Source arc endpoints are not exactly identical Decimal coordinates')
            ring += part if not ring else part[1:]
            origins += [{'sourceDrawingIndex': index, 'sourceLineItemIndex': item,
                         'reversed': reverse} for item in (range(end - 1, start - 1, -1)
                                                          if reverse else range(start, end))]
        if ring[0] != ring[-1] or len(origins) != len(ring) - 1:
            raise ValueError('Literal source circuit does not close without a generated edge')
        # Prove every exported edge belongs to its actual original drawing item.
        for before, after, origin in zip(ring, ring[1:], origins):
            source = paths[origin['sourceDrawingIndex']]['items'][origin['sourceLineItemIndex']]
            expected = (source[2], source[1]) if origin['reversed'] else (source[1], source[2])
            if (before, after) != expected:
                raise ValueError('An output edge differs from its literal source edge')
        return ring, origins

    # These are explicit source identities, not geometry repair heuristics.
    if points(1815)[366] != points(1815)[368] or points(4851)[11] != points(4851)[13]:
        raise ValueError('Recorded exact nonboundary out-and-back spur identity changed')
    if points(6325) != points(5531):
        raise ValueError('Explicit forest inner ring is not exactly existing Síkvölgy source boundary')
    def signed_area(ring):
        return sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(ring, ring[1:])) / Decimal(2)
    if signed_area(points(1286)) * signed_area(points(6325)) >= 0:
        raise ValueError('Explicit same-color source forest hole has no opposite winding')
    if points(3277)[:21] != list(reversed(points(3696)[203:224])):
        raise ValueError('Northern omitted internal source chain is no longer exactly shared')
    if points(5527)[336] != points(5527)[0] or points(5527)[339] != points(5527)[0]:
        raise ValueError('Western main source cycle does not explicitly close')

    labels = {}
    for block in parsed['page'].get_text('dict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                if span['text'] in LABELS:
                    a, b, c, d = span['bbox']
                    labels[span['text']] = {'bbox': list(span['bbox']),
                                            'centre': [(a+c)/2, (b+d)/2]}
    if set(labels) != set(LABELS):
        raise ValueError('Original 16 source labels not reproduced')

    legacy = json.loads((OLD / 'tatabanya-georeference-proof.json').read_text())
    affine = legacy['affinePdfToEov']
    if len(affine) != 6 or not all(math.isfinite(value) for value in affine):
        raise ValueError('Invalid frozen source georeference')
    inverse_projection = Transformer.from_crs(23700, 4326, always_xy=True)
    to_metric = Transformer.from_crs(4326, 23700, always_xy=True)

    def metric_xy(x, y, z=None):
        x, y = np.array(x), np.array(y)
        return (affine[0]*x+affine[1]*y+affine[4],
                affine[2]*x+affine[3]*y+affine[5])

    def world_ring(ring):
        array = np.array([[float(value) for value in point] for point in ring])
        x, y = metric_xy(array[:, 0], array[:, 1])
        lon, lat = inverse_projection.transform(x, y)
        return np.c_[lon, lat].tolist()

    parent_path = ROOT / 'data/neighborhoods/sources/country-osm/municipalities.geojson.gz'
    parent_features = json.loads(gzip.decompress(parent_path.read_bytes()))['features']
    parent_feature = next(feature for feature in parent_features
                          if feature['properties']['name'] == 'Tatabánya'
                          and feature['properties'].get('usedForAssociation'))
    parent_metric = transform(to_metric.transform, shape(parent_feature['geometry']))
    control_checks = []
    for control in legacy['registration']['controlPoints']:
        pixel = control['sourcePdfPoint']
        x, y = metric_xy(*pixel)
        x, y = float(x), float(y)
        reported = control['transformedEovPoint']
        nearest = nearest_points(Point(x, y), parent_metric.boundary)[1]
        residual = Point(x, y).distance(parent_metric.boundary)
        if (math.dist([x, y], reported) > 1e-7
                or abs(residual-control['residualM']) > 1e-5
                or nearest.distance(Point(control['referenceEovPoint'])) > 1e-5):
            raise ValueError('Frozen control no longer matches current literal reference geometry')
        control_checks.append({**control, 'recomputedResidualM': residual,
                               'frozenAffineReproducesReportedControl': True,
                               'currentParentNearestPointReproducesReportedReference': True})

    geod = Geod(ellps='WGS84')
    primary, groups, circuits, geometries, metric_geometries = [], [], [], {}, {}
    for unit in UNITS:
        rings_and_origins = [joined(arcs) for arcs in unit['rings']]
        rings = [item[0] for item in rings_and_origins]
        polygon = Polygon(rings[0], rings[1:])
        if not polygon.is_valid or polygon.is_empty:
            raise ValueError('Selected literal source circuit is not valid: ' + unit['name'])
        contained_labels = [name for name, label in labels.items()
                            if polygon.covers(Point(label['centre']))]
        if set(contained_labels) != set(unit['labels']):
            raise ValueError('Fine/group source label coverage mismatch: ' + unit['name'] + str(contained_labels))
        metric = transform(metric_xy, polygon)
        world = Polygon(world_ring(rings[0]), [world_ring(ring) for ring in rings[1:]])
        if not metric.is_valid or not world.is_valid:
            raise ValueError('Georeference invalidates literal source circuit')
        geometries[unit['name']], metric_geometries[unit['name']] = polygon, metric
        outside = metric.difference(parent_metric)
        fraction = outside.area / metric.area
        if fraction > 0.005:
            raise ValueError('Georeferenced source extent differs materially from intended municipality')
        outside_vertex_distances = [Point(point).distance(parent_metric)
                                    for point in metric.exterior.coords]
        comparison = {'referenceMunicipality': 'Tatabánya',
                      'fullyContained': parent_metric.covers(metric),
                      'outsideAreaM2': outside.area, 'outsideFraction': fraction,
                      'maximumOutsideDistanceAmongExteriorVerticesM': max(outside_vertex_distances),
                      'sourceClippedToReference': False,
                      'interpretation': 'Historical source outline plus approximate registration compared with contemporary OSM reference; mismatch preserved, not repaired.'}
        area, perimeter = geod.geometry_area_perimeter(world)
        is_primary = unit['kind'] == 'neighbourhood'
        properties = {
            'name': unit['name'], 'municipality': 'Tatabánya', 'boundaryKind': unit['kind'],
            'canonicalNameIsNeighborhood': is_primary, 'estimated': False,
            'method': METHOD, 'evidenceUrls': [URL],
            'sourceDocuments': [{'url': URL, 'sha256': PDF_SHA, 'pdfPageOneBased': 1,
                                 'title': 'Tatabánya városrészek településrendezési szempontú lehatárolása',
                                 'annex': '8/2018. (IV.19.) önk. rendelet, 3. melléklet'}],
            'sourceLabels': unit['labels'], 'sourcePeriod': '2018 municipal map; current legal force and underlying data date not independently checked.',
            'sourceCircuitArcs': unit['rings'],
            'sourcePdfCoordinatesFromExactDecimalOperands': True,
            'sourceGeographicCoordinatesAreOsmVertices': False,
            'sourceIsOfficial': False, 'sourceIsHardBoundary': False,
            'usableForAddressAssignment': False, 'claimedAbsoluteAccuracyMetres': None,
            'geometryVerificationStatus': 'literal_source_vector_circuit_approximate_georeference',
            'reviewStatus': 'historical_source_boundary_reference_differences_review_required',
            'currentNameEvidence': {'status': 'municipal_2018_source_label_only',
                                    'currentNameIndependentlyConfirmed': False},
            'referenceMunicipalityComparison': comparison,
            'sourceInterpretation': unit.get('interpretation', 'Individually named literal source circuit, with explicitly recorded nonboundary retraced spur.'),
            'excludedNonboundarySourceStrokes': unit['excluded'],
            'sourceOverlapCaveat': 'The original source has small boundary overlaps; they are measured separately and preserved without trimming.',
            'areaM2': abs(area), 'perimeterM': perimeter,
            'license': 'Municipal map open-reuse license not independently established; ODbL-1.0 pertains to the OSM registration reference.',
            'attribution': 'Source: Tatabánya 8/2018 (IV.19.), annex 3; geographic registration reference ©OpenStreetMap contributors.',
        }
        if not is_primary:
            properties.update({'constituentSourceLabels': unit['labels'],
                               'nameIsDescriptiveCombination': True,
                               'notIndividualFineNeighbourhood': True})
        feature = {'type': 'Feature', 'id': 'manual:tatabanya-more:' + unit['slug'],
                   'properties': properties, 'geometry': mapping(world)}
        (primary if is_primary else groups).append(feature)
        circuits.append({'name': unit['name'], 'kind': unit['kind'],
                         'literalSourceRings': [[[str(value) for value in point] for point in ring] for ring in rings],
                         'sourceArcs': unit['rings'],
                         'edgeOrigins': [item[1] for item in rings_and_origins],
                         'allSourceEdgesVerifiedExactly': True, 'sourceRingsExplicitlyClosed': True,
                         'noInventedClosingEdge': True,
                         'excludedNonboundarySourceStrokes': unit['excluded'],
                         'sourcePdfSquaredPointArea': polygon.area,
                         'labelCentresInside': contained_labels,
                         'referenceMunicipalityComparison': comparison})

    # The extra tiny source loops are genuine interior strokes. Prove that
    # selecting the literal outer cycles does not discard any exterior extent.
    west_triangle = Polygon(points(5527)[336:340])
    a, b = points(4836), points(4851)
    south_interior_loop = Polygon(a[3:6] + list(reversed(b[3:5])) + [a[3]])
    interior_loop_checks = []
    for name, loop, group in [
        ('5527:336-339', west_triangle, 'Nyugati ipari park – Erőmű ltp.'),
        ('4836/4851 shared leading stem loop', south_interior_loop, 'VI-os telep – Felsőgalla'),
    ]:
        if not geometries[group].covers(loop):
            raise ValueError('Omitted source loop extends outside selected group source circuit')
        interior_loop_checks.append({'sourceLoop': name, 'sourcePdfSquaredPointArea': loop.area,
                                     'entirelyInsideSelectedSourceCycle': True,
                                     'exteriorExtentDiscarded': False})

    # Compare to all original source quarters as well as the seven new outputs.
    # Small source slivers are evidence, not a reason to alter source boundaries.
    for name, index in OLD_UNITS.items():
        polygon = Polygon(points(index))
        geometries[name] = polygon
        metric_geometries[name] = transform(metric_xy, polygon)
    overlaps = []
    names = list(geometries)
    for index, name in enumerate(names):
        for other in names[index + 1:]:
            source_overlap = geometries[name].intersection(geometries[other]).area
            if source_overlap > 1e-9:
                overlaps.append({'names': [name, other], 'sourcePdfSquaredPoints': source_overlap,
                                 'approximateMetricOverlapM2': metric_geometries[name].intersection(metric_geometries[other]).area,
                                 'overlapAlreadyInOriginalSource': True, 'trimmedOrRepaired': False})
    selected_indices = sorted(set(source_points) | {6326})
    drawing_archive = []
    for index in selected_indices:
        drawing = paths[index]
        matrices = []
        commands = []
        for command in drawing['rawPath']:
            matrix = command.get('ctm')
            if matrix is not None and matrix not in matrices:
                matrices.append(matrix)
            commands.append({'operator': command['operator'], 'operands': command.get('operands', []),
                             'ctmIndex': matrices.index(matrix) if matrix is not None else None})
        drawing_archive.append({'sourceDrawingIndex': index, 'paintOperator': drawing['paint'],
                                'strokeRgbDecimal': [str(v) for v in drawing['color']] if drawing['color'] else None,
                                'graphicsMatricesDecimal': matrices, 'originalCommands': commands,
                                'exactPageLineItems': [[item[0], *[[str(v) for v in point] for point in item[1:]]]
                                                       for item in drawing['items']]})
    save('source-vector-trace.json', {
        'schemaVersion': 1, 'sourcePdfSha256': PDF_SHA,
        'contentStreamRefs': parsed['page'].get_contents(),
        'decodedConcatenatedContentSha256': hashlib.sha256(parsed['rawStreams']).hexdigest(),
        'sourcePageSizePoints': [str(value) for value in parsed['pageSize']],
        'parsedDrawingCount': len(paths), 'drawingPaintOrderMatchesMuPdf': True,
        'maximumMuPdfFloatBoundingCoordinateDifferencePoints': parsed['maximumMuPdfBoundingCoordinateDifferencePoints'],
        'decimalMeaning': 'Exact original PDF numbers and graphics CTMs; endpoint equality is not coordinate snapping.',
        'parserSha256': sha(helper), 'sourceLabels': labels,
        'selectedOriginalDrawings': drawing_archive, 'extractedCircuits': circuits,
        'existingFourNotReexported': OLD_UNITS, 'sourceOverlapsPreserved': overlaps,
        'sourceForestRingSignedAreas': {'outer1286': str(signed_area(points(1286))),
                                       'inner6325': str(signed_area(points(6325)))},
        'excludedInteriorSourceLoopChecks': interior_loop_checks,
        'waterFootprintExcluded': {'drawing': 6326, 'reason': 'Erőmű-tó lake, not the Erőmű LTP. label extent.'},
    })
    save('additional-quarter-vectors.geojson', {'type': 'FeatureCollection', 'features': primary})
    save('compound-source-groups.geojson', {'type': 'FeatureCollection', 'features': groups})
    save('georeference-proof.json', {
        'schemaVersion': 1, 'frozenEarlierProofPath': str((OLD / 'tatabanya-georeference-proof.json').relative_to(ROOT)),
        'frozenEarlierProofSha256': GEOREF_SHA, 'affinePdfToEov': affine,
        'registrationMethod': legacy['registration']['method'],
        'frozenCalibrationVertexCount': legacy['registration']['calibrationVertices'],
        'frozenCalibrationRmsM': legacy['registration']['rmsM'],
        'recomputedSampledControlChecks': control_checks,
        'referenceMunicipalitySource': legacy['registration']['municipalitySource'],
        'currentReferenceMunicipalityArchivePath': str(parent_path.relative_to(ROOT)),
        'currentReferenceMunicipalityArchiveSha256': sha(parent_path),
        'reoptimisedOrShiftedToFitNewSourceCycles': False,
        'originalSourceGeographicCrsKnown': False, 'metricCrs': 'EPSG:23700', 'outputCrs': 'EPSG:4326',
        'inverseProjectionPipeline': inverse_projection.get_last_used_operation().definition,
        'projectionOperationAccuracyMetadataM': inverse_projection.get_last_used_operation().accuracy,
        'projectionAccuracyMetadataMeaning': 'Library datum operation metadata only, not source-map or boundary accuracy.',
        'pyprojVersion': pyproj.__version__, 'projVersion': pyproj.proj_version_str,
        'projNetworkDisabled': True, 'claimedAbsoluteAccuracyMetres': None,
        'referenceDifferencesAndOverlapsPreserved': True, 'usableForAddressAssignment': False,
    })
    blockers = [
        {'names': ['Bánhida', 'Dózsakert'], 'sourceGroup': 'Bánhida – Dózsakert',
         'reason': 'One source contour contains two labels; no distinct complete internal quarter divider is shown.'},
        {'names': ['Szőlőhegy', 'Újváros', 'Sárberek'], 'sourceGroup': 'Szőlőhegy – Újváros – Sárberek',
         'reason': 'The literal outer circuit is recoverable. The northern M1 divider has an actual missing A–B section; Újváros and Sárberek also share one outline without a complete internal source divider.',
         'missingNorthernDividerExactEndpointsPdf': [['274.52', '160.72'], ['303.56', '199.96']]},
        {'names': ['VI-os telep', 'Felsőgalla'], 'sourceGroup': 'VI-os telep – Felsőgalla',
         'reason': 'Only the combined actual source outer cycle closes. A complete literal internal road-1 dividing circuit is absent; road ink/nearby gray strips are not an exact named-area closure.',
         'individualOpenPathEndpointsPdf': [['555.20', '535.24'], ['597.68', '613.36']]},
        {'names': ['Nyugati ipari park', 'Erőmű ltp.'], 'sourceGroup': 'Nyugati ipari park – Erőmű ltp.',
         'reason': 'Both labels lie in one large source outline. The turquoise closed shape nearby is a lake and cannot substitute for the missing residential outline.'},
    ]
    save('unresolved-fine-areas.json', {'schemaVersion': 1, 'sourceLabelCount': 16,
                                      'previousFineQuarterCount': 4, 'newFineQuarterCount': 3,
                                      'individuallyUnresolvedFineNames': 9,
                                      'compoundSourceAreasProduced': 4,
                                      'blockers': blockers, 'inventedFineSplitsProduced': False,
                                      'currentNamesIndependentlyVerified': False,
                                      'usableForAddressAssignment': False})
    save('conversion-proof.json', {'schemaVersion': 1, 'method': METHOD, 'sourcePdfSha256': PDF_SHA,
                                   'primaryCount': 3, 'compoundGroupCount': 4,
                                   'oldFourReexported': False, 'parserSha256': sha(helper),
                                   'sourceOverlapsPreserved': overlaps,
                                   'exactOriginalDecimalOperandsUsed': True,
                                   'allExportedEdgesMatchActualSourceLineItems': True,
                                   'automaticGeometryRepairOrSourceClipping': False,
                                   'primaryOutputSha256': artifacts['additional-quarter-vectors.geojson'],
                                   'groupOutputSha256': artifacts['compound-source-groups.geojson'],
                                   'reproduce': 'PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-tatabanya-more.py --check',
                                   'usableForAddressAssignment': False})
    for filename, dataset, geometry, kind in [
        ('registry-entry.json', 'tatabanya-more-source-vectors', 'additional-quarter-vectors.geojson', 'neighbourhood'),
        ('planning-registry-entry.json', 'tatabanya-compound-source-vectors', 'compound-source-groups.geojson', 'planning_unit'),
    ]:
        save(filename, {'id': dataset, 'path': str((OUT / geometry).relative_to(ROOT)),
                        'sha256': artifacts[geometry], 'municipality': 'Tatabánya', 'method': METHOD,
                        'evidenceUrls': [URL],
                        'license': 'Municipal source-map open-reuse rights unverified; ODbL-1.0 for OSM geographic reference.',
                        'propertyOverrides': {'boundaryKind': kind, 'canonicalNameIsNeighborhood': kind == 'neighbourhood',
                                              'usableForAddressAssignment': False},
                        'reviewPath': str((OUT / 'independent-review.json').relative_to(ROOT)),
                        'rightsStatus': 'Public legal-annex source; open-reuse licence not independently established.'})
    save('generated-manifest.json', {'schemaVersion': 1, 'primaryCount': 3, 'compoundGroupCount': 4,
                                     'originalPdfSha256': PDF_SHA, 'parserSha256': sha(helper),
                                     'visualReviewSha256': sha(OUT / 'visual-review.json'),
                                     'converterPath': str(Path(__file__).relative_to(ROOT)),
                                     'converterSha256': sha(Path(__file__)),
                                     'artifactsSha256': dict(artifacts),
                                     'usableForAddressAssignment': False})
    if not check:
        pixmap = parsed['page'].get_pixmap(matrix=parser.fitz.Matrix(2, 2))
        preview = Image.frombytes('RGB', [pixmap.width, pixmap.height], pixmap.samples)
        draw = ImageDraw.Draw(preview)
        for unit, circuit in zip(UNITS, circuits):
            color = 'red' if unit['kind'] == 'neighbourhood' else 'blue'
            for ring in circuit['literalSourceRings']:
                draw.line([(float(x)*2, float(y)*2) for x, y in ring], fill=color, width=2)
        preview.save(OUT / 'source-cycle-preview.png')
    print(json.dumps({'primary': [unit['name'] for unit in UNITS if unit['kind'] == 'neighbourhood'],
                      'compoundGroups': 4, 'unresolvedFineNames': 9,
                      'primarySha256': artifacts['additional-quarter-vectors.geojson'],
                      'groupSha256': artifacts['compound-source-groups.geojson'], 'check': check}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    build(parser.parse_args().check)
