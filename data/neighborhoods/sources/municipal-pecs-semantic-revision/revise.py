#!/usr/bin/env python3
"""Revise one source category without changing any frozen geometry or source file."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ORIGINAL = 'data/neighborhoods/sources/municipal-pecs-first-inferred/source-inferred.geojson'
RECOMMENDATION = 'data/neighborhoods/sources/municipal-pecs-remaining-next/first-cohort-semantic-recommendation.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def outputs():
    original = (ROOT / ORIGINAL).read_bytes()
    recommendation_bytes = (ROOT / RECOMMENDATION).read_bytes()
    recommendation = json.loads(recommendation_bytes)
    assert digest(original) == recommendation['frozenSourceGeojsonSha256']
    document = json.loads(original)
    before = {f['id']: json.dumps(f['geometry'], sort_keys=True, separators=(',', ':'))
              for f in document['features']}
    names_before = [(f['id'], f['properties']['name']) for f in document['features']]
    assert len(document['features']) == 33
    targets = [f for f in document['features'] if f['id'] == recommendation['frozenFeatureId']]
    assert len(targets) == 1
    feature = targets[0]
    geometry_bytes = json.dumps(feature['geometry'], sort_keys=True,
                                ensure_ascii=False, separators=(',', ':')).encode()
    assert digest(geometry_bytes) == recommendation['exactGeometrySha256']
    p = feature['properties']
    assert p['name'] == recommendation['sourceName']
    assert p['candidateBoundaryKind'] == recommendation['existingFrozenCandidateBoundaryKind']
    assert p['estimated'] is True and p['usableForAddressAssignment'] is False
    previous = dict(p['sourceNameEvidence'])
    p['candidateBoundaryKind'] = recommendation['recommendedCandidateBoundaryKind']
    p['sourceNameEvidence']['previousSemanticInterpretation'] = {
        'semanticKind': previous['semanticKind'], 'evidence': previous['evidence']}
    p['sourceNameEvidence']['semanticKind'] = recommendation['recommendedSemanticKind']
    p['sourceNameEvidence']['evidence'] = (
        'Table 8, row XIII explicitly designates this sole unit as an independent quarter '
        'because of its strategic and structural role. Economic function is not a reason '
        'to exclude this source-defined quarter. Geographic placement remains inferred.')
    p['semanticRevision'] = {
        'reviewPath': str((HERE / 'review.json').relative_to(ROOT)),
        'originalSourceSha256': digest(original),
        'originalGeometrySha256': recommendation['exactGeometrySha256'],
        'classificationOnly': True, 'geometryChanged': False}
    assert all(json.dumps(f['geometry'], sort_keys=True, separators=(',', ':')) == before[f['id']]
               for f in document['features'])
    assert [(f['id'], f['properties']['name']) for f in document['features']] == names_before
    geometry = encoded(document)
    review = {
        'schemaVersion': 1, 'status': 'source_semantic_revision_applied',
        'recommendationPath': RECOMMENDATION,
        'recommendationSha256': digest(recommendation_bytes),
        'originalSourcePath': ORIGINAL, 'originalSourceSha256': digest(original),
        'revisedSourceSha256': digest(geometry), 'featureId': feature['id'],
        'previousCandidateKind': 'planning_unit', 'candidateKind': 'neighbourhood',
        'originalGeometryReviewPath': 'data/neighborhoods/sources/municipal-pecs-first-inferred/independent-review.json',
        'sourceEvidence': recommendation['sourceEvidence'],
        'all33GeometriesUnchanged': True, 'sourceNamesUnchanged': True,
        'totalInferredCountChange': 0, 'primaryCountChange': 0,
        'geographicPlacementVerified': False, 'usableForAddressAssignment': False,
        'meaning': 'A documented category correction. The original frozen snapshot and '
                   'its historical audit remain intact. No new geometry, name, positional '
                   'accuracy or address-assignment approval follows.'}
    entry = json.loads((HERE / 'original-registry-entry.json').read_bytes())
    entry['classificationRevisionFrom'] = {'path': ORIGINAL, 'sha256': digest(original)}
    entry['path'] = str((HERE / 'source-inferred-reclassified.geojson').relative_to(ROOT))
    entry['sha256'] = digest(geometry)
    entry['reviewPath'] = str((HERE / 'review.json').relative_to(ROOT))
    entry['method'] += ' Classification-only revision of one source-defined economic quarter; all original geometries are unchanged.'
    result = {'source-inferred-reclassified.geojson': geometry,
              'review.json': encoded(review), 'registry-entry.json': encoded(entry)}
    manifest = {'schemaVersion': 1, 'status': 'classification_only_frozen_revision',
                'sourceInputs': [{'path': path, 'sha256': digest((ROOT / path).read_bytes())}
                                 for path in [ORIGINAL, RECOMMENDATION]],
                'files': [{'path': name, 'sha256': digest(data)} for name, data in result.items()]}
    manifest['files'] += [{'path': name, 'sha256': digest((HERE / name).read_bytes())}
                          for name in ['revise.py', 'original-registry-entry.json']]
    result['manifest.json'] = encoded(manifest)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for name, content in outputs().items():
        path = HERE / name
        if args.check:
            assert path.read_bytes() == content, 'Stale semantic revision: ' + name
        else:
            path.write_bytes(content)
    print('Pécs category revision verified: 33 unchanged inferred geometries, no primary increase.')


if __name__ == '__main__':
    main()
