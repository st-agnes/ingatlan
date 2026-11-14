#!/usr/bin/env python3
"""Read literal local PBF roads/waterways; the selection window is not a boundary."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

import osmium

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PBF = ROOT / '.local/neighborhoods/hungary-latest.osm.pbf'
PBF_SHA256 = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
WINDOW = (17.77, 46.325, 17.82, 46.365)


class Extract(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.features = []

    def way(self, way):
        tags = dict(way.tags)
        if not ('highway' in tags or 'waterway' in tags):
            return
        name = tags.get('name:hu', tags.get('name', ''))
        relevant = (tags.get('ref') == '67'
                    or name in {'Szigetvári utca', 'Zselici út', 'Pécsi utca',
                                'Bartók Béla utca', 'Zrínyi Miklós utca'}
                    or ('waterway' in tags and name in {'Kapos', 'Zselic-patak'}))
        if not relevant:
            return
        if not any(node.location.valid() and WINDOW[0] <= node.lon <= WINDOW[2]
                   and WINDOW[1] <= node.lat <= WINDOW[3] for node in way.nodes):
            return
        assert all(node.location.valid() for node in way.nodes), way.id
        self.features.append({
            'type': 'Feature', 'id': f'osm:way:{way.id}',
            'properties': {
                'name': tags.get('name:hu', tags.get('name', '')),
                'source': {
                    'provider': 'OpenStreetMap', 'osmType': 'way', 'osmId': way.id,
                    'tags': tags, 'nodeRefs': [node.ref for node in way.nodes],
                    'objectVersion': way.version, 'objectTimestamp': str(way.timestamp),
                    'geometryUnmodified': True,
                    'url': f'https://www.openstreetmap.org/way/{way.id}',
                    'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
                },
            },
            'geometry': {'type': 'LineString',
                         'coordinates': [[node.lon, node.lat] for node in way.nodes]},
        })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Compare without writing')
    args = parser.parse_args()
    handler = Extract()
    with tempfile.TemporaryDirectory(prefix='kaposvar-donner-osm-') as temp:
        handler.apply_file(str(PBF), locations=True,
                           idx='sparse_file_array,' + str(Path(temp) / 'nodes.idx'),
                           filters=[osmium.filter.KeyFilter('highway', 'waterway')])
    handler.features.sort(key=lambda feature: feature['properties']['source']['osmId'])
    data = (json.dumps({'type': 'FeatureCollection', 'features': handler.features},
                       ensure_ascii=False, indent=2) + '\n').encode()
    if args.check:
        assert (HERE / 'literal-roads-waterways.geojson').read_bytes() == data
    else:
        (HERE / 'literal-roads-waterways.geojson').write_bytes(data)
    reader = osmium.io.Reader(str(PBF))
    header = reader.header()
    replication_timestamp = header.get('osmosis_replication_timestamp')
    reader.close()
    proof = {
        'schemaVersion': 1,
        'sourcePbfPath': str(PBF.relative_to(ROOT)), 'sourcePbfSha256': PBF_SHA256,
        'sourcePbfHashProvenance': 'Previously independently hashed whole-country PBF; extraction does not rehash it.',
        'sourcePbfReplicationTimestamp': replication_timestamp,
        'acquisitionWindowOnly': WINDOW, 'windowUsedAsBoundary': False,
        'selection': 'Route 67; Szigetvári/Zselici/Pécsi/Bartók/Zrínyi roads; named Kapos and Zselic waterways. Other nearby roads are not retained.',
        'fullWaysPreservedWithoutClipping': True, 'wayCount': len(handler.features),
        'outputSha256': hashlib.sha256(data).hexdigest(),
        'usableForAddressAssignment': False,
    }
    proof_text = json.dumps(proof, indent=2) + '\n'
    if args.check:
        assert (HERE / 'osm-extraction.json').read_text() == proof_text
    else:
        (HERE / 'osm-extraction.json').write_text(proof_text)
    print(json.dumps(proof))
