"""Independent native-image component and exact cell-union checks; no world fit."""
from collections import deque
from pathlib import Path
import hashlib
import json

import numpy as np
from PIL import Image
from shapely.geometry import box
from shapely.ops import unary_union
from shapely.validation import explain_validity

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def components(mask, diagonal=False):
    seen = np.zeros(mask.shape, dtype=bool)
    h, w = mask.shape
    offsets = [(0, -1), (-1, 0), (1, 0), (0, 1)]
    if diagonal:
        offsets += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    result = []
    for sy, sx in zip(*np.where(mask)):
        if seen[sy, sx]:
            continue
        queue = deque([(int(sy), int(sx))])
        seen[sy, sx] = True
        cells = []
        while queue:
            y, x = queue.popleft()
            cells.append((y, x))
            for dy, dx in offsets:
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    queue.append((yy, xx))
        result.append(cells)
    return sorted(result, key=len, reverse=True)


def component_mask(shape, cells):
    answer = np.zeros(shape, dtype=bool)
    y, x = zip(*cells)
    answer[y, x] = True
    return answer


image_path = ROOT / 'p141-xref778.jpeg'
rgb = np.array(Image.open(image_path).convert('RGB'))
stored = np.load(ROOT / 'hathaz-mask.npz')
dark = rgb.max(axis=2) < 120
dark_parts = components(dark, diagonal=True)
stroke = component_mask(dark.shape, dark_parts[0])
non_stroke_parts = components(~stroke)
inside_parts = [part for part in non_stroke_parts if (220, 160) in part]
assert len(inside_parts) == 1
inside = component_mask(stroke.shape, inside_parts[0])
assert np.array_equal(stroke, stored['stroke'])
assert np.array_equal(inside, stored['inside'])

# Independently build exact union of unit pixel cells by row runs. Do not repair.
runs = []
for y, row in enumerate(inside):
    starts = np.where(np.diff(np.r_[False, row, False].astype(int)) == 1)[0]
    ends = np.where(np.diff(np.r_[False, row, False].astype(int)) == -1)[0]
    runs.extend(box(int(a), y, int(b), y + 1) for a, b in zip(starts, ends))
geom = unary_union(runs)
assert geom.is_valid
assert geom.geom_type == 'Polygon'
assert len(geom.interiors) == 0
assert geom.area == int(inside.sum())

sensitivity = []
for cutoff in [100, 140]:
    candidate_stroke = component_mask(dark.shape, components(rgb.max(axis=2) < cutoff, True)[0])
    free_parts = components(~candidate_stroke)
    candidate_inside_parts = [part for part in free_parts if (220, 160) in part]
    candidate_inside = component_mask(dark.shape, candidate_inside_parts[0])
    sensitivity.append({
        'maximumRgbExclusiveCutoff': cutoff,
        'largestDark8NeighborComponentPixels': int(candidate_stroke.sum()),
        'nonStroke4NeighborComponentSizes': sorted([len(c) for c in free_parts], reverse=True),
        'seedInteriorPixels': int(candidate_inside.sum()),
        'seedInteriorTouchesRasterEdge': bool(candidate_inside[0].any() or candidate_inside[-1].any() or candidate_inside[:, 0].any() or candidate_inside[:, -1].any()),
        'symmetricDifferenceFromSelectedInteriorPixels': int(np.logical_xor(inside, candidate_inside).sum()),
    })

ys, xs = np.where(stroke)
review = {
    'schemaVersion': 1,
    'reviewKind': 'independent_native_raster_contour_and_source_pixel_topology',
    'reviewer': 'independent child agent zala_semantic_qa',
    'status': 'passes_source_raster_closed_contour_and_exact_cell_union_checks',
    'inputs': [{'path': p.name, 'sha256': sha(p)} for p in [image_path, ROOT / 'hathaz-mask.npz', ROOT / 'hathaz-contour-extraction-preview.png', Path(__file__)]],
    'imageDimensionsPixels': [rgb.shape[1], rgb.shape[0]],
    'independentReconstruction': {
        'strokeRule': 'Largest 8-neighbor component of source-native pixels whose max(R,G,B) is below120; independently implemented breadth-first labeling.',
        'sourceStrokePixels': int(stroke.sum()),
        'sourceStrokeInclusivePixelBounds': [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
        'seedPixelXY': [160, 220],
        'nonStroke4NeighborComponentSizes': sorted([len(c) for c in non_stroke_parts], reverse=True),
        'interiorPixels': int(inside.sum()),
        'interiorTouchesRasterEdge': bool(inside[0].any() or inside[-1].any() or inside[:, 0].any() or inside[:, -1].any()),
        'independentStrokeEqualsStoredMask': bool(np.array_equal(stroke, stored['stroke'])),
        'independentInteriorEqualsStoredMask': bool(np.array_equal(inside, stored['inside'])),
        'sourceCellUnion': {'type': geom.geom_type, 'isValid': geom.is_valid, 'validityReason': explain_validity(geom), 'areaSquarePixels': geom.area, 'holes': len(geom.interiors), 'boundsCellEdges': list(geom.bounds)},
        'noGapBridgingClippingOrGeometryRepair': True,
    },
    'thresholdSensitivity': sensitivity,
    'visualReview': {
        'inspected': ['native source image xref778 at355x451', 'native satellite image xref773 at194x246', 'hathaz-contour-extraction-preview.png'],
        'findings': [
            'Selected mask tracks the visible single closed black Hatház perimeter, including the top stepped projection, east-facing wide lobe, concave east edge and southern narrow strip.',
            'No detached lobe or alternate boundary arc is visible outside the selected ring; the contour is continuous in the source, and no closure has been manually added.',
            'The Hatház label and unrelated map marks are excluded from the stroke component but remain ordinary interior cells; they have not been used to reshape the perimeter.',
            'Inside-edge interpretation excludes the source stroke itself. Threshold sensitivity measures source-pixel variation only, not positional accuracy.'
        ]
    },
    'placementReview': 'World placement and geographic calibration not reviewed in this source-only check.',
    'claimedAbsoluteAccuracyMetres': None,
    'usableForAddressAssignment': False,
}
(ROOT / 'independent-raster-review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(review, ensure_ascii=False, indent=2))
