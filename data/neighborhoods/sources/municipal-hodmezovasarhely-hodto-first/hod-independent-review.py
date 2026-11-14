#!/usr/bin/env python3
"""Independent local Hódtó readback/segment/circuit review; frozen inputs stay read-only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np
import osmium
from pyproj import Transformer
from shapely.geometry import shape, LineString, Point
from shapely.ops import transform, unary_union, polygonize

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PBF = ROOT / '.local/neighborhoods/hungary-latest.osm.pbf'
PBF_SHA = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
CANDIDATE_SHA = '5b201c8a8c632f6096934b57d618beaf66db24b3492b0f2eece5d2d4b937d6ff'
MUNICIPALITIES = ROOT / '.local/neighborhoods/country/municipalities.geojson'
NAMES = ['Kaszap utca', 'Andrássy út', 'Bajcsy-Zsilinszky Endre utca']
EXCLUDED = {'footway', 'cycleway', 'path', 'steps', None}
FWD = Transformer.from_crs(4326, 23700, always_xy=True)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def read(name):
    return json.loads((OUT / name).read_text())


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def circuit_group(tags):
    if tags.get('name') in NAMES and tags.get('highway') not in EXCLUDED:
        return tags['name']
    if tags.get('railway') == 'rail' and tags.get('ref') == '135' and tags.get('usage') == 'main' and not tags.get('service'):
        return '135 railway'
    return None


def is_roundabout(tags):
    return tags.get('junction') == 'roundabout' and tags.get('highway') not in EXCLUDED


def readback(expected, name_point):
    """Read original PBF coordinates plus refs/tags/version/timestamp, freshly."""
    if sha(PBF) != PBF_SHA:
        raise ValueError('Pinned PBF hash differs')
    seen = {}
    node_seen = {}
    counts = Counter()
    node_id = name_point['properties']['osmNodeId']

    class Collector(osmium.SimpleHandler):
        def node(self, obj):
            counts['filteredNodeCallbacks'] += 1
            if obj.id == node_id:
                node_seen.update({'osmNodeId': obj.id, 'tags': dict(obj.tags),
                                  'version': obj.version, 'timestamp': str(obj.timestamp),
                                  'coordinates': [obj.location.lon, obj.location.lat]})

        def way(self, obj):
            counts['filteredWayCallbacks'] += 1
            if obj.id not in expected:
                return
            if not all(node.location.valid() for node in obj.nodes):
                raise ValueError('Original node coordinates missing for way ' + str(obj.id))
            seen[obj.id] = {'osmWayId': obj.id, 'tags': dict(obj.tags),
                            'nodeRefs': [n.ref for n in obj.nodes],
                            'version': obj.version, 'timestamp': str(obj.timestamp),
                            'coordinates': [[n.lon, n.lat] for n in obj.nodes]}

    with osmium.io.Reader(str(PBF), osmium.osm.osm_entity_bits.NOTHING) as reader:
        header = reader.header()
        snapshot = {key: header.get(key) for key in ['generator', 'osmosis_replication_timestamp', 'osmosis_replication_sequence_number']}
    ids = list(expected) + [node_id]
    with tempfile.TemporaryDirectory(prefix='hod-independent-pbf-') as temp:
        Collector().apply_file(str(PBF), locations=True,
            idx='sparse_file_array,' + str(Path(temp) / 'nodes.idx'),
            filters=[osmium.filter.IdFilter(ids)])
    mismatches = []
    for ident, f in sorted(expected.items()):
        p = f['properties']
        if ident not in seen:
            mismatches.append({'osmWayId': ident, 'field': 'missing_original_way'})
            continue
        for field in ['tags', 'nodeRefs', 'version', 'timestamp']:
            if p[field] != seen[ident][field]:
                mismatches.append({'osmWayId': ident, 'field': field})
        if f['geometry']['coordinates'] != seen[ident]['coordinates']:
            mismatches.append({'osmWayId': ident, 'field': 'complete_coordinates'})
    expected_node = {**name_point['properties'], 'coordinates': name_point['geometry']['coordinates']}
    node_exact = node_seen == expected_node
    return seen, {'pbfSha256': PBF_SHA, 'pbfHeader': snapshot,
                  'freshOriginalWayCount': len(seen), 'requestedGraphWayCount': len(expected),
                  'allCompleteOriginalWayFieldsMatch': not mismatches,
                  'comparedWayFields': ['complete coordinates', 'complete nodeRefs', 'complete tags', 'version', 'timestamp'],
                  'wayMismatches': mismatches, 'currentNamePointMatchesAllOriginalFields': node_exact,
                  'currentNamePointComparedFields': ['coordinates', 'complete tags', 'version', 'timestamp'],
                  'counts': dict(sorted(counts.items())), 'errors': []}


def segment_support(a, b, way):
    """Require a whole candidate segment to lie on one consecutive original node pair."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    supports = []
    for index, (p, q) in enumerate(zip(way['coordinates'], way['coordinates'][1:])):
        p, q = np.asarray(p, dtype=float), np.asarray(q, dtype=float)
        vector = q-p
        squared = float(vector @ vector)
        if squared == 0:
            continue
        t0, t1 = float((a-p) @ vector/squared), float((b-p) @ vector/squared)
        d0 = float(np.linalg.norm(a-(p+t0*vector)))
        d1 = float(np.linalg.norm(b-(p+t1*vector)))
        linear_tolerance = 1e-11/np.sqrt(squared)
        if min(t0, t1) >= -linear_tolerance and max(t0, t1) <= 1+linear_tolerance and max(d0, d1) <= 1e-11:
            supports.append({'originalNodePairIndex': index,
                             'originalNodeRefs': way['nodeRefs'][index:index+2],
                             'maximumEndpointLineDistanceDegrees': max(d0, d1),
                             'endpointFractionsOnOriginalSegment': [t0, t1]})
    return supports


