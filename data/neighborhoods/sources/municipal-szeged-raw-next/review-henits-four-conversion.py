"""Audit source-cell export and independently implemented road-fit/world conversion."""
from pathlib import Path
import hashlib
import json

import numpy as np
from pyproj import Transformer
from shapely import contains_xy
from shapely.affinity import affine_transform
from shapely.geometry import MultiPoint, Point, shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
SCRATCH = REPO / '.local/neighborhoods/szeged-raw-review/henits2013'
TO_EOV = Transformer.from_crs(4326, 23700, always_xy=True)
TO_WGS = Transformer.from_crs(23700, 4326, always_xy=True)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eov(geometry):
    return transform(TO_EOV.transform, geometry)


reg_path = ROOT / 'registration.json'
reg = read(reg_path)
source_path = ROOT / 'henits-five-black60-source-pixels-working.geojson'
source_features = read(source_path)['features']
sources = {f['properties']['number']: shape(f['geometry']) for f in source_features}
assert set(sources) == {19, 20, 28, 11}
masks = np.load(SCRATCH / 'five-traces/black60-masks.npz')
source_checks = []
for number, geom in sources.items():
    assert geom.is_valid and geom.geom_type == 'Polygon' and not geom.interiors
    assert geom.area == int(masks[f'unit{number}'].sum())
    x0, y0, x1, y1 = map(int, geom.bounds)
    xx, yy = np.meshgrid(np.arange(x0, x1) + .5, np.arange(y0, y1) + .5)
    burned = contains_xy(geom, xx, yy)
    assert np.array_equal(burned, masks[f'unit{number}'][y0:y1, x0:x1])
    vertices = list(geom.exterior.coords)
    assert all(float(x).is_integer() and float(y).is_integer() for x, y in vertices)
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(vertices, vertices[1:]))
    source_checks.append({'number': number, 'sourcePixelArea': geom.area,
                          'sourceCellCentersExactlyEqualMask': True,
                          'allVerticesOnIntegerPixelGrid': True, 'allEdgesPixelAxisAligned': True,
                          'valid': True, 'holes': 0})

matrix, offset = np.array(reg['pixelToEovMatrix']), np.array(reg['pixelToEovOffset'])
design, target = [], []
for control in reg['controls']:
    x, y = control['pixel']
    east, north = TO_EOV.transform(*control['wgs84'])
    design += [[x, y, 1, 0], [-y, x, 0, 1]]
    target += [east, north]
a, b, c, d = np.linalg.lstsq(np.array(design), np.array(target), rcond=None)[0]
refit_matrix, refit_offset = np.array([[a, b], [b, -a]]), np.array([c, d])
assert np.max(np.abs(refit_matrix - matrix)) < 1e-7
assert np.max(np.abs(refit_offset - offset)) < 1e-5
control_hull = MultiPoint([c['pixel'] for c in reg['controls']]).convex_hull
road_path = ROOT / 'registration-road-controls.geojson'
road_features = {f['id']: f for f in read(road_path)['features']}
control_checks, metadata_notes = [], []
for control in reg['controls']:
    names, coordinates = set(), []
    for ident in control['sourceWays']:
        feature = road_features[ident]
        src = feature['properties']['source']
        assert control['osmNodeId'] in src['nodeRefs']
        at = src['nodeRefs'].index(control['osmNodeId'])
        coordinates.append(feature['geometry']['coordinates'][at])
        names.add(src['tags']['name'])
    assert all(co == control['wgs84'] for co in coordinates)
    matched = set(control['observedRoadJunction']) & names
    assert len(matched) >= 2
    missing = set(control['observedRoadJunction']) - names
    if missing:
        metadata_notes.append({'control': control['id'], 'describedRoadNamesNotIncidentAtOriginalNode': sorted(missing),
                               'meaning': 'Nearby/divided outer-ring arm is not automatically incident at this exact original road node. Source control location/model is unaffected.'})
    control_checks.append({'id': control['id'], 'originalNodeId': control['osmNodeId'],
                           'originalWayNodeCoordinatesAgree': True, 'actualIncidentRoadNames': sorted(names),
                           'atLeastTwoNamedPhysicalRoadsMeetAtOriginalNode': True,
                           'allDescribedNamesIncidentAtNode': not bool(missing)})

