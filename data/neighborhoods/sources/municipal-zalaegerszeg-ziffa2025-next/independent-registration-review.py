"""Independent frozen similarity/identity/containment checks; no fit mutation."""
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


registration_path = ROOT / 'hathaz-registration.json'
reg = read(registration_path)
source_path = ROOT / 'hathaz-observed-source-pixels.geojson'
source = first_geom(source_path)
matrix = np.array(reg['pixelToEovMatrix'])
offset = np.array(reg['pixelToEovOffset'])

# Refit from the recorded WGS84 road/footprint correspondences, independently.
design, target = [], []
for control in reg['controls']:
    x, y = control['pixel']
    east, north = TO_EOV.transform(*control['wgs84'])
    design += [[x, y, 1, 0], [-y, x, 0, 1]]
    target += [east, north]
a, b, c, d = np.linalg.lstsq(np.array(design), np.array(target), rcond=None)[0]
recomputed_matrix = np.array([[a, b], [b, -a]])
recomputed_offset = np.array([c, d])
assert np.max(np.abs(recomputed_matrix - matrix)) < 1e-7
assert np.max(np.abs(recomputed_offset - offset)) < 1e-5

municipality_path = REPO / 'data/neighborhoods/sources/municipal-local-map-next/zalaegerszeg-calibration-municipality.geojson'
municipality = shape(read(municipality_path)['geometry'])
name_path = ROOT / 'current-name-evidence.geojson'
name_feature = read(name_path)['features'][0]
name_point = shape(name_feature['geometry'])
variants = []
for filename, model in [
    ('hathaz-inferred-import.geojson', reg),
    ('hathaz-placement-alternative.geojson', reg['roadOnlyAlternative']),
]:
    path = ROOT / filename
    feature = read(path)['features'][0]
    actual = shape(feature['geometry'])
    actual_eov = eov(actual)
    m = model['pixelToEovMatrix']
    off = model['pixelToEovOffset']
    expected_eov = affine_transform(source, [m[0][0], m[0][1], m[1][0], m[1][1], off[0], off[1]])
    expected_wgs = transform(TO_WGS.transform, expected_eov)
    assert actual.is_valid and actual_eov.is_valid and actual.geom_type == 'Polygon'
    assert len(actual.interiors) == 0
    assert actual.hausdorff_distance(expected_wgs) < 1e-11
    assert abs(actual_eov.area - feature['properties']['areaM2']) < 0.001
    assert municipality.covers(actual)
    assert actual.covers(name_point)
    variants.append({
        'path': filename, 'sha256': sha(path), 'geometryType': actual.geom_type,
        'isValidWgs84': actual.is_valid, 'isValidEov': actual_eov.is_valid,
        'validityReason': explain_validity(actual), 'holes': len(actual.interiors),
        'areaM2RecomputedEov': actual_eov.area,
        'areaMetadataAbsoluteDifferenceM2': abs(actual_eov.area - feature['properties']['areaM2']),
        'exactSourceContourForwardTransformHausdorffDegrees': actual.hausdorff_distance(expected_wgs),
        'municipalityFullContainment': municipality.covers(actual),
        'outsideMunicipalityAreaM2': eov(actual.difference(municipality)).area,
        'exactNamePointContained': actual.covers(name_point),
        'namePointToBoundaryMetresDiagnosticOnly': eov(name_point).distance(actual_eov.boundary),
    })

main_eov = eov(first_geom(ROOT / 'hathaz-inferred-import.geojson'))
alternative_eov = eov(first_geom(ROOT / 'hathaz-placement-alternative.geojson'))
diagnostics = []
for ident, pixel, wgs, confidence in [
    ('northern_west_fieldtrack_junction', [140, 89], [16.7930263, 46.8910831], 'Visible junction; source pixel manually read approximately; road center broadened by raster.'),
    ('northwestern_fieldtrack_endpoint', [33, 79], [16.7900598, 46.8912379], 'Faint track adjacent to outline; credible approximate off-axis correspondence but endpoint picking has lower confidence.'),
]:
    actual_eov = np.array(TO_EOV.transform(*wgs))
    main_difference = float(np.linalg.norm(matrix @ pixel + offset - actual_eov))
    alt_matrix = np.array(reg['roadOnlyAlternative']['pixelToEovMatrix'])
    alt_offset = np.array(reg['roadOnlyAlternative']['pixelToEovOffset'])
    alt_difference = float(np.linalg.norm(alt_matrix @ pixel + alt_offset - actual_eov))
    diagnostics.append({'id': ident, 'sourcePixelXY': pixel, 'wgs84': wgs,
                        'mainDifferenceMetresDiagnosticOnly': main_difference,
                        'roadOnlyDifferenceMetresDiagnosticOnly': alt_difference,
                        'correspondenceCaveat': confidence,
                        'independenceLimitation': 'Both points belong to one mapped road and source panel; not independent survey controls.'})

