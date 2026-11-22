#!/usr/bin/env python3
"""Build lazy, public, display-only neighborhood map layers from pinned sources.

The existing MySQL/search geometry is never rewritten. Native GEOS performs
topology-preserving simplification for screen rendering; every polygon part and
hole is retained. Requires libgeos_c (Ubuntu: libgeos-c1t64), no Python packages or
network requests. The manifest has bounds only; actual layers are separate,
content-addressed municipality files loaded as the viewport reaches a city.
Containment is computed offline from the original geometry into a separate
small metadata file, never from polygon size or viewport position alone.
"""
import argparse
import ctypes
import ctypes.util
import gzip
import hashlib
import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/neighborhoods/search-areas.geojson.gz'
MUNICIPALITIES = ROOT / 'data/neighborhoods/sources/country-osm/municipalities.geojson.gz'
NAMED_NODES = ROOT / 'data/neighborhoods/sources/country-osm/named-nodes.geojson.gz'
OUTPUT = ROOT / 'dist/data/map'
# Provider map styling is pinned separately and is not a generated boundary or
# label asset. Never delete it when refreshing the canonical display catalogue.
STATIC_ASSETS = {'style.json'}
SOURCE_SHA = '367af069d58c60e171d189e23673fe20fd5cef51792769c161c3eccb87321e4d'
MUNICIPALITIES_SHA = 'fb5f1293628b9eeaabce243ae6ebc884f6bdc93443a2488e5fb213029bf766b7'
NAMED_NODES_SHA = '5c9193a72d4327e133f86d9c2625a4caeae3d21ec71d2575a3128b1d97931ecc'
POLICY = '20261120-neighborhood-display-v1'
VERSION = POLICY + '-' + SOURCE_SHA[:12] + '-' + MUNICIPALITIES_SHA[:12]
EXPECTED_COUNT = 4308
TOLERANCE = 12 / 111_320  # approximately twelve metres in latitude, screen use only
HIERARCHY_POLICY = '20261121-neighborhood-containment-v1'
MINIMUM_COVERAGE = 0.95
MAXIMUM_CHILD_AREA_RATIO = 0.8
LABEL_VERSION = '20261121-map-labels-v1-' + SOURCE_SHA[:12] + '-' + NAMED_NODES_SHA[:12]
# These established regional centres get earlier, more prominent labels. This
# is a display priority, never a claim about source population or city status.
REGIONAL_CENTRES = {'Békéscsaba', 'Debrecen', 'Eger', 'Győr', 'Kaposvár', 'Kecskemét',
                    'Miskolc', 'Nyíregyháza', 'Pécs', 'Salgótarján', 'Szeged',
                    'Székesfehérvár', 'Szekszárd', 'Szolnok', 'Szombathely',
                    'Tatabánya', 'Veszprém', 'Zalaegerszeg', 'Sopron', 'Dunaújváros', 'Érd'}
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
            'GEOSIntersection_r': (pointer, [pointer, pointer, pointer]),
            'GEOSUnaryUnion_r': (pointer, [pointer, pointer]),
            'GEOSArea_r': (integer, [pointer, pointer, ctypes.POINTER(double)]),
            'GEOSPointOnSurface_r': (pointer, [pointer, pointer]),
            'GEOSCovers_r': (ctypes.c_char, [pointer, pointer, pointer]),
            'GEOSGeomGetX_r': (integer, [pointer, pointer, ctypes.POINTER(double)]),
            'GEOSGeomGetY_r': (integer, [pointer, pointer, ctypes.POINTER(double)]),
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

    def handle_area(self, handle):
        result = ctypes.c_double()
        if not handle or not self.lib.GEOSArea_r(self.context, handle, ctypes.byref(result)):
            raise ValueError('Could not measure a hierarchy geometry.')
        return result.value

    def overlap_area(self, left, right):
        handle = self.lib.GEOSIntersection_r(self.context, left, right)
        try:
            return self.handle_area(handle)
        finally:
            if handle:
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

    def anchor(self, original, display, candidates=()):
        """Prefer a known name point, otherwise use a verified interior point.

        The fallback lies in both the original and simplified footprint. A
        polygon centre/bounding-box midpoint is unsafe for concave shapes,
        holes and multipart areas. No address or geocoding data is involved.
        """
        source, screen = self.read(original), self.read(display)
        intersection = interior = component = None
        payload = None
        try:
            def covers(point):
                handle = self.read({'type': 'Point', 'coordinates': point})
                try:
                    return (self.lib.GEOSCovers_r(self.context, source, handle) == b'\x01'
                            and self.lib.GEOSCovers_r(self.context, screen, handle) == b'\x01')
                finally:
                    self.lib.GEOSGeom_destroy_r(self.context, handle)
            for candidate in candidates:
                if covers(candidate):
                    return list(candidate), 'osm_name_point'
            intersection = self.lib.GEOSIntersection_r(self.context, source, screen)
            if not intersection or self.handle_area(intersection) <= 0:
                raise ValueError('A label requires a shared original/display interior.')
            payload = self.lib.GEOSGeoJSONWriter_writeGeometry_r(self.context, self.writer, intersection, 0)
            if not payload:
                raise ValueError('Could not inspect the label interior.')
            intersection_geometry = json.loads(ctypes.string_at(payload))
            # Use the largest polygonal component: tiny detached islands must
            # not attract the main label away from the neighbourhood itself.
            def polygonal_parts(geometry):
                if geometry['type'] == 'Polygon':
                    return [geometry['coordinates']]
                if geometry['type'] == 'MultiPolygon':
                    return geometry['coordinates']
                if geometry['type'] == 'GeometryCollection':
                    return [part for child in geometry['geometries'] for part in polygonal_parts(child)]
                return []
            pieces = polygonal_parts(intersection_geometry)
            if not pieces:
                raise ValueError('A map label requires a polygonal interior.')
            largest = max(pieces, key=lambda coordinates: area({'type': 'Polygon', 'coordinates': coordinates}))
            component = self.read({'type': 'Polygon', 'coordinates': largest})
            interior = self.lib.GEOSPointOnSurface_r(self.context, component)
            x, y = ctypes.c_double(), ctypes.c_double()
            if (not interior or not self.lib.GEOSGeomGetX_r(self.context, interior, ctypes.byref(x))
                    or not self.lib.GEOSGeomGetY_r(self.context, interior, ctypes.byref(y))):
                raise ValueError('Could not construct an interior map label point.')
            point = [x.value, y.value]
            rounded = [round(value, 7) for value in point]
            result = rounded if covers(rounded) else point
            if not covers(result):
                raise ValueError('A generated map label escaped its own boundary.')
            return result, 'verified_interior'
        finally:
            if payload:
                self.lib.GEOSFree_r(self.context, payload)
            for handle in (interior, component, intersection, screen, source):
                if handle:
                    self.lib.GEOSGeom_destroy_r(self.context, handle)

    def close(self):
        self.lib.GEOSGeoJSONWriter_destroy_r(self.context, self.writer)
        self.lib.GEOSGeoJSONReader_destroy_r(self.context, self.reader)
        self.lib.GEOS_finish_r(self.context)

    def coverage(self, geometries):
        """Coarse public national coverage for suppressing duplicate base labels.

        This is not an address-matching geometry. It is deliberately simplified
        to about 200 metres and stays independent of all canonical search data.
        """
        collection = self.read({'type': 'GeometryCollection', 'geometries': geometries})
        merged = simplified = None
        payload = None
        try:
            merged = self.lib.GEOSUnaryUnion_r(self.context, collection)
            if not merged or self.lib.GEOSisValid_r(self.context, merged) != b'\x01':
                raise ValueError('Could not assemble municipality label coverage.')
            simplified = self.lib.GEOSTopologyPreserveSimplify_r(self.context, merged, 0.002)
            if not simplified or self.lib.GEOSisValid_r(self.context, simplified) != b'\x01':
                raise ValueError('Could not simplify municipality label coverage.')
            payload = self.lib.GEOSGeoJSONWriter_writeGeometry_r(self.context, self.writer, simplified, 0)
            if not payload:
                raise ValueError('Could not serialize municipality label coverage.')
            result = quantized(json.loads(ctypes.string_at(payload)), 6)
            if not self.valid(result) or len(positions(result)) > 10000:
                raise ValueError('National label coverage exceeds its geometry budget.')
            return result
        finally:
            if payload:
                self.lib.GEOSFree_r(self.context, payload)
            for handle in (simplified, merged, collection):
                if handle:
                    self.lib.GEOSGeom_destroy_r(self.context, handle)


