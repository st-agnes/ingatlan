#!/usr/bin/env python3
"""Reproduce the separate Dózsa inference from unchanged archived OSM ways, offline."""
import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/neighborhoods/sources/municipal-dunaujvaros-next'
INPUT_SHA = '241835aa107403a3e8dcc2c1cd06118590a950f5e4992749eb115cf32e107a2b'
SOURCE_NAMES = {'Aranyvölgyi út', 'Dózsa György út', 'Szórád Márton út'}
INFERRED_NAME = 'Vasmű út'
ROUNDABOUT_ID = 'osm:way:445990097'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value, check):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    if check:
        if not path.exists() or path.read_bytes() != data:
            raise ValueError('Stale derived file: ' + str(path))
    else:
        path.write_bytes(data)


def edge(a, b):
    return tuple(sorted((tuple(a), tuple(b))))


def verify_pbf():
    import osmium
    inputs = OUT / 'dozsa-input-ways.geojson'
    expected = {f['properties']['source']['osmId']: f for f in json.loads(inputs.read_text())['features']}
    pbf = ROOT / '.local/neighborhoods/hungary-latest.osm.pbf'
    if sha(pbf) != '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a':
        raise ValueError('The archived original PBF changed.')
    seen = set()

    class OriginalWayCheck(osmium.SimpleHandler):
        def way(self, way):
            if way.id not in expected:
                return
            archived = expected[way.id]
            source = archived['properties']['source']
            actual = {'nodeRefs': [n.ref for n in way.nodes], 'tags': dict(way.tags),
                      'objectVersion': way.version, 'objectTimestamp': str(way.timestamp)}
            if any(source[k] != v for k, v in actual.items()):
                raise ValueError('Changed source fields: ' + str(way.id))
            if not all(n.location.valid() for n in way.nodes):
                raise ValueError('Missing original node location.')
            if archived['geometry']['coordinates'] != [[n.lon, n.lat] for n in way.nodes]:
                raise ValueError('Changed original coordinate sequence: ' + str(way.id))
            seen.add(way.id)

    with tempfile.TemporaryDirectory(prefix='otthonra-dunaujvaros-pbf-') as temp:
        OriginalWayCheck().apply_file(str(pbf), locations=True,
            idx='sparse_file_array,' + str(Path(temp) / 'nodes.idx'),
            filters=[osmium.filter.IdFilter(expected)])
    if seen != set(expected):
        raise ValueError('Missing original ways: ' + str(set(expected) - seen))
    result = {'originalPbfSha256': sha(pbf), 'inputWaySha256': sha(inputs),
              'checkedOriginalWays': len(seen), 'allSourceWaysMatched': True,
              'comparedFields': ['complete original coordinate sequence', 'nodeRefs', 'complete tags',
                                 'objectVersion', 'objectTimestamp'],
              'actualSourceWayIds': sorted(seen), 'networkUsed': False}
    save(OUT / 'pbf-way-verification.json', result, False)
    print(json.dumps(result))


