#!/usr/bin/env python3
"""Audit the unresolved legal chain of Soroksár's Történeti központ.

This intentionally emits an audit, not a fabricated polygon. Requires Shapely
and pyproj. All measurements refer to retained real OSM street geometries.
"""
import hashlib
import json
from pathlib import Path
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import nearest_points, transform, unary_union

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/neighborhoods/manual/sources/budapest-torteneti-input.geojson'
OUTPUT = ROOT / 'data/neighborhoods/manual/budapest-torteneti-audit.json'


def build():
    features = json.loads(SOURCE.read_text())['features']
    groups = {}
    for feature in features:
        groups.setdefault(feature['properties']['name'], []).append(feature)
    geometries = {name: unary_union([shape(f['geometry']) for f in ff])
        for name, ff in groups.items()}
    forward = Transformer.from_crs(4326, 23700, always_xy=True).transform
    backward = Transformer.from_crs(23700, 4326, always_xy=True).transform
    pairs = [
        ('Csendes utca', 'Sínpár utca', 'consecutive_named_streets_do_not_meet'),
        ('Sínpár utca', 'Grassalkovich út', 'consecutive_named_streets_do_not_meet'),
        ('Táncsics Mihály utca', 'Dobó utca', 'legal_natural_slope_continuation_requires_evidence'),
        ('Tárcsás utca', 'Molnársziget mellékág', 'legal_natural_street_continuation_requires_evidence')
    ]
    gaps = []
    for start, end, reason in pairs:
        a = transform(forward, geometries[start])
        b = transform(forward, geometries[end])
        pa, pb = nearest_points(a, b)
        gaps.append({'from': start, 'to': end, 'reason': reason,
            'distanceMetres': round(pa.distance(pb), 3),
            'crsUsedForDistance': 'EPSG:23700',
            'nearestCoordinates': [list(transform(backward, pa).coords[0]), list(transform(backward, pb).coords[0])],
            'fromSourceIds': [f['id'] for f in groups[start]],
            'toSourceIds': [f['id'] for f in groups[end]],
            'connectorCreated': False})
    legal = next(r for r in json.loads((ROOT / 'data/neighborhoods/manual/budapest-definitions.json').read_text())['records']
        if r['referenceName'] == 'Történeti központ')
    return {'schemaVersion': 1, 'municipality': 'Budapest', 'district': 23,
        'name': 'Történeti központ', 'sourceParagraph': legal['sourceParagraph'],
        'boundaryText': legal['boundaryText'], 'sourceDocuments': legal['sourceDocuments'],
        'status': 'unresolved_boundary_chain', 'polygonCreated': False,
        'usableForAddressAssignment': False,
        'sourceGeometry': {'path': str(SOURCE.relative_to(ROOT)),
            'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'osmTimestamp': '2026-11-12T21:23:05Z',
            'pbfSha256': '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'},
        'gaps': gaps,
        'requiredEvidence': [
            'A contemporary or historical municipal street/boundary map identifying the Csendes–Sínpár–Grassalkovich boundary corridor. Present OSM streets have gaps exceeding 600 m, so automatic junction snapping would invent a substantial boundary.',
            'Mapped natural slope/parcel boundary between the northern Táncsics endpoint and Dobó utca.',
            'The physical continuation of Tárcsás utca west to the Duna side branch.'
        ],
        'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors'}


if __name__ == '__main__':
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n')
    print(OUTPUT.relative_to(ROOT))
