#!/usr/bin/env python3
"""Retain the real residential outline as an explicit Péterimajor candidate.

The neighborhood point and Majori út establish identity only. They never
generate, buffer, expand, clip or otherwise alter the residential boundary.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/neighborhoods/manual/sources/budapest-peterimajor-input.geojson'
OUTPUT = ROOT / 'data/neighborhoods/manual/budapest-peterimajor.geojson'


def contains_point(ring, point):
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def build():
    ff = json.loads(SOURCE.read_text())['features']
    by_id = {f['id']: f for f in ff}
    residential = by_id['osm:way:115726893']
    point = by_id['osm:node:905070343']
    roads = [f for f in ff if f['properties'].get('name') == 'Majori út']
    assert {f['id'] for f in roads} == {'osm:way:574785521', 'osm:way:854074581',
        'osm:way:854074582', 'osm:way:854074583', 'osm:way:854074585'}
    assert residential['properties']['source']['tags']['landuse'] == 'residential'
    assert point['properties']['name'] == 'Péterimajor' and roads
    geometry = residential['geometry']
    ring = geometry['coordinates'][0]
    assert geometry['type'] == 'Polygon' and len(ring) == 20 and ring[0] == ring[-1]
    assert contains_point(ring, point['geometry']['coordinates'])
    geometry_sha = hashlib.sha256(json.dumps(geometry, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    assert geometry_sha == '087962c9b0ab3af7814a746ea0f0b32e34d4d828254e0f5eac608e5bff1f2206'
    definition = next(r for r in json.loads((ROOT / 'data/neighborhoods/manual/budapest-definitions.json').read_text())['records']
        if r['referenceName'] == 'Péterimajor')
    law = definition['sourceDocuments'][0]['url']
    properties = {
        'name': 'Péterimajor', 'municipality': 'Budapest', 'district': 23,
        'boundaryKind': 'neighbourhood',
        'method': 'legal_named_builtup_area_with_existing_osm_residential_outline_as_explicit_proxy',
        'evidenceUrls': [law, residential['properties']['source']['url'], point['properties']['source']['url']]
            + [f['properties']['source']['url'] for f in roads],
        'sourceDocuments': definition['sourceDocuments'],
        'sourceParagraph': definition['sourceParagraph'],
        'boundaryText': definition['boundaryText'],
        'sourceLineIds': [residential['id']],
        'identitySourceIds': [point['id']] + [f['id'] for f in roads],
        'sourceGeometry': {'path': str(SOURCE.relative_to(ROOT)),
            'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'featureId': residential['id'], 'geometrySha256': geometry_sha,
            'geometryOperation': 'Copy complete existing residential Polygon without any coordinate or edge change.',
            'originalVertexCount': 20, 'addedVertices': 0, 'addedSegments': 0,
            'pointUsedToGenerateGeometry': False, 'buffersUsed': False},
        'quality': 'source_based_inferred_boundary_candidate',
        'reviewNotes': [
            'The legal description identifies a built-up neighborhood beside Majori út but does not supply a surveyed ring.',
            'The actual OSM residential land-use polygon beside Majori út contains the independently named Péterimajor neighborhood point.',
            'The complete existing residential outline is used as a candidate proxy. Its land-use edge has not been established as the legal belterület or neighborhood boundary.',
            'The named point and street establish identity only; neither supplies a radius, bounding box, Voronoi cell or synthetic polygon.',
            'This inferred candidate requires municipal boundary-map review before precise legal or address assignment use.'
        ],
        'usableForAddressAssignment': False,
        'source': residential['properties']['source'],
        'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
        'attributionUrl': 'https://www.openstreetmap.org/copyright'
    }
    return {'type': 'FeatureCollection', 'features': [{'type': 'Feature',
        'id': 'manual:Budapest:Peterimajor', 'properties': properties, 'geometry': geometry}]}


if __name__ == '__main__':
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n')
    print(OUTPUT.relative_to(ROOT))
