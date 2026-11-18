#!/usr/bin/env python3
"""Convert the preserved OSM admin10 snapshot without third-party packages.

The .prj declares EPSG:3857. Original ring vertices are transformed, never
synthesised from points, bounding boxes or a current map display.
"""
import hashlib
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent
COMMIT = '2f7a91ee1f320e6a08488ef8413715be13abf226'
REPOSITORY = 'ferenci-tamas/BudapestiElerhetoseg'
SHAS = {
    'admin10.cpg': '3ad133c048f2189041151425a73485649e6c32c0',
    'admin10.dbf': '42d3d2c7ab1c2f2ce069a3ae0323ee7d3ff5e786',
    'admin10.prj': '49dc10298e72da81ed6794dfdc272e5deff7812e',
    'admin10.shp': '20ac849eda8eacf04712cc748ce941967b7bce81',
    'admin10.shx': 'c03598f6f988fdde7f94e83207947c5af8168796',
}


def area(ring):
    return sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(ring, ring[1:]))/2


def contains(ring, point):
    x, y = point
    inside = False
    for (ax, ay), (bx, by) in zip(ring, ring[1:]):
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            inside = not inside
    return inside


def geometry(rings):
    # Parent containment preserves multipart polygons and holes even if an
    # upstream ring happens to have the wrong ESRI orientation.
    ordered = sorted(rings, key=lambda r: abs(area(r)), reverse=True)
    parents, depths = [], []
    for i, ring in enumerate(ordered):
        parent = next((j for j in range(i-1, -1, -1)
                       if contains(ordered[j], ring[0])), None)
        parents.append(parent)
        depths.append(0 if parent is None else depths[parent]+1)
    polygons, outer_index = [], {}
    for i, ring in enumerate(ordered):
        outer = depths[i] % 2 == 0
        # RFC7946 exterior rings counterclockwise, holes clockwise.
        if (area(ring) > 0) != outer:
            ring = list(reversed(ring))
        if outer:
            outer_index[i] = len(polygons)
            polygons.append([ring])
        else:
            polygons[outer_index[parents[i]]].append(ring)
    return {'type': 'Polygon', 'coordinates': polygons[0]} if len(polygons) == 1 else {
        'type': 'MultiPolygon', 'coordinates': polygons}


def decode_dbf(data):
    count, header, row_length = struct.unpack_from('<IHH', data, 4)
    fields, offset = [], 32
    while data[offset] != 13:
        fields.append((data[offset:offset+11].split(b'\0')[0].decode('ascii'),
                       data[offset+16]))
        offset += 32
    rows = []
    for i in range(count):
        offset = header+i*row_length
        assert data[offset] != ord('*'), 'Deleted DBF record'
        offset += 1
        row = {}
        for name, length in fields:
            row[name] = data[offset:offset+length].decode('utf-8').strip()
            offset += length
        rows.append(row)
    return rows


