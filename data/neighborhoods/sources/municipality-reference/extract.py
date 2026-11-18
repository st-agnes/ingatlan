#!/usr/bin/env python3
"""Extract seven municipal reference polygons from the pinned, verified 2025 OSM ZIP."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import zipfile

ROOT = Path(__file__).resolve().parent
COMMIT = '2f7a91ee1f320e6a08488ef8413715be13abf226'
REPOSITORY = 'ferenci-tamas/BudapestiElerhetoseg'
ARCHIVE_SHA256 = '2c38117de636dc03d7452db14ecb6c8e66a426e05e2a6d7c8932717bf609db7a'
ARCHIVE_GIT_SHA1 = 'e7f24b8ef283cffee740cd3cd3a3c3ec16b71d0d'


def git_sha(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    args = parser.parse_args()
    data = args.archive.read_bytes()
    assert len(data) == 6285474 and hashlib.sha256(data).hexdigest() == ARCHIVE_SHA256
    assert git_sha(data) == ARCHIVE_GIT_SHA1
    spec = importlib.util.spec_from_file_location('admin10_converter', ROOT.parent/'national-osm-2025/convert.py')
    converter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(converter)
    layers = {'admin6': ['Budapest'],
              'admin8': ['Dorog', 'Esztergom', 'Debrecen', 'Székesfehérvár', 'Sopron', 'Budaörs']}
    with zipfile.ZipFile(args.archive) as archive:
        components = {layer+'.'+ext: archive.read('kozighatarok/'+layer+'.'+ext)
                      for layer in layers for ext in ['cpg', 'dbf', 'prj', 'shp', 'shx']}
    features = []
    for layer, cities in layers.items():
        assert components[layer+'.cpg'] == b'UTF-8'
        assert 'AUTHORITY["EPSG","3857"]' in components[layer+'.prj'].decode()
        rows = converter.decode_dbf(components[layer+'.dbf'])
        wanted = {i+1: row['NAME'] for i, row in enumerate(rows) if row['NAME'] in cities}
        shape, offset = components[layer+'.shp'], 100
        while offset < len(shape):
            record, words = struct.unpack_from('>ii', shape, offset)
            offset += 8
            part = shape[offset:offset+words*2]
            offset += words*2
            if record not in wanted:
                continue
            assert struct.unpack_from('<i', part)[0] == 5
            part_count, point_count = struct.unpack_from('<ii', part, 36)
            parts = list(struct.unpack_from(f'<{part_count}i', part, 44))+[point_count]
            point_offset = 44+4*part_count
            points = []
            for i in range(point_count):
                x, y = struct.unpack_from('<dd', part, point_offset+i*16)
                lon = math.degrees(x/6378137)
                lat = math.degrees(2*math.atan(math.exp(y/6378137))-math.pi/2)
                assert 16 < lon < 23 and 45 < lat < 49
                points.append([round(lon, 8), round(lat, 8)])
            rings = [points[a:b] for a, b in zip(parts, parts[1:])]
            assert all(len(ring) >= 4 and ring[0] == ring[-1] for ring in rings)
            features.append({'type': 'Feature', 'id': f'osm-hu-20250828:{layer}:{record}',
                             'properties': {'name': wanted[record], 'adminLevel': int(layer[5:]), 'sourceLayer': layer,
                                            'sourceRecord': record, 'license': 'ODbL-1.0',
                                            'attribution': '© OpenStreetMap contributors',
                                            'sourceCommit': COMMIT,
                                            'sourceCommitDate': '2025-08-28T17:51:58Z',
                                            'geometryStatus': 'historical-reference-not-currently-rechecked'},
                             'geometry': converter.geometry(rings)})
    assert len(features) == 7
    document = {'type': 'FeatureCollection', 'features': features}
    encoded = (json.dumps(document, ensure_ascii=False, separators=(',', ':'))+'\n').encode('utf-8')
    (ROOT/'municipalities.geojson').write_bytes(encoded)
    manifest = {
        'source': 'OpenStreetMap Hungarian administrative boundary export',
        'sourceCommit': COMMIT, 'sourceCommitDate': '2025-08-28T17:51:58Z',
        'sourceUrl': f'https://github.com/{REPOSITORY}/blob/{COMMIT}/kozighatarok.zip',
        'archive': {'bytes': 6285474, 'gitBlobSha1': ARCHIVE_GIT_SHA1, 'sha256': ARCHIVE_SHA256},
        'sourceComponents': [{'archiveMember': 'kozighatarok/'+name, 'bytes': len(value),
                              'gitBlobSha1': git_sha(value), 'sha256': hashlib.sha256(value).hexdigest(),
                              'storedInThisDirectory': False} for name, value in components.items()],
        'inputCrs': 'EPSG:3857', 'outputCrs': 'EPSG:4326',
        'geojson': {'path': 'municipalities.geojson', 'bytes': len(encoded),
                    'sha256': hashlib.sha256(encoded).hexdigest()},
        'records': [{'name': f['properties']['name'], 'id': f['id'],
                     'sourceRecord': f['properties']['sourceRecord'], 'sourceLayer': f['properties']['sourceLayer'],
                     'geometryType': f['geometry']['type']} for f in features],
        'license': 'ODbL-1.0', 'licenseUrl': 'https://opendatacommons.org/licenses/odbl/1-0/',
        'attribution': '© OpenStreetMap contributors', 'copyrightUrl': 'https://www.openstreetmap.org/copyright',
        'limitations': ['Seven selected municipality reference polygons; Budapest uses admin6, the other six use admin8.',
                        'The commit date is not a documented OSM extraction date.',
                        'No original admin6/admin8 components are duplicated here; pinned archive and component hashes make extraction reproducible.',
                        'A query intersecting a municipality is not evidence that its result belongs to that municipality.']}
    (ROOT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(manifest['geojson']))


if __name__ == '__main__':
    main()