municipality_path = REPO / 'data/neighborhoods/sources/municipal-szeged-next/municipality.geojson'
municipality = shape(read(municipality_path)['features'][0]['geometry'])
old_path = REPO / 'data/neighborhoods/sources/municipal-szeged-next/szeged-street-candidates.geojson'
old = read(old_path)['features']
rows, world_by_variant = [], {}
for variant, filename, model in [
    ('main', 'szeged-four-inferred-import.geojson', reg),
    ('three-junction', 'szeged-four-placement-alternative.geojson', reg['alternatives']['threeJunctionSimilarity']),
]:
    features = read(ROOT / filename)['features']
    assert len(features) == 4
    current = {}
    for feature in features:
        p = feature['properties']
        number = p['sourceUnitNumber']
        actual = shape(feature['geometry'])
        actual_eov = eov(actual)
        m, off = model['pixelToEovMatrix'], model['pixelToEovOffset']
        expected_eov = affine_transform(sources[number], [m[0][0], m[0][1], m[1][0], m[1][1], off[0], off[1]])
        expected_wgs = transform(TO_WGS.transform, expected_eov)
        assert actual.hausdorff_distance(expected_wgs) < 1e-11
        assert actual.is_valid and actual.geom_type == 'Polygon' and not actual.interiors
        assert municipality.covers(actual)
        assert abs(actual_eov.area - p['areaM2']) < .001
        assert p['sourceContourObserved'] and not p['estimatedContour']
        assert p['estimated'] and p['estimatedPlacement'] and not p['canonicalNameIsNeighborhood']
        assert p['claimedAbsoluteAccuracyMetres'] is None and not p['usableForAddressAssignment']
        assert p['controlHullCoverageFraction'] == 0 and p['placementConfidence'] == 'low'
        outside_fraction = sources[number].difference(control_hull).area / sources[number].area
        assert outside_fraction == 1
        name_checks = []
        for evidence in p['sourceLabelEvidence']:
            inside = actual.covers(Point(*evidence['coordinates']))
            assert inside == evidence['insideCandidate'] and not evidence['usedForFit']
            name_checks.append({'name': evidence['name'], 'id': evidence['id'], 'inside': inside,
                                'usedForFit': False})
        assert all(r['inside'] for r in name_checks if r['name'] != 'Hattyas')
        if number == 19:
            assert not next(r for r in name_checks if r['name'] == 'Hattyas')['inside']
        old_checks = [{'name': o['properties']['name'], 'exactGeometryEqual': actual.equals(shape(o['geometry'])),
                       'intersectionAreaM2': actual_eov.intersection(eov(shape(o['geometry']))).area}
                      for o in old]
        assert not any(o['exactGeometryEqual'] or o['intersectionAreaM2'] > 0 for o in old_checks)
        rows.append({'variant': variant, 'sourceUnitNumber': number, 'name': p['name'],
                     'sourceForwardTransformHausdorffDegrees': actual.hausdorff_distance(expected_wgs),
                     'valid': True, 'holes': 0, 'insideMunicipality': True,
                     'areaM2RecomputedEov': actual_eov.area,
                     'sourceInteriorFractionOutsideControlHull': outside_fraction,
                     'nameEvidenceChecks': name_checks, 'existingTarjanAndPlanningComparisons': old_checks})
        current[number] = actual_eov
    for number, geom in current.items():
        assert all(geom.intersection(g).area == 0 for n, g in current.items() if n != number)
    world_by_variant[variant] = current

holdouts = []
for ident, pixel, wgs, node_id, caveat in [
    ('szilleri_romai', [740, 314], [20.1614145, 46.2603496], 27225705,
     'Visible7/22/core triple junction, identified as Szilléri/Római using the KSH gray-road companion. Approximately2–3nativepixel picking/generalization ambiguity.'),
    ('retek_jozsef_north_arm', [715, 256], [20.1575691, 46.2669732], 3994379097,
     'Visible23/22/7 junction; the present Retek/József intersection has offset north/south arms. This uses the northern arm; source graphic does not resolve carriageway corners precisely.'),
]:
    target_eov = np.array(TO_EOV.transform(*wgs))
    alternative = reg['alternatives']['threeJunctionSimilarity']
    holdouts.append({'id': ident, 'sourcePixelXYApproximate': pixel, 'wgs84': wgs,
                     'originalNodeId': node_id, 'usedForFit': False, 'sourcePickingCaveat': caveat,
                     'mainDifferenceMetresDiagnosticOnly': float(np.linalg.norm(matrix @ pixel + offset - target_eov)),
                     'alternativeDifferenceMetresDiagnosticOnly': float(np.linalg.norm(np.array(alternative['pixelToEovMatrix']) @ pixel + np.array(alternative['pixelToEovOffset']) - target_eov))})

