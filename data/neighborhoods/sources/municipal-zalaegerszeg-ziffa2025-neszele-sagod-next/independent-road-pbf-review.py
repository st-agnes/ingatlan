"""Verify every archived complete road way directly against the pinned local PBF."""
from pathlib import Path
import hashlib
import json

import osmium

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
PBF = REPO / '.local/neighborhoods/hungary-latest.osm.pbf'
EXPECTED_PBF_SHA256 = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
REFERENCE = ROOT / 'road-geographic-reference.geojson'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


assert sha(PBF) == EXPECTED_PBF_SHA256
features = json.loads(REFERENCE.read_text())['features']
expected = {f['properties']['source']['osmId']: f for f in features}
assert len(features) == len(expected) == 86
assert all(f['geometry']['type'] == 'LineString' for f in features)

# C++ entity and ID filters avoid invoking Python on unrelated country objects.
ways = {}
node_ids = set()
for way in osmium.FileProcessor(str(PBF), entities=osmium.osm.WAY).with_filter(osmium.filter.IdFilter(expected)):
    refs = [n.ref for n in way.nodes]
    ways[way.id] = {'nodeRefs': refs, 'tags': dict(way.tags), 'version': way.version,
                    'timestamp': str(way.timestamp)}
    node_ids.update(refs)
assert set(ways) == set(expected)
nodes = {}
for node in osmium.FileProcessor(str(PBF), entities=osmium.osm.NODE).with_filter(osmium.filter.IdFilter(node_ids)):
    assert node.location.valid()
    nodes[node.id] = [node.location.lon, node.location.lat]
assert set(nodes) == node_ids

checks = []
maximum_coordinate_difference = 0.0
coordinate_count = 0
for osm_id, feature in expected.items():
    source = feature['properties']['source']
    actual = ways[osm_id]
    assert source['nodeRefs'] == actual['nodeRefs']
    assert source['tags'] == actual['tags']
    assert source['objectVersion'] == actual['version']
    assert source['objectTimestamp'] == actual['timestamp']
    coordinates = feature['geometry']['coordinates']
    assert len(coordinates) == len(actual['nodeRefs'])
    maximum_way_difference = 0.0
    for reference_coordinate, node_id in zip(coordinates, actual['nodeRefs']):
        maximum_way_difference = max(maximum_way_difference, *(abs(a - b) for a, b in zip(reference_coordinate, nodes[node_id])))
        coordinate_count += 1
    assert maximum_way_difference < 1e-10
    maximum_coordinate_difference = max(maximum_coordinate_difference, maximum_way_difference)
    checks.append({'id': f'osm:way:{osm_id}', 'nodeCount': len(actual['nodeRefs']),
                   'completeNodeRefsEqualInOriginalOrder': True, 'allTagsEqual': True,
                   'versionAndTimestampEqual': True,
                   'maximumCoordinateDifferenceDegrees': maximum_way_difference})

review = {
    'schemaVersion': 1,
    'reviewKind': 'independent_direct_local_pbf_complete_road_way_verification',
    'reviewer': 'independent child agent zala_semantic_qa',
    'status': 'all86_complete_original_road_ways_match_pinned_local_pbf',
    'inputs': [{'path': str(PBF.relative_to(REPO)), 'sha256': EXPECTED_PBF_SHA256},
               {'path': REFERENCE.name, 'sha256': sha(REFERENCE)},
               {'path': Path(__file__).name, 'sha256': sha(Path(__file__))}],
    'algorithm': 'Entity-restricted FileProcessor plus C++ IdFilter first selects86ways, then all their original node IDs. Compare complete ordered nodeRefs, tags, versions, timestamps and every original node coordinate.',
    'wayCount': len(checks), 'uniqueNodeCount': len(nodes),
    'coordinateOccurrencesChecked': coordinate_count,
    'maximumCoordinateDifferenceDegrees': maximum_coordinate_difference,
    'generatedVerticesOrClippedSegments': False,
    'checks': checks,
    'limits': 'Confirms local reference fidelity only. It does not establish source-map correspondence, map accuracy, neighborhood boundaries or address suitability.',
    'networkCallsPerformed': False,
    'globalRegistryModified': False,
    'hathazFrozenPacketModified': False,
}
(ROOT / 'independent-road-pbf-review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': review['status'], 'wayCount': len(checks),
                  'uniqueNodeCount': len(nodes), 'coordinateOccurrencesChecked': coordinate_count,
                  'maximumCoordinateDifferenceDegrees': maximum_coordinate_difference}))