def main():
    sources = []
    for name, expected in SHAS.items():
        data = (ROOT/name).read_bytes()
        actual = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        assert actual == expected, f'Original blob mismatch: {name}'
        sources.append({'path': name, 'bytes': len(data), 'gitBlobSha1': actual,
                        'sha256': hashlib.sha256(data).hexdigest()})
    assert 'AUTHORITY["EPSG","3857"]' in (ROOT/'admin10.prj').read_text()
    assert (ROOT/'admin10.cpg').read_text() == 'UTF-8'
    rows = decode_dbf((ROOT/'admin10.dbf').read_bytes())
    data = (ROOT/'admin10.shp').read_bytes()
    assert struct.unpack_from('>i', data, 0)[0] == 9994
    assert struct.unpack_from('<ii', data, 28) == (1000, 5)
    assert struct.unpack_from('>i', data, 24)[0]*2 == len(data)
    offset, features = 100, []
    while offset < len(data):
        record, words = struct.unpack_from('>ii', data, offset)
        offset += 8
        shape = data[offset:offset+words*2]
        offset += words*2
        assert struct.unpack_from('<i', shape)[0] == 5
        part_count, point_count = struct.unpack_from('<ii', shape, 36)
        parts = list(struct.unpack_from(f'<{part_count}i', shape, 44))+[point_count]
        point_offset = 44+4*part_count
        points = []
        for i in range(point_count):
            x, y = struct.unpack_from('<dd', shape, point_offset+i*16)
            lon = math.degrees(x/6378137)
            lat = math.degrees(2*math.atan(math.exp(y/6378137))-math.pi/2)
            assert 18.8 < lon < 19.4 and 47.3 < lat < 47.7
            points.append([round(lon, 8), round(lat, 8)])
        rings = [points[a:b] for a, b in zip(parts, parts[1:])]
        assert all(len(ring) >= 4 and ring[0] == ring[-1] for ring in rings)
        row = rows[record-1]
        assert row['ADMIN_LEVE'] == '10'
        identifier = f'osm-hu-20250828:admin10:{record}'
        features.append({'type': 'Feature', 'id': identifier,
                         'properties': {'id': identifier, 'name': row['NAME'],
                                        'city': 'Budapest', 'adminLevel': 10,
                                        'sourceRecord': record,
                                        'source': 'national-osm-admin10',
                                        'sourceCommit': COMMIT,
                                        'sourceSnapshotDate': '2025-08-28',
                                        'license': 'ODbL-1.0',
                                        'attribution': '© OpenStreetMap contributors',
                                        'geometryReview': 'historical-not-rechecked'},
                         'geometry': geometry(rings)})
    assert len(rows) == len(features) == 202
    assert len({f['properties']['name'] for f in features}) == len(features)
    (ROOT/'admin10.geojson').write_text(json.dumps({
        'type': 'FeatureCollection', 'name': 'Budapest OSM admin10 snapshot 2025-08-28',
        'features': features}, ensure_ascii=False, separators=(',', ':'))+'\n')
    manifest = {
        'source': 'OpenStreetMap Hungarian administrative boundary export',
        'originalDownloadUrl': 'http://data2.openstreetmap.hu/hatarok/kozighatarok.zip',
        'mirrorRepository': REPOSITORY, 'sourceCommit': COMMIT,
        'sourceCommitDate': '2025-08-28T17:51:58Z',
        'retrievedAt': '2026-11-13',
        'upstreamDirectoryUrl': f'https://github.com/{REPOSITORY}/tree/{COMMIT}',
        'upstreamArchiveUrl': f'https://github.com/{REPOSITORY}/blob/{COMMIT}/kozighatarok.zip',
        'archive': {'name': 'kozighatarok.zip', 'memberDirectory': 'kozighatarok',
                    'bytes': 6285474, 'gitBlobSha1': 'e7f24b8ef283cffee740cd3cd3a3c3ec16b71d0d',
                    'sha256': '2c38117de636dc03d7452db14ecb6c8e66a426e05e2a6d7c8932717bf609db7a'},
        'upstreamProvenanceUrl': f'https://github.com/{REPOSITORY}/blob/{COMMIT}/README.Rmd',
        'license': 'ODbL-1.0',
        'licenseUrl': 'https://opendatacommons.org/licenses/odbl/1-0/',
        'copyrightUrl': 'https://www.openstreetmap.org/copyright',
        'attribution': '© OpenStreetMap contributors',
        'inputCrs': 'EPSG:3857', 'outputCrs': 'EPSG:4326',
        'sourceFiles': sources, 'featureCount': len(features),
        'geojson': {'path': 'admin10.geojson',
                    'bytes': (ROOT/'admin10.geojson').stat().st_size,
                    'sha256': hashlib.sha256((ROOT/'admin10.geojson').read_bytes()).hexdigest()},
        'cities': [{'city': 'Budapest', 'neighborhoodCount': len(features)}],
        'geometryStatus': 'historical-not-rechecked',
        'nameStatus': 'not-individually-rechecked',
        'limitations': [
            'The date is the mirror commit date; exact OSM extraction time is not supplied.',
            'All 202 admin10 records are in Budapest; this is not countrywide city coverage.',
            'The mirror contains no admin11 layer.',
            'Source components were extracted from the verified pinned archive; component Git SHA1 hashes are local content fingerprints.',
            'Compared to the 2022 export: Magdolna negyed is spelled Magdolnanegyed, and Millenniumtelep has no polygon.',
            'The shapefile has no OSM relation IDs; stable IDs identify original record numbers.',
            'No Google tracing, point buffers, bounding-box polygons or manually changed island boundaries.'
        ],
        'records': [{'record': f['properties']['sourceRecord'], 'name': f['properties']['name'],
                     'city': 'Budapest', 'id': f['id'], 'geometryType': f['geometry']['type']}
                    for f in features]
    }
    (ROOT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'features': len(features), 'types': sorted({f['geometry']['type'] for f in features}),
                      'geojsonBytes': (ROOT/'admin10.geojson').stat().st_size}))


if __name__ == '__main__':
    main()