def name_key(value):
    return ''.join(character for character in unicodedata.normalize('NFKD', str(value).casefold())
                   if not unicodedata.combining(character) and character.isalnum())


def build_labels(source, named_nodes, municipality_features, display_groups, hierarchy, geos):
    """Canonical place labels, separate from provider IDs or live tile snapshots.

    The 2026-11-12 OSM name points improve anchors where an exact name/alias and
    municipality match is verified inside the footprint. They are not claimed
    to be a current inventory of OpenFreeMap labels. Every other canonical area
    remains selectable through its own safe interior point.
    """
    named = defaultdict(list)
    for feature in named_nodes['features']:
        p = feature['properties']
        if feature['geometry']['type'] != 'Point':
            raise ValueError('The pinned name-point source must contain points.')
        named[(p['municipality'], name_key(p['name']))].append((str(feature['id']), feature['geometry']['coordinates']))
    for items in named.values():
        items.sort()
    display = {feature['id']: feature for features in display_groups.values() for feature in features}
    parents = hierarchy['parents']
    labels, outlines, towns, district_boundaries = [], {}, [], {}
    neighbourhood_labels = defaultdict(list)

    def point_feature(identity, name, city, kind, point, minimum, priority, boundary_id, anchor_source, aliases=()):
        properties = {'id': identity, 'name': name, 'label': city if kind == 'city' else name + ' (' + city + ')',
                      'city': city, 'kind': kind, 'minZoom': minimum, 'priority': priority,
                      'boundaryId': boundary_id, 'anchorSource': anchor_source}
        if aliases:
            properties['aliases'] = sorted(set(aliases))
        return {'type': 'Feature', 'id': identity, 'properties': properties,
                'geometry': {'type': 'Point', 'coordinates': point}}

    for feature in sorted(source['features'], key=lambda item: item['id']):
        p = feature['properties']
        identity, city, name = p['id'], p['municipality'], p['name']
        aliases = [alias for alias in p.get('aliases', []) if isinstance(alias, str)]
        candidates = []
        for variant in [name, *aliases]:
            candidates.extend(point for _, point in named.get((city, name_key(variant)), []))
        point, anchor_source = geos.anchor(feature['geometry'], display[identity]['geometry'], candidates)
        depth, parent = 0, identity
        while parent in parents:
            depth, parent = depth + 1, parents[parent]
        ward = city == 'Budapest' and name in [value + '. kerület' for value in ROMAN]
        broad = city == 'Budapest' and name in ('Buda', 'Pest')
        minimum = 8 if broad else 10
        priority = 50 if broad else 70 if ward else 100 + depth * 10
        label = point_feature(identity, name, city, 'neighborhood', point, minimum, priority, identity, anchor_source, aliases)
        labels.append(label)
        neighbourhood_labels[city].append(label)
        if ward:
            district_id = 'district:Budapest:' + str(ROMAN.index(name.split('.')[0]) + 1)
            district_boundaries[district_id] = identity
            labels.append(point_feature(district_id, name, city, 'district', point, 10, 65, identity, anchor_source))

    for city, feature in sorted(municipality_features.items()):
        identity = 'city:' + city
        original = feature['geometry']
        screen = geos.simplify(original)
        if topology(screen) != topology(original):
            raise ValueError('A municipality display outline lost an original component or hole.')
        central = [label['geometry']['coordinates'] for label in neighbourhood_labels[city]
                   if name_key(label['properties']['name']) in ('belvaros', 'varoskozpont', 'kozpont')]
        point, anchor_source = geos.anchor(original, screen, central)
        if anchor_source == 'osm_name_point':
            anchor_source = 'verified_central_neighborhood'
        major = city in REGIONAL_CENTRES
        minimum, priority = (6, 0) if city == 'Budapest' else (7, 10) if major else (9, 30)
        labels.append(point_feature(identity, city, city, 'city', point, minimum, priority, identity, anchor_source))
        box = bounds(original)
        content = encoded({'type': 'Feature', 'version': LABEL_VERSION, 'mapVersion': VERSION,
                           'id': identity, 'bbox': box,
                           'properties': {'id': identity, 'city': city, 'name': city, 'label': city},
                           'geometry': screen})
        if len(content) > 2 * 1024 * 1024:
            raise ValueError('A selected municipality outline exceeds its two-MiB budget.')
        filename = 'town-' + hashlib.sha256(content).hexdigest()[:20] + '.json'
        outlines[filename] = content
        towns.append({'id': identity, 'file': filename, 'bounds': box})
    counts = dict(sorted((kind, sum(label['properties']['kind'] == kind for label in labels))
                         for kind in ('city', 'district', 'neighborhood')))
    if counts != {'city': 3155, 'district': 23, 'neighborhood': 4308}:
        raise ValueError('The label registry must cover every canonical town, ward and neighborhood.')
    labels.sort(key=lambda feature: feature['id'])
    coverage = geos.coverage([feature['geometry'] for feature in municipality_features.values()])
    collection = {'schemaVersion': 1, 'type': 'FeatureCollection', 'version': LABEL_VERSION,
                  'mapVersion': VERSION, 'sourceSha256': SOURCE_SHA,
                  'municipalitiesSha256': MUNICIPALITIES_SHA, 'namedNodesSha256': NAMED_NODES_SHA,
                  'displayOnly': True, 'count': len(labels), 'counts': counts,
                  'features': labels, 'towns': towns,
                  'districtBoundaries': dict(sorted(district_boundaries.items())), 'coverage': coverage,
                  'attribution': ['© OpenStreetMap contributors (ODbL-1.0)',
                                  'Az összeállított városrészek forrásai: THIRD-PARTY-NOTICES.txt.'],
                  'sourceNotice': 'Canonical display labels with verified interior anchors, not a live OpenFreeMap inventory. '
                                  'Town outlines and coarse national label coverage are display-only. '
                                  'Property matching uses the unchanged full MySQL boundaries.'}
    outlines['labels.json'] = encoded(collection)
    return outlines


