#!/usr/bin/env python3
"""Read pinned Hungary PBF and retain complete local source ways/name points."""
import hashlib
import json
from pathlib import Path

import osmium

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PBF = ROOT / '.local/neighborhoods/hungary-latest.osm.pbf'
EXPECTED = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
BOUNDS = (19.70, 46.57, 20.03, 46.87)
RETAIN_NAMES = {'Dr. Holló Lajos utca', 'Bercsényi utca', 'Mikszáth Kálmán utca',
                'Árok utca', 'Kőrösi út', 'Kőrösi utca', 'Rét utca',
                'Tanyasori út', 'Alpári út', 'Róna utca', 'Délibáb utca',
                'Templomhalom utca'}
RETAIN_WAYS = {219429915, 210781090, 562896874, 562896875,
               538786403, 219429901, 1312804805, 211274699}
RETAIN_NODES = {1843236649, 1843235605, 1843237905, 2208340620, 2208340619,
                2212985376, 1843236018, 5914756408, 2139468150, 5914074516}
NAME_NODES = {1300486631, 1300486634, 1300486629, 10707051448, 1300505896}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inside(x, y):
    return BOUNDS[0] <= x <= BOUNDS[2] and BOUNDS[1] <= y <= BOUNDS[3]

assert digest(PBF) == EXPECTED
ways, names = [], []
processor = osmium.FileProcessor(str(PBF)).with_locations('flex_mem')
processor = processor.with_filter(osmium.filter.KeyFilter('highway', 'railway', 'place'))
for obj in processor:
    if obj.is_node():
        tags = dict(obj.tags)
        if tags.get('name') and tags.get('place') and obj.location.valid() and inside(obj.lon, obj.lat):
            names.append({'type': 'Feature', 'id': f'osm:node:{obj.id}',
                          'properties': {'name': tags['name'], 'place': tags['place'],
                                         'osmNodeId': obj.id, 'tags': tags,
                                         'objectVersion': obj.version,
                                         'objectTimestamp': str(obj.timestamp),
                                         'usedForFit': False},
                          'geometry': {'type': 'Point', 'coordinates': [obj.lon, obj.lat]}})
    elif obj.is_way():
        tags = dict(obj.tags)
        if not (tags.get('highway') or tags.get('railway')):
            continue
        if not all(n.location.valid() for n in obj.nodes):
            continue
        coords = [[n.lon, n.lat] for n in obj.nodes]
        if not any(inside(x, y) for x, y in coords):
            continue
        ways.append({'type': 'Feature', 'id': f'osm:way:{obj.id}',
                     'properties': {'osmWayId': obj.id, 'tags': tags,
                                    'nodeRefs': [n.ref for n in obj.nodes],
                                    'objectVersion': obj.version,
                                    'objectTimestamp': str(obj.timestamp)},
                     'geometry': {'type': 'LineString', 'coordinates': coords}})

raw_way_count, raw_name_count = len(ways), len(names)
# Retain bounded control/holdout evidence only. Complete source ways are preserved.
ways = [f for f in ways if f['properties']['tags'].get('name') in RETAIN_NAMES
        or f['properties']['osmWayId'] in RETAIN_WAYS
        or set(f['properties']['nodeRefs']) & RETAIN_NODES]
names = [f for f in names if f['properties']['osmNodeId'] in NAME_NODES]

def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

for filename, features in [('source-road-rail-reference.geojson', ways),
                           ('source-name-points.geojson', names)]:
    write(filename, {'type': 'FeatureCollection', 'sourcePbfSha256': EXPECTED,
                     'sourcePbfTimestamp': '2026-11-12T21:23:05Z',
                     'bboxUsedOnlyForSelection': list(BOUNDS),
                     'coordinatesClippedOrModified': False,
                     'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
                     'features': features})
write('reference-extraction-proof.json', {
    'schemaVersion': 1, 'sourcePbfPath': str(PBF.relative_to(ROOT)),
    'sourcePbfSha256': EXPECTED, 'sourcePbfBytes': PBF.stat().st_size,
    'osmTimestamp': '2026-11-12T21:23:05Z', 'completeWays': len(ways),
    'actualPlaceNamePoints': len(names), 'boundsSelectOnly': list(BOUNDS),
    'broadLocalWaysInspected': raw_way_count, 'broadLocalNamePointsInspected': raw_name_count,
    'retentionMeaning': 'Only actual control/holdout streets, road/rail context and five identity points; no way geometry clipping.',
    'coordinateClippingSnappingOrRepair': False, 'namePointsUsedForFit': False,
    'outputs': [{'path': name, 'sha256': digest(HERE / name)} for name in
                ['source-road-rail-reference.geojson', 'source-name-points.geojson']]})
print(json.dumps({'ways': len(ways), 'namePoints': len(names)}))
