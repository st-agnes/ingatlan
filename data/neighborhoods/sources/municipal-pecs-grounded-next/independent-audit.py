#!/usr/bin/env python3
"""Independent numerical/raw-link audit; no approval of geographic correspondence."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from pyproj import Transformer, network
from shapely.geometry import Point, MultiPoint, shape
from shapely.ops import transform, unary_union

network.set_network_enabled(False)
P = Path(__file__).resolve().parent
TO = Transformer.from_crs(4326, 23700, always_xy=True).transform


def read(name):
    return json.loads((P / name).read_text())


def sha(name):
    return hashlib.sha256((P / name).read_bytes()).hexdigest()


def summary(values):
    a = np.array(values, dtype=float)
    return dict(count=len(a), minimum=float(a.min()), median=float(np.median(a)),
                rms=float(np.sqrt(np.mean(a ** 2))), percentile95=float(np.percentile(a, 95)),
                maximum=float(a.max()))


def same(a, b, tolerance=1e-6):
    assert np.allclose(a, b, atol=tolerance, rtol=0), (a, b)


def compare_summary(a, b):
    assert a.keys() == b.keys()
    for key in a:
        same(a[key], b[key])


def segment_intersection(a, b, c, d):
    """Independent 2D determinant intersection, not author's Shapely intersection."""
    a, b, c, d = [np.array(TO(*v)) for v in [a, b, c, d]]
    u, v = b - a, d - c
    cross = lambda x, y: x[0] * y[1] - x[1] * y[0]
    determinant = cross(u, v)
    assert abs(determinant) > 1e-10
    s, t = cross(c - a, v) / determinant, cross(c - a, u) / determinant
    assert 0 <= s <= 1 and 0 <= t <= 1
    same(a + s * u, c + t * v, 1e-7)
    return a + s * u


def solve(x, y):
    """Independent centered covariance solve; avoid author's augmented lstsq."""
    xbar, ybar = x.mean(axis=0), y.mean(axis=0)
    linear = np.linalg.solve((x - xbar).T @ (x - xbar), (x - xbar).T @ (y - ybar))
    return np.vstack((linear, ybar - xbar @ linear))


