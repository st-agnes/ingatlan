#!/usr/bin/env python3
"""Build lazy, public, display-only neighborhood map layers from pinned sources.

The existing MySQL/search geometry is never rewritten. Native GEOS performs
topology-preserving simplification for screen rendering; every polygon part and
hole is retained. Requires libgeos_c (Ubuntu: libgeos-c1t64), no Python packages or
network requests. The manifest has bounds only; actual layers are separate,
content-addressed municipality files loaded as the viewport reaches a city.
"""
import argparse
import ctypes
import ctypes.util
import gzip
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/neighborhoods/search-areas.geojson.gz'
MUNICIPALITIES = ROOT / 'data/neighborhoods/sources/country-osm/municipalities.geojson.gz'
OUTPUT = ROOT / 'dist/data/map'
SOURCE_SHA = '367af069d58c60e171d189e23673fe20fd5cef51792769c161c3eccb87321e4d'
MUNICIPALITIES_SHA = 'fb5f1293628b9eeaabce243ae6ebc884f6bdc93443a2488e5fb213029bf766b7'
POLICY = '20261120-neighborhood-display-v1'
VERSION = POLICY + '-' + SOURCE_SHA[:12] + '-' + MUNICIPALITIES_SHA[:12]
EXPECTED_COUNT = 4308
TOLERANCE = 12 / 111_320  # approximately twelve metres in latitude, screen use only
ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII',
         'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX', 'XXI', 'XXII', 'XXIII']


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pinned(path, digest):
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError('Pinned map source changed: ' + str(path.relative_to(ROOT)))
    return json.loads(gzip.decompress(content))


def polygons(geometry):
    kind = geometry.get('type')
    if kind == 'Polygon':
        return [geometry['coordinates']]
    if kind == 'MultiPolygon':
        return geometry['coordinates']
    raise ValueError('Map source must be polygonal.')


def positions(geometry):
    return [coordinate for polygon in polygons(geometry) for ring in polygon for coordinate in ring]


def bounds(geometry):
    points = positions(geometry)
    if not points:
        raise ValueError('Map source geometry is empty.')
    # Round outwards, so screen-fit bounds do not exclude the original outline.
    return [math.floor(min(p[0] for p in points) * 1e6) / 1e6,
            math.floor(min(p[1] for p in points) * 1e6) / 1e6,
            math.ceil(max(p[0] for p in points) * 1e6) / 1e6,
            math.ceil(max(p[1] for p in points) * 1e6) / 1e6]


def union_bounds(values):
    return [min(b[0] for b in values), min(b[1] for b in values),
            max(b[2] for b in values), max(b[3] for b in values)]


def area(geometry):
    result = 0
    for polygon in polygons(geometry):
        for index, ring in enumerate(polygon):
            x0, y0 = ring[0]
            value = abs(math.fsum((a[0] - x0) * (b[1] - y0) - (b[0] - x0) * (a[1] - y0)
                                  for a, b in zip(ring, ring[1:])))
            result += value if index == 0 else -value
    return result


def topology(geometry):
    return [len(polygon) for polygon in polygons(geometry)]


def quantized(geometry, digits):
    def visit(value):
        if isinstance(value[0], (int, float)):
            return [round(float(value[0]), digits), round(float(value[1]), digits)]
        return [visit(child) for child in value]
    return {'type': geometry['type'], 'coordinates': visit(geometry['coordinates'])}


class Geos:
    """Small owned-context wrapper; native handles always have matching frees."""
    def __init__(self):
        library = ctypes.util.find_library('geos_c')
        if not library:
            raise SystemExit('Map generation needs libgeos_c; install the Ubuntu libgeos-c1t64 package.')
        self.lib = ctypes.CDLL(library)
        pointer, double, integer, string = ctypes.c_void_p, ctypes.c_double, ctypes.c_int, ctypes.c_char_p
        definitions = {
            'GEOS_init_r': (pointer, []), 'GEOS_finish_r': (None, [pointer]),
            'GEOSGeoJSONReader_create_r': (pointer, [pointer]),
            'GEOSGeoJSONReader_destroy_r': (None, [pointer, pointer]),
            'GEOSGeoJSONReader_readGeometry_r': (pointer, [pointer, pointer, string]),
            'GEOSGeoJSONWriter_create_r': (pointer, [pointer]),
            'GEOSGeoJSONWriter_destroy_r': (None, [pointer, pointer]),
            'GEOSGeoJSONWriter_writeGeometry_r': (pointer, [pointer, pointer, pointer, integer]),
            'GEOSTopologyPreserveSimplify_r': (pointer, [pointer, pointer, double]),
            'GEOSisValid_r': (ctypes.c_char, [pointer, pointer]),
            'GEOSGeom_destroy_r': (None, [pointer, pointer]), 'GEOSFree_r': (None, [pointer, pointer]),
        }
        for name, (result, args) in definitions.items():
            function = getattr(self.lib, name)
            function.restype, function.argtypes = result, args
        self.context = self.lib.GEOS_init_r()
        self.reader = self.lib.GEOSGeoJSONReader_create_r(self.context)
        self.writer = self.lib.GEOSGeoJSONWriter_create_r(self.context)
        if not self.context or not self.reader or not self.writer:
            raise RuntimeError('Could not initialize the display geometry builder.')

    def read(self, geometry):
        handle = self.lib.GEOSGeoJSONReader_readGeometry_r(self.context, self.reader, encoded(geometry))
        if not handle:
            raise ValueError('Could not read a display geometry.')
        return handle

    def valid(self, geometry):
        handle = self.read(geometry)
        try:
            return self.lib.GEOSisValid_r(self.context, handle) == b'\x01'
        finally:
            self.lib.GEOSGeom_destroy_r(self.context, handle)

    def simplify(self, geometry):
        source = self.read(geometry)
        simplified = None
        payload = None
        try:
            simplified = self.lib.GEOSTopologyPreserveSimplify_r(self.context, source, TOLERANCE)
            if not simplified or self.lib.GEOSisValid_r(self.context, simplified) != b'\x01':
                return geometry
            payload = self.lib.GEOSGeoJSONWriter_writeGeometry_r(self.context, self.writer, simplified, 0)
            if not payload:
                raise ValueError('Could not serialize a display geometry.')
            result = json.loads(ctypes.string_at(payload))
            if result['type'] != geometry['type'] or topology(result) != topology(geometry):
                return geometry
            # Precision reduction is accepted only when native topology remains
            # valid. Thin holes and tiny separate parts fall back to full precision.
            for digits in (6, 7):
                rounded = quantized(result, digits)
                if self.valid(rounded):
                    return rounded
            return result
        finally:
            if payload:
                self.lib.GEOSFree_r(self.context, payload)
            if simplified:
                self.lib.GEOSGeom_destroy_r(self.context, simplified)
            self.lib.GEOSGeom_destroy_r(self.context, source)

    def close(self):
        self.lib.GEOSGeoJSONWriter_destroy_r(self.context, self.writer)
        self.lib.GEOSGeoJSONReader_destroy_r(self.context, self.reader)
        self.lib.GEOS_finish_r(self.context)


