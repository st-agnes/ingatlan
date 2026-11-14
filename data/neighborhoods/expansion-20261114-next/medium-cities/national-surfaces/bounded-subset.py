#!/usr/bin/env python3
"""Split frozen shared surfaces into bounded candidates and dense context."""
from pathlib import Path
import collections, hashlib, json

HERE = Path(__file__).resolve().parent
source_path = HERE/'multi-label-features.geojson'
original = source_path.read_bytes()
document = json.loads(original)
bounded, dense = [], []
for feature in document['features']:
    properties = feature['properties']
    labels = properties.get('containedQuarterLabels', [])
    distinct = {(row['municipality'], row['name']) for row in labels}
    count = len(distinct) if labels else properties['distinctContainedQuarterNames']
    (bounded if count <= 4 else dense).append(feature)

layers = [
    ('bounded-multi-label-features.geojson', bounded,
     'Eligible bounded approximate source footprints: at most four distinct named source place labels.'),
    ('dense-context-features.geojson', dense,
     'Context only: dense shared source footprints retained as seeds for later road-based subdivision, excluded from admission.'),
]
for filename, features, role in layers:
    (HERE/filename).write_text(json.dumps({**document, 'features': features,
        'featureCount': len(features), 'subsetRole': role}, ensure_ascii=False, separators=(',', ':'))+'\n')

summary = {
    'schemaVersion': 1, 'fullMultiLabelCount': len(document['features']),
    'boundedMultiLabelCount': len(bounded), 'denseContextExcludedCount': len(dense),
    'sourceOwnNameCount': 84, 'singleLabelAssociationCount': 9,
    'totalEligibleCount': 84+9+len(bounded), 'distinctContainedLabelMaximum': 4,
    'municipalities': dict(sorted(collections.Counter(f['properties']['municipality'] for f in bounded).items())),
    'originalFullMultiLabelSha256': hashlib.sha256(original).hexdigest(),
    'originalFullMultiLabelUnchanged': source_path.read_bytes() == original,
    'files': [{'path': name, 'bytes': (HERE/name).stat().st_size,
               'sha256': hashlib.sha256((HERE/name).read_bytes()).hexdigest()} for name, _, _ in layers],
}
assert summary['originalFullMultiLabelUnchanged']
assert len(bounded)+len(dense) == len(document['features'])
(HERE/'bounded-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({key: summary[key] for key in ['boundedMultiLabelCount', 'denseContextExcludedCount', 'totalEligibleCount']}, ensure_ascii=False))