def build_hierarchy(source, geos):
    """Derive containment once, without changing any search/display outline.

    A proper parent covers at least 95% of the child's original geometry and
    must be at least 25% larger. The small boundary allowance accommodates the
    mixed estimated sources; mere overlap or a larger area is insufficient.
    Picking the smallest qualifying parent yields an acyclic containment forest.
    Unrelated city quarters remain roots, regardless of their relative sizes.
    """
    groups, parents = defaultdict(list), {}
    for feature in source['features']:
        groups[feature['properties']['municipality']].append(feature)
    for features in groups.values():
        handles = {}
        try:
            for feature in features:
                handles[feature['id']] = geos.read(feature['geometry'])
            sizes = {identity: geos.handle_area(handle) for identity, handle in handles.items()}
            if any(not math.isfinite(size) or size <= 0 for size in sizes.values()):
                raise ValueError('Every hierarchy geometry must have positive area.')
            boxes = {feature['id']: bounds(feature['geometry']) for feature in features}
            ordered = sorted(handles, key=lambda identity: (sizes[identity], identity))
            for child in ordered:
                child_box, child_area = boxes[child], sizes[child]
                for parent in ordered:
                    if child_area > sizes[parent] * MAXIMUM_CHILD_AREA_RATIO:
                        continue
                    parent_box = boxes[parent]
                    width = min(child_box[2], parent_box[2]) - max(child_box[0], parent_box[0])
                    height = min(child_box[3], parent_box[3]) - max(child_box[1], parent_box[1])
                    # A bounding intersection can disprove containment cheaply,
                    # but never proves it: the actual polygon intersection does.
                    if width <= 0 or height <= 0 or width * height < child_area * MINIMUM_COVERAGE:
                        continue
                    coverage = geos.overlap_area(handles[child], handles[parent]) / child_area
                    if coverage >= MINIMUM_COVERAGE:
                        parents[child] = parent
                        break
        finally:
            for handle in handles.values():
                geos.lib.GEOSGeom_destroy_r(geos.context, handle)
    return {'schemaVersion': 1, 'version': HIERARCHY_POLICY + '-' + SOURCE_SHA[:12],
            'mapVersion': VERSION, 'sourceSha256': SOURCE_SHA, 'count': EXPECTED_COUNT,
            'policy': {'minimumCoverage': MINIMUM_COVERAGE,
                       'maximumChildAreaRatio': MAXIMUM_CHILD_AREA_RATIO},
            'parents': dict(sorted(parents.items()))}


