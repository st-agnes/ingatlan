#!/usr/bin/env python3
"""Recover the legally described island from a retained OSM waterbody hole.

No points, buffers, raster traces or synthetic connecting segments are used.
The entire ring is an existing inner ring of OSM water relation 417508.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/neighborhoods/manual/sources/budapest-molnar-input.geojson'
OUTPUT = ROOT / 'data/neighborhoods/manual/budapest-molnar.geojson'


def build():
    data = json.loads(SOURCE.read_text())
    water = next(f for f in data['features'] if f['id'] == 'osm:relation:417508')
    branch = next(f for f in data['features'] if f['id'] == 'osm:way:1084440121')
    assert water['properties']['source']['tags']['name'] == 'Ráckevei-Duna-észak'
    assert branch['properties']['source']['tags']['name'] == 'Molnársziget mellékág'
    # The index selects an actual waterbody hole, not a newly calculated shape.
    ring = water['geometry']['coordinates'][0][4]
    assert len(ring) == 170 and ring[0] == ring[-1]
    assert len({tuple(c) for c in ring}) == len(ring) - 1
    ring_sha = hashlib.sha256(json.dumps(ring, separators=(',', ':')).encode()).hexdigest()
    assert ring_sha == '14049856b336c90dce71f29516e11e4485a9f0f59a7abe0075cdf387f40299df'
    # Convert the waterbody's inner-ring orientation into a polygon exterior.
    signed = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))
    exterior = ring if signed > 0 else list(reversed(ring))
    source_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    law = 'https://net.jogtar.hu/rendelet?council=fovaros&dbnum=104&docid=A1200094.FOV'
    properties = {
        'name': 'Molnár-sziget', 'municipality': 'Budapest', 'district': 23,
        'boundaryKind': 'neighbourhood',
        'method': 'legal_island_definition_with_existing_osm_waterbody_inner_ring',
        'evidenceUrls': [law, water['properties']['source']['url'], branch['properties']['source']['url']],
        'sourceDocuments': [{'url': law, 'sha256': 'fb61b865266990e43e6407f7d46e8421a17541b5efa4962bcff3cd8f9f0ecfac', 'paragraph': '3. melléklet 23.4.'}],
        'sourceLineIds': ['osm:relation:417508'],
        'sourceGeometry': {
            'path': 'data/neighborhoods/manual/sources/budapest-molnar-input.geojson',
            'sha256': source_sha, 'featureId': 'osm:relation:417508',
            'polygonIndex': 0, 'ringIndex': 4, 'ringSha256': ring_sha,
            'originalVertexCount': 170, 'addedVertices': 0, 'addedSegments': 0,
            'geometryOperation': 'Promote complete existing waterbody inner ring to exterior; normalize orientation only.',
            'supportingFeatureId': 'osm:way:1084440121'
        },
        'source': {'provider': 'OpenStreetMap via Geofabrik Hungary extract',
            'url': 'https://download.geofabrik.de/europe/hungary-261112.osm.pbf',
            'pbfSha256': '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a',
            'timestamp': '2026-11-12T21:23:05Z'},
        'quality': 'source_based_boundary_candidate',
        'reviewNotes': [
            'The legal definition specifies the island bounded by the Ráckevei (Soroksári) Duna and its side branch.',
            'The chosen existing waterbody hole is the island west of the named Molnársziget mellékág; all 169 unique source vertices are preserved.',
            'The polygon follows the mapped shoreline; the legal water-boundary convention and address assignment have not been independently surveyed.'
        ],
        'usableForAddressAssignment': False,
        'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
        'attributionUrl': 'https://www.openstreetmap.org/copyright'
    }
    return {'type': 'FeatureCollection', 'features': [{'type': 'Feature',
        'id': 'manual:Budapest:Molnar-sziget', 'properties': properties,
        'geometry': {'type': 'Polygon', 'coordinates': [exterior]}}]}


if __name__ == '__main__':
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n')
    print(OUTPUT.relative_to(ROOT))
