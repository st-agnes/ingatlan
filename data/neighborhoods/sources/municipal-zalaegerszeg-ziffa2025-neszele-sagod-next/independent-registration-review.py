"""Independent Neszele source/world fit, topology, containment and identity audit."""
from pathlib import Path
import hashlib
import json

import numpy as np
from pyproj import Transformer
from shapely.affinity import affine_transform
from shapely.geometry import shape
from shapely.ops import transform
from shapely.validation import explain_validity

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
TO_EOV = Transformer.from_crs(4326, 23700, always_xy=True)
TO_WGS = Transformer.from_crs(23700, 4326, always_xy=True)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first_geom(path):
    return shape(read(path)['features'][0]['geometry'])


def eov(geom):
    return transform(TO_EOV.transform, geom)


registration_path = ROOT / 'neszele-registration.json'
reg = read(registration_path)
source_path = ROOT / 'neszele-literal-source-pixels.geojson'
source = first_geom(source_path)
assert source.is_valid and source.geom_type == 'Polygon' and not source.interiors
assert source.area == 40385
matrix = np.array(reg['pixelToEovMatrix'])
offset = np.array(reg['pixelToEovOffset'])
design, target = [], []
for control in reg['controls']:
    x, y = control['pixel']
    east, north = TO_EOV.transform(*control['wgs84'])
    design += [[x, y, 1, 0], [-y, x, 0, 1]]
    target += [east, north]
a, b, c, d = np.linalg.lstsq(np.array(design), np.array(target), rcond=None)[0]
assert np.max(np.abs(np.array([[a, b], [b, -a]]) - matrix)) < 1e-7
assert np.max(np.abs(np.array([c, d]) - offset)) < 1e-5

municipality_path = REPO / 'data/neighborhoods/sources/municipal-local-map-next/zalaegerszeg-calibration-municipality.geojson'
municipality = shape(read(municipality_path)['geometry'])
name_path = ROOT / 'current-name-evidence.geojson'
name_features = read(name_path)['features']
name_feature = next(f for f in name_features if f['properties']['name'] == 'Neszele')
name_point = shape(name_feature['geometry'])
variants = []
for filename, model in [('neszele-inferred-import.geojson', reg),
                         ('neszele-placement-alternative.geojson', reg['twoJunctionAlternative'])]:
    path = ROOT / filename
    feature = read(path)['features'][0]
    actual = shape(feature['geometry'])
    actual_eov = eov(actual)
    m, off = model['pixelToEovMatrix'], model['pixelToEovOffset']
    expected_eov = affine_transform(source, [m[0][0], m[0][1], m[1][0], m[1][1], off[0], off[1]])
    expected_wgs = transform(TO_WGS.transform, expected_eov)
    assert actual.is_valid and actual_eov.is_valid and actual.geom_type == 'Polygon'
    assert not actual.interiors
    assert actual.hausdorff_distance(expected_wgs) < 1e-11
    assert abs(actual_eov.area - feature['properties']['areaM2']) < 0.001
    assert municipality.covers(actual) and actual.covers(name_point)
    assert feature['properties']['estimated'] is True
    assert feature['properties']['estimatedContour'] is False
    assert feature['properties']['estimatedPlacement'] is True
    assert feature['properties']['claimedAbsoluteAccuracyMetres'] is None
    assert feature['properties']['usableForAddressAssignment'] is False
    variants.append({'path': filename, 'sha256': sha(path), 'type': actual.geom_type,
                     'isValidWgs84': actual.is_valid, 'isValidEov': actual_eov.is_valid,
                     'validityReason': explain_validity(actual), 'holes': len(actual.interiors),
                     'exteriorCoordinateCountIncludingClosure': len(actual.exterior.coords),
                     'areaM2RecomputedEov': actual_eov.area,
                     'areaMetadataAbsoluteDifferenceM2': abs(actual_eov.area - feature['properties']['areaM2']),
                     'sourceForwardTransformHausdorffDegrees': actual.hausdorff_distance(expected_wgs),
                     'municipalityFullContainment': True, 'outsideMunicipalityAreaM2': eov(actual.difference(municipality)).area,
                     'exactNamePointContained': True,
                     'namePointToBoundaryMetresDiagnosticOnly': eov(name_point).distance(actual_eov.boundary)})

main_eov = eov(first_geom(ROOT / 'neszele-inferred-import.geojson'))
alternative_eov = eov(first_geom(ROOT / 'neszele-placement-alternative.geojson'))
diagnostics = []
for ident, pixel, wgs, confidence, node_id in [
    ('jegmadar_jedlik', [310, 213], [16.8317051, 46.8561736], 'Moderate: small visible junction, approximately2sourcepixel manual picking.', 386168968),
    ('neszele_zala_malom', [179, 267], [16.8270657, 46.8548101], 'Moderate-to-low: source quarter band interferes with gray road, a few sourcepixels of picking ambiguity.', 347300965),
]:
    target_eov = np.array(TO_EOV.transform(*wgs))
    alt = reg['twoJunctionAlternative']
    diagnostics.append({'id': ident, 'sourcePixelXYApproximate': pixel, 'wgs84': wgs, 'originalOsmNodeId': node_id,
                        'sourcePickingCaveat': confidence, 'usedForFit': False,
                        'mainDifferenceMetresDiagnosticOnly': float(np.linalg.norm(matrix @ pixel + offset - target_eov)),
                        'alternativeDifferenceMetresDiagnosticOnly': float(np.linalg.norm(np.array(alt['pixelToEovMatrix']) @ pixel + np.array(alt['pixelToEovOffset']) - target_eov))})

