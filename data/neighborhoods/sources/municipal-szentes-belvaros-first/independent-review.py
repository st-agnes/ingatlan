#!/usr/bin/env python3
"""Fresh local-PBF and analytic segment review of the frozen Szentes alternatives."""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import osmium
from pyproj import Transformer
from shapely.geometry import shape, LineString
from shapely.ops import transform, unary_union

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PBF = ROOT / '.local/neighborhoods/hungary-latest.osm.pbf'
PBF_SHA = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
CANDIDATE_SHA = '2a2aab8baf53aae2f55b8dfbdec0b6cda8cd13863ae18f1c00bbfc16ec909c69'
METRIC = Transformer.from_crs(4326, 23700, always_xy=True).transform
TOLERANCE = 1e-11


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1048576), b''):
            h.update(part)
    return h.hexdigest()


def read(name):
    return json.loads((OUT / name).read_text())


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def fresh_readback(features, current_name):
    if sha(PBF) != PBF_SHA:
        raise ValueError('Pinned PBF changed')
    expected = {f['properties']['source']['osmId']: f for f in features}
    node_id = current_name['properties']['source']['osmId']
    ways = {}; node = {}; counts = Counter()
    class Collector(osmium.SimpleHandler):
        def node(self, obj):
            counts['nativeFilteredNodeCallbacks'] += 1
            if obj.id == node_id:
                node.update({'osmId': obj.id, 'tags': dict(obj.tags),
                             'objectVersion': obj.version, 'objectTimestamp': str(obj.timestamp),
                             'coordinates': [obj.location.lon, obj.location.lat]})
        def way(self, obj):
            counts['nativeFilteredWayCallbacks'] += 1
            if obj.id not in expected:
                return
            if not all(n.location.valid() for n in obj.nodes):
                raise ValueError('Missing original coordinates: ' + str(obj.id))
            ways[obj.id] = {'osmId': obj.id, 'tags': dict(obj.tags),
                            'objectVersion': obj.version, 'objectTimestamp': str(obj.timestamp),
                            'nodeRefs': [n.ref for n in obj.nodes],
                            'coordinates': [[n.lon, n.lat] for n in obj.nodes]}
    with osmium.io.Reader(str(PBF), osmium.osm.osm_entity_bits.NOTHING) as reader:
        header = {key: reader.header().get(key) for key in ['generator', 'osmosis_replication_timestamp', 'osmosis_replication_sequence_number']}
    with tempfile.TemporaryDirectory(prefix='szentes-independent-pbf-') as temp:
        Collector().apply_file(str(PBF), locations=True,
            idx='sparse_file_array,' + str(Path(temp) / 'nodes.idx'),
            filters=[osmium.filter.IdFilter([*expected, node_id])])
    errors = []
    for ident, feature in sorted(expected.items()):
        if ident not in ways:
            errors.append({'osmWayId': ident, 'field': 'missing_original_way'})
            continue
        source = feature['properties']['source']
        for field in ['tags', 'objectVersion', 'objectTimestamp', 'nodeRefs']:
            if source[field] != ways[ident][field]:
                errors.append({'osmWayId': ident, 'field': field})
        if feature['geometry']['coordinates'] != ways[ident]['coordinates']:
            errors.append({'osmWayId': ident, 'field': 'complete_original_coordinates'})
    source = current_name['properties']['source']
    expected_node = {key: source[key] for key in ['osmId', 'tags', 'objectVersion', 'objectTimestamp']}
    expected_node['coordinates'] = current_name['geometry']['coordinates']
    report = {'pbfSha256': PBF_SHA, 'pbfHeader': header, 'completeLocalSourceWayCount': len(ways),
              'expectedCompleteLocalSourceWayCount': len(expected), 'allOriginalFieldsMatch': not errors and len(ways) == len(expected),
              'comparedFields': ['all coordinates', 'all node references', 'complete tags', 'object version', 'object timestamp'],
              'currentNameNodeId': node_id, 'currentNameAllOriginalFieldsMatch': node == expected_node,
              'currentNamePointHasNoGeometryConstructionRole': True,
              'counts': dict(sorted(counts.items())), 'mismatches': errors, 'errors': []}
    if not report['allOriginalFieldsMatch'] or not report['currentNameAllOriginalFieldsMatch']:
        raise ValueError('Fresh PBF metadata/geometry readback mismatch: ' + str(errors[:5]))
    return ways, report


