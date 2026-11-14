#!/usr/bin/env python3
"""Research physical map cells, then benchmark them against actual mapped quarters.

This local prototype does not publish or integrate neighbourhood boundaries.
Cells use only municipality borders and actual major-road/rail/river/canal ways.
No snapping, line extension, buffers, Voronoi partitions or nearest-centre rules
are used. A named point inside a cell does not establish that quarter's extent.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import statistics
import sys
import unicodedata

from pyproj import Transformer
from shapely.geometry import Point, box, mapping, shape
from shapely.ops import polygonize, transform, unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
PROJECTED_CRS = 'EPSG:32634'
DEFAULT_CITIES = ('Budapest', 'Debrecen', 'Szeged')
QA_MINIMUM_MEDIAN_IOU = 0.5
TINY_CELL_AREA_RATIO = 0.1
MAXIMUM_PARENT_AREA_FRACTION = 0.95


def normalized_name(value):
    return ''.join(character for character in unicodedata.normalize('NFKD', value or '').casefold()
                   if character.isalnum() and not unicodedata.combining(character))


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def geometry_hash(geometry):
    return hashlib.sha256(json.dumps(mapping(geometry), separators=(',', ':')).encode()).hexdigest()


def read_json(path):
    if path.suffix == '.gz':
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding='utf-8'))


def pinned_output(directory, manifest, filename):
    entries = [entry for entry in manifest.get('outputs', []) if entry.get('file') == filename]
    if len(entries) != 1:
        raise ValueError(f'Missing/duplicate source fingerprint: {filename}')
    path = directory / filename
    if not path.exists():
        path = directory / (filename + '.gz')
    stored = path.read_bytes()
    raw = gzip.decompress(stored) if path.suffix == '.gz' else stored
    entry = entries[0]
    if len(raw) != entry.get('bytes') or hashlib.sha256(raw).hexdigest() != entry.get('sha256'):
        raise ValueError(f'Source fingerprint mismatch: {filename}')
    return json.loads(raw), {'path': str(path), 'sha256': hashlib.sha256(stored).hexdigest(),
                             'rawSha256': entry['sha256'], 'bytes': len(stored)}


def line_parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type in ('LineString', 'LinearRing'):
        return [geometry] if geometry.length > 0 else []
    if hasattr(geometry, 'geoms'):
        return [part for child in geometry.geoms for part in line_parts(child)]
    return []


def physical_cells(parent, barriers):
    """Polygonize actual source edges in metric coordinates, without gap filling."""
    if parent.is_empty or not parent.is_valid or parent.geom_type not in ('Polygon', 'MultiPolygon'):
        raise ValueError('A valid polygon municipality is required')
    clipped = []
    for record in barriers:
        for part in line_parts(record['geometry'].intersection(parent)):
            clipped.append({'id': record['id'], 'geometry': part})
    network = unary_union([parent.boundary, *(record['geometry'] for record in clipped)])
    cells = []
    for cell in polygonize(network):
        # Noding two floating-point lines can put an intersection a few ulps
        # outside an original segment. Intersect with the exact source parent;
        # this uses existing parent edges and never repairs/snaps a geometry.
        if not parent.covers(cell.representative_point()):
            continue
        clipped_cell = cell.intersection(parent)
        parts = list(clipped_cell.geoms) if clipped_cell.geom_type == 'MultiPolygon' else [clipped_cell]
        for part in parts:
            if part.geom_type != 'Polygon' or part.area <= 0:
                continue
            outside_area = part.difference(parent).area
            if outside_area > max(1e-8, parent.area * 1e-12):
                raise ValueError(f'Clipped cell has substantive area outside its parent: {outside_area} m²')
            cells.append(part)
    cells.sort(key=lambda cell: (*cell.bounds, cell.area))
    difference = parent.symmetric_difference(unary_union(cells)).area if cells else parent.area
    if difference > max(0.0001, parent.area * 1e-10):
        raise ValueError(f'Polygonized partition differs by {difference:.9g} m² of {parent.area:.9g} m² ({len(cells)} cells)')
    component_count = len(parent.geoms) if parent.geom_type == 'MultiPolygon' else 1
    return cells, clipped, {'cellCount': len(cells), 'parentAreaM2': parent.area,
                            'partitionDifferenceAreaM2': difference,
                            'maximumCellOutsideParentAreaM2': max((cell.difference(parent).area for cell in cells), default=0),
                            'hasMeaningfulSplit': len(cells) > component_count}


def assign_points(cells, points):
    index = STRtree(cells)
    groups, unresolved = defaultdict(list), []
    for point in points:
        candidates = [int(item) for item in index.query(point['geometry'])
                      if cells[int(item)].covers(point['geometry'])]
        containing = [item for item in candidates if cells[item].contains(point['geometry'])]
        if len(containing) != 1 or len(candidates) != 1:
            reason = 'point_on_cell_boundary' if candidates else 'point_outside_parent'
            unresolved.append({'id': point['id'], 'name': point['name'], 'reason': reason,
                               'candidateCellIndexes': candidates})
            continue
        groups[containing[0]].append(point)
    return dict(groups), unresolved


def analyse_assignments(city, cells, groups, known, parent_area, excluded_known_names=None, meaningful_split=None):
    """Benchmark first; only afterward exclude known names and ambiguous cells."""
    candidates, unresolved, benchmarks, benchmark_exclusions = [], [], [], []
    meaningful_split = len(cells) > 1 if meaningful_split is None else meaningful_split
    excluded_known_names = set(excluded_known_names or ()) | set(known)
    for cell_index, points in sorted(groups.items()):
        cell = cells[cell_index]
        names = {normalized_name(point['name']) for point in points}
        for point in points:
            key = normalized_name(point['name'])
            if key in known:
                reference = known[key]
                if not reference.covers(point['geometry']):
                    benchmark_exclusions.append({'city': city, 'pointId': point['id'], 'name': point['name'],
                                                 'reason': 'known_name_geometry_mismatch'})
                else:
                    intersection = cell.intersection(reference).area
                    union_area = cell.union(reference).area
                    benchmarks.append({'city': city, 'stratum': 'Budapest' if city == 'Budapest' else 'outside_Budapest',
                        'pointId': point['id'], 'name': point['name'], 'cellIndex': cell_index,
                        'iou': intersection / union_area if union_area else 0,
                        'cellAreaM2': cell.area, 'knownQuarterAreaM2': reference.area,
                        'cellToKnownAreaRatio': cell.area / reference.area,
                        'sharedDistinctNameCount': len(names)})
        for point in points:
            key = normalized_name(point['name'])
            reason = ('shared_cell_multiple_names' if len(names) > 1 else
                      'known_polygon_available' if key in excluded_known_names else
                      'no_meaningful_municipal_split' if not meaningful_split else
                      'cell_is_almost_whole_municipality' if cell.area / parent_area >= MAXIMUM_PARENT_AREA_FRACTION else None)
            if reason:
                unresolved.append({'id': point['id'], 'name': point['name'], 'reason': reason,
                                   'cellIndex': cell_index, 'sharedNames': sorted({item['name'] for item in points})})
        if len(names) == 1 and next(iter(names)) not in excluded_known_names and meaningful_split and cell.area / parent_area < MAXIMUM_PARENT_AREA_FRACTION:
            candidates.append({'cellIndex': cell_index, 'points': points})
    return candidates, unresolved, benchmarks, benchmark_exclusions


def benchmark_summary(records):
    def summary(items):
        return {'count': len(items), 'medianIoU': statistics.median(item['iou'] for item in items) if items else None,
                'medianCellToKnownAreaRatio': statistics.median(item['cellToKnownAreaRatio'] for item in items) if items else None,
                'tinyCellFraction': sum(item['cellToKnownAreaRatio'] < TINY_CELL_AREA_RATIO for item in items) / len(items) if items else None,
                'sharedCellFraction': sum(item['sharedDistinctNameCount'] > 1 for item in items) / len(items) if items else None}
    overall = summary(records)
    strata = {key: summary([record for record in records if record['stratum'] == key])
              for key in ('Budapest', 'outside_Budapest')}
    failures = []
    for label, item in [('overall', overall), *strata.items()]:
        if not item['count']:
            failures.append(label + ':no_benchmark_pairs')
        elif item['medianIoU'] < QA_MINIMUM_MEDIAN_IOU:
            failures.append(label + ':median_iou_below_0.5')
        if item['count'] and item['tinyCellFraction'] > 0.5:
            failures.append(label + ':mostly_tiny_cells')
    return {'overall': overall, 'strata': strata, 'methodQaPassed': not failures, 'failures': failures,
            'thresholds': {'minimumMedianIoU': QA_MINIMUM_MEDIAN_IOU,
                           'tinyCellToKnownAreaRatio': TINY_CELL_AREA_RATIO, 'maximumTinyCellFraction': 0.5},
            'interpretation': 'QA thresholds test fit to actual mapped quarter extents; they are not probabilities or legal validation.'}


def is_known_quarter(feature):
    properties = feature.get('properties', {})
    tags = properties.get('source', {}).get('tags', {})
    if properties.get('boundaryKind') == 'district':
        return False
    return tags.get('place') in ('suburb', 'quarter', 'neighbourhood') or (
        tags.get('boundary') == 'administrative' and tags.get('admin_level') in ('10', '11'))


def run(country_directory, barrier_directory, output, cities, known_catalog=None):
    if output.exists():
        raise FileExistsError(f'Output directory already exists: {output}')
    if not 1 <= len(cities) <= 3 or len(set(cities)) != len(cities):
        raise ValueError('This prototype is limited to one to three distinct municipalities')
    country_manifest = read_json(country_directory / 'manifest.json')
    barrier_manifest = read_json(barrier_directory / 'manifest.json')
    pbf_sha = country_manifest['input']['sha256']
    if pbf_sha != barrier_manifest['input']['sha256']:
        raise ValueError('Municipality/point and barrier sources use different PBF snapshots')
    parents_document, parent_pin = pinned_output(country_directory, country_manifest, 'municipalities.geojson')
    point_document, point_pin = pinned_output(country_directory, country_manifest, 'named-nodes.geojson')
    known_document, known_pin = pinned_output(country_directory, country_manifest, 'polygons.geojson')
    parents = {}
    for feature in parents_document['features']:
        properties = feature['properties']
        if properties.get('usedForAssociation') is True and properties.get('name') in cities:
            if properties['name'] in parents:
                raise ValueError('Selected source municipality is not unique: ' + properties['name'])
            parents[properties['name']] = feature
    if set(parents) != set(cities):
        raise ValueError('Missing selected association municipality: ' + ', '.join(set(cities) - set(parents)))
    forward = Transformer.from_crs('EPSG:4326', PROJECTED_CRS, always_xy=True).transform
    backward = Transformer.from_crs(PROJECTED_CRS, 'EPSG:4326', always_xy=True).transform
    geographic_parents = [shape(parents[city]['geometry']) for city in cities]
    parent_index = STRtree(geographic_parents)
    city_barriers = {city: [] for city in cities}
    line_entry = next(entry for entry in barrier_manifest['outputs'] if entry['file'] == 'barriers.ndjson')
    line_path = barrier_directory / 'barriers.ndjson'
    if line_path.stat().st_size != line_entry['bytes'] or digest_file(line_path) != line_entry['sha256']:
        raise ValueError('Barrier source fingerprint mismatch')
    with line_path.open(encoding='utf-8') as stream:
        for line in stream:
            feature = json.loads(line)
            coordinates = feature['geometry']['coordinates']
            xs, ys = zip(*coordinates)
            indexes = parent_index.query(box(min(xs), min(ys), max(xs), max(ys)))
            if not len(indexes):
                continue
            geometry = shape(feature['geometry'])
            projected = None
            for index in indexes:
                if geographic_parents[int(index)].intersects(geometry):
                    if projected is None:
                        projected = transform(forward, geometry)
                    city_barriers[cities[int(index)]].append({'id': feature['id'], 'geometry': projected})
    excluded_known_names = defaultdict(set)
    known_catalog_pin = None
    if known_catalog and known_catalog.exists():
        catalog_document = read_json(known_catalog)
        known_catalog_pin = {'path': str(known_catalog), 'sha256': digest_file(known_catalog)}
        for feature in catalog_document['features']:
            properties = feature.get('properties', {})
            if properties.get('municipality') in cities and properties.get('boundaryKind') != 'district' and not properties.get('estimated'):
                excluded_known_names[properties['municipality']].add(normalized_name(properties.get('name')))
    cell_features, candidate_features, unresolved, benchmarks, benchmark_exclusions, city_summaries = [], [], [], [], [], []
    for city in cities:
        parent_feature = parents[city]
        geographic_parent = shape(parent_feature['geometry'])
        parent = transform(forward, geographic_parent)
        cells, clipped, city_summary = physical_cells(parent, city_barriers[city])
        points = []
        for feature in point_document['features']:
            properties = feature['properties']
            if properties.get('municipality') == city:
                points.append({'id': feature['id'], 'name': properties['name'],
                    'geometry': transform(forward, shape(feature['geometry'])), 'source': properties['source']})
        grouped_known = defaultdict(list)
        for feature in known_document['features']:
            properties = feature.get('properties', {})
            if properties.get('municipality') == city and is_known_quarter(feature):
                geometry = transform(forward, shape(feature['geometry']))
                if geometry.is_valid and not geometry.is_empty:
                    grouped_known[normalized_name(properties['name'])].append(geometry)
        known = {key: unary_union(geometries) for key, geometries in grouped_known.items()}
        groups, point_failures = assign_points(cells, points)
        candidates, assignment_failures, city_benchmarks, city_benchmark_exclusions = analyse_assignments(
            city, cells, groups, known, parent.area, excluded_known_names[city], city_summary['hasMeaningfulSplit'])
        unresolved.extend({'city': city, **record} for record in point_failures + assignment_failures)
        benchmarks.extend(city_benchmarks)
        benchmark_exclusions.extend(city_benchmark_exclusions)
        barrier_shapes = [record['geometry'] for record in clipped]
        barrier_index = STRtree(barrier_shapes)
        feature_by_index = {}
        for index, cell in enumerate(cells):
            border_ids = sorted({clipped[int(item)]['id'] for item in barrier_index.query(cell.boundary)
                                 if cell.boundary.intersection(barrier_shapes[int(item)]).length > 1e-7})
            geographic = transform(backward, cell).intersection(geographic_parent)
            # Do not reproject a nearly collinear numerical residue polygon:
            # projection curvature can turn its zero-area geographic chords
            # into a spurious metric triangle. Scale its geographic area for
            # this containment diagnostic; all benchmark areas remain metric.
            outside_area = geographic.difference(geographic_parent).area * parent.area / geographic_parent.area
            if geographic.is_empty or not geographic.is_valid or geographic.geom_type not in ('Polygon', 'MultiPolygon'):
                unresolved.append({'city': city, 'cellIndex': index, 'reason': 'nonexportable_inverse_projection_cell',
                                   'metricCellAreaM2': cell.area, 'geometryType': geographic.geom_type})
                continue
            if outside_area > max(1e-8, parent.area * 1e-12):
                raise ValueError(f'Inverse projected cell has {outside_area:.9g} m² outside its source municipality: {city}/{index}')
            properties = {'id': f'physical-cell:{city}:{index}', 'municipality': city,
                'estimated': True, 'method': 'physical_barrier_cell', 'confidence': 'low',
                'reviewStatus': 'research_only', 'entityKind': 'physical_map_cell',
                'isVerifiedQuarterBoundary': False, 'isLegalBoundary': False, 'usableForAddressAssignment': False,
                'areaM2': cell.area, 'parentAreaFraction': cell.area / parent.area,
                'numericalOutsideParentAreaM2': outside_area,
                'sourceLabels': [{'id': point['id'], 'name': point['name']} for point in groups.get(index, [])],
                'sharedDistinctNameCount': len({normalized_name(point['name']) for point in groups.get(index, [])}),
                'sources': {'pbfSha256': pbf_sha, 'parentOsmId': parent_feature['id'],
                    'parentGeometrySha256': geometry_hash(geographic_parent), 'parentFile': parent_pin,
                    'barrierOsmIds': border_ids, 'barrierFile': {'path': str(line_path), 'sha256': line_entry['sha256']},
                    'pointIds': [point['id'] for point in groups.get(index, [])], 'pointFile': point_pin},
                'geometryProcessing': 'WGS84 source vertices projected to EPSG:32634; source-line intersections noded and polygonized inside the source parent; inverse projection clipped to the actual parent. No snapping, buffers, line extension or invented closing edges.'}
            feature = {'type': 'Feature', 'id': properties['id'], 'properties': properties, 'geometry': mapping(geographic)}
            cell_features.append(feature)
            feature_by_index[index] = feature
        for candidate in candidates:
            if candidate['cellIndex'] not in feature_by_index:
                continue
            original = feature_by_index[candidate['cellIndex']]
            candidate_features.append({**original, 'properties': {**original['properties'],
                'researchLabel': candidate['points'][0]['name'], 'labelDoesNotEstablishQuarterExtent': True}})
        city_summaries.append({'city': city, **city_summary, 'sourceBarrierWays': len(city_barriers[city]),
            'sourcePoints': len(points), 'knownQuarterNames': len(known), 'researchCandidateCells': len(candidates),
            'exportedPhysicalCells': len(feature_by_index),
            'unresolvedPoints': len(point_failures) + len(assignment_failures), 'benchmarkPairs': len(city_benchmarks)})
    qa = benchmark_summary(benchmarks)
    for feature in candidate_features:
        feature['properties']['methodQaPassed'] = qa['methodQaPassed']
        feature['properties']['quarantinedFromQuarterEstimation'] = not qa['methodQaPassed']
    output.mkdir(parents=True)
    documents = {
        'physical-map-cells.geojson': {'type': 'FeatureCollection', 'features': cell_features},
        'point-cell-research.geojson': {'type': 'FeatureCollection', 'features': candidate_features},
        'unresolved.json': {'countsByReason': dict(Counter(item['reason'] for item in unresolved)), 'records': unresolved},
        'benchmark.json': {'summary': qa, 'pairs': benchmarks, 'excludedPairs': benchmark_exclusions,
            'referenceMeaning': 'Same-PBF actual mapped quarter polygons, selected by matching actual point names and point containment. These are a geometric fit reference, not official legal ground truth.'}}
    outputs = []
    for filename, document in documents.items():
        path = output / filename
        path.write_text(json.dumps(document, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')
        outputs.append({'file': filename, 'bytes': path.stat().st_size, 'sha256': digest_file(path)})
    manifest = {'version': 1, 'generatedAt': datetime.now(timezone.utc).isoformat(),
        'scope': 'Local three-municipality physical-map-cell prototype; no quarter boundary publication',
        'cities': city_summaries, 'method': 'physical_barrier_cell', 'researchOnly': True,
        'quarterBoundaryPublicationAllowed': False, 'methodQa': qa,
        'inputs': {'pbfSha256': pbf_sha, 'countryManifestSha256': digest_file(country_directory / 'manifest.json'),
                   'barrierManifestSha256': digest_file(barrier_directory / 'manifest.json'), 'knownPolygons': known_pin,
                   'knownCatalog': known_catalog_pin},
        'projection': PROJECTED_CRS, 'dependencies': {key: version(key) for key in ('shapely', 'pyproj')},
        'outputs': outputs, 'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
        'notes': ['A cell containing one label does not establish the quarter extent.',
                  'Known mapped quarter names are excluded from candidate research after the independent benchmark.',
                  'Shared cells, boundary points, and almost-whole-municipality cells remain unresolved.',
                  'QA thresholds test geometric fit and are not confidence probabilities. No verified catalogue is changed.']}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'cities': city_summaries, 'methodQa': qa}, ensure_ascii=False))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--country-source', type=Path, default=ROOT / '.local/neighborhoods/country-associated')
    parser.add_argument('--barriers', type=Path, default=ROOT / '.local/neighborhoods/country-barriers')
    parser.add_argument('--known-catalog', type=Path, default=ROOT / 'data/neighborhoods/neighborhoods.geojson')
    parser.add_argument('--cities', nargs='+', default=list(DEFAULT_CITIES))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.country_source, args.barriers, args.output, args.cities, args.known_catalog)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Physical-cell prototype failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
