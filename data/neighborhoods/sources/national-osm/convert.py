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
COMMIT = '7d3749a06d785d9329fc2f113c8fbc4cec43256a'
REPOSITORY = 'ferenci-tamas/MagyarorszagKozutiElerhetoseg'
SHAS = {
    'admin10.cpg': '3ad133c048f2189041151425a73485649e6c32c0',
    'admin10.dbf': '9e02b8173706aa59514ff323f89ac1e2639455e3',
    'admin10.prj': '49dc10298e72da81ed6794dfdc272e5deff7812e',
    'admin10.shp': '3339982093fa442e05afb05f2fcc09a18071d685',
    'admin10.shx': '350bed8554ab727057742f55815acca86a4fc926',
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
        identifier = f'osm-hu-20221123:admin10:{record}'
        features.append({'type': 'Feature', 'id': identifier,
                         'properties': {'id': identifier, 'name': row['NAME'],
                                        'city': 'Budapest', 'adminLevel': 10,
                                        'sourceRecord': record,
                                        'source': 'national-osm-admin10',
                                        'sourceCommit': COMMIT,
                                        'sourceSnapshotDate': '2022-11-23',
                                        'license': 'ODbL-1.0',
                                        'attribution': '© OpenStreetMap contributors',
                                        'geometryReview': 'historical-not-rechecked'},
                         'geometry': geometry(rings)})
    assert len(rows) == len(features) == 203
    assert len({f['properties']['name'] for f in features}) == len(features)
    (ROOT/'admin10.geojson').write_text(json.dumps({
        'type': 'FeatureCollection', 'name': 'Budapest OSM admin10 snapshot 2022-11-23',
        'features': features}, ensure_ascii=False, separators=(',', ':'))+'\n')
    manifest = {
        'source': 'OpenStreetMap Hungarian administrative boundary export',
        'originalDownloadUrl': 'http://data2.openstreetmap.hu/hatarok/kozighatarok.zip',
        'mirrorRepository': REPOSITORY, 'sourceCommit': COMMIT,
        'sourceCommitDate': '2022-11-23T01:28:11Z',
        'retrievedAt': '2026-11-13',
        'upstreamDirectoryUrl': f'https://github.com/{REPOSITORY}/tree/{COMMIT}/kozighatarok',
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
            'All 203 admin10 records are in Budapest; this is not countrywide city coverage.',
            'The mirror contains no admin11 layer.',
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
