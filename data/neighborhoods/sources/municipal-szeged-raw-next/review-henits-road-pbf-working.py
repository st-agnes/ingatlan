"""Read-only fidelity check of the23 original road-control ways against local PBF."""
from pathlib import Path
import hashlib
import json

import osmium

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
PBF = REPO / '.local/neighborhoods/hungary-latest.osm.pbf'
EXPECTED_HASH = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
REFERENCE = ROOT / 'registration-road-controls.geojson'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


assert sha(PBF) == EXPECTED_HASH
features = json.loads(REFERENCE.read_text())['features']
expected = {f['properties']['source']['osmId']: f for f in features}
assert len(expected) == len(features) == 23
ways, node_ids = {}, set()
for way in osmium.FileProcessor(str(PBF), entities=osmium.osm.WAY).with_filter(osmium.filter.IdFilter(expected)):
    refs = [node.ref for node in way.nodes]
    ways[way.id] = {'nodeRefs': refs, 'tags': dict(way.tags), 'version': way.version, 'timestamp': str(way.timestamp)}
    node_ids.update(refs)
assert set(ways) == set(expected)
nodes = {}
for node in osmium.FileProcessor(str(PBF), entities=osmium.osm.NODE).with_filter(osmium.filter.IdFilter(node_ids)):
    assert node.location.valid()
    nodes[node.id] = [node.location.lon, node.location.lat]
assert set(nodes) == node_ids
checks, occurrences = [], 0
for ident, feature in expected.items():
    source, actual = feature['properties']['source'], ways[ident]
    assert feature['geometry']['type'] == 'LineString'
    assert source['nodeRefs'] == actual['nodeRefs']
    assert source['tags'] == actual['tags']
    assert source['objectVersion'] == actual['version']
    assert source['objectTimestamp'] == actual['timestamp']
    assert len(feature['geometry']['coordinates']) == len(actual['nodeRefs'])
    difference = 0.0
    for co, ref in zip(feature['geometry']['coordinates'], actual['nodeRefs']):
        difference = max(difference, *(abs(a - b) for a, b in zip(co, nodes[ref])))
        occurrences += 1
    assert difference == 0
    checks.append({'id': f'osm:way:{ident}', 'completeNodeRefsEqual': True, 'completeTagsEqual': True,
                   'versionAndTimestampEqual': True, 'nodeCount': len(actual['nodeRefs']),
                   'maximumCoordinateDifferenceDegrees': difference})
review = {'schemaVersion': 1, 'status': 'all23_complete_original_control_ways_match_pinned_PBF',
          'reviewer': 'zala_semantic_qa, independent of road extraction/registration',
          'inputs': [{'path': str(PBF.relative_to(REPO)), 'sha256': EXPECTED_HASH},
                     {'path': REFERENCE.name, 'sha256': sha(REFERENCE)},
                     {'path': Path(__file__).name, 'sha256': sha(Path(__file__))}],
          'method': 'C++ entity/ID-filtered passes over original ways, then their original nodes. Compare complete ordered refs, tags, versions, timestamps and all coordinates.',
          'wayCount': len(checks), 'uniqueOriginalNodes': len(nodes), 'coordinateOccurrences': occurrences,
          'maximumCoordinateDifferenceDegrees': 0, 'checks': checks,
          'limits': 'Reference fidelity only. Does not establish source-map feature correspondence or positional accuracy.',
          'networkCallsPerformed': False, 'globalRegistryModified': False, 'frozenPacketsModified': False}
(ROOT / 'henits-road-pbf-review-working.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': review['status'], 'ways': len(checks), 'uniqueNodes': len(nodes), 'coordinates': occurrences}))