def build():
    source = pinned(SOURCE, SOURCE_SHA)
    municipal = pinned(MUNICIPALITIES, MUNICIPALITIES_SHA)
    named_nodes = pinned(NAMED_NODES, NAMED_NODES_SHA)
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
            municipal_selected[city] = (footprint, bounds(feature['geometry']), feature)
    if set(municipal_selected) != known or len(known) != 3155:
        raise ValueError('Map focus bounds must cover every canonical municipality.')
    for city in sorted(known):
        focus['city:' + city] = municipal_selected[city][1]
    geos = Geos()
    try:
        hierarchy = build_hierarchy(source, geos)
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
        label_assets = build_labels(source, named_nodes,
                                    {city: row[2] for city, row in municipal_selected.items()},
                                    grouped, hierarchy, geos)
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
    output['hierarchy.json'] = encoded(hierarchy)
    output.update(label_assets)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check the reproducible generated assets without writing.')
    args = parser.parse_args()
    output = build()
    if args.check:
        actual_names = {path.name for path in OUTPUT.glob('*.json') if path.name not in STATIC_ASSETS}
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
            if path.name not in output and path.name not in STATIC_ASSETS:
                path.unlink()
    index = json.loads(output['index.json'])
    print(f"Verified {index['count']} display areas in {len(index['cities'])} lazy municipality layers; "
          f"{len(index['focus'])} focus bounds, {sum(map(len, output.values())):,} total bytes, "
          f"{max(map(len, output.values())):,} maximum asset bytes.")
    parents = json.loads(output['hierarchy.json'])['parents']
    print(f"Containment hierarchy: {len(parents)} parent links, "
          f"{EXPECTED_COUNT - len(parents)} independent roots.")
    labels = json.loads(output['labels.json'])
    print(f"Canonical labels: {labels['count']} ({labels['counts']}); "
          f"{len(labels['towns'])} lazy selected-town outlines; "
          f"{len(output['labels.json']):,} label bytes, {len(positions(labels['coverage']))} national coverage points.")


if __name__ == '__main__':
    main()