class SegmentIndex:
    def __init__(self, ways):
        self.metadata = []; starts = []; ends = []
        for ident, way in sorted(ways.items()):
            for index, (a, b) in enumerate(zip(way['coordinates'], way['coordinates'][1:])):
                if a == b:
                    continue
                starts.append(a); ends.append(b)
                self.metadata.append({'osmWayId': ident, 'sourceNodeIndex': index,
                                      'sourceNodeRefs': way['nodeRefs'][index:index+2],
                                      'sourceName': way['tags'].get('name', '')})
        self.starts = np.asarray(starts, dtype=float)
        self.vectors = np.asarray(ends, dtype=float)-self.starts
        self.squared = np.einsum('ij,ij->i', self.vectors, self.vectors)
    def point_distances(self, point):
        delta = np.asarray(point)-self.starts
        fractions = np.einsum('ij,ij->i', delta, self.vectors)/self.squared
        # Cross products in local coordinate differences avoid rounding an
        # absolute20/46-degree projected coordinate back onto the query point.
        perpendicular = np.abs(delta[:, 0]*self.vectors[:, 1]-delta[:, 1]*self.vectors[:, 0])/np.sqrt(self.squared)
        distances = np.where(fractions < 0, np.linalg.norm(delta, axis=1),
                             np.where(fractions > 1, np.linalg.norm(delta-self.vectors, axis=1), perpendicular))
        return distances, fractions
    def supports(self, a, b):
        da, ta = self.point_distances(a); db, tb = self.point_distances(b)
        indices = np.flatnonzero(np.maximum(da, db) < TOLERANCE)
        return [{**self.metadata[i], 'maxEndpointDistanceDegrees': float(max(da[i], db[i])),
                 'endpointFractionsOnOriginalNodePair': [float(ta[i]), float(tb[i])]} for i in indices]


def line_parts(geometry):
    if geometry.geom_type == 'LineString':
        return [geometry]
    if hasattr(geometry, 'geoms'):
        return [part for member in geometry.geoms for part in line_parts(member)]
    return []


def cross(a, b):
    return a[0]*b[1]-a[1]*b[0]


def intersection_review(coordinate, index, ways):
    distances, _ = index.point_distances(coordinate)
    hits = np.flatnonzero(distances < TOLERANCE)
    river = [i for i in hits if index.metadata[i]['osmWayId'] == 591675710]
    bridges = [i for i in hits if index.metadata[i]['osmWayId'] in {178546767, 370667751}]
    records = []
    for ri in river:
        for bi in bridges:
            p, v = index.starts[ri], index.vectors[ri]
            q, w = index.starts[bi], index.vectors[bi]
            denominator = cross(v, w)
            if denominator == 0:
                continue
            t, u = cross(q-p, w)/denominator, cross(q-p, v)/denominator
            value = p+t*v
            if 0 <= t <= 1 and 0 <= u <= 1:
                records.append({'riverOriginalNodePair': index.metadata[ri],
                                'bridgeOriginalNodePair': index.metadata[bi],
                                'analyticallyComputedCoordinate': value.tolist(),
                                'differenceFromSavedCoordinateDegrees': float(np.linalg.norm(value-np.asarray(coordinate))),
                                'riverTags': ways[591675710]['tags'],
                                'bridgeTags': ways[index.metadata[bi]['osmWayId']]['tags']})
    return {'coordinate': list(coordinate), 'originalBridgeCanalIntersectionVerified': any(
        row['differenceFromSavedCoordinateDegrees'] < TOLERANCE and row['bridgeTags'].get('bridge') == 'yes' for row in records),
        'pairs': records}