def build():
    source = pinned(SOURCE, SOURCE_SHA)
    municipal = pinned(MUNICIPALITIES, MUNICIPALITIES_SHA)
    known = set(json.loads((ROOT / 'dist/data/settlements.json').read_text())['settlements'])
    if source['featureCount'] != EXPECTED_COUNT or len(source['features']) != EXPECTED_COUNT:
        raise ValueError('Expected all 4308 canonical areas.')
    focus, grouped, identities = {}, defaultdict(list), set()
    municipal_selected = {}
    for feature in municipal['features']:
        city = feature['properties']['name']
        if city not in known:
            continue
        footprint = area(feature['geometry'])
        if city not in municipal_selected or footprint > municipal_selected[city][0]:
            municipal_selected[city] = (footprint, bounds(feature['geometry']))
    if set(municipal_selected) != known or len(known) != 3155:
        raise ValueError('Map focus bounds must cover every canonical municipality.')
    for city in sorted(known):
        focus['city:' + city] = municipal_selected[city][1]
    geos = Geos()
    try:
        for feature in sorted(source['features'], key=lambda item: item['id']):
            p, original = feature['properties'], feature['geometry']
            identity, city = p['id'], p['municipality']
            if not re.fullmatch(r'neighborhood:[a-f0-9]{24}', identity) or identity in identities or city not in known:
                raise ValueError('Invalid display identity or municipality.')
            identities.add(identity)
            box = bounds(original)
            focus[identity] = box
            if city == 'Budapest' and p['name'] in [value + '. kerület' for value in ROMAN]:
                focus['district:Budapest:' + str(ROMAN.index(p['name'].split('.')[0]) + 1)] = box
            display = geos.simplify(original)
            if topology(display) != topology(original):
                raise ValueError('Display simplification lost an original component or hole.')
            grouped[city].append({'type': 'Feature', 'id': identity, 'bbox': box,
                                  'properties': {'id': identity, 'name': p['name'], 'city': city,
                                                 'label': p['label'], 'estimated': p['estimated']},
                                  'geometry': display})
    finally:
        geos.close()
    if any('district:Budapest:' + str(number) not in focus for number in range(1, 24)):
        raise ValueError('All 23 Budapest district focus bounds are required.')
    output, cities = {}, []
    for city, features in sorted(grouped.items()):
        content = encoded({'type': 'FeatureCollection', 'version': VERSION, 'city': city, 'features': features})
        name = 'city-' + hashlib.sha256(content).hexdigest()[:20] + '.json'
        if len(content) > 2 * 1024 * 1024:
            raise ValueError('A municipality map layer exceeds the bounded two-MiB budget.')
        output[name] = content
        cities.append({'city': city, 'bounds': union_bounds([feature['bbox'] for feature in features]),
                       'file': name, 'count': len(features)})
    output['index.json'] = encoded({'schemaVersion': 1, 'version': VERSION, 'count': EXPECTED_COUNT,
                                    'sourceSha256': SOURCE_SHA, 'municipalitiesSha256': MUNICIPALITIES_SHA,
                                    'displayOnly': True, 'cities': cities, 'focus': dict(sorted(focus.items())),
                                    'attribution': ['© OpenStreetMap contributors (ODbL-1.0)',
                                                    'Az összeállított városrészek forrásai: THIRD-PARTY-NOTICES.txt.'],
                                    'sourceNotice': 'Display layers only; property matching uses the unchanged full MySQL boundaries.'})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check the reproducible generated assets without writing.')
    args = parser.parse_args()
    output = build()
    if args.check:
        actual_names = {path.name for path in OUTPUT.glob('*.json')}
        if actual_names != set(output):
            raise SystemExit('Map assets have missing or stale municipality chunks.')
        for name, content in output.items():
            if (OUTPUT / name).read_bytes() != content:
                raise SystemExit('Stale map asset: ' + name)
    else:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for name, content in output.items():
            (OUTPUT / name).write_bytes(content)
        for path in OUTPUT.glob('*.json'):
            if path.name not in output:
                path.unlink()
    index = json.loads(output['index.json'])
    print(f"Verified {index['count']} display areas in {len(index['cities'])} lazy municipality layers; "
          f"{len(index['focus'])} focus bounds, {sum(map(len, output.values())):,} total bytes, "
          f"{max(map(len, output.values())):,} maximum asset bytes.")


if __name__ == '__main__':
    main()
