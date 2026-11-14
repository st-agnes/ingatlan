#!/usr/bin/env python3
"""Audit archived WOF alternate geometry without turning point proxies into boundaries.

Reads local data only. The original four source snapshots remain unchanged.
The empty candidate collection is intentional: both alternatives show literal
coordinate-space circle-buffer signatures, so neither is an actual boundary.
"""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/neighborhoods/sources/public-vector-next/wof-alt'
PINNED = {
    '85901183-primary.source.geojson': '30537fb94cbf41c37a1692b9ea2b3cb7ec4f605db5a368dd4123cb892df6e169',
    '85901183-alt-quattroshapes.source.geojson': '3ccda268d403d446d44f27790c01aabd21ca95b6229abae0d3ea7059b9bb3709',
    '85901339-primary.source.geojson': 'bca2ff9505c0458c63630c3216017c3c77865e018d1bc73cdb59723e053ccb6a',
    '85901339-alt-quattroshapes.source.geojson': '2892d31e236901c1d6c941069d2c64062b89d21924280d61baa4e0b03a7111cd',
}
REPORTED_ALT_BLOBS = {
    85901183: '130b66447b6551f170b8c4295be7bdae9eaefad0',
    85901339: 'fad2472f4129fa40da57e8fed2f9bca05d6a0baa',
}
EXISTING_IDS = [85901077, 85901111, 85901165, 85901203, 85901243,
                85901253, 85901347, 85906441, 85906443]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def circumcircle(a, b, c):
    u = (b[0] - a[0], b[1] - a[1])
    v = (c[0] - a[0], c[1] - a[1])
    det = u[0] * v[1] - u[1] * v[0]
    if abs(det) < 1e-22:
        return None
    uu, vv = sum(x*x for x in u), sum(x*x for x in v)
    x = (uu*v[1] - vv*u[1]) / (2*det)
    y = (u[0]*vv - v[0]*uu) / (2*det)
    return a[0] + x, a[1] + y, math.hypot(x, y)


def circle_patterns(geometry):
    rings = geometry['coordinates'] if geometry['type'] == 'Polygon' else [
        ring for polygon in geometry['coordinates'] for ring in polygon]
    results = []
    for ri, ring in enumerate(rings):
        cs = ring[:-1] if ring[0] == ring[-1] else ring
        n = len(cs)
        candidates = [circumcircle(cs[i], cs[(i+1) % n], cs[(i+2) % n]) for i in range(n)]
        candidates = [c for c in candidates if c and abs(c[2] - .01) < 1e-8]
        if not candidates:
            continue
        center = max(candidates, key=lambda c: sum(
            abs(math.hypot(p[0]-c[0], p[1]-c[1])-.01) < 1e-9 for p in cs))
        cx, cy, radius = center
        residuals = [abs(math.hypot(p[0]-cx, p[1]-cy)-.01) for p in cs]
        mask = [r < 1e-9 for r in residuals]
        best = run = steps = 0
        for on_circle in mask*2:
            run = run+1 if on_circle else 0
            best = min(n, max(best, run))
        for i in range(n):
            if not (mask[i] and mask[(i+1) % n]):
                continue
            a = math.atan2(cs[i][1]-cy, cs[i][0]-cx)
            b = math.atan2(cs[(i+1) % n][1]-cy, cs[(i+1) % n][0]-cx)
            angle = abs((math.degrees(b-a)+180) % 360-180)
            steps += abs(angle-11.25) < 1e-5
        if best < 4 or steps < 3:
            continue
        results.append({'ring': ri, 'uniqueVertices': n, 'fittedCenterDegrees': [cx, cy],
                        'fittedRadiusDegrees': radius, 'targetRadiusDegrees': .01,
                        'radialToleranceDegrees': 1e-9, 'angularToleranceDegrees': 1e-5,
                        'onCircleVertices': sum(mask), 'longestConsecutiveCircleRun': best,
                        'regular11_25DegreeSteps': steps,
                        'maxMatchingVertexRadialResidualDegrees': max(r for r in residuals if r < 1e-9)})
    return results


