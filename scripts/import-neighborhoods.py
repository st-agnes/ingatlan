#!/usr/bin/env python3
"""Package the pinned 4,308 search boundaries for the API and metadata for browsers.

Offline, standard-library-only generation. The gzip is a JSON array whose first
element is a small metadata catalogue, followed by individual boundary records.
The API can load that first element without retaining any polygon coordinates.
All geometry coordinates, polygon holes, multipart shapes and persistent IDs are
copied unchanged from the authoritative search-areas.geojson.gz snapshot.
"""
import argparse
import gzip
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/neighborhoods/search-areas.geojson.gz'
MUNICIPALITIES = ROOT / 'data/neighborhoods/sources/country-osm/municipalities.geojson.gz'
EXPECTED_COUNT = 4308
EXPECTED_SOURCE_SHA256 = '367af069d58c60e171d189e23673fe20fd5cef51792769c161c3eccb87321e4d'
EXPECTED_MUNICIPALITIES_SHA256 = 'fb5f1293628b9eeaabce243ae6ebc884f6bdc93443a2488e5fb213029bf766b7'
IDENTITY = re.compile(r'neighborhood:[0-9a-f]{24}\Z')
DEMO_AREAS = {
    ('Budapest', name) for name in ('Albertfalva', 'Belváros', 'Lágymányos', 'Marina part', 'Országút', 'Pasarét',
                                   'Rózsadomb', 'Szentimreváros', 'Vizafogó', 'Újlipótváros')
} | {('Debrecen', 'Vénkert'), ('Debrecen', 'Sestakert'), ('Nyíregyháza', 'Belváros')}


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def polygons(geometry):
    if geometry.get('type') == 'Polygon':
        return [geometry['coordinates']]
    if geometry.get('type') == 'MultiPolygon':
        return geometry['coordinates']
    raise ValueError('Only Polygon and MultiPolygon boundaries are supported.')


def ring_position(ring, x, y):
    """Return -1 outside, 0 on the boundary, 1 inside a linear ring."""
    inside = False
    for a, b in zip(ring, ring[1:]):
        cross = (x - a[0]) * (b[1] - a[1]) - (y - a[1]) * (b[0] - a[0])
        if abs(cross) <= 1e-12 and min(a[0], b[0]) - 1e-12 <= x <= max(a[0], b[0]) + 1e-12 and min(a[1], b[1]) - 1e-12 <= y <= max(a[1], b[1]) + 1e-12:
            return 0
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return 1 if inside else -1


def covers(geometry, longitude, latitude, boundary=True):
    """Fixture verification with MySQL ST_Intersects(point) boundary semantics."""
    for polygon in polygons(geometry):
        outer = ring_position(polygon[0], longitude, latitude)
        if outer == 0 and boundary:
            return True
        if outer != 1:
            continue
        holes = [ring_position(ring, longitude, latitude) for ring in polygon[1:]]
        if boundary and 0 in holes:
            return True
        if all(position == -1 for position in holes):
            return True
    return False


def validate_geometry(geometry):
    parts = polygons(geometry)
    if not parts:
        raise ValueError('Empty neighborhood boundary.')
    for polygon in parts:
        if not polygon:
            raise ValueError('Empty polygon.')
        for ring in polygon:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError('A polygon ring is not closed.')
            for coordinate in ring:
                if len(coordinate) != 2 or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in coordinate):
                    raise ValueError('A polygon coordinate is not a finite longitude/latitude pair.')
                if not (16 <= coordinate[0] <= 23 and 45 <= coordinate[1] <= 49):
                    raise ValueError('Coordinates must use Hungarian longitude,latitude order.')
            # Translate before summation: authoritative boundaries contain
            # legitimate tiny slivers whose unshifted shoelace sums cancel.
            x0, y0 = ring[0]
            if math.fsum((a[0] - x0) * (b[1] - y0) - (b[0] - x0) * (a[1] - y0) for a, b in zip(ring, ring[1:])) == 0:
                raise ValueError('Degenerate polygon ring.')


def representative_point(geometry):
    """Choose a deterministic interior point for explicitly fictional fixtures.

    A horizontal scanline considers outer and inner rings together, preserving
    holes. This is never used to infer a real property's address or coordinates.
    """
    for polygon in sorted(polygons(geometry), key=lambda part: len(part[0]), reverse=True):
        outer = polygon[0]
        ys = sorted(set(point[1] for point in outer))
        candidates = [(ys[0] + ys[-1]) / 2]
        candidates += [(ys[0] + (ys[-1] - ys[0]) * fraction) for fraction in (.25, .75, .125, .875)]
        candidates += [(a + b) / 2 for a, b in zip(ys, ys[1:])]
        for y in candidates:
            crossings = sorted(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                               for ring in polygon for a, b in zip(ring, ring[1:])
                               if (a[1] > y) != (b[1] > y))
            intervals = sorted(zip(crossings[::2], crossings[1::2]), key=lambda pair: pair[1] - pair[0], reverse=True)
            for left, right in intervals:
                x = (left + right) / 2
                if right > left and covers(geometry, x, y, boundary=False):
                    return [x, y]
    raise ValueError('No interior fixture point found for polygon.')