affine_path = SCRATCH / 'affine-world-diagnostic-local-only.geojson'
affine = {f['properties']['sourceUnitNumber']: eov(shape(f['geometry'])) for f in read(affine_path)['features']}
model_differences = []
for number, main in world_by_variant['main'].items():
    alt = world_by_variant['three-junction'][number]
    model_differences.append({'sourceUnitNumber': number,
                              'threeJunctionHausdorffMetresDiagnosticOnly': main.hausdorff_distance(alt),
                              'threeJunctionSymmetricDifferenceM2': main.symmetric_difference(alt).area,
                              'nonPreferredAffineHausdorffMetresDiagnosticOnly': main.hausdorff_distance(affine[number]),
                              'meaning': 'Retained model hypotheses/sensitivity only; not confidence bounds or absolute accuracy.'})

inputs = [reg_path, source_path, road_path, municipality_path, old_path,
          ROOT / 'current-name-evidence.geojson', ROOT / 'szeged-four-inferred-import.geojson',
          ROOT / 'szeged-four-placement-alternative.geojson', ROOT / 'henits-road-pbf-review-working.json',
          ROOT / 'henits-four-world-strict-review-working.json', Path(__file__)]
review = {'schemaVersion': 1,
          'status': 'passes_source_export_and_world_conversion_checks_as_four_low_confidence_estimated_candidates_only',
          'reviewerRoles': {'sourcePixelGeometry': 'Author cross-check with independent pixel-center rasterization and axis/grid checks; source geometry was authored by this agent. Parent/root visual review is separate.',
                            'roadReferenceAndWorldConversion': 'Independent of road extraction, source control picking, model fitting and world converter.'},
          'inputs': [{'path': str(p.relative_to(REPO)), 'sha256': sha(p)} for p in inputs],
          'limitationsProminent': [
              'ALL FOUR source interiors lie entirely outside the six-control convex hull. Every placement is extrapolation under the map/model assumption; controlHullCoverageFraction is0 and placementConfidence islow.',
              'No absolute positional accuracy is established. The map is a generalizedKSH2003-era scheme reproduced in2013, not a survey of current/full historical neighborhood boundaries.',
              'Main six-control similarity is a plausible preferred estimate supported by source scale consistency. The affine model is weakly constrained outside the control region and is a nonpreferred local diagnostic; it varies by hundreds of metres for eastern/southwestern units.',
              'Holdouts remain central/northern and cannot independently validate far-southwest/east target placement. No quarter-name point was used as a fit control.',
          ],
          'authorSourceExportCrossChecks': source_checks,
          'independentSimilarityRefit': {'matrixMaximumDifference': float(np.max(np.abs(refit_matrix - matrix))),
                                          'offsetMaximumDifference': float(np.max(np.abs(refit_offset - offset)))},
          'originalRoadNodeControlChecks': control_checks,
          'metadataNotes': metadata_notes,
          'physicalCorrespondenceReview': 'Six proposed junctions are credible matches to the source road/quarter pattern. The6/7divider is Csongrádi, not József Attila. Three western outer-ring vertices are the Kossuth, Kálvária and Petőfi radials; northern controls agree with the companion gray-road network. This does not establish survey accuracy.',
          'unusedRoadHoldoutDiagnostics': holdouts,
          'rejectedHoldoutIdea': 'József/TiszaLajos and Kossuth/TiszaLajos positions are not clearly marked physical junctions in the cleanHenits image; radial strokes within core2 are omitted. Do not invent their exact Henits pixel positions along a smooth ring.',
          'worldConversionChecks': rows, 'modelDifferences': model_differences,
          'pairwiseWorldInteriorOverlaps': 0, 'existingPrimaryOrPlanningGeometryOverlaps': 0,
          'sourceIdentityDisposition': 'Four explicitly keyed source identities only. Tarján23 and Felsőváros22/Ófelsőváros7 are deferred; no existing parent geometry was cloned. The distinct southernHattyas point remains separate from Klebelsberg. Unit27literal tracing remains quarantined with no world candidate.',
          'preferredModelDisposition': 'Retain six-junction main only as an explicitly low-confidence estimated placement with the three-junction alternative and affine sensitivity caveat. No coordinate/topology failure requires source-mask quarantine for these four. A current/legal/address-boundary claim would require additional local evidence.',
          'estimatedIdentityCount': 4, 'primaryFeatureCount': 0, 'additionalAlternativeIdentityCount': 0,
          'claimedAbsoluteAccuracyMetres': None, 'usableForAddressAssignment': False,
          'sourceGeometryOrWorldFilesModified': False, 'globalRegistryModified': False,
          'frozenPacketsModified': False, 'directNarrativeQuotationWords': 0}
(ROOT / 'independent-registration-review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': review['status'], 'sourceUnits': sorted(sources), 'worldFeatureVariantsChecked': len(rows),
                  'sourceCellMasksExactlyPreserved': True, 'allTargetInteriorsOutsideControlHull': True,
                  'holdouts': holdouts, 'modelDifferences': model_differences}, ensure_ascii=False, indent=2))
