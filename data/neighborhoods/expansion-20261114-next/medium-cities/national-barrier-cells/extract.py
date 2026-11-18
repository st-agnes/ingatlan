#!/usr/bin/env python3
"""Split dense archived source footprints using actual mapped major barriers.

One offline PBF way pass, then bounded source-line polygonization. No inferred
straight connections, snapping, buffers, circles, Voronoi or hull operations.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip, hashlib, json, math, os, sys, tempfile, time, unicodedata
from pathlib import Path

import osmium
from pyproj import Transformer
from shapely import from_wkb
from shapely.geometry import mapping, shape
from shapely.ops import polygonize, transform, unary_union
from shapely.strtree import STRtree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
DATA = ROOT/'data/neighborhoods'
SURFACES = HERE.parent/'national-surfaces'
PBF = Path(os.environ.get('OTTHONRA_NEIGHBORHOOD_PBF', '/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf'))
ROAD_KINDS = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
              'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'unclassified'}


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value).casefold() if not unicodedata.combining(c))


def encode(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n').encode()


def write(name, value):
    (HERE/name).write_bytes(encode(value))


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())


def main():
    start = time.monotonic()
    saved = '--saved-sources' in sys.argv
    manifest = load(DATA/'sources/country-osm/manifest.json')
    pbf_sha = manifest['input']['sha256'] if saved else hashlib.file_digest(PBF.open('rb'), 'sha256').hexdigest()
    assert pbf_sha == manifest['input']['sha256']
    dense = load(SURFACES/'dense-context-features.geojson')['features']
    raw = {f['id']: f for f in load(SURFACES/'raw-source-areas.geojson')['features']}
    nodes = [f for f in load(DATA/'sources/country-osm/named-nodes.geojson.gz')['features']
             if f['properties'].get('municipality') and f['properties'].get('place') in {'quarter', 'suburb', 'neighbourhood'}]
    frozen = HERE/'baseline-known-keys.json'
    if frozen.exists():
        known = {tuple(key) for key in load(frozen)['keys']}
    else:
        paths = [DATA/'search-areas.geojson']
        paths += [ROOT/row['path'] for row in load(DATA/'expansion-20261114/input-registry.json')['datasets']]
        paths += [SURFACES/name for name in ['source-own-name-features.geojson', 'single-label-features.geojson', 'bounded-multi-label-features.geojson']]
        known = set()
        for path in paths:
            for feature in load(path)['features']:
                p = feature['properties']
                if p.get('municipality') and p.get('name'):
                    for name in [p['name']] + p.get('aliases', []):
                        known.add((p['municipality'], norm(name)))
        for row in load(DATA/'expansion-20261114/name-aliases.json')['aliases']:
            keys = [(row['municipality'], norm(name)) for name in [row['name']] + row['aliases']]
            if any(key in known for key in keys):
                known.update(keys)
        write(frozen.name, {'keys': sorted([list(key) for key in known]),
            'inputPaths': [str(path.relative_to(ROOT)) for path in paths]})
    target_features = [f for f in dense if (f['properties']['municipality'], norm(f['properties']['name'])) not in known]
    target_keys = {(f['properties']['municipality'], norm(f['properties']['name'])) for f in target_features}
    context_targets = defaultdict(set)
    for f in target_features:
        context_targets[f['properties']['sourceAreaId']].add((f['properties']['municipality'], norm(f['properties']['name'])))
    contexts = [raw[ident] for ident in sorted(context_targets)]
    context_shapes = [shape(f['geometry']) for f in contexts]
    context_index = STRtree(context_shapes)
    all_context_ids = {f['properties']['sourceAreaId'] for f in dense}
    write('source-contexts.geojson', {'type': 'FeatureCollection', 'features': [raw[ident] for ident in sorted(all_context_ids)]})
    write('source-labels.geojson', {'type': 'FeatureCollection', 'features': nodes})
    write('target-selection.json', {'schemaVersion': 1, 'targets': [{'municipality': city, 'nameKey': name} for city, name in sorted(target_keys)],
        'denseContextInputPath': str((SURFACES/'dense-context-features.geojson').relative_to(ROOT)),
        'denseInputFeatures': len(dense), 'missingTargetCount': len(target_keys), 'activeSourceContexts': len(contexts)})
    print(json.dumps({'phase': 'extracting_actual_major_barriers', 'missingTargets': len(target_keys),
        'activeSourceContexts': len(contexts), 'elapsedSeconds': round(time.monotonic()-start, 1)}), flush=True)
    barriers, extraction_stats = [], Counter()
    factory = osmium.geom.WKBFactory()

    class Handler(osmium.SimpleHandler):
        def way(self, obj):
            tags = dict(obj.tags)
            if not (tags.get('highway') in ROAD_KINDS or tags.get('railway') in {'rail', 'light_rail', 'narrow_gauge'}
                    or tags.get('waterway') in {'river', 'stream', 'canal'}):
                return
            extraction_stats['eligibleSourceWaysExamined'] += 1
            try:
                line = from_wkb(bytes.fromhex(factory.create_linestring(obj)))
                if line.is_empty or not line.is_valid:
                    return
                hits = [int(i) for i in context_index.query(line, predicate='intersects')]
                if not hits:
                    return
                barriers.append({'type': 'Feature', 'id': 'osm:way:'+str(obj.id), 'geometry': mapping(line),
                    'properties': {'name': tags.get('name'), 'sourceContextIds': [contexts[i]['id'] for i in hits],
                        'source': {'provider': 'openstreetmap', 'osmType': 'way', 'osmId': obj.id,
                            'url': 'https://www.openstreetmap.org/way/'+str(obj.id), 'tags': tags,
                            'objectVersion': obj.version, 'objectTimestamp': str(obj.timestamp),
                            'pbfSha256': pbf_sha, 'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors'}}})
            except (RuntimeError, ValueError):
                extraction_stats['failedSourceWayAssembly'] += 1

    if saved:
        barriers = load(HERE/'source-barriers.geojson')['features']
    elif contexts:
        with tempfile.TemporaryDirectory(prefix='national-barrier-cells-') as temporary:
            Handler().apply_file(str(PBF), locations=True,
                idx='sparse_file_array,'+str(Path(temporary)/'nodes.idx'),
                filters=[osmium.filter.KeyFilter('highway', 'railway', 'waterway')])
        write('source-barriers.geojson', {'type': 'FeatureCollection', 'features': barriers})
    else:
        write('source-barriers.geojson', {'type': 'FeatureCollection', 'features': []})
    print(json.dumps({'phase': 'polygonizing_closed_source_cells', 'barrierWays': len(barriers),
        'elapsedSeconds': round(time.monotonic()-start, 1)}), flush=True)
    forward = Transformer.from_crs(4326, 23700, always_xy=True).transform
    inverse = Transformer.from_crs(23700, 4326, always_xy=True).transform
    projected_points = [transform(forward, shape(f['geometry'])) for f in nodes]
    point_index = STRtree(projected_points)
    road_map = defaultdict(list)
    for f in barriers:
        for ident in f['properties']['sourceContextIds']:
            road_map[ident].append(f)
    context_stats, rejected, candidates, all_cells = [], [], [], []
    for ci, context in enumerate(contexts):
        ident = context['id']
        parent = transform(forward, shape(context['geometry']))
        local = road_map[ident]
        lines = [transform(forward, shape(f['geometry'])).intersection(parent) for f in local]
        nonempty = [(f, line) for f, line in zip(local, lines) if not line.is_empty]
        local, lines = [x[0] for x in nonempty], [x[1] for x in nonempty]
        line_index = STRtree(lines)
        cells = list(polygonize(unary_union([parent.boundary]+lines)))
        counts = Counter()
        for cell_index, cell in enumerate(cells):
            if not parent.covers(cell.representative_point()):
                continue
            hits = [int(i) for i in point_index.query(cell, predicate='covers')]
            missing = {(nodes[i]['properties']['municipality'], norm(nodes[i]['properties']['name']))
                       for i in hits if (nodes[i]['properties']['municipality'], norm(nodes[i]['properties']['name'])) not in known}
            targets = missing.intersection(context_targets[ident])
            if not targets:
                counts['noMissingTarget'] += 1
                continue
            labels = [{'id': nodes[i]['id'], 'name': nodes[i]['properties']['name'],
                'municipality': nodes[i]['properties']['municipality'],
                'alreadyCovered': (nodes[i]['properties']['municipality'], norm(nodes[i]['properties']['name'])) in known} for i in hits]
            reason = None
            if len(missing) != 1:
                reason = 'multiple_still_missing_source_place_names'
            elif not cell.is_valid:
                reason = 'invalid_original_polygonized_cell'
            key = next(iter(targets))
            label = next(nodes[i] for i in hits if (nodes[i]['properties']['municipality'], norm(nodes[i]['properties']['name'])) == key)
            name = label['properties']['name']
            lower = fold(name)
            minimum = 5000 if 'lakopark' in lower else (10000 if 'lakotelep' in lower else 20000)
            cap = 250000 if 'lakopark' in lower else (750000 if 'lakotelep' in lower else 4000000)
            if reason is None and not minimum <= cell.area <= cap:
                reason = 'outside_coarse_area_bounds'
            if reason is None and cell.area >= parent.area*0.9:
                reason = 'not_meaningfully_smaller_than_shared_source_surface'
            bound_ways = []
            if reason is None:
                for index in line_index.query(cell.boundary):
                    index = int(index)
                    overlap = cell.boundary.intersection(lines[index]).length
                    if overlap > 10:
                        f = local[index]
                        bound_ways.append({'id': f['id'], 'name': f['properties']['name'],
                            'url': f['properties']['source']['url'], 'boundaryOverlapMetres': round(overlap, 1)})
                if not bound_ways:
                    reason = 'no_actual_major_barrier_bounds_cell'
            record = {'sourceContextId': ident, 'cellIndex': cell_index, 'municipality': key[0], 'name': name,
                'areaSquareMetres': round(cell.area, 1), 'sourceContextAreaSquareMetres': round(parent.area, 1),
                'coarseAreaMinimumSquareMetres': minimum, 'coarseAreaCapSquareMetres': cap,
                'containedSourceLabels': labels, 'missingNameCount': len(missing), 'rejectionReason': reason}
            if reason:
                rejected.append(record)
                counts[reason] += 1
                continue
            geo = transform(inverse, cell)
            if not geo.is_valid:
                rejected.append({**record, 'rejectionReason': 'invalid_reprojected_cell'})
                counts['invalid_reprojected_cell'] += 1
                continue
            source = {'provider': 'osm-physical-map-cell-inference', 'pbfSha256': pbf_sha,
                'sourceContextPath': str((HERE/'source-contexts.geojson').relative_to(ROOT)),
                'barrierSourcePath': str((HERE/'source-barriers.geojson').relative_to(ROOT)),
                'sourceContextUrl': context['properties']['source']['url'],
                'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors'}
            feature = {'type': 'Feature', 'id': 'dense-source-cell:'+hashlib.sha256(encode([ident, cell_index, key])).hexdigest()[:24],
                'geometry': mapping(geo), 'properties': {**record, 'method': 'physical_barrier_cell_estimate',
                    'estimated': True, 'semanticFootprint': True, 'qualityScore': 15, 'pointRadiusFallback': False,
                    'candidateBoundaryKind': 'neighbourhood', 'source': source, 'boundingSourceWays': bound_ways,
                    'namePoint': {'id': label['id'], 'coordinates': label['geometry']['coordinates'], 'sourceUrl': label['properties']['source']['url']},
                    'approximationNote': 'Actual major roads, railways and river/stream/canal linework polygonized with an archived source residential surface. The smaller closed cell contains exactly one still-missing named place; already-covered parent labels may coexist. Low-confidence source-informed search extent, not a mapped whole-quarter boundary. No circle, Voronoi, hull, snapping or invented straight divider.'}}
            candidates.append(feature)
            counts['qualifiedMissingSingleNameCell'] += 1
        context_stats.append({'id': ident, 'sourceTargets': len(context_targets[ident]), 'barrierWays': len(local),
            'polygonizedCells': len(cells), 'counts': dict(counts)})
        if (ci+1) % 20 == 0:
            print(json.dumps({'contextsCompleted': ci+1, 'candidateCells': len(candidates), 'elapsedSeconds': round(time.monotonic()-start, 1)}), flush=True)
    # Use the largest bounded cell for each name, then spread the max200 budget
    # over municipalities rather than filling it from one city.
    best = {}
    for f in sorted(candidates, key=lambda f: (-f['properties']['areaSquareMetres'], f['id'])):
        p = f['properties']
        best.setdefault((p['municipality'], norm(p['name'])), f)
    by_city = defaultdict(list)
    for f in best.values():
        by_city[f['properties']['municipality']].append(f)
    for city in by_city:
        by_city[city].sort(key=lambda f: (-f['properties']['areaSquareMetres'], f['properties']['name']))
    selected = []
    while any(by_city.values()) and len(selected) < 200:
        for city in sorted(by_city):
            if by_city[city]:
                selected.append(by_city[city].pop(0))
            if len(selected) >= 200:
                break
    selected.sort(key=lambda f: (f['properties']['municipality'], f['properties']['name']))
    write('all-candidate-cells.geojson', {'type': 'FeatureCollection', 'features': candidates})
    write('features.geojson', {'type': 'FeatureCollection', 'features': selected})
    write('skipped-contexts-and-cells.json', {'schemaVersion': 1, 'sourceContexts': context_stats,
        'targetCellRejections': rejected, 'unchangedAllDenseSourceContextsPath': str((HERE/'source-contexts.geojson').relative_to(ROOT)),
        'denseTargetsAlreadyCoveredCount': len(dense)-len(target_features)})
    summary = {'schemaVersion': 1, 'featureCount': len(selected), 'candidateCellCount': len(candidates),
        'municipalityCount': len({f['properties']['municipality'] for f in selected}),
        'municipalities': dict(sorted(Counter(f['properties']['municipality'] for f in selected).items())),
        'sourceContextCount': len(all_context_ids), 'activeSourceContextCount': len(contexts), 'sourceBarrierWays': len(barriers),
        'missingTargetCount': len(target_keys), 'method': 'physical_barrier_cell_estimate',
        'circlesGenerated': 0, 'voronoiGenerated': 0, 'inventedDividers': 0, 'pbfPassCount': 0 if saved else 1,
        'extractionStats': dict(extraction_stats), 'elapsedSeconds': round(time.monotonic()-start, 2),
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'featuresSha256': hashlib.sha256((HERE/'features.geojson').read_bytes()).hexdigest(),
        'geographicAccuracyReviewed': False}
    write('summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