old_paths = [
    REPO / 'data/neighborhoods/sources/municipal-local-map-next/zalaegerszeg-import.geojson',
    REPO / 'data/neighborhoods/sources/municipal-local-map-next/zalaegerszeg-quarantine.geojson',
    REPO / 'data/neighborhoods/sources/municipal-zalaegerszeg-remaining-next/remaining-inferred-import.geojson',
]
duplicates = []
for path in old_paths:
    for feature in read(path)['features']:
        previous = eov(shape(feature['geometry']))
        duplicates.append({'input': str(path.relative_to(REPO)), 'name': feature['properties']['name'],
                           'exactGeometryEqual': main_eov.equals(previous),
                           'intersectionAreaM2': main_eov.intersection(previous).area,
                           'distanceMetresDiagnosticOnly': main_eov.distance(previous),
                           'exactCanonicalNameEqual': feature['properties']['name'] == 'Hatház'})
assert not any(f['exactGeometryEqual'] or f['exactCanonicalNameEqual'] or f['intersectionAreaM2'] > 0 for f in duplicates)

inputs = [registration_path, source_path, ROOT / 'hathaz-geographic-reference.geojson',
          municipality_path, name_path, ROOT / 'hathaz-registration-preview.png', Path(__file__), *old_paths]
review = {
    'schemaVersion': 1,
    'reviewKind': 'independent_registration_source_to_world_containment_and_identity_review',
    'reviewer': 'independent child agent zala_semantic_qa',
    'status': 'passes_as_one_explicitly_estimated_placement_candidate_with_retained_alternative',
    'limitations': [
        'No absolute positional accuracy is established. Manual source pixels, low-resolution map backdrop of unknown age/projection, and current OSM geometry are approximate references.',
        'The six-control main fit is one plausible placement. The road-only model matches the two additional northern fieldtrack diagnostics more closely; this unresolved discrepancy is preserved by retaining both placements.',
        'Roads and house-centroid controls lie mostly near a north-south line. The full east/west contour uses an isotropic similarity assumption with limited off-axis corroboration. Neither residuals nor the difference between two models provides a confidence envelope.',
        'Observed source contour does not establish legal, cadastral, surveyed or address-assignment boundaries. Candidate remains estimated true / estimatedContour false / estimatedPlacement true.',
    ],
    'inputs': [{'path': str(p.relative_to(REPO)), 'sha256': sha(p)} for p in inputs],
    'sourceTopology': {'type': source.geom_type, 'isValid': source.is_valid, 'holes': len(source.interiors), 'areaSquarePixels': source.area},
    'independentRefit': {'model': 'E=a*x+b*y+c; N=b*x-a*y+d, least squares from6 recorded actual road/footprint correspondences',
                         'maximumMatrixCoefficientDifference': float(np.max(np.abs(recomputed_matrix - matrix))),
                         'maximumOffsetCoefficientDifference': float(np.max(np.abs(recomputed_offset - offset))),
                         'sourceNamePointUsedAsControl': False},
    'visualCorrespondenceReview': [
        'Main Hatházi/Vad junction, upper/lower bus-turnaround joins and the northwest fieldtrack are identifiable in the native source raster and correspond to the local original OSM roads.',
        'Four fitting house footprints and three building checks have corresponding visible gray source footprint shapes/positions. Subpixel centroid precision is not independently established; approximate2pixel source-picking uncertainty is reasonable as a manual-picking description.',
        'Main registration-preview aligns road/footprint rows generally; visible few-pixel compromises remain and are explicitly estimated.'
    ],
    'variants': variants,
    'additionalRoadDiagnostics': diagnostics,
    'alternativeDifference': {'symmetricDifferenceAreaM2': main_eov.symmetric_difference(alternative_eov).area,
                              'hausdorffMetres': main_eov.hausdorff_distance(alternative_eov),
                              'meaning': 'Describes two retained placement hypotheses only; not an accuracy bound.'},
    'identityReview': {'existingFrozenFeatureCountCompared': len(duplicates),
                       'newCanonicalName': 'Hatház',
                       'sourceSchemaId': 'zalaegerszeg-ziffa2025-chapter3.4-unit17-hathaz',
                       'sourceUnit17IsNotHistoricalUnit17Alias': True,
                       'notParentCloneOrWholeMunicipality': True,
                       'notAdditionalFeatureForAlternative': True,
                       'comparisons': duplicates},
    'globalRegistryModified': False,
    'claimedAbsoluteAccuracyMetres': None,
    'usableForAddressAssignment': False,
}
(ROOT / 'independent-registration-review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': review['status'], 'variants': variants, 'additionalRoadDiagnostics': diagnostics,
                  'alternativeDifference': review['alternativeDifference'], 'previousFeaturesCompared': len(duplicates)}, ensure_ascii=False, indent=2))
