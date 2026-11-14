#!/usr/bin/env python3
"""Validate original-shape preservation and expose name-association groups."""
from collections import Counter
import hashlib, json, unicodedata
from pathlib import Path
from shapely.geometry import Point, shape

HERE = Path(__file__).resolve().parent
norm = lambda value: ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())
write = lambda name, value: (HERE/name).write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'))+'\n')
document = json.loads((HERE/'features.geojson').read_text())
features = document['features']
raw = {f['id']: f for f in json.loads((HERE/'raw-source-areas.geojson').read_text())['features']}
baseline = {tuple(key) for key in json.loads((HERE/'baseline-keys.json').read_text())['knownKeys']}
own = [f for f in features if f['properties']['associationKind'] == 'source_area_name']
single = [f for f in features if f['properties'].get('distinctContainedQuarterNames') == 1]
multi = [f for f in features if f['properties'].get('distinctContainedQuarterNames', 0) > 1]
for name, group in [('source-own-name-features.geojson', own), ('single-label-features.geojson', single), ('multi-label-features.geojson', multi)]:
    write(name, {**document, 'features': group, 'featureCount': len(group)})
check = {
    'schemaVersion': 1, 'featureCount': len(features),
    'validGeometryCount': sum(shape(f['geometry']).is_valid and not shape(f['geometry']).is_empty for f in features),
    'allSourceCoordinatesUnchanged': all(f['geometry'] == raw[f['properties']['sourceAreaId']]['geometry'] for f in features),
    'allSourceAreaIdsExistInRawLayer': all(f['properties']['sourceAreaId'] in raw for f in features),
    'namePointContainedCount': sum(shape(f['geometry']).covers(Point(f['properties']['namePoint']['coordinates'])) for f in features if f['properties']['namePoint']),
    'sourceOwnNameCount': len(own), 'singleLabelAssociationCount': len(single), 'multiLabelAssociationCount': len(multi),
    'uniqueMunicipalityNameCount': len({(f['properties']['municipality'], norm(f['properties']['name'])) for f in features}),
    'duplicateWithFrozenBaselineCount': sum((f['properties']['municipality'], norm(f['properties']['name'])) in baseline for f in features),
    'sharedSourceOutlineCount': sum(n > 1 for n in Counter(f['properties']['sourceAreaId'] for f in features).values()),
    'maximumNamesSharingSourceOutline': max(Counter(f['properties']['sourceAreaId'] for f in features).values(), default=0),
    'featuresSha256': hashlib.sha256((HERE/'features.geojson').read_bytes()).hexdigest(),
    'geographicBoundaryAccuracyReviewed': False, 'circlesGenerated': 0,
}
assert check['validGeometryCount'] == len(features)
assert check['allSourceCoordinatesUnchanged'] and check['allSourceAreaIdsExistInRawLayer']
assert check['uniqueMunicipalityNameCount'] == len(features) and check['duplicateWithFrozenBaselineCount'] == 0
assert check['namePointContainedCount'] == len(single)+len(multi)
write('validation.json', check)
print(json.dumps(check, ensure_ascii=False))