def audit():
    model, calc, diag = [read(n) for n in ['model.json', 'calculation-proof.json', 'diagnostics.json']]
    boundary, road, ways, road_proof = [read(n) for n in [
        'boundary-source-proof.json', 'source-road-controls.json', 'source-road-ways.geojson', 'source-road-proof.json']]
    original = {f['properties']['osmWayId']: f for f in ways['features']}
    nodes = {n['osmNodeId']: n['coordinates'] for n in boundary['rawBoundaryNodes']}
    members = {w['osmWayId']: w['nodeRefs'] for w in boundary['rawMemberWays']}
    assert len(members) == 32 and len(nodes) == 535
    assert road_proof['archiveSha256'] == sha('source-road-ways.geojson')
    assert boundary['sourceMunicipalitySha256'] == sha('source-municipality.geojson')
    for item in calc['inputs']:
        assert sha(item['path']) == item['sha256']
    pairs = calc['fitControls']
    assert len(pairs) == 5
    targets = []
    raw_checks = []
    for i, pair in enumerate(pairs):
        if i < 3:
            assert pair['sourcePixel'] == boundary['cornerLinks'][i]['sourcePixel']
            for node_id in pair['actualOsmNodeIds']:
                assert nodes[node_id] == pair['targetWgs84']
                assert any(node_id in members[w] for w in pair['actualSourceMemberWays'])
            target = np.array(TO(*pair['targetWgs84']))
            raw_checks.append(dict(id=pair['id'], literalBoundaryNodeIds=pair['actualOsmNodeIds'],
                                   coordinateAndMembershipMatch=True, imageVertexCorrespondenceApproved=False))
        else:
            intersections = []
            for cross in pair['originalRoadwayCrossingProof']:
                motorway, other = [original[cross[k]] for k in ['motorwayWayId', 'crossRoadWayId']]
                for prefix, feature in [('motorway', motorway), ('crossRoad', other)]:
                    j = cross[prefix + 'SegmentIndex']
                    assert feature['properties']['nodeRefs'][j:j + 2] == cross[prefix + 'OriginalNodeRefs']
                    assert feature['geometry']['coordinates'][j:j + 2] == cross[prefix + 'OriginalCoordinates']
                crossing = segment_intersection(*cross['motorwayOriginalCoordinates'], *cross['crossRoadOriginalCoordinates'])
                same(crossing, cross['eovPlanCrossing'], 1e-7)
                intersections.append(crossing)
            target = np.mean(intersections, axis=0)
            raw_checks.append(dict(id=pair['id'], mainCarriagewayCrossingsRecomputed=True,
                                   isLiteralOsmCrossingNode=False, absoluteAccuracyApproved=False))
        same(target, pair['targetEov'], 1e-7)
        targets.append(target)
    x, y = np.array([p['sourcePixel'] for p in pairs], dtype=float), np.array(targets)
    a = np.column_stack((x, np.ones(len(x))))
    independent = solve(x, y)
    same(independent, model['matrixPixelToEov'], 1e-6)
    residuals = a @ independent - y
    compare_summary(summary(np.linalg.norm(residuals, axis=1)), model['fitResidualSummaryMetres'])
    inv = np.linalg.inv(independent[:2])
    image_residuals = (y - independent[2]) @ inv - x
    compare_summary(summary(np.linalg.norm(image_residuals, axis=1)), model['fitInverseImageResidualSummaryPixels'])
    for i, pair in enumerate(pairs):
        same(residuals[i], pair['fitResidualEov'])
        same(image_residuals[i], pair['fitInverseImageResidualPixels'])
    municipality = transform(TO, shape(read('source-municipality.geojson')['geometry'])).boundary
    gray = read('source-gray-control-pixels.json')['records']
    retained = [p for p in gray if tuple(p['pixel']) not in {tuple(v) for v in x}]
    assert len(retained) == len(diag['heldoutGrayBoundary']['records']) == 51
    gray_distances = []
    for source, reported in zip(retained, diag['heldoutGrayBoundary']['records']):
        assert source['pixel'] == reported['sourcePixel']
        predicted = np.r_[source['pixel'], 1] @ independent
        distance = municipality.distance(Point(predicted))
        same(distance, reported['distanceToArchivedCurrentMunicipalityMetres'])
        gray_distances.append(distance)
    compare_summary(summary(gray_distances), diag['heldoutGrayBoundary']['summaryMetres'])
    line_diagnostics = []
    for source, reported in zip(road['lineControls'], diag['heldoutRoadLines']):
        assert source['roadReference'] == reported['roadReference']
        target = unary_union([transform(TO, shape(original[w]['geometry'])) for w in source['targetOriginalWayIds']])
        distances = []
        for observation, result in zip(source['sourceObservations'], reported['observations']):
            assert observation['sourcePixel'] == result['sourcePixel']
            predicted = np.r_[observation['sourcePixel'], 1] @ independent
            distance = target.distance(Point(predicted))
            same(distance, result['crossTrackDistanceMetres'])
            distances.append(distance)
        compare_summary(summary(distances), reported['summaryMetres'])
        assert reported['independentAbsoluteValidation'] is False
        line_diagnostics.append(dict(reference=source['roadReference'], summaryMetres=summary(distances)))
    checkpoints = diag['readingSensitivity']['checkpoints']
    q = np.array([[*c['sourcePixel'], 1] for c in checkpoints])
    baseline = q @ independent
    hull = MultiPoint(x).convex_hull
    for c in checkpoints:
        assert hull.covers(Point(c['sourcePixel'])) == c['insideFitControlConvexHull']
    for i, report in enumerate(diag['leaveOneOut']):
        keep = np.arange(len(x)) != i
        m = solve(x[keep], y[keep])
        same(m, report['matrixPixelToEov'])
        same(np.linalg.norm(a[i] @ m - y[i]), report['omittedControlPredictionErrorMetres'])
        same(np.linalg.norm(q @ m - baseline, axis=1), report['checkpointDisplacementsMetres'])
    rng = np.random.default_rng(diag['readingSensitivity']['seed'])
    uncertainty = np.array([p['sourceImageReadingUncertaintyPixels'] for p in pairs])
    scenario = []
    for _ in range(diag['readingSensitivity']['trials']):
        perturbed = x + rng.uniform(-1, 1, x.shape) * uncertainty
        scenario.append(np.linalg.norm(q @ solve(perturbed, y) - baseline, axis=1))
    scenario = np.array(scenario)
    for j, c in enumerate(checkpoints):
        compare_summary(summary(scenario[:, j]), c['readingPerturbationDisplacementMetres'])
    for flag in ['automaticPrimaryApproval', 'surveyOrCadastralAccuracyApproved', 'usableForAddressAssignment',
                 'quarterGeometriesGeneratedOrChanged', 'fitResidualIsAbsoluteAccuracy']:
        assert model[flag] is False
    assert model['absoluteBoundaryAccuracyMetres'] is None
    inputs = ['model.json', 'calculation-proof.json', 'diagnostics.json', 'boundary-source-proof.json',
              'source-road-controls.json', 'source-road-ways.geojson', 'source-road-proof.json',
              'source-municipality.geojson', 'source-corner-candidates.json', 'source-gray-control-pixels.json',
              'source-name-map.jpeg', 'source-control-crops.png', 'candidate-model-overlay.png']
    return dict(
        schemaVersion=1, reviewScope='Independent offline arithmetic/raw-link audit and source-image inspection; no new geographic controls or quarter geometry.',
        status='arithmetic_and_archived_raw_links_pass_geographic_correspondence_not_approved',
        authorBuildScriptImportedOrInvoked=False, networkUsed=False,
        independentNumericalMethod='Centered 2x2 covariance solve; determinant segment intersections. Author uses augmented affine least squares and Shapely intersections.',
        checkedInputHashes=[dict(path=n, sha256=sha(n)) for n in inputs],
        checkedControls=raw_checks,
        fivePairAffineAndResidualsRecomputed=True, heldoutGrayDistancesRecomputed=True,
        heldoutRoadCrossTrackDistancesRecomputed=True, leaveOneOutRecomputed=True,
        seeded2000ScenarioSensitivityRecomputed=True,
        rawPbfIndependentlyRescannedByThisAudit=False,
        rawPbfEvidenceScope='This audit checks the complete archived node/way linkage and hashes. Separate source-proof records report independent exact PBF reads; this audit does not claim a third PBF read.',
        fitResidualRmsMetres=float(np.sqrt(np.mean(np.sum(residuals ** 2, axis=1)))),
        heldoutGraySummaryMetres=summary(gray_distances), heldoutRoadSummaries=line_diagnostics,
        sourceImageFindings=[
            dict(control='gray-corner-1', imagePixel=[160,162], observation='Marker lies on the approximately vertical gray stroke, not on its visibly sharper L turn at approximately [160,167]. Literal OSM target ring vertex455 is also on a nearly vertical segment; the actual sharp westward turn is vertex457. Thus a coordinate mismatch is NOT established, but a distinctive corner-to-vertex point identity is NOT established either.',
                 fitPairApproved=False, readingUncertaintyIsNotCorrespondenceUncertainty=True,
                 possibleNewControl=dict(sourcePixelApproximate=[160,167], targetOuterRingVertexIndex=457, targetOsmNodeId=684770966, targetWgs84=[18.1848498,46.1107725], approved=False)),
            dict(control='gray-corner-2', imagePixel=[286,83], observation='Marker is on the western side of the wider gray trough, rather than its obvious low bend. Literal target vertex388 is a small zigzag adjacent to the larger low bend. It may correspond, but the blurred thick stroke does not independently distinguish this exact small vertex. No definite coordinate mismatch is asserted.',
                 fitPairApproved=False, possibleNewControl=dict(sourcePixelApproximate=[294,86], targetOuterRingVertexIndex=386, targetOsmNodeId=684771054, targetWgs84=[18.2401705,46.1351487], approved=False)),
            dict(control='gray-corner-3', imagePixel=[75,151], observation='Source marker is near the broad northwestern shoulder apex. Its form is consistent with the literal vertex467 and its neighbouring ring directions. The old/current exact boundary correspondence and absolute accuracy remain unverified.', fitPairApproved=False),
            dict(control='road-crossing-1', observation='Crop visibly places the selected box at the southbound road / red motorway crossing; raw determinant crossings and actual way references agree with the stored target. Source map does not print road references, so raw-graph identity and map reading remain interpretation evidence, not surveyed control.', absoluteAccuracyApproved=False),
            dict(control='road-crossing-2', observation='Crop visibly places the selected box at the crossroad passing through the motorway interchange loop. Stored current578 raw-way identity and crossing arithmetic are consistent. Source map has no printed578 label, so this audit does not independently establish historical road identity or survey accuracy.', absoluteAccuracyApproved=False)
        ],
        limitations=[
            'Fit residuals measure agreement among assumed pairs, not the correctness of manual source-to-world correspondence.',
            'At least two gray controls are not unambiguous distinctive corners. Their reading boxes cannot substitute for unknown correspondence uncertainty.',
            '51 heldout gray-stroke pixels share the boundary feature with fit corners and have unverified historical/current correspondence. The maximum approximately475m discrepancy is retained.',
            'Road-line checks are along-track ambiguous; M60 checks share the physical feature with the two fitted road crossings.',
            'Eastern and northeastern checkpoints are outside the five-control convex hull. The assumed pixel-reading perturbation scenario gives approximately182m p95 displacement there; these are not confidence intervals or absolute error bounds.',
            'Current OSM coordinates, old/generalised cartography and municipal map reuse permissions are not transformed into cadastral or legal authority by this numerical audit.'
        ],
        georeferenceModelApproved=False, automaticPrimaryApproval=False,
        usableForAddressAssignment=False, absoluteBoundaryAccuracyMetres=None,
        independentNewQuarterGeometriesCreated=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    report = json.dumps(audit(), ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.check:
        assert (P / 'independent-review.json').read_text() == report
    else:
        (P / 'independent-review.json').write_text(report)
    print(json.dumps(dict(check=args.check, arithmetic=True, georeferenceModelApproved=False)))
