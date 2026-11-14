"""Recreate literal local OSM control ways; selection box is only a retrieval filter.

PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-new-city-scout-next/hod-extract-local.py
"""
import hashlib
import json
import pathlib
import tempfile

import osmium

ROOT = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).resolve().parent
PBF = ROOT / '.local/neighborhoods/hungary-latest.osm.pbf'
EXPECTED_SHA = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'


def inside(lon, lat):
    return 20.27 <= lon <= 20.4 and 46.37 <= lat <= 46.47


def main():
    actual = hashlib.file_digest(PBF.open('rb'), 'sha256').hexdigest()
    if actual != EXPECTED_SHA:
        raise ValueError('Country PBF fingerprint changed')
    ways, points = [], []

    class Handler(osmium.SimpleHandler):
        def way(self, way):
            tags = dict(way.tags)
            if not any(tags.get(key) for key in ['highway', 'railway', 'waterway', 'barrier']):
                return
            if not len(way.nodes) or not way.nodes[0].location.valid():
                return
            if not inside(way.nodes[0].lon, way.nodes[0].lat):
                return
            if any(not node.location.valid() for node in way.nodes):
                raise ValueError('Incomplete local way: ' + str(way.id))
            ways.append({'type': 'Feature', 'properties': {
                'osmWayId': way.id, 'tags': tags,
                'nodeRefs': [node.ref for node in way.nodes],
                'version': way.version, 'timestamp': str(way.timestamp)
            }, 'geometry': {'type': 'LineString', 'coordinates': [[node.lon, node.lat] for node in way.nodes]}})

        def node(self, node):
            if node.tags.get('name') and node.tags.get('place') and inside(node.location.lon, node.location.lat):
                points.append({'type': 'Feature', 'properties': {
                    'osmNodeId': node.id, 'tags': dict(node.tags),
                    'version': node.version, 'timestamp': str(node.timestamp)
                }, 'geometry': {'type': 'Point', 'coordinates': [node.location.lon, node.location.lat]}})

    with tempfile.TemporaryDirectory(prefix='otthonra-hod-osm-') as temporary:
        Handler().apply_file(str(PBF), locations=True, idx='sparse_file_array,' + temporary + '/nodes.idx')
    for name, features in [('hod-local-lines.geojson', ways), ('hod-local-name-points.geojson', points)]:
        (OUT / name).write_text(json.dumps({'type': 'FeatureCollection', 'features': features}, ensure_ascii=False, indent=2) + '\n')
    proof = {'sourcePbfSha256': actual, 'sourcePbfBytes': PBF.stat().st_size,
             'method': 'Literal OSM way/node scan; rectangle used for retrieval only, never a neighborhood polygon.',
             'lineCount': len(ways), 'namePointCount': len(points), 'license': 'ODbL-1.0',
             'attribution': '© OpenStreetMap contributors', 'licenseUrl': 'https://www.openstreetmap.org/copyright'}
    (OUT / 'hod-local-lines-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(proof, ensure_ascii=False))


if __name__ == '__main__':
    main()