def main_review():
    candidate_path = OUT / 'hod-hodto-first-candidate.geojson'
    if sha(candidate_path) != CANDIDATE_SHA:
        raise ValueError('Frozen first candidate changed')
    handoff = read('hod-hodto-frozen-handoff.json')
    frozen_hashes = [{'path': name, 'expectedSha256': digest, 'actualSha256': sha(OUT / name),
                      'matches': sha(OUT / name) == digest} for name, digest in handoff['files'].items()]
    if not all(row['matches'] for row in frozen_hashes):
        raise ValueError('A frozen handoff input changed')
    proof = read('hod-hodto-first-candidate-proof.json')
    candidate_feature = read('hod-hodto-first-candidate.geojson')['features'][0]
    candidate = shape(candidate_feature['geometry'])
    controls = read('hod-hodto-boundary-controls.geojson')['features']
    control_ids = {f['properties']['osmWayId'] for f in controls}
    local = read('hod-local-lines.geojson')['features']
    graph_features = [f for f in local if circuit_group(f['properties']['tags']) or is_roundabout(f['properties']['tags'])]
    expected = {f['properties']['osmWayId']: f for f in graph_features}
    for f in controls:
        ident = f['properties']['osmWayId']
        if ident not in expected or f != expected[ident]:
            raise ValueError('Frozen control does not match graph catalogue: ' + str(ident))
    originals, pbf_review = readback(expected, proof['currentNamePoint'])
    if not pbf_review['allCompleteOriginalWayFieldsMatch'] or not pbf_review['currentNamePointMatchesAllOriginalFields']:
        raise ValueError('Fresh PBF readback differs')
    pbf_review['freshBoundaryControlWayCount'] = len(control_ids)
    pbf_review['all42BoundaryControlWaysVerified'] = len(control_ids) == 42 and control_ids <= originals.keys()

    # Independently assemble all eligible source-named circuit linework and add
    # physical roundabouts to a fixed point. Face selection uses no name point.
    cited = {ident: LineString(w['coordinates']) for ident, w in originals.items() if circuit_group(w['tags'])}
    roundabouts = {ident: LineString(w['coordinates']) for ident, w in originals.items() if is_roundabout(w['tags']) and ident not in cited}
    graph = unary_union(list(cited.values()))
    selected_roundabouts = set()
    while True:
        new = {ident for ident, g in roundabouts.items() if ident not in selected_roundabouts and g.intersects(graph)}
        if not new:
            break
        selected_roundabouts |= new
        graph = unary_union([graph, *[roundabouts[ident] for ident in new]])
    faces = list(polygonize(graph))
    group_lines = {name: unary_union([g for ident, g in cited.items() if circuit_group(originals[ident]['tags']) == name]) for name in [*NAMES, '135 railway']}
    four_group_faces = [g for g in faces if all(g.boundary.intersection(lines).length > 0 for lines in group_lines.values())]
    name_point = shape(proof['currentNamePoint']['geometry'])
    selected_faces = [g for g in four_group_faces if g.covers(name_point)]
    face_review = {'freshEligibleCitedWayCount': len(cited), 'freshRoundaboutCatalogueWayCount': len(roundabouts),
                   'connectedPhysicalRoundaboutWayCount': len(selected_roundabouts),
                   'polygonizedFaceCount': len(faces), 'facesUsingAllFourSourceGroupsBeforeNamePoint': len(four_group_faces),
                   'namePointNeededToChooseAmongFourGroupFaces': len(four_group_faces) != 1,
                   'selectedFaceEqualsFrozenCandidate': len(selected_faces) == 1 and selected_faces[0].equals(candidate),
                   'uniqueSourceFactFaceEqualsFrozenCandidate': len(four_group_faces) == 1 and four_group_faces[0].equals(candidate),
                   'currentNamePointInsideCandidate': candidate.covers(name_point),
                   'namePointGeneratesPerimeterCoordinates': False,
                   'sourceGroupBorderLengthMetres': {group: transform(FWD.transform, candidate.boundary.intersection(lines)).length for group, lines in group_lines.items()}}

    rows = []
    failures = []
    role_errors = []
    inferred_ids = set()
    total_length = 0.0
    inferred_length = 0.0
    maximum_length_difference = 0.0
    ring = [list(c) for c in candidate.exterior.coords]
    for index, row in enumerate(proof['orderedEdges']):
        a, b = row['coordinates']
        if row['edgeIndex'] != index or [a, b] != ring[index:index+2]:
            failures.append({'edgeIndex': index, 'reason': 'ordered_edge_not_exact_ring_edge'})
        segment = LineString([a, b])
        length = transform(FWD.transform, segment).length
        total_length += length
        maximum_length_difference = max(maximum_length_difference, abs(length-row['lengthMeters']))
        choices = []
        roles = []
        for choice in row['sourceChoices']:
            ident = choice['osmWayId']; way = originals[ident]
            support = segment_support(a, b, way)
            if not support:
                failures.append({'edgeIndex': index, 'osmWayId': ident, 'reason': 'not_on_one_original_consecutive_node_pair'})
            role = choice['role']; roles.append(role)
            group = circuit_group(way['tags'])
            inferred = role == 'inferred_physical_junction_arc'
            if inferred:
                inferred_ids.add(ident)
                if not is_roundabout(way['tags']):
                    role_errors.append({'edgeIndex': index, 'osmWayId': ident, 'reason': 'inferred_arc_not_tagged_roundabout'})
            elif role != 'explicit_circuit_road_or_rail' or not group:
                role_errors.append({'edgeIndex': index, 'osmWayId': ident, 'reason': 'explicit_choice_not_source_circuit_group'})
            if choice['name'] != way['tags'].get('name') or choice['railwayRef'] != (way['tags'].get('ref') if way['tags'].get('railway') else None):
                role_errors.append({'edgeIndex': index, 'osmWayId': ident, 'reason': 'choice_name_or_rail_ref_differs_from_original_tags'})
            choices.append({'osmWayId': ident, 'circuitGroup': group, 'role': role, 'consecutiveNodePairSupport': support})
        inferred_only = bool(roles) and all(role == 'inferred_physical_junction_arc' for role in roles)
        if inferred_only:
            inferred_length += length
        rows.append({'edgeIndex': index, 'lengthMetres': length, 'inferredJunctionOnly': inferred_only, 'verifiedChoices': choices})
    all_choice_ids = {c['osmWayId'] for row in proof['orderedEdges'] for c in row['sourceChoices']}
    original_node_coordinates = {tuple(coordinate) for ident in control_ids for coordinate in originals[ident]['coordinates']}
    inserted_intersections = [coordinate for coordinate in ring[:-1] if tuple(coordinate) not in original_node_coordinates]
    segment_review = {'orderedBoundarySegmentCount': len(rows), 'sourceRingVertexCount': len(ring),
                      'allEdgesExactlyMatchFrozenRing': len(rows) == len(ring)-1 and not failures,
                      'sourceSupportMethod': 'Whole segment endpoints must project within one consecutive original node pair at <=1e-11 degree perpendicular error; no midpoint-only support test, buffering, snapping or chord generation.',
                      'all125SegmentsSupportedByOriginalConsecutiveNodePairs': len(rows) == 125 and not failures,
                      'sourceChoiceIdsExactlyEqualFrozen42Controls': all_choice_ids == control_ids == set(proof['sourceWayIds']),
                      'inferredJunctionWayCount': len(inferred_ids), 'inferredJunctionWayIds': sorted(inferred_ids),
                      'inferredIdsMatchProof': inferred_ids == set(proof['inferredJunctionWayIds']),
                      'independentPerimeterMetres': total_length,
                      'independentInferredJunctionLengthMetres': inferred_length,
                      'inferredJunctionLengthDifferenceMetres': abs(inferred_length-proof['inferredJunctionLengthMeters']),
                      'maximumPerEdgeLengthDifferenceMetres': maximum_length_difference,
                      'uniqueBoundaryVertexCount': len(ring)-1,
                      'originalOsmNodeCoordinateVertexCount': len(ring)-1-len(inserted_intersections),
                      'sourceLineIntersectionVertexCount': len(inserted_intersections),
                      'sourceLineIntersectionVertices': inserted_intersections,
                      'allBoundaryCoordinatesAreOriginalOsmNodes': not inserted_intersections,
                      'intersectionVertexMeaning': 'One analytical intersection subdivides original road and railway node-pair segments. It introduces no connector or chord; both incident boundary segments remain wholly supported by the original linework.',
                      'supportFailures': failures, 'classificationErrors': role_errors, 'records': rows}
    metric = transform(FWD.transform, candidate)
    municipalities_hash = sha(MUNICIPALITIES)
    city = next(f for f in json.loads(MUNICIPALITIES.read_text())['features'] if f['properties']['name'] == 'Hódmezővásárhely')
    municipal = shape(city['geometry'])
    outside = transform(FWD.transform, candidate.difference(municipal)).area
    validator_code = "import fs from 'node:fs';import{validateGeometry}from'./scripts/neighborhoods/build.mjs';const d=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));process.stdout.write(JSON.stringify(validateGeometry(d.features[0].geometry)));"
    strict = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', validator_code, str(candidate_path)], cwd=ROOT, text=True))
    properties = candidate_feature['properties']
    geometry_review = {'geometryType': candidate.geom_type, 'geosValid': candidate.is_valid,
                       'holeCount': len(candidate.interiors), 'ringClosed': ring[0] == ring[-1],
                       'areaSquareMetres': metric.area, 'areaDifferenceFromProofSquareMetres': abs(metric.area-proof['areaSquareMeters']),
                       'perimeterMetres': metric.length, 'perimeterDifferenceFromSegmentSumMetres': abs(metric.length-total_length),
                       'municipalityReferenceSha256': municipalities_hash,
                       'municipalityReferenceHashMatchesFrozenChecks': municipalities_hash == read('hod-final-checks.json')['municipalityReferenceSha256'],
                       'insideArchivedCurrentMunicipality': municipal.covers(candidate),
                       'outsideMunicipalitySquareMetres': outside, 'strictProjectValidator': strict,
                       'estimatedTrue': properties.get('estimated') is True, 'confidenceLow': properties.get('confidence') == 'low',
                       'usableForAddressAssignmentFalse': properties.get('usableForAddressAssignment') is False,
                       'absoluteAccuracyClaimNull': properties.get('accuracyMeters') is None}
    quote = read('hod-hodto-semantic-quote-proof.json')
    source_review = {'sourceDate': '2014-09-17', 'sourcePrintedPage': 61, 'sourceSection': '2.3.4',
                     'sourceQuarterEquivalenceQuote': quote['literalQuote'], 'quoteProofFile': 'hod-hodto-semantic-quote-proof.json',
                     'sourceQuoteWasIndependentlyRefetchedByThisReviewer': False,
                     'quoteEvidenceAuthority': 'Separate source-research agent reported actual original municipal PDF text seen through read-only web; local bounded quote retained.',
                     'originalPdfBytesAcquired': False, 'sourcePdfBinaryHashAvailable': False,
                     'originalPdfReopenBlockedHttp403': True,
                     'current2023NameConfirmationIsGeometryEvidence': False,
                     'sourceBajcsyStreetShortNameMappedToCurrentFullName': 'Bajcsy-Zsilinszky utca → Bajcsy-Zsilinszky Endre utca; ordinary full-name expansion, not a route change.',
                     'railwayRoute135ExplicitlyConfirmedInFreshOriginalTags': all(originals[i]['tags'].get('ref') == '135' and originals[i]['tags'].get('railway') == 'rail' for i in control_ids if originals[i]['tags'].get('railway')),
                     'verifiedRailway135ControlWayIds': sorted(i for i in control_ids if originals[i]['tags'].get('railway')),
                     'currentCenterlineTracingConventionIsInferred': True,
                     'source2014ToOsm2026HistoricalAlignmentIndependentlyVerified': False}
    inputs = sorted(set(handoff['files']) | {'hod-hodto-frozen-handoff.json', 'hod-hodto-semantic-quote-proof.json'})
    result = {'schemaVersion': 1, 'reviewer': 'independent first-cohort Hódtó reviewer', 'reviewDate': '2026-11-14',
              'networkUsed': False, 'frozenFirstCohortInputsUnmodified': all(r['matches'] for r in frozen_hashes),
              'inputFingerprints': [{'path': name, 'sha256': sha(OUT / name)} for name in inputs],
              'frozenHandoffHashChecks': frozen_hashes,
              'freshPbfReadback': pbf_review, 'sourceFactFaceReview': face_review,
              'orderedSegmentReview': segment_review, 'geometryReview': geometry_review,
              'sourceSemanticReview': source_review,
              'limitations': ['The original municipal PDF bytes and section screenshot remain unavailable after HTTP403; the bounded text proof is the source researcher’s observed extraction and was not independently refetched in this audit.',
                              'The2014 circuit is represented with2026 OSM road/rail centerlines; historical alignment and width ownership are not established.',
                              'Modern physical roundabout arcs total the measured inferred length; their real OSM support does not make them observed2014 quarter edges.',
                              'The2023 decree and current OSM name point confirm the name separately from perimeter geometry. No primary supported polygon is established.'],
              'recommendation': {'eligibleAsLowConfidenceEstimatedHistoricalCircuitCandidate': True,
                                 'newPrimarySupportedPolygonCount': 0, 'sourcePolygonDownloadedCount': 0,
                                 'independentInferredCandidateCount': 1, 'usableForAddressAssignment': False},
              'sourceOrCandidateFilesEdited': False, 'globalRegistryOrExportsEdited': False}
    checks = [pbf_review['all42BoundaryControlWaysVerified'], face_review['selectedFaceEqualsFrozenCandidate'],
              segment_review['all125SegmentsSupportedByOriginalConsecutiveNodePairs'], segment_review['sourceChoiceIdsExactlyEqualFrozen42Controls'],
              segment_review['inferredIdsMatchProof'], not role_errors, maximum_length_difference < 1e-7,
              abs(inferred_length-proof['inferredJunctionLengthMeters']) < 1e-7,
              geometry_review['geosValid'], strict['valid'], geometry_review['holeCount'] == 0,
              outside == 0, geometry_review['municipalityReferenceHashMatchesFrozenChecks'],
              abs(metric.area-proof['areaSquareMeters']) < 1e-5,
              geometry_review['estimatedTrue'], geometry_review['confidenceLow'], geometry_review['usableForAddressAssignmentFalse']]
    result['allRequiredTechnicalChecksPassed'] = all(checks)
    if not all(checks):
        raise ValueError('Hódtó independent technical check failed: ' + str([i for i, passed in enumerate(checks) if not passed]))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = main_review()
    destination = OUT / 'hod-independent-review.json'
    content = encode(result)
    if args.check:
        if destination.read_text() != content:
            raise ValueError('Independent Hódtó review differs from frozen output')
    else:
        destination.write_text(content)
    print(json.dumps({'technicalChecksPassed': result['allRequiredTechnicalChecksPassed'],
                      'freshOriginalWays': result['freshPbfReadback']['freshOriginalWayCount'],
                      'boundarySegments': result['orderedSegmentReview']['orderedBoundarySegmentCount'],
                      'fourGroupFacesBeforeNamePoint': result['sourceFactFaceReview']['facesUsingAllFourSourceGroupsBeforeNamePoint'],
                      'check': args.check}))
