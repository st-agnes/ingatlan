#!/usr/bin/env python3
"""Independently compare the frozen road and name inputs with the original PBF.

PYTHONPATH=.local/geodata python3 .../verify-original-pbf.py --check
If the country PBF is absent, --check checks the frozen proof and input hashes;
it reports that limitation on stdout without rewriting the original proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PBF_SHA = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
PBF_RELATIVE = '.local/neighborhoods/hungary-latest.osm.pbf'
INPUTS = ['control-roads.geojson', 'current-name-points.geojson']
PROOF = 'original-pbf-verification.json'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def verify(pbf, check=False):
    road_features = json.loads((OUT / INPUTS[0]).read_text())['features']
    point_features = json.loads((OUT / INPUTS[1]).read_text())['features']
    input_hashes = {name: sha(OUT / name) for name in INPUTS}
    roads = {feature['properties']['source']['osmId']: feature for feature in road_features}
    names = {feature['properties']['source']['osmId']: feature for feature in point_features}
    if len(roads) != 20 or len(names) != 3:
        raise ValueError('Unexpected frozen input object count')
    expected_nodes = {}
    for way_id, feature in roads.items():
        source = feature['properties']['source']
        refs, coords = source['nodeRefs'], feature['geometry']['coordinates']
        if (feature['id'] != 'osm:way:' + str(way_id) or len(refs) != len(coords)
                or source['sourcePbfSha256'] != PBF_SHA or not source['geometryUnmodified']):
            raise ValueError('Changed source-way identity or node pairing')
        for node_id, coord in zip(refs, coords):
            if node_id in expected_nodes and expected_nodes[node_id] != coord:
                raise ValueError('Conflicting archived node coordinates')
            expected_nodes[node_id] = coord
    for node_id, feature in names.items():
        source = feature['properties']['source']
        if feature['id'] != 'osm:node:' + str(node_id) or source['pbfSha256'] != PBF_SHA:
            raise ValueError('Changed current-name node identity')
        coord = feature['geometry']['coordinates']
        if node_id in expected_nodes and expected_nodes[node_id] != coord:
            raise ValueError('Name/control coordinate conflict')
        expected_nodes[node_id] = coord

    if not pbf.exists():
        if not check:
            raise ValueError('Original PBF is required to create the proof')
        proof = json.loads((OUT / PROOF).read_text())
        if (proof['inputSha256'] != input_hashes or proof['sourcePbfSha256'] != PBF_SHA
                or proof['wayCount'] != len(roads) or proof['namePointCount'] != len(names)
                or proof['uniqueComparedNodeCount'] != len(expected_nodes)
                or not proof['allOriginalWayNodeSequencesAndCoordinatesMatch']
                or not proof['allOriginalWayTagsVersionsAndTimestampsMatch']
                or not proof['allOriginalNameNodeCoordinatesTagsVersionsAndTimestampsMatch']):
            raise ValueError('Archived PBF proof is not bound to these exact inputs')
        print(json.dumps({'mode': 'check', 'fullPbfAvailable': False,
                          'archivedProofAndInputHashesVerified': True,
                          'originalPbfReReadDuringThisRun': False,
                          'wayCount': len(roads), 'namePointCount': len(names)}, ensure_ascii=False))
        return

    if sha(pbf) != PBF_SHA:
        raise ValueError('Unexpected original PBF checksum')
    import osmium
    ids = set(expected_nodes) | set(roads)
    seen_nodes, seen_ways, name_records, way_records = set(), set(), {}, {}
    processor = osmium.FileProcessor(str(pbf), entities=osmium.osm.NODE | osmium.osm.WAY)
    processor = processor.with_filter(osmium.filter.IdFilter(ids))
    for obj in processor:
        if obj.is_node():
            if obj.id not in expected_nodes:
                continue
            coord = [obj.location.lon, obj.location.lat]
            if coord != expected_nodes[obj.id]:
                raise ValueError('Original node coordinate differs: ' + str(obj.id))
            seen_nodes.add(obj.id)
            if obj.id in names:
                feature = names[obj.id]
                source = feature['properties']['source']
                tags = dict(obj.tags)
                if (tags != source['tags'] or obj.version != source['objectVersion']
                        or str(obj.timestamp) != source['objectTimestamp']
                        or tags.get('name') != feature['properties']['name']
                        or tags.get('place') != feature['properties']['place']):
                    raise ValueError('Original name-node metadata differs: ' + str(obj.id))
                name_records[obj.id] = {'osmNodeId': obj.id, 'name': tags['name'],
                                        'coordinates': coord, 'objectVersion': obj.version,
                                        'objectTimestamp': str(obj.timestamp), 'tagsMatch': True,
                                        'coordinatesMatch': True, 'versionAndTimestampMatch': True}
        elif obj.is_way() and obj.id in roads:
            feature = roads[obj.id]
            source = feature['properties']['source']
            refs = [node.ref for node in obj.nodes]
            if (refs != source['nodeRefs'] or dict(obj.tags) != source['tags']
                    or obj.version != source['objectVersion']
                    or str(obj.timestamp) != source['objectTimestamp']):
                raise ValueError('Original way sequence or metadata differs: ' + str(obj.id))
            seen_ways.add(obj.id)
            way_records[obj.id] = {'osmWayId': obj.id, 'name': source['tags'].get('name', ''),
                                   'nodeCount': len(refs), 'nodeReferenceSequenceMatches': True,
                                   'everyNodeCoordinateMatches': True, 'tagsMatch': True,
                                   'objectVersion': obj.version, 'objectTimestamp': str(obj.timestamp),
                                   'versionAndTimestampMatch': True}
    if seen_nodes != set(expected_nodes) or seen_ways != set(roads) or set(name_records) != set(names):
        raise ValueError('Some requested original source objects are absent')
    proof = {'schemaVersion': 1,
             'reviewScope': 'Independent original-PBF identity check for frozen geographical-control roads and current-name points only. This does not validate historical raster junction identity or neighborhood boundary extent.',
             'reviewMethod': 'A separate C++-filtered osmium FileProcessor pass reads literal original nodes and ways. No derivation script, generated geometry or location interpolation is used.',
             'sourcePbfPath': PBF_RELATIVE, 'sourcePbfSha256': PBF_SHA,
             'sourcePbfBytes': pbf.stat().st_size, 'inputSha256': input_hashes,
             'wayCount': len(roads), 'namePointCount': len(names),
             'uniqueComparedNodeCount': len(expected_nodes),
             'pairedWayNodeCoordinateCountIncludingSharedNodes': sum(len(f['properties']['source']['nodeRefs']) for f in roads.values()),
             'wayRecords': [way_records[key] for key in sorted(way_records)],
             'namePointRecords': [name_records[key] for key in sorted(name_records)],
             'allOriginalWayNodeSequencesAndCoordinatesMatch': True,
             'allOriginalWayTagsVersionsAndTimestampsMatch': True,
             'allOriginalNameNodeCoordinatesTagsVersionsAndTimestampsMatch': True,
             'originalPbfWasActuallyReadToCreateThisProof': True,
             'historicalSourceFeatureCorrespondenceValidated': False,
             'absoluteAccuracyMeters': None, 'usableForAddressAssignment': False,
             'conclusion': 'PASS for literal OSM source identity. Historical map registration and source-cell semantics remain separate review questions.'}
    payload = encoded(proof)
    if check:
        if (OUT / PROOF).read_bytes() != payload:
            raise ValueError('Missing or stale original-PBF verification proof')
    else:
        (OUT / PROOF).write_bytes(payload)
    print(json.dumps({'mode': 'check' if check else 'build', 'fullPbfAvailable': True,
                      'originalPbfReReadDuringThisRun': True, 'wayCount': len(roads),
                      'namePointCount': len(names), 'uniqueComparedNodeCount': len(expected_nodes),
                      'allLiteralSourceObjectsMatch': True}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--pbf', type=Path, default=ROOT / PBF_RELATIVE)
    args = parser.parse_args()
    verify(args.pbf, args.check)
