#!/usr/bin/env python3
"""Technical cell integrity checks; no claim of quarter-boundary accuracy."""
import hashlib, json, unicodedata
from pathlib import Path
from shapely.geometry import Point, shape

HERE = Path(__file__).resolve().parent
norm = lambda value: ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())
features = json.loads((HERE/'features.geojson').read_text())['features']
known = {tuple(key) for key in json.loads((HERE/'baseline-known-keys.json').read_text())['keys']}
contexts = {f['id']: shape(f['geometry']) for f in json.loads((HERE/'source-contexts.geojson').read_text())['features']}
roads = {f['id'] for f in json.loads((HERE/'source-barriers.geojson').read_text())['features']}
keys = [(f['properties']['municipality'], norm(f['properties']['name'])) for f in features]
check = {
    'schemaVersion': 1, 'featureCount': len(features),
    'validGeometryCount': sum(shape(f['geometry']).is_valid and not shape(f['geometry']).is_empty for f in features),
    'uniqueMunicipalityNameCount': len(set(keys)),
    'duplicateWithFrozenBaselineCount': sum(key in known for key in keys),
    'everyCellContainsItsSourceNamePoint': all(shape(f['geometry']).covers(Point(f['properties']['namePoint']['coordinates'])) for f in features),
    'everyCellHasExactlyOneMissingName': all(f['properties']['missingNameCount'] == 1 for f in features),
    'everyBoundingSourceWayRetained': all(row['id'] in roads for f in features for row in f['properties']['boundingSourceWays']),
    'everyCellIsSmallerThanItsDenseContext': all(f['properties']['areaSquareMetres'] < .9*f['properties']['sourceContextAreaSquareMetres'] for f in features),
    'allWithinRecordedCoarseAreaBounds': all(f['properties']['coarseAreaMinimumSquareMetres'] <= f['properties']['areaSquareMetres'] <= f['properties']['coarseAreaCapSquareMetres'] for f in features),
    'allExplicitLowConfidenceEstimates': all(f['properties']['method'] == 'physical_barrier_cell_estimate' and f['properties']['estimated'] is True and f['properties']['qualityScore'] == 15 for f in features),
    'circlesGenerated': 0, 'inventedDividers': 0,
    'geographicBoundaryAccuracyReviewed': False,
    'featuresSha256': hashlib.sha256((HERE/'features.geojson').read_bytes()).hexdigest(),
}
assert check['featureCount'] <= 200 and check['validGeometryCount'] == len(features)
assert check['uniqueMunicipalityNameCount'] == len(features) and check['duplicateWithFrozenBaselineCount'] == 0
for key, value in check.items():
    if key.startswith('every') or key.startswith('all'):
        assert value, key
(HERE/'validation.json').write_text(json.dumps(check, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(check, ensure_ascii=False))