def save(name, value, check):
    path = OUT/name
    raw = (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()
    if check:
        if not path.exists() or path.read_bytes() != raw:
            raise ValueError('Stale or missing audit: '+str(path))
    else:
        path.write_bytes(raw)


def build(check=False):
    inputs = []
    for name, expected in PINNED.items():
        raw = (OUT/name).read_bytes()
        if sha(raw) != expected:
            raise ValueError('Changed source snapshot '+name)
        inputs.append({'path': name, 'sha256': expected, 'bytes': len(raw),
                       'localGitBlobSha': git_blob(raw)})
    country = ROOT/'data/neighborhoods/sources/country-osm'
    municipalities = json.loads(gzip.decompress((country/'municipalities.geojson.gz').read_bytes()))
    canonical = [f for f in municipalities['features'] if f['properties'].get('usedForAssociation')]
    inventory = read(ROOT/'data/neighborhoods/nationwide-inventory.json')
    rows, quarantine = [], []
    for ident in [85901183, 85901339]:
        primary = read(OUT/f'{ident}-primary.source.geojson')
        alternative_path = OUT/f'{ident}-alt-quattroshapes.source.geojson'
        alternative = read(alternative_path)
        props = primary['properties']
        assert primary['id'] == alternative['id'] == ident
        assert primary['geometry']['type'] == 'Point'
        assert props['wof:country'] == 'HU' and props['wof:placetype'] == 'neighbourhood'
        assert not props.get('wof:superseded_by')
        polygon, point = shape(alternative['geometry']), shape(primary['geometry'])
        assert polygon.is_valid and polygon.covers(point)
        parents = [f for f in canonical if shape(f['geometry']).covers(polygon)]
        assert len(parents) == 1
        city = parents[0]['properties']['name']
        expected_city = 'Pécs' if ident == 85901183 else 'Szentes'
        assert city == expected_city
        parent_id = props['wof:hierarchy'][0]['locality_id']
        old_parent = read(ROOT/f'data/neighborhoods/sources/whosonfirst/parents/{parent_id}.geojson')
        assert old_parent['properties']['wof:name'] == city
        older_primary = read(ROOT/f'data/neighborhoods/sources/whosonfirst/{ident}.geojson')
        assert primary == older_primary
        patterns = circle_patterns(alternative['geometry'])
        assert patterns, 'Expected literal point-buffer signature no longer reproduced'
        name = props['name:hun_x_preferred'][0]
        ksh = next(r for r in inventory['municipalities'] if r['municipality'] == city)
        parts = [r for r in ksh['settlementParts'] if r['name'] == name]
        row = {'id': ident, 'name': name, 'municipality': city, 'wofLocalityId': parent_id,
               'primaryGeometryType': 'Point', 'primaryAreaSquareMetres': props['geom:area_square_m'],
               'primaryCurrentFlag': props['mz:is_current'], 'primaryCurrentMeaning': 'unknown',
               'alternativeGeometryValid': True, 'fullyInsideCanonicalMunicipality': True,
               'sourceMunicipalityId': parents[0]['id'], 'primaryPointInsideAlternative': True,
               'primaryParsedValuesEqualPinnedOlderArchive': True, 'circlePatterns': patterns,
               'kshNameEvidence': [{'name': r['name'], 'category': r['category'], 'sourceRow': r['sourceRow']} for r in parts],
               'decision': 'quarantine_provider_point_buffer_proxy', 'acceptedBoundaryCandidate': False,
               'eligibleForInferredBoundaryLayer': False, 'usableForAddressAssignment': False,
               'declaredRemoteAltGitBlobSha': REPORTED_ALT_BLOBS[ident],
               'localAltGitBlobSha': git_blob(alternative_path.read_bytes()),
               'byteExactRemoteGitBlobMatch': False}
        assert row['declaredRemoteAltGitBlobSha'] != row['localAltGitBlobSha']
        rows.append(row)
        quarantine.append({**alternative, 'properties': {**alternative['properties'],
            'name': name, 'municipality': city, 'sourceGeometryRole': 'provider_point_buffer_proxy',
            'excludedFromAllBoundaryLayers': True, 'usableForAddressAssignment': False,
            'reviewStatus': 'quarantined', 'sourceSnapshotSha256': sha(alternative_path.read_bytes())}})
    review = {'schemaVersion': 1, 'scope': 'Two WOF Quattroshapes alternatives; no accepted new boundary.',
              'inputs': inputs, 'sourceLicencePath': 'data/neighborhoods/sources/whosonfirst/LICENSE.md',
              'sourceRepresentation': 'Archived connector snapshots differ in byte serialization from declared remote Git blobs; byte-exact remote equivalence is not established.',
              'evidenceInterpretation': 'Consecutive 11.25-degree steps on a literal0.01-degree circle strongly identify a clipped coordinate-space point-buffer construction, not a physical quarter boundary.',
              'records': rows, 'acceptedNewBoundaryCandidates': 0,
              'limits': ['A real place name does not validate its provider proxy geometry.',
                         'No source circles were generated here; original alternative coordinates are retained only in quarantine.',
                         'A missing KSH urban-quarter row does not disprove a quarter name.',
                         'No root registry or existing catalog is modified by this script.']}
    save('wof-alt-review.json', review, check)
    save('quarantined-source-polygons.geojson', {'type': 'FeatureCollection', 'features': quarantine}, check)
    save('boundary-candidates.geojson', {'type': 'FeatureCollection', 'features': []}, check)
    catalog = read(ROOT/'data/neighborhoods/catalog.geojson')
    current = {int(f['id'].split(':')[1]): f for f in catalog['features'] if f['properties']['source']['provider'] == 'whosonfirst'}
    existing = []
    for ident in EXISTING_IDS:
        path = ROOT/f'data/neighborhoods/sources/whosonfirst/{ident}.geojson'
        raw = path.read_bytes()
        source = json.loads(raw)
        feature = current[ident]
        assert feature['geometry'] == source['geometry']
        assert feature['properties'].get('canonicalNameIsNeighborhood') is False
        patterns = circle_patterns(source['geometry'])
        existing.append({'id': f'wof:{ident}', 'name': feature['properties']['name'],
                         'sourcePath': str(path.relative_to(ROOT)), 'sourceSha256': sha(raw),
                         'sourceGitBlobSha': git_blob(raw), 'circlePatterns': patterns,
                         'existingCanonicalNameIsNeighborhood': False, 'contributesToPrimaryQuarterCount': False,
                         'recommendation': 'retain_source_bound_research_classification_with_provider_circle_warning' if patterns else
                             'no_targeted_circle_signature_detected_not_independent_boundary_verification'})
    save('existing-wof-proxy-review.json', {'schemaVersion': 1, 'scope': 'Nine retained WOF large/local-area source geometries, already excluded from primary quarter counts.',
         'reviewedFeatures': len(existing), 'literalPointBufferSignatureFeatures': sum(bool(r['circlePatterns']) for r in existing),
         'additionalPrimaryQuarterSuppressions': 0, 'records': existing,
         'limits': ['A negative0.01-degree/11.25-degree signature does not verify a physical boundary.',
                    'The positive Pesthidegkút signature is an additional geometry warning, not a new primary-quarter suppression.']}, check)
    print(json.dumps({'acceptedNewBoundaries': 0, 'quarantinedAlternatives': len(rows),
                      'existingWofReviewed': len(existing), 'existingWofCircleWarnings': sum(bool(r['circlePatterns']) for r in existing),
                      'check': check}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Compare deterministic audit files without writing')
    build(parser.parse_args().check)
