#!/usr/bin/env python3
"""Read-only reproduction of mask, cap, placement and candidate safeguards."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys

import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import shape

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.dont_write_bytecode = True

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(name):
    return json.loads((HERE / name).read_text())

def coordinates(geometry):
    if geometry['type'] == 'Polygon':
        return [v for ring in geometry['coordinates'] for v in ring]
    return [v for part in geometry['coordinates'] for ring in part for v in ring]

def main():
    spec = importlib.util.spec_from_file_location('source_extractor', HERE / 'extract-source.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    facts = load('source-facts.json')
    original = ROOT / facts['sourcePdfPath']
    assert sha(original) == facts['sourcePdfSha256'] == module.PDF_SHA
    image_path = HERE / 'source-map-p25-xref365.jpeg'
    assert sha(image_path) == facts['sourceMap']['nativeJpegSha256']
    image = np.array(Image.open(image_path).convert('RGB')).astype(np.int16)
    r, g, b = np.moveaxis(image, -1, 0)
    raw = {2: (r > 120) & (g > 115) & (b < 180) & (np.minimum(r, g) - b > 45),
           3: (g > 70) & (g - r > 35) & (g - b > 35),
           4: (g > 95) & (b > 100) & (np.minimum(g, b) - r > 35),
           13: (r - g > 15) & (r - b > 5) & (r > 100) & (g > 40) & (b > 40),
           14: (r > 120) & (r - g > 25) & (g - b > 15) & (g > 45)}
    boundary_pixels = {2: (316, 655), 3: (396, 630), 4: (441, 576),
                       13: (195, 282), 14: (546, 874)}
    seeds = {2: (350, 655), 3: (410, 632), 4: (450, 605), 13: (204, 297), 14: (552, 882)}
    masks = np.load(HERE / 'source-segmentation.npz')
    src = {f['properties']['sourceUnitNumber']: f for f in load('source-pixel-contours.geojson')['features']}
    for unit, mask in raw.items():
        assert np.array_equal(mask, masks[f'raw_color_mask_{unit}'])
        capped = mask.copy()
        if unit == 3:
            capped[618, 401:403] = True
            assert np.count_nonzero(capped & ~mask) == 2
        selected = module.outline_component(capped, boundary_pixels[unit])
        interior = module.interior(selected, seeds[unit])
        assert np.array_equal(selected, masks[f'barrier_{unit}'])
        assert np.array_equal(interior, masks[f'interior_{unit}'])
        assert json.dumps(module.pixels_geometry(interior), sort_keys=True) == json.dumps(src[unit]['geometry'], sort_keys=True)
    reg = load('road-registration.json')
    M, O = np.array(reg['pixelToEovMatrix']), np.array(reg['pixelToEovOffset'])
    actual = {}
    roads = load('source-road-rail-reference.geojson')
    assert sha(HERE / 'source-road-rail-reference.geojson') == reg['sourceRoadReferenceSha256']
    for way in roads['features']:
        for ref, coordinate in zip(way['properties']['nodeRefs'], way['geometry']['coordinates']):
            if ref in actual:
                assert actual[ref] == coordinate
            actual[ref] = coordinate
    to_eov = Transformer.from_crs(4326, 23700, always_xy=True)
    to_wgs = Transformer.from_crs(23700, 4326, always_xy=True)
    X = np.array([c['sourcePixel'] for c in reg['controls']])
    Y = np.array([to_eov.transform(*actual[c['targetOsmNodeId']]) for c in reg['controls']])
    coefficients = np.linalg.lstsq(np.column_stack([X, np.ones(len(X))]), Y, rcond=None)[0]
    assert np.array_equal(coefficients[:2].T, M) and np.array_equal(coefficients[2], O)
    assert not reg['sourceNamePointsUsedForFit']
    features = load('kiskunfelegyhaza-inferred-import.geojson')['features']
    assert len(features) == 5 and {f['properties']['sourceUnitNumber'] for f in features} == {2, 3, 4, 13, 14}
    results = []
    for f in features:
        p = f['properties']; unit = p['sourceUnitNumber']
        expected_xy = np.array(coordinates(src[unit]['geometry'])) @ M.T + O
        lon, lat = to_wgs.transform(expected_xy[:, 0], expected_xy[:, 1])
        expected = np.column_stack([lon, lat])
        assert np.array_equal(expected, np.array(coordinates(f['geometry'])))
        assert shape(f['geometry']).is_valid
        assert p['estimated'] and p['estimatedPlacement'] and p['boundaryKind'] == 'inferred_area'
        assert not p['canonicalNameIsNeighborhood'] and not p['sourceIsOfficial']
        assert not p['sourceIsHardBoundary'] and not p['usableForAddressAssignment']
        assert p['estimatedContour'] == (unit == 3)
        assert p['completeSourceContourObserved'] == (unit != 3)
        assert p['sourceContourIsObserved'] == (unit != 3)
        assert p['claimedAbsoluteAccuracyMetres'] is None
        assert not p['sourceNameEvidence']['usedForFitOrCorrection']
        results.append({'unit': unit, 'name': p['name'], 'geometryValid': True,
                        'sourceVertexCount': len(expected), 'worldVertexCount': len(expected),
                        'sourcePixelArea': src[unit]['properties']['sourcePixelArea'],
                        'allCoordinatesExactlyReproduced': True,
                        'estimatedContour': p['estimatedContour']})
    registry = load('inferred-registry-entry.json')
    assert registry['sha256'] == sha(HERE / 'kiskunfelegyhaza-inferred-import.geojson')
    assert not ({'estimatedContour', 'sourceContourObserved', 'sourceContourIsObserved'} & set(registry['propertyOverrides']))
    result = {'schemaVersion': 1, 'status': 'PASS', 'sourceMasksReproduced': 5,
              'newPrimaryFeatures': 0, 'estimatedCandidateFeatures': 5,
              'allMixedContourFlagsPreserved': True, 'placePointsUsedForFit': False,
              'sourceFrameClosureOrGeometryRepair': False, 'globalFilesWritten': False,
              'candidatePath': 'kiskunfelegyhaza-inferred-import.geojson',
              'candidateSha256': sha(HERE / 'kiskunfelegyhaza-inferred-import.geojson'),
              'features': results}
    if '--write-report' in __import__('sys').argv:
        (HERE / 'validation-report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
