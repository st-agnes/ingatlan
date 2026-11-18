#!/usr/bin/env python3
"""Reproduce five actual source contours with explicitly unverified georeference.

Requires numpy, scipy, Pillow, shapely and pyproj. Default offline build never
fetches a source or changes central registries. --check compares derived bytes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt
from pyproj import Transformer
from shapely.geometry import Polygon, mapping

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/neighborhoods/sources/municipal-gyongyos-more'
SOURCE_URL = 'https://gyongyos.hu/wp-content/uploads/2021/01/integralt-telepulesfejlesztesi-strategia-2016-its-gyongyos.pdf'
FROZEN_INPUT_SHA256 = {
    'source-map.jpeg': '42e7d237cbd3fa6c5fc896ab6766a7d9c79d7c9e962123772784b8f360042e6a',
    'source-contours.json': '7a5a87db20d524535826b8b5adc04ff215a396f1c19ed6975b28996e7b62cac9',
    'registration-controls.json': '920ba78b6cfe2404f2275523166e66f87dc0b84944d201584998724f7bd1b9c7',
    'source-facts.json': '57823cfd194281ae1cdd0ed42b2655d4b4fdb0c27d3aaff07b8d453084526822',
    'source-proof-pages.pdf': 'de9e48bf2cb8c1e1b26f829b7f423bf35f202f5f0831c9e951396b1535cb31b5',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def write(name, value, check):
    value = value if isinstance(value, bytes) else data(value)
    p = OUT / name
    if check:
        if not p.exists() or p.read_bytes() != value:
            raise ValueError('Stale derived artifact: ' + str(p))
    else:
        p.write_bytes(value)


def build(check):
    from shapely.validation import explain_validity
    for name, expected in FROZEN_INPUT_SHA256.items():
        if sha(OUT / name) != expected:
            raise ValueError('Changed frozen source input; repeat manual review: ' + name)
    traces = json.loads((OUT / 'source-contours.json').read_text())
    facts = json.loads((OUT / 'source-facts.json').read_text())
    controls = json.loads((OUT / 'registration-controls.json').read_text())['controls']
    to_eov = Transformer.from_crs(4326, 23700, always_xy=True)
    to_wgs = Transformer.from_crs(23700, 4326, always_xy=True)
    design = np.array([[*c['sourcePixel'], 1] for c in controls])
    targets = np.array([to_eov.transform(*c['lonLat']) for c in controls])
    affine = np.round(np.linalg.lstsq(design, targets, rcond=None)[0], 12)
    residuals = np.linalg.norm(design @ affine - targets, axis=1)
    rows = [{'controlId': c['id'], 'imageIdentification': c['imageIdentification'],
             'residualMetres': float(v)} for c, v in zip(controls, residuals)]
    image = np.asarray(Image.open(OUT / 'source-map.jpeg')).astype(float)
    ink = (image.min(2) > 110) & ((image.max(2) - image.min(2)) < 85)
    distance = distance_transform_edt(~ink)
    features, contour_rows = [], []
    # Every output pixel edge must exist literally in the manually guided ink paths.
    source_edges = set()
    for chain in traces['sharedInkPaths'].values():
        for a, b in zip(chain, chain[1:]):
            source_edges.add(tuple(sorted((tuple(a), tuple(b)))))
    for i, region in enumerate(traces['regions']):
        ring, holes = region['pixelRing'], region['sourcePixelHoles']
        pixel_polygon = Polygon(ring, holes)
        assert pixel_polygon.is_valid, explain_validity(pixel_polygon)
        assert ring[0] == ring[-1]
        assert all(0 < x < 808 and 0 < y < 932 for x, y in ring), 'Frame contact forbidden.'
        for chain in [ring, *holes]:
            assert all(tuple(sorted((tuple(a), tuple(b)))) in source_edges
                       for a, b in zip(chain, chain[1:])), 'Synthetic source pixel edge.'
        def project(chain):
            result = []
            for x, y in chain:
                east, north = np.array([x, y, 1]) @ affine
                lon, lat = to_wgs.transform(east, north)
                result.append([round(lon, 8), round(lat, 8)])
            return result
        geographic = Polygon(project(ring), [project(h) for h in holes])
        assert geographic.is_valid, explain_validity(geographic)
        support = [float(distance[int(y), int(x)]) for x, y in ring]
        contour_rows.append({'name': region['name'], 'sourceVerticesIncludingClosure': len(ring),
            'sourcePixelArea': pixel_polygon.area, 'holes': len(holes), 'valid': geographic.is_valid,
            'allSourcePixelEdgesMatchedLiteralInkPathSteps': True, 'frameContact': False,
            'maxDistanceToThresholdedCartographicInkPixels': max(support),
            'meanDistanceToThresholdedCartographicInkPixels': sum(support) / len(support),
            'inkDiagnosticMeaning': 'Proximity to a declared JPEG brightness/color threshold, not a statistical accuracy, confidence or absolute position bound.'})
        props = {'name': region['name'], 'municipality': 'Gyöngyös',
            'boundaryKind': 'inferred_area', 'candidateBoundaryKind': 'neighbourhood',
            'estimated': True, 'canonicalNameIsNeighborhood': False,
            'sourceNameIsNeighborhood': True, 'sourceContourIsReal': True,
            'geometryVerificationStatus': 'actual_source_outline_with_unverified_georeference',
            'reviewStatus': 'estimated_georeference_requires_independent_registration',
            'sourcePeriod': '2016 ITS; underlying imagery marked 2015 on detailed maps',
            'method': 'Manual white cartographic ink tracing; pixel-step polygonization; approximate manually identified scene landmark affine registration in EOV, then EPSG:4326. Source outline preserved; nationwide placement unverified.',
            'sourceDocuments': [{'url': SOURCE_URL, 'sha256': facts['primarySource']['originalPdfSha256'],
                                 'pdfPageOneBased': 19, 'printedPage': 18, 'imageXref': 44}],
            'evidenceUrls': [SOURCE_URL],
            'sourceIsOfficial': False, 'sourcePublisherIsMunicipal': True,
            'sourceIsHardBoundary': False, 'primaryLayerAdmission': False,
            'usableForAddressAssignment': False, 'claimedAbsoluteAccuracyMetres': None,
            'sourceContourVertexCountIncludingClosure': len(ring),
            'missingSourceBoundarySegments': [], 'inferredClosingEdges': 0,
            'registrationUncertainty': 'All scene point identifications are approximate. The detailed map-to-overview correspondence and urban-network overlay do not establish source-pixel accuracy. Spatial extent and individual edge placement require independent registration. Fit residuals are internal diagnostics, not absolute accuracy.',
            'uncertaintyAppliesTo': 'All geographic boundary vertices and segments through unverified registration, rather than a fabricated missing cap or street connector.',
            'license': 'Municipal/Google Earth imagery reuse licence unestablished; ODbL-1.0 for OSM calibration',
            'attribution': 'Gyöngyös municipal ITS; imagery Google Earth / DigitalGlobe 2015; © OpenStreetMap contributors'}
        features.append({'type': 'Feature', 'id': 'manual:gyongyos:source-contour:' + str(i+1),
                         'properties': props, 'geometry': mapping(geographic)})
    collection = {'type': 'FeatureCollection', 'status': 'estimated_georeference_candidates_only',
        'primaryCandidateCount': 0, 'features': features}
    write('gyongyos-inferred.geojson', collection, check)
    proof = {'schemaVersion': 1, 'municipality': 'Gyöngyös', 'primaryCandidateCount': 0,
        'estimatedCandidateCount': 5, 'actualClosedSourceContourCount': 5,
        'excludedClippedNorthContourCount': 1, 'sourceContourSha256': sha(OUT / 'source-contours.json'),
        'sourceImageSha256': sha(OUT / 'source-map.jpeg'), 'sourceFactsSha256': sha(OUT / 'source-facts.json'),
        'registrationControlsSha256': sha(OUT / 'registration-controls.json'),
        'affinePixelToEovCoefficientsRowsX_Y_1': affine.tolist(),
        'calibrationResiduals': rows, 'internalFitRmsMetres': float(np.sqrt(np.mean(residuals**2))),
        'internalFitMaxMetres': float(max(residuals)),
        'residualMeaning': 'Internal fit to manually approximate scene identifications only. No independent ground-control accuracy; not an absolute error bound.',
        'claimedAbsoluteAccuracyMetres': None, 'syntheticGeographicClosingEdges': 0,
        'modernStreetReplacement': False, 'geometricRepair': False, 'frameClosure': False,
        'pixelPolygonization': 'Union/noding of four-neighbor traced ink line steps, select uniquely containing interior seed. Removes dangling/backtracking pixel line artifacts; inserts no new pixel edge. Original chosen ink paths are retained.',
        'contours': contour_rows, 'georeferenceAcceptedForPrimaryLayer': False,
        'usableForAddressAssignment': False}
    write('conversion-proof.json', proof, check)
    entry = {'id': 'gyongyos-2016-source-contours-unverified-registration',
        'path': str((OUT / 'gyongyos-inferred.geojson').relative_to(ROOT)),
        'sha256': hashlib.sha256(data(collection)).hexdigest(), 'municipality': 'Gyöngyös',
        'method': 'Five real closed municipal source contours with explicitly unverified manually approximate affine geographic registration; estimated research layer only.',
        'evidenceUrls': [SOURCE_URL], 'license': features[0]['properties']['license'],
        'propertyOverrides': {'boundaryKind': 'inferred_area', 'candidateBoundaryKind': 'neighbourhood',
            'estimated': True, 'canonicalNameIsNeighborhood': False, 'usableForAddressAssignment': False},
        'reviewPath': str((OUT / 'independent-review.json').relative_to(ROOT)),
        'uncertainties': ['All geographic placement remains unverified; no absolute accuracy asserted. Source contours are real and complete. North contour is omitted, not closed at the frame.'],
        'rightsStatus': facts['rightsStatus']}
    write('registry-entry.json', entry, check)
    input_names = ['source-map.jpeg', 'source-proof-pages.pdf', 'source-region-p29.jpeg',
        'source-region-p31.jpeg', 'source-region-p33.jpeg', 'source-region-p35.jpeg', 'source-region-p37.jpeg',
        'source-facts.json', 'source-contours.json', 'registration-controls.json',
        'image-correspondence-experiment.json', 'osm-water-control.json',
        'osm-calibration-lines.geojson', 'osm-calibration-landmarks.json', 'trace-source.py']
    derived = {'gyongyos-inferred.geojson': data(collection), 'conversion-proof.json': data(proof),
               'registry-entry.json': data(entry)}
    manifest = {'schemaVersion': 1, 'municipality': 'Gyöngyös',
        'primaryCandidateCount': 0, 'estimatedCandidateCount': 5, 'actualSourceContourCount': 5,
        'integrationTarget': 'inferred-candidate-registry.json only; central registry not modified by converter',
        'sourcePdf': facts['primarySource'], 'sourceSemantics': facts['semanticEvidence']['decision'],
        'claimedAbsoluteAccuracyMetres': None,
        'artifacts': [{'path': n, 'bytes': (OUT/n).stat().st_size, 'sha256': sha(OUT/n)} for n in input_names] +
            [{'path': n, 'bytes': len(v), 'sha256': hashlib.sha256(v).hexdigest()} for n,v in derived.items()],
        'converter': {'path': str(Path(__file__).relative_to(ROOT)), 'sha256': sha(Path(__file__))},
        'independentReview': 'independent-review.json is a subsequent separately authored QA artifact.',
        'rightsStatus': facts['rightsStatus']}
    write('manifest.json', manifest, check)
    print(json.dumps({'check': check, 'sourceContours': 5, 'inferredCandidates': 5,
                      'primaryCandidates': 0, 'internalFitRmsMetres': proof['internalFitRmsMetres'],
                      'absoluteAccuracyMetres': None}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    build(parser.parse_args().check)
