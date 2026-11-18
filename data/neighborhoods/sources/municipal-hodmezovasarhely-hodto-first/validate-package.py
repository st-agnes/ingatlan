#!/usr/bin/env python3
"""Read-only package check; converter replay writes only to a temporary folder."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def read(name):
    return json.loads((OUT / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = read('manifest.json')
    for name, expected in manifest['fileSha256'].items():
        if sha(OUT / name) != expected:
            raise ValueError('Changed package artifact: ' + name)
    original = read('hod-hodto-frozen-handoff.json')
    for name, expected in original['files'].items():
        if sha(OUT / name) != expected:
            raise ValueError('Changed original frozen staging input: ' + name)
    quote = read('hod-hodto-semantic-quote-proof.json')
    assert quote['literalQuoteWordCount'] == len(quote['literalQuote'].split()) == 8
    audit = read('hod-independent-review.json')
    assert audit['allRequiredTechnicalChecksPassed']
    assert audit['sourceSemanticReview']['sourceQuoteWasIndependentlyRefetchedByThisReviewer'] is False
    entry = read('package-registry-entry.json')
    candidate_path = ROOT / entry['path']
    assert candidate_path.resolve() == OUT / 'hod-hodto-first-candidate.geojson'
    assert sha(candidate_path) == entry['sha256']
    feature = read('hod-hodto-first-candidate.geojson')['features'][0]
    properties = feature['properties']
    assert properties['estimated'] is True and properties['confidence'] == 'low'
    assert properties['usableForAddressAssignment'] is False
    geometry = shape(feature['geometry'])
    reference = read('hod-municipality-reference.geojson')['features'][0]
    original_feature_hash = hashlib.sha256(json.dumps(reference, ensure_ascii=False,
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert original_feature_hash == read('hod-municipality-reference-proof.json')['sourceFeatureCanonicalJsonSha256']
    municipality = shape(reference['geometry'])
    assert geometry.is_valid and not geometry.interiors and municipality.covers(geometry)
    metric = transform(Transformer.from_crs(4326, 23700, always_xy=True).transform, geometry)
    assert abs(metric.area - read('hod-hodto-first-candidate-proof.json')['areaSquareMeters']) < 1e-6
    replay_inputs = ['hod-build-first.py', 'hod-local-lines.geojson', 'hod-local-name-points.geojson',
                     'hod-source-research.json']
    replay_outputs = ['hod-hodto-first-candidate.geojson', 'hod-hodto-boundary-controls.geojson',
                      'hod-hodto-first-candidate-proof.json']
    with tempfile.TemporaryDirectory(prefix='hodto-package-replay-') as temporary:
        directory = Path(temporary)
        for name in replay_inputs:
            shutil.copyfile(OUT / name, directory / name)
        env = os.environ.copy()
        env['PYTHONPATH'] = str(ROOT / '.local/geodata') + os.pathsep + env.get('PYTHONPATH', '')
        subprocess.run([sys.executable, str(directory / 'hod-build-first.py')], cwd=ROOT,
                       env=env, check=True, stdout=subprocess.PIPE, text=True)
        for name in replay_outputs:
            if sha(directory / name) != sha(OUT / name):
                raise ValueError('Converter replay differs: ' + name)
    validator = """import fs from 'node:fs';
import {validateGeometry} from './scripts/neighborhoods/build.mjs';
const f=JSON.parse(fs.readFileSync(process.argv[1])).features[0];
process.stdout.write(JSON.stringify(validateGeometry(f.geometry)));
"""
    result = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', validator,
                         str(candidate_path)], cwd=ROOT, text=True))
    assert result['valid'] is True and result['vertices'] == 126
    print(json.dumps({'packageFileHashesChecked': len(manifest['fileSha256']),
                      'originalFrozenInputHashesChecked': len(original['files']),
                      'byteIdenticalConverterReplayOutputs': len(replay_outputs),
                      'projectGeometryValidator': result, 'insideArchivedMunicipality': True,
                      'independentTechnicalReviewPassed': True, 'sourceGeometryVerified': False,
                      'estimated': True, 'confidence': 'low', 'usableForAddressAssignment': False}))


if __name__ == '__main__':
    main()