def test_city_points():
    """Canonical municipality interior points exclusively for synthetic fixtures."""
    content = MUNICIPALITIES.read_bytes()
    if hashlib.sha256(content).hexdigest() != EXPECTED_MUNICIPALITIES_SHA256:
        raise ValueError('The synthetic-point municipality source changed; review its pinned SHA-256.')
    known_cities = set(json.loads((ROOT / 'dist/data/settlements.json').read_text())['settlements'])
    selected = {}
    for feature in json.loads(gzip.decompress(content))['features']:
        city, geometry = feature['properties']['name'], feature['geometry']
        if city not in known_cities:
            continue
        # A few source relations repeat a city name. Prefer the larger actual
        # municipal footprint, preserving its original geometry for the point.
        area = 0
        for polygon in polygons(geometry):
            for index, ring in enumerate(polygon):
                x0, y0 = ring[0]
                part = abs(math.fsum((a[0] - x0) * (b[1] - y0) - (b[0] - x0) * (a[1] - y0) for a, b in zip(ring, ring[1:])))
                area += part if index == 0 else -part
        if city not in selected or area > selected[city][0]:
            selected[city] = (area, geometry)
    if set(selected) != known_cities:
        raise ValueError('The synthetic municipality points do not cover every canonical city.')
    return {city: representative_point(selected[city][1]) for city in sorted(selected)}


def build(source=SOURCE):
    source_bytes = source.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise ValueError('The authoritative neighborhood snapshot changed; review and pin its SHA-256 before regenerating.')
    document = json.loads(gzip.decompress(source_bytes))
    features = document['features']
    if len(features) != EXPECTED_COUNT or document.get('featureCount') != EXPECTED_COUNT:
        raise ValueError('The authoritative neighborhood count must be 4308.')
    if document.get('coordinateSystem') != 'EPSG:4326' or document.get('coordinateOrder') != 'longitude,latitude':
        raise ValueError('Unsupported source coordinate system or order.')
    areas, rows, browser, identities, keys = [], [], [], set(), set()
    for feature in features:
        p, geometry = feature['properties'], feature['geometry']
        identity = p['id']
        if not IDENTITY.fullmatch(identity) or identity != feature['id'] or identity in identities:
            raise ValueError('Invalid or duplicate persistent neighborhood ID.')
        identities.add(identity)
        key = (p['municipality'], p['canonicalNameKey'])
        if key in keys:
            raise ValueError('Duplicate municipality and canonical neighborhood name.')
        keys.add(key)
        validate_geometry(geometry)
        metadata = dict(id=identity, name=p['name'], city=p['municipality'], label=p['label'], aliases=p['aliases'], estimated=p['estimated'])
        browser.append(metadata)
        areas.append({**metadata, 'representativePoint': representative_point(geometry)})
        rows.append(dict(id=identity, canonicalNameKey=p['canonicalNameKey'], method=p['method'], geometrySha256=p['geometrySha256'], geometry=geometry))
    header = dict(schemaVersion=1, sourceSha256=source_sha256, featureCount=EXPECTED_COUNT,
                  coordinateSystem='EPSG:4326', coordinateOrder='longitude,latitude', areas=areas,
                  testMunicipalitySourceSha256=EXPECTED_MUNICIPALITIES_SHA256, testCityPoints=test_city_points())
    # The header occupies one line, so metadata-only readers need not parse the
    # following 4308 geometries. The complete document remains ordinary JSON.
    runtime = ('[\n' + packed(header) + ',\n' + ',\n'.join(map(packed, rows)) + '\n]\n').encode()
    module = ('// Generated by scripts/import-neighborhoods.py; metadata only, no boundaries.\n'
              '// OpenStreetMap contributors (ODbL-1.0) and cited municipal sources; see THIRD-PARTY-NOTICES.txt.\n'
              'export const neighborhoodDataset = Object.freeze(' + packed({k: header[k] for k in ('schemaVersion', 'sourceSha256', 'featureCount')}) + ');\n'
              'export const neighborhoods = Object.freeze(' + packed(browser)
              + '.map(area => Object.freeze({...area, aliases: Object.freeze(area.aliases)})));\n').encode()
    fixtures = []
    for area in areas:
        if (area['city'], area['name']) not in DEMO_AREAS:
            continue
        longitude, latitude = area['representativePoint']
        membership = sorted(feature['id'] for feature in features
                            if feature['bbox'][0] <= longitude <= feature['bbox'][2]
                            and feature['bbox'][1] <= latitude <= feature['bbox'][3]
                            and covers(feature['geometry'], longitude, latitude))
        if area['id'] not in membership:
            raise ValueError('A synthetic fixture point is outside its intended boundary.')
        fixtures.append(dict(id=area['id'], city=area['city'], name=area['name'], latitude=latitude, longitude=longitude,
                             membershipIds=membership, synthetic=True))
    if len(fixtures) != len(DEMO_AREAS):
        raise ValueError('An explicitly named synthetic demo boundary is missing.')
    demo_module = ('// Generated fictional demo/TEST points, never a real-address geocoding fallback.\n'
                   '// Membership was tested against all 4308 source boundaries, including overlaps and other municipalities.\n'
                   'export const neighborhoodDemoPoints = Object.freeze(' + packed(fixtures)
                   + '.map(point => Object.freeze({...point, membershipIds: Object.freeze(point.membershipIds)})));\n').encode()
    return {'dist/data/neighborhoods.json.gz': gzip.compress(runtime, mtime=0), 'dist/neighborhoods-data.js': module,
            'dist/neighborhood-demo-points.js': demo_module}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify generated files offline without writing.')
    args = parser.parse_args()
    for relative, content in build().items():
        target = ROOT / relative
        if args.check:
            actual = target.read_bytes()
            if relative.endswith('.gz'):
                actual, content = gzip.decompress(actual), gzip.decompress(content)
            if actual != content:
                raise SystemExit('Stale neighborhood runtime export: ' + relative)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    print(f'Verified {EXPECTED_COUNT} stable neighborhood IDs, full boundaries and metadata-only browser catalogue.')


if __name__ == '__main__':
    main()