old_paths = [
    REPO / 'data/neighborhoods/sources/municipal-local-map-next/zalaegerszeg-import.geojson',
    REPO / 'data/neighborhoods/sources/municipal-local-map-next/zalaegerszeg-quarantine.geojson',
    REPO / 'data/neighborhoods/sources/municipal-zalaegerszeg-remaining-next/remaining-inferred-import.geojson',
    REPO / 'data/neighborhoods/sources/municipal-zalaegerszeg-ziffa2025-next/hathaz-inferred-import.geojson',
]
comparisons = []
for path in old_paths:
    for feature in read(path)['features']:
        previous = eov(shape(feature['geometry']))
        comparisons.append({'input': str(path.relative_to(REPO)), 'name': feature['properties']['name'],
                            'exactCanonicalNameEqual': feature['properties']['name'] == 'Neszele',
                            'exactGeometryEqual': main_eov.equals(previous),
                            'intersectionAreaM2': main_eov.intersection(previous).area,
                            'distanceMetresDiagnosticOnly': main_eov.distance(previous)})
assert len(comparisons) == 14
assert not any(c['exactCanonicalNameEqual'] or c['exactGeometryEqual'] or c['intersectionAreaM2'] > 0 for c in comparisons)
sagod_path = ROOT / 'sagod-literal-source-pixels.geojson'
sagod_properties = read(sagod_path)['features'][0]['properties']
assert sagod_properties['quarantined'] and sagod_properties['literalThematicMaskNotAdmitted']
assert not sagod_properties['sourceContourObserved']
assert not (ROOT / 'sagod-inferred-import.geojson').exists()

inputs = [registration_path, source_path, municipality_path, name_path,
          ROOT / 'neszele-registration-preview.png', ROOT / 'independent-road-pbf-review.json',
          ROOT / 'independent-source-road-control-review.json', sagod_path, Path(__file__), *old_paths]
review = {
    'schemaVersion': 1,
    'reviewKind': 'independent_neszele_registration_topology_containment_and_identity_audit',
    'reviewer': 'independent child agent zala_semantic_qa',
    'status': 'passes_as_one_estimated_Neszele_candidate_with_placement_alternative; Sagod_remains_source_pixel_quarantine',
    'limitations': [
        'Absolute geographic accuracy remains unknown. Native387x329 map, thick quarter band, manual road centerlines, unknown backdrop age/projection and current-road generalization limit placement.',
        'Four-point similarity is a model assumption. Fit and holdout residuals are comparison diagnostics only; neither metre accuracy nor a complete uncertainty envelope is established.',
        'Ságod is separately named in the source but its literal dark component is thematically contaminated and remains excluded from world candidates.',
        'Consultation-study neighborhood extents do not establish surveyed/legal/cadastral boundaries or address assignment approval.',
    ],
    'inputs': [{'path': str(p.relative_to(REPO)), 'sha256': sha(p)} for p in inputs],
    'sourceTopology': {'type': source.geom_type, 'isValid': source.is_valid, 'areaSquarePixels': source.area,
                       'holes': len(source.interiors), 'exteriorCoordinateCountIncludingClosure': len(source.exterior.coords)},
    'independentRefit': {'model': 'E=a*x+b*y+c; N=b*x-a*y+d, independently least-squares fitted from4 recorded actual road-junction correspondences',
                         'maximumMatrixCoefficientDifference': float(np.max(np.abs(np.array([[a,b],[b,-a]]) - matrix))),
                         'maximumOffsetCoefficientDifference': float(np.max(np.abs(np.array([c,d]) - offset))),
                         'namePointUsedForFit': False},
    'visualRegistrationReview': 'Source/road correspondence reviewed independently: four junctions are identifiable, while the central label-obscured junction is excluded. Preview generally follows the network; manual-pick and model ambiguity remain.',
    'variants': variants,
    'independentRoadHoldoutDiagnostics': diagnostics,
    'alternativeDifference': {'symmetricDifferenceAreaM2': main_eov.symmetric_difference(alternative_eov).area,
                              'hausdorffMetres': main_eov.hausdorff_distance(alternative_eov),
                              'meaning': 'Two placement hypotheses of one contour only; not additional quarters or accuracy bounds.'},
    'identityReview': {'name': 'Neszele', 'sourceSchemaId': 'zalaegerszeg-ziffa2025-chapter3.4-unit16-map-neszele',
                       'sourceUnitNumber': 16, 'sharedChapterGroup': 'Neszele-Ságod',
                       'separateObservedFineContour': True, 'notParentCloneOrGroupAlias': True,
                       'previousFrozenFeaturesCompared': len(comparisons), 'comparisons': comparisons,
                       'SagodWorldCandidateAbsent': True, 'SagodSourcePixelQuarantineExplicit': True},
    'primaryFeatureCount': 0, 'estimatedFeatureCount': 1, 'placementAlternativeAdditionalFeatureCount': 0,
    'claimedAbsoluteAccuracyMetres': None, 'usableForAddressAssignment': False,
    'directNarrativeQuotationWords': 0, 'networkCallsPerformed': False,
    'globalRegistryModified': False, 'hathazFrozenPacketModified': False,
}
(ROOT / 'independent-registration-review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': review['status'], 'variants': variants,
                  'holdouts': diagnostics, 'alternativeDifference': review['alternativeDifference'],
                  'previousFeaturesCompared': len(comparisons)}, ensure_ascii=False, indent=2))