def constructor_review(manifest):
    constructor = OUT / 'raw/szentes-build-bounded-inference.py'
    text = constructor.read_text(); tree = ast.parse(text)
    reads = [ast.get_source_segment(text, node) for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'read_text']
    label_methods = [node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and node.func.attr in {'contains', 'covers', 'within'}]
    with tempfile.TemporaryDirectory(prefix='szentes-independent-replay-') as temp:
        target = Path(temp)
        for filename in ['szentes-local-lines.geojson', constructor.name]:
            shutil.copy2(OUT / 'raw' / filename, target / filename)
        process = subprocess.run([sys.executable, str(target / constructor.name)], cwd=ROOT,
                                 capture_output=True, text=True, check=True)
        outputs = [{'path': name, 'expectedSha256': digest, 'actualSha256': sha(target / name),
                    'matches': sha(target / name) == digest} for name, digest in manifest['replayOutputSha256'].items()]
    return {'constructorSourceTextReads': reads,
            'pointContainmentMethodCallsInConstructor': label_methods,
            'replayedWithOnlyLineworkAndConstructorFiles': True,
            'namePointFileAbsentFromReplayWorkspace': True,
            'allThreeOutputsReproducedByteIdentically': all(row['matches'] for row in outputs),
            'outputChecks': outputs,
            'faceChoiceRule': 'Minimum-area contiguous face union whose boundary includes all15 cited road names and the Kurca; no label-point test.',
            'sourceContourObserved': False}


