#!/usr/bin/env python3
"""Re-read exact names from the pinned local OSM PBF; never use them as controls."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile
import unicodedata

import osmium
from shapely import from_wkb
from shapely.geometry import Point, LineString, shape, mapping

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PBF = ROOT / '.local/neighborhoods/hungary-latest.osm.pbf'
EXPECTED_PBF_SHA = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
FROZEN = ROOT / 'data/neighborhoods/sources/municipal-local-map-next'
NAMES = ['Iparterület', 'Zalabesenyő', 'Botfa', 'Bazita', 'Ebergény', 'Szenterzsébethegy']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower()) if c.isalnum())


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def build():
    if sha(PBF) != EXPECTED_PBF_SHA:
        raise ValueError('Pinned local PBF changed')
    municipality = shape(json.loads((FROZEN / 'zalaegerszeg-calibration-municipality.geojson').read_text())['geometry'])
    # This coarse selection box is only a search filter, never a geometry or cap.
    # Full original coordinates are retained; city containment is reported below.
    search_bounds = [16.72, 46.74, 16.99, 46.94]
    names = {norm(name): name for name in NAMES}
    counts = Counter()
    objects = {}
    geometries = {}
    errors = []
    factory = osmium.geom.WKBFactory()
    with osmium.io.Reader(str(PBF), osmium.osm.osm_entity_bits.NOTHING) as reader:
        snapshot = reader.header().get('osmosis_replication_timestamp')

    def selected(obj):
        name = obj.tags.get('name', '')
        return names.get(norm(name))

    def near(g):
        a, b, c, d = g.bounds
        x0, y0, x1, y1 = search_bounds
        return c >= x0 and a <= x1 and d >= y0 and b <= y1

    def record(obj, kind):
        ident = f'osm:{kind}:{obj.id}'
        objects[ident] = {
            'id': ident, 'requestedName': selected(obj), 'name': obj.tags.get('name'),
            'osmType': kind, 'osmId': obj.id, 'objectVersion': obj.version,
            'objectTimestamp': str(obj.timestamp), 'tags': dict(obj.tags),
            'sourceUrl': f'https://www.openstreetmap.org/{kind}/{obj.id}',
        }
        return ident

    class Collector(osmium.SimpleHandler):
        def node(self, obj):
            counts['nativeFilteredNodes'] += 1
            if not selected(obj):
                return
            counts['exactNameNodesCountrywide'] += 1
            if obj.location.valid():
                g = Point(obj.location.lon, obj.location.lat)
                if near(g):
                    geometries[record(obj, 'node')] = g

        def way(self, obj):
            counts['nativeFilteredWays'] += 1
            if not selected(obj):
                return
            counts['exactNameWaysCountrywide'] += 1
            if not all(n.location.valid() for n in obj.nodes):
                errors.append({'id': f'osm:way:{obj.id}', 'reason': 'missing_original_node_location'})
                return
            g = LineString([(n.lon, n.lat) for n in obj.nodes])
            if near(g):
                ident = record(obj, 'way')
                objects[ident]['nodeRefs'] = [n.ref for n in obj.nodes]
                geometries.setdefault(ident, g)

        def relation(self, obj):
            counts['nativeFilteredRelations'] += 1
            if selected(obj):
                counts['exactNameRelationsCountrywide'] += 1
                # Keep original metadata if its assembled area is in the city filter.
                ident = record(obj, 'relation')
                objects[ident]['members'] = [{'type': m.type, 'ref': m.ref, 'role': m.role} for m in obj.members]

        def area(self, obj):
            if not selected(obj):
                return
            counts['exactNameAssembledAreasCountrywide'] += 1
            kind = 'way' if obj.from_way() else 'relation'
            ident = f'osm:{kind}:{obj.orig_id()}'
            try:
                g = from_wkb(bytes.fromhex(factory.create_multipolygon(obj)))
                if g.is_empty or not g.is_valid:
                    raise ValueError('invalid_original_area')
                if near(g):
                    geometries[ident] = g
                    # Original way/relation callbacks supply authoritative metadata.
            except (RuntimeError, ValueError) as error:
                errors.append({'id': ident, 'reason': str(error)[:120]})

    with tempfile.TemporaryDirectory(prefix='zala-name-index-') as temp:
        Collector().apply_file(str(PBF), locations=True,
            idx='sparse_file_array,' + str(Path(temp) / 'nodes.idx'),
            filters=[osmium.filter.KeyFilter('name')])
    features = []
    for ident, g in sorted(geometries.items()):
        if ident not in objects:
            raise ValueError('Assembled geometry has no original object metadata: ' + ident)
        record = objects[ident]
        tags = record['tags']
        record['nameRole'] = ('named_place' if tags.get('place') in {'suburb', 'quarter', 'neighbourhood', 'hamlet', 'village', 'locality'}
                              else 'named_landuse' if tags.get('landuse') else 'other_named_object')
        record['insideOrIntersectsArchivedCurrentMunicipality'] = municipality.intersects(g)
        record['usedForGeoreferencing'] = False
        record['establishesHistoricalContour'] = False
        features.append({'type': 'Feature', 'id': ident, 'properties': record, 'geometry': mapping(g)})
    per_name = []
    for name in NAMES:
        matches = [f for f in features if f['properties']['requestedName'] == name]
        supporting = [f for f in matches if f['properties']['nameRole'] == 'named_place' and f['properties']['insideOrIntersectsArchivedCurrentMunicipality']]
        per_name.append({'name': name, 'exactNamedPlaceObservedInCity': bool(supporting),
                         'status': 'same_city_exact_osm_name_observed' if supporting else 'not_independently_confirmed',
                         'evidenceIds': [f['id'] for f in matches], 'supportingPlaceIds': [f['id'] for f in supporting]})
    source = {'provider': 'OpenStreetMap', 'pbfPath': str(PBF.relative_to(ROOT)),
              'pbfSha256': EXPECTED_PBF_SHA, 'osmSnapshotTimestamp': snapshot,
              'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors'}
    evidence = {'schemaVersion': 1, 'source': source, 'networkUsed': False,
                'method': 'Exact normalized primary-name match from original local PBF nodes, complete ways and libosmium assembled areas; complete original geometry retained. Search bounds only select evidence.',
                'searchBoundsWgs84': search_bounds, 'counts': dict(sorted(counts.items())),
                'errors': errors, 'nameResults': per_name,
                'georeferenceControlCount': 0, 'establishesHistoricalContour': False,
                'allFeaturesAreEvidenceOnly': True,
                'evidenceGeojson': 'current-name-evidence.geojson'}
    return {'current-name-evidence.json': encode(evidence),
            'current-name-evidence.geojson': encode({'type': 'FeatureCollection', 'features': features})}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    outputs = build()
    for name, content in outputs.items():
        path = OUT / name
        if args.check:
            if path.read_text() != content:
                raise ValueError('Evidence differs: ' + name)
        else:
            path.write_text(content)
    print(json.dumps({'outputs': list(outputs), 'check': args.check}))