def build(check=False):
    from shapely.geometry import LineString, shape, mapping
    from shapely.ops import unary_union, polygonize, transform, nearest_points
    from pyproj import Geod, Transformer

    inputs = OUT / 'dozsa-input-ways.geojson'
    if sha(inputs) != INPUT_SHA:
        raise ValueError('The original-way input changed; repeat source review.')
    roads = json.loads(inputs.read_text())['features']
    parent = shape(json.loads((OUT / 'municipality.geojson').read_text())['features'][0]['geometry'])
    point = shape(json.loads((OUT / 'name-control-point.geojson').read_text())['features'][0]['geometry'])
    facts = json.loads((OUT / 'source-facts.json').read_text())
    geometries = [shape(f['geometry']) for f in roads]
    candidates = []
    for polygon in polygonize(unary_union(geometries)):
        if not polygon.contains(point):
            continue
        used = [f for f, g in zip(roads, geometries) if polygon.boundary.intersection(g).length > 1e-10]
        if SOURCE_NAMES | {INFERRED_NAME} <= {f['properties']['name'] for f in used}:
            candidates.append((polygon, used))
    if len(candidates) != 1:
        raise ValueError('Expected one original-edge face containing the actual Dózsa name point.')
    polygon, used = candidates[0]
    if not polygon.is_valid or polygon.interiors or not parent.covers(polygon):
        raise ValueError('Invalid, holed or outside-municipality candidate.')
    owners = defaultdict(list)
    for f in roads:
        coords, refs = f['geometry']['coordinates'], f['properties']['source']['nodeRefs']
        if len(coords) != len(refs):
            raise ValueError('Source-node reference count mismatch.')
        for a, b, na, nb in zip(coords, coords[1:], refs, refs[1:]):
            owners[edge(a, b)].append((f, na, nb, a, b))
    geod, lengths, rows, uncertain = Geod(ellps='WGS84'), defaultdict(float), [], []
    chain = list(polygon.exterior.coords)
    for i, (a, b) in enumerate(zip(chain, chain[1:])):
        matches = owners[edge(a, b)]
        if len(matches) != 1:
            raise ValueError('Nonliteral or ambiguous source edge; no insertion/repair allowed.')
        f, na, nb, sa, sb = matches[0]
        p = f['properties']; tags = p['source']['tags']
        if tags.get('bridge') not in (None, 'no') or tags.get('tunnel') not in (None, 'no') or tags.get('layer') not in (None, '0'):
            raise ValueError('Grade separation needs explicit review.')
        name = p['name']; unproven = name not in SOURCE_NAMES
        if unproven and name != INFERRED_NAME and f['id'] != ROUNDABOUT_ID:
            raise ValueError('Unexplained inference corridor.')
        length = geod.inv(*a, *b)[2]
        lengths[name or 'unnamed_roundabout'] += length
        oriented_refs = [na, nb] if tuple(sa) == tuple(a) else [nb, na]
        row = {'edgeIndex': i, 'wayId': f['id'], 'sourceNodeRefs': oriented_refs,
               'name': name, 'lengthMetres': length,
               'unprovenBoundaryRole': unproven, 'actualOriginalEdge': True}
        rows.append(row)
        if unproven:
            uncertain.append({'type': 'Feature', 'id': 'unproven-edge:' + str(i),
                              'properties': row, 'geometry': mapping(LineString([a, b]))})
    source_only = [g for f, g in zip(roads, geometries) if f['properties']['name'] in SOURCE_NAMES]
    if any(p.contains(point) for p in polygonize(unary_union(source_only))):
        raise ValueError('The original three corridors now close; inference classification must be reviewed.')
    project = Transformer.from_crs(4326, 23700, always_xy=True).transform
    arany = unary_union([transform(project, g) for f, g in zip(roads, geometries) if f['properties']['name'] == 'Aranyvölgyi út'])
    dozsa = unary_union([transform(project, g) for f, g in zip(roads, geometries) if f['properties']['name'] == 'Dózsa György út'])
    near_a, near_b = nearest_points(arany, dozsa)
    roundabout = next(f for f in roads if f['id'] == ROUNDABOUT_ID)
    round_length = geod.geometry_length(shape(roundabout['geometry']))
    area, perimeter = geod.geometry_area_perimeter(polygon)
    props = {'name': 'Dózsa városrész', 'municipality': 'Dunaújváros',
             'boundaryKind': 'inferred_area', 'candidateBoundaryKind': 'neighbourhood',
             'estimated': True, 'canonicalNameIsNeighborhood': False,
             'method': 'Manually inferred completion of a three-road source description along actual modern Vasmű út and roundabout original-node edges; unique inside face containing the genuine Dózsa place node.',
             'sourcePeriod': 'Named quarter description in 2003 law / 2015 version and 2020 municipal concept; actual OSM ways snapshot 2026-11-12T21:23:05Z.',
             'sourceDocuments': [{'url': facts['primarySource']['url'], 'title': facts['primarySource']['title'], 'page': 12,
                                  'retrieval': 'web_reader_factual_transcription', 'fullSourcePdfArchivedLocally': False, 'sourcePdfSha256': None}],
             'evidenceUrls': [facts['primarySource']['url'], facts['corroboratingLaw']['url'], facts['roadConnectionCorroboration']['url']],
             'sourceLineIds': sorted(f['id'] for f in used),
             'sourceIsOfficial': False, 'sourceIsHardBoundary': False,
             'reviewStatus': 'estimated_candidate_not_verified', 'geometryVerificationStatus': 'inferred_not_verified',
             'usableForAddressAssignment': False, 'claimedAbsoluteAccuracyMetres': None,
             'areaM2': abs(area), 'perimeterM': perimeter,
             'unprovenVasmuBoundaryMetres': lengths[INFERRED_NAME],
             'unprovenRoundaboutBoundaryMetres': lengths['unnamed_roundabout'],
             'reviewNotes': ['The municipal name is authentic; the whole quarter boundary is not verified.',
                             'The source does not mention Vasmű út. Its boundary role and the selected roundabout arc are explicit manual interpretations, not silently renamed source streets.',
                             'All geographical edges follow consecutive original PBF nodes. No chord, buffer, hull, snapping, clipping, geometric repair or interpolated intersection vertex.',
                             'Opposite roundabout arc and alternative carriageway/parcel-side choices remain possible. No statistical confidence or legal boundary accuracy is asserted.'],
             'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors; factual quarter descriptions Dunaújváros MJV.'}
    save(OUT / 'dozsa-inferred.geojson', {'type': 'FeatureCollection', 'status': 'estimated_candidates_only',
         'features': [{'type': 'Feature', 'id': 'manual:dunaujvaros:dozsa-vasmu-inference', 'properties': props, 'geometry': mapping(polygon)}]}, check)
    save(OUT / 'unproven-boundary-segments.geojson', {'type': 'FeatureCollection', 'features': uncertain}, check)
    proof = {'schemaVersion': 1, 'classification': 'inferred_area_only', 'primaryCandidateCount': 0,
             'candidateCount': 1, 'inputWaySha256': INPUT_SHA, 'sourceFactsSha256': sha(OUT / 'source-facts.json'),
             'municipalitySha256': sha(OUT / 'municipality.geojson'), 'namePointSha256': sha(OUT / 'name-control-point.geojson'),
             'originalPbfSha256': '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a',
             'uniqueNameContainingFace': True, 'insideMunicipality': True, 'containsOriginalNamePoint': True,
             'valid': True, 'holes': 0, 'boundaryVerticesIncludingClosure': len(chain),
             'usedSourceWays': len(used), 'allEdgesConsecutiveOriginalNodes': True,
             'syntheticVertices': 0, 'syntheticEdges': 0, 'geometryRepairs': 0,
             'namedOnlyRoadsClose': False, 'metricGapBetweenAranyAndDozsaMetres': near_a.distance(near_b),
             'corridorLengthsMetres': dict(lengths), 'areaM2': abs(area), 'perimeterMetres': perimeter,
             'roundaboutAlternative': {'originalWayId': ROUNDABOUT_ID, 'wholeLoopMetres': round_length,
                                     'chosenArcMetres': lengths['unnamed_roundabout'],
                                     'otherArcMetres': round_length - lengths['unnamed_roundabout'],
                                     'alternativeNotResolvedBySource': True},
             'boundaryEdges': rows, 'usableForAddressAssignment': False}
    save(OUT / 'conversion-proof.json', proof, check)
    print(json.dumps({'inferredCandidates': 1, 'primaryCandidates': 0, 'literalEdges': len(rows),
                      'unprovenBoundaryMetres': sum(r['lengthMetres'] for r in rows if r['unprovenBoundaryRole']),
                      'check': check}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--verify-pbf', action='store_true')
    args = parser.parse_args()
    if args.verify_pbf:
        verify_pbf()
    else:
        build(args.check)