def build():
    manifest = read('manifest.json')
    immutable = manifest['inputSha256']
    # Independent review artifacts are deliberately outside the immutable source
    # inputs; package review/registry/manifest may later add this review's hashes.
    source_fingerprints = [{'path': path, 'expectedSha256': digest, 'actualSha256': sha(OUT / path),
                            'matches': sha(OUT / path) == digest} for path, digest in sorted(immutable.items())
                           if path not in {'review.json', 'registry-entry.json', 'manifest.json', 'independent-review.py', 'independent-review.json'}]
    if not all(row['matches'] for row in source_fingerprints):
        raise ValueError('A frozen Szentes source input changed')
    if sha(OUT / 'inferred-candidate.geojson') != CANDIDATE_SHA:
        raise ValueError('Preferred blue candidate changed')
    local = read('raw/szentes-local-lines.geojson')['features']
    names = read('raw/current-name-points.geojson')['features']
    name = next(f for f in names if f['properties']['source']['osmId'] == 12088970184)
    ways, pbf = fresh_readback(local, name)
    index = SegmentIndex(ways)
    graph = unary_union([LineString(way['coordinates']) for way in ways.values()])
    parent_feature = next(f for f in read('raw/szentes-parent-control.geojson')['features'] if f['properties']['name'] == 'Szentes')
    parent = shape(parent_feature['geometry'])
    master_parents = json.loads((ROOT / '.local/neighborhoods/country/municipalities.geojson').read_text())['features']
    master_parent = next(f for f in master_parents if f['properties']['name'] == 'Szentes')
    parent_matches = parent_feature == master_parent
    proof = read('raw/szentes-bounded-inference-proof.json')
    semantic = read('semantic-proof.json')
    assumption_edge_count = 0
    assumption_edge_errors = []
    maximum_assumption_length_difference = 0.0
    for assumption in proof['assumptions']:
        for field in ['chosenPathEdges', 'directSideEdges', 'aroundSquareEdges']:
            for edge in assumption.get(field, []):
                assumption_edge_count += 1
                way = ways[edge['sourceWayId']]; i = edge['sourceNodeIndex']
                actual_coordinates = way['coordinates'][i:i+2]
                actual_refs = way['nodeRefs'][i:i+2]
                actual_length = transform(METRIC, LineString(actual_coordinates)).length
                maximum_assumption_length_difference = max(maximum_assumption_length_difference, abs(actual_length-edge['lengthM']))
                if (actual_coordinates != edge['coordinates'] or actual_refs != [edge['a'], edge['b']]
                        or way['tags'].get('name', '') != edge['name']):
                    assumption_edge_errors.append({'assumption': assumption['id'], 'field': field,
                                                   'osmWayId': edge['sourceWayId'], 'sourceNodeIndex': i})
    facts = read('raw/source-facts.json')['sourceFacts']['belvarosCircuitFactsInSourceOrder']
    raw_check = {row['file']: row for row in read('raw/szentes-final-checks.json')['results']}
    node_coordinates = {tuple(c) for way in ways.values() for c in way['coordinates']}
    candidates = [('preferred', 'inferred-candidate.geojson', 'szentes-belvaros-deak-side-inferred-review.geojson'),
                  ('alternative_same_quarter', 'raw/szentes-belvaros-apponyi-around-inferred-review.geojson', 'szentes-belvaros-apponyi-around-inferred-review.geojson')]
    reports = []; polygons = []; metrics = []
    validator_code = "import fs from 'node:fs';import{validateGeometry}from'./scripts/neighborhoods/build.mjs';const d=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));process.stdout.write(JSON.stringify(validateGeometry(d.features[0].geometry)));"
    assumption_edges = {}
    for a in proof['assumptions']:
        edges = a.get('chosenPathEdges', a.get('directSideEdges', []))
        assumption_edges[a['id']] = {(e['sourceWayId'], e['sourceNodeIndex']) for e in edges}
    for role, filename, proof_filename in candidates:
        feature = read(filename)['features'][0]; polygon = shape(feature['geometry'])
        metric = transform(METRIC, polygon); polygons.append(polygon); metrics.append(metric)
        segment_rows = []; unsupported = []; way_ids = set(); named_coverage = Counter(); inferred_lengths = Counter()
        ring = list(polygon.exterior.coords)
        for number, (a, b) in enumerate(zip(ring, ring[1:])):
            hits = index.supports(a, b)
            if not hits:
                unsupported.append(number)
            length = transform(METRIC, LineString([a, b])).length
            way_ids |= {h['osmWayId'] for h in hits}
            for source_name in {h['sourceName'] for h in hits}:
                named_coverage[source_name] += length
            row_assumptions = []
            for assumption in proof['assumptions']:
                keys = assumption_edges[assumption['id']]
                if role != 'preferred' and assumption['id'] == 'apponyi-square':
                    keys = {(e['sourceWayId'], e['sourceNodeIndex']) for e in assumption['aroundSquareEdges']}
                matches = any((h['osmWayId'], h['sourceNodeIndex']) in keys for h in hits)
                if assumption.get('chosenPhysicalBridgeWayId') in {h['osmWayId'] for h in hits}:
                    matches = True
                if role != 'preferred' and assumption['id'] == 'apponyi-square' and any(h['osmWayId'] == 149888202 for h in hits):
                    matches = True
                if matches:
                    row_assumptions.append(assumption['id']); inferred_lengths[assumption['id']] += length
            segment_rows.append({'edgeIndex': number, 'from': list(a), 'to': list(b), 'lengthMetres': length,
                                 'originalConsecutiveSegmentSupports': hits, 'sourceUnspecifiedAssumptionRoles': row_assumptions})
        constructed = [c for c in ring[:-1] if tuple(c) not in node_coordinates]
        intersections = [intersection_review(c, index, ways) for c in constructed]
        residual = polygon.boundary.difference(graph)
        residual_segments = [(a, b) for line in line_parts(residual) for a, b in zip(line.coords, list(line.coords)[1:])]
        residual_unsupported = [i for i, (a, b) in enumerate(residual_segments) if not index.supports(a, b)]
        strict = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', validator_code, str(OUT / filename)], cwd=ROOT, text=True))
        source_result = raw_check[proof_filename]
        outside = transform(METRIC, polygon.difference(parent)).area
        assumed_total = sum(row['lengthMetres'] for row in segment_rows if row['sourceUnspecifiedAssumptionRoles'])
        expected_roads = semantic['factAccounting']['explicitNamedRoadsRepresentedOnCandidateBoundary']
        reports.append({'role': role, 'path': filename, 'sha256': sha(OUT / filename),
                        'geosValid': polygon.is_valid, 'holeCount': len(polygon.interiors),
                        'verticesIncludingClosure': len(ring), 'boundarySegmentCount': len(ring)-1,
                        'areaSquareMetres': metric.area, 'perimeterMetres': metric.length,
                        'sumSegmentLengthsMetres': sum(r['lengthMetres'] for r in segment_rows),
                        'areaDifferenceFromProducerProofSquareMetres': abs(metric.area-source_result['areaM2']),
                        'strictProjectValidator': strict, 'outsideSzentesParentAreaSquareMetres': outside,
                        'parentCoversCandidate': parent.covers(polygon),
                        'unsupportedAnalyticSegments': unsupported, 'supportToleranceDegrees': TOLERANCE,
                        'supportMethod': 'Both endpoints lie on the same finite original consecutive OSM node pair; analytic projection onto that straight pair proves whole-segment support. No buffer, snap, repair or geometry modification.',
                        'verifiedBoundarySourceWayCount': len(way_ids), 'verifiedBoundarySourceWayIds': sorted(way_ids),
                        'maximumActualEndpointDistanceDegrees': max(h['maxEndpointDistanceDegrees'] for r in segment_rows for h in r['originalConsecutiveSegmentSupports']),
                        'literalOriginalNodeCoordinateVertexCount': len(ring)-1-len(constructed),
                        'analyticBridgeKurcaIntersectionVertexCount': len(constructed), 'analyticIntersections': intersections,
                        'rawExactGeosDifferenceFromFreshSourceGraphMetres': transform(METRIC, residual).length,
                        'producerRawExactGeosDifferenceMetres': source_result['rawGeosDifferenceFromEntireNodedSourceGraphM'],
                        'rawGeosResidualSubsegmentCount': len(residual_segments),
                        'unsupportedRawGeosResidualSubsegments': residual_unsupported,
                        'rawGeosResidualInterpretation': 'The exact overlay residual persists on analytically supported partial source segments at the two computed intersections. It is retained as floating collinearity evidence, not filled or repaired and not reported as a real source gap.',
                        'all15NamedRoadRolesRepresented': all(named_coverage[name] > 0 for name in expected_roads),
                        'namedRoleBoundaryLengthsMetres': {name: named_coverage[name] for name in expected_roads},
                        'kurcaBoundaryLengthMetres': named_coverage['Kurca'],
                        'sourceUnspecifiedChosenBoundaryLengthsMetres': dict(inferred_lengths),
                        'sourceUnspecifiedTotalBoundaryLengthMetresWithoutDoubleCount': assumed_total,
                        'sourceUnspecifiedPerimeterFraction': assumed_total/metric.length,
                        'namePointCoveredForIdentityReportOnly': polygon.covers(shape(name['geometry'])),
                        'sourceContourObservedFalse': feature['properties'].get('sourceContourIsObserved') is False,
                        'confidenceLow': feature['properties'].get('confidence') == 'low',
                        'addressAssignmentDisabled': feature['properties'].get('usableForAddressAssignment') is False,
                        'segments': segment_rows})
    symmetric_area = metrics[0].symmetric_difference(metrics[1]).area
    constructor = constructor_review(manifest)
    entry = read('registry-entry.json'); overrides = entry['propertyOverrides']
    source_roles = {'orderedFacts': facts, 'orderedItemCount': len(facts), 'uniqueFactCount': len(set(facts)),
                    'sourceFactsMatchSemanticProofExactly': facts == semantic['sourceStreetCadastralRiverFacts'],
                    'namedRoadRoleCount': semantic['factAccounting']['namedRoadCount'],
                    'remainingDistinctRoles': ['Kurca named waterway', 'Apponyi square/place reference', '4697 cadastral road reference', '5631 cadastral road reference'],
                    'kurcaFreshOriginalTags': ways[591675710]['tags'],
                    'kurcaGeometryUsesOsmCanalCenterline': ways[591675710]['tags'] == {'name': 'Kurca', 'waterway': 'canal'},
                    'cadastralIdentitiesRemainUnverified': all(not r['identityVerified'] for r in semantic['factAccounting']['cadastralRoles']),
                    'sixExplicitAssumptions': [{'id': a['id'], 'sourceRole': a['sourceRole'], 'qualification': a['qualification'],
                                               'chosenExistingRoadPathLengthMetres': a.get('chosenExistingRoadPathLengthM'),
                                               'directSideLengthMetres': a.get('directSideLengthM'), 'aroundSquareLengthMetres': a.get('aroundSquareLengthM')} for a in proof['assumptions']],
                    'assumptionPathEdgesVerifiedAgainstFreshOriginalWays': assumption_edge_count,
                    'assumptionPathEdgeMetadataMismatches': assumption_edge_errors,
                    'maximumAssumptionSourceEdgeLengthDifferenceMetres': maximum_assumption_length_difference,
                    'onlyApponyiHasSecondPolygonFootprint': True,
                    'otherFiveAssumptionsHaveOnlyOneChosenPathInThisCohort': True,
                    'sourceEra': semantic['sourceEra'], 'sourcePdfBytesOrMapContoursAvailable': False,
                    'sourceTextIndependentlyRefetchedInThisAudit': False,
                    'currentNamePointIsIdentityEvidenceOnly': True}
    registry_review = {'candidateSha256MatchesFrozenPreferred': entry['sha256'] == CANDIDATE_SHA,
                       'estimatedTrue': overrides.get('estimated') is True,
                       'boundaryKindInferredArea': overrides.get('boundaryKind') == 'inferred_area',
                       'candidateBoundaryKindNeighborhood': overrides.get('candidateBoundaryKind') == 'neighbourhood',
                       'canonicalNeighborhoodFalse': overrides.get('canonicalNameIsNeighborhood') is False,
                       'sourceOfficialAndHardBoundaryFalse': overrides.get('sourceIsOfficial') is False and overrides.get('sourceIsHardBoundary') is False,
                       'sourceContourObservedFalse': overrides.get('sourceContourIsObserved') is False,
                       'confidenceLow': overrides.get('confidence') == 'low', 'addressAssignmentDisabled': overrides.get('usableForAddressAssignment') is False,
                       'accuracyClaimNull': entry['accuracyMeters'] is None}
    checks = [pbf['allOriginalFieldsMatch'], pbf['currentNameAllOriginalFieldsMatch'], parent_matches,
              source_roles['sourceFactsMatchSemanticProofExactly'], len(facts) == 20, len(set(facts)) == 19,
              source_roles['namedRoadRoleCount'] == 15, len(proof['assumptions']) == 6,
              source_roles['cadastralIdentitiesRemainUnverified'], constructor['allThreeOutputsReproducedByteIdentically'],
              not assumption_edge_errors, maximum_assumption_length_difference < 1e-7,
              not constructor['pointContainmentMethodCallsInConstructor'], len(constructor['constructorSourceTextReads']) == 1,
              all(registry_review.values()), abs(symmetric_area-proof['alternatives']['appOnyiCandidatesSymmetricDifferenceM2']) < 1e-5]
    for index_number, report in enumerate(reports):
        checks += [report['geosValid'], report['holeCount'] == 0, report['strictProjectValidator']['valid'],
                   report['outsideSzentesParentAreaSquareMetres'] == 0, not report['unsupportedAnalyticSegments'],
                   not report['unsupportedRawGeosResidualSubsegments'], report['analyticBridgeKurcaIntersectionVertexCount'] == 2,
                   all(r['originalBridgeCanalIntersectionVerified'] for r in report['analyticIntersections']),
                   report['all15NamedRoadRolesRepresented'], report['kurcaBoundaryLengthMetres'] > 0,
                   report['areaDifferenceFromProducerProofSquareMetres'] < 1e-5,
                   report['sourceContourObservedFalse'], report['confidenceLow'], report['addressAssignmentDisabled']]
    checks += [reports[0]['boundarySegmentCount'] == 98, reports[0]['literalOriginalNodeCoordinateVertexCount'] == 96]
    if not all(checks):
        raise ValueError('Szentes independent check failure indices: ' + str([i for i, passed in enumerate(checks) if not passed]))
    return {'schemaVersion': 1, 'reviewer': 'independent local PBF and analytic-boundary reviewer', 'reviewDate': '2026-11-14',
            'allRequiredTechnicalChecksPassed': True, 'networkUsed': False,
            'frozenSourceInputsUnchanged': all(row['matches'] for row in source_fingerprints),
            'frozenSourceInputFingerprints': source_fingerprints,
            'freshPbfReadback': pbf, 'parentMatchesPinnedCountryMunicipalityExactly': parent_matches,
            'parentOsmRelationId': parent_feature['properties']['source']['osmId'],
            'candidateReviews': reports, 'constructorIndependence': constructor,
            'sourceRoleReview': source_roles, 'registryRestrictionsReview': registry_review,
            'alternativeComparison': {'preferredAreaSquareMetres': metrics[0].area, 'alternativeAreaSquareMetres': metrics[1].area,
                                      'symmetricDifferenceSquareMetres': symmetric_area,
                                      'symmetricDifferenceAsFractionOfPreferredArea': symmetric_area/metrics[0].area,
                                      'alternativeMinusPreferredAreaSquareMetres': metrics[1].area-metrics[0].area,
                                      'alternativeIsSameQuarterAndNotSecondExport': True, 'finiteAlternativeIsNotAbsoluteAccuracyBound': True},
            'limitations': ['Older municipal source contains2009/2010-era material and was reuploaded2015; exact adoption/edition and historical alignment remain unverified.',
                            'No original source PDF bytes or contour pixels were acquired; this audit checks the retained text-fact accounting and current OSM geometry, not an observed municipal contour.',
                            'All six source-unspecified junction choices remain inferred;4697/5631 cadastral-to-current-road identities remain unverified.',
                            'Only Apponyi is varied as a second polygon footprint. The other five junction assumptions retain one chosen physical path, without an exhaustive uncertainty envelope.',
                            'Current name evidence, including node12088970184 and later municipal maps, does not establish current or historical perimeter accuracy.'],
            'recommendation': {'newPrimarySupportedFeatures': 0, 'preferredLowConfidenceInferredFeatures': 1,
                               'additionalCompiledAlternativeFeatures': 0, 'sourceContourIsObserved': False,
                               'usableForAddressAssignment': False, 'absoluteAccuracyMetres': None},
            'sourceOrCandidateGeometryEdited': False, 'globalRegistryOrExportsEdited': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build(); content = encode(result)
    path = OUT / 'independent-review.json'
    if args.check:
        if path.read_text() != content:
            raise ValueError('Szentes independent audit changed')
    else:
        path.write_text(content)
    print(json.dumps({'allTechnicalChecksPassed': True, 'freshLocalWays': result['freshPbfReadback']['completeLocalSourceWayCount'],
                      'preferredSegments': result['candidateReviews'][0]['boundarySegmentCount'], 'compiledCandidates': 1,
                      'rawAlternativeOnly': 1, 'check': args.check}))
