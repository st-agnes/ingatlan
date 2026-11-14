"""Working native-raster extraction of five explicitly keyed source areas; no world fit."""
from collections import deque
from pathlib import Path
import hashlib
import json

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import box, mapping
from shapely.ops import unary_union
from shapely.validation import explain_validity

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
SOURCE = REPO / '.local/neighborhoods/szeged-raw-review/henits2013/p24-xref249.jpeg'
RAW = REPO / '.local/neighborhoods/quarter-map-batch/szeged-henits-ksh-map-2013.pdf'
EXPECTED_RAW = 'b490214f9f038afe38fb1c74e24c0d5b99aeb04e54f192c417b06018363b3d0f'
SCRATCH = REPO / '.local/neighborhoods/szeged-raw-review/henits2013/five-traces'
SCRATCH.mkdir(parents=True, exist_ok=True)
UNITS = [
    {'number': 19, 'name': 'Klebelsberg-telep', 'nameAsPrinted': 'Klebersberg-telep', 'seedXY': [465, 610]},
    {'number': 20, 'name': 'Kecskés-telep', 'nameAsPrinted': 'Kecskés-telep', 'seedXY': [425, 540]},
    {'number': 28, 'name': 'Odessza', 'nameAsPrinted': 'Odessza', 'seedXY': [722, 461]},
    {'number': 11, 'name': 'Marostő', 'nameAsPrinted': 'Marostő', 'seedXY': [896, 540]},
    {'number': 27, 'name': 'Újszőreg', 'nameAsPrinted': 'Újszőreg', 'seedXY': [850, 605]},
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def components(mask, diagonal=False):
    labels = np.zeros(mask.shape, dtype=np.int32)
    sizes = [0]
    h, w = mask.shape
    offsets = [(0, -1), (-1, 0), (1, 0), (0, 1)]
    if diagonal:
        offsets += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    for sy, sx in zip(*np.where(mask)):
        if labels[sy, sx]:
            continue
        ident = len(sizes)
        queue = deque([(int(sy), int(sx))])
        labels[sy, sx] = ident
        count = 0
        while queue:
            y, x = queue.popleft()
            count += 1
            for dy, dx in offsets:
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not labels[yy, xx]:
                    labels[yy, xx] = ident
                    queue.append((yy, xx))
        sizes.append(count)
    return labels, sizes


def exact_cell_union(mask):
    runs = []
    for y, row in enumerate(mask):
        transitions = np.diff(np.r_[False, row, False].astype(int))
        starts, ends = np.where(transitions == 1)[0], np.where(transitions == -1)[0]
        runs.extend(box(int(a), y, int(b), y + 1) for a, b in zip(starts, ends))
    return unary_union(runs)


assert sha(RAW) == EXPECTED_RAW
rgb = np.array(Image.open(SOURCE).convert('RGB'))
assert rgb.shape == (1018, 1174, 3)
all_results, all_geometries, inside_by_cutoff = [], {}, {}
for cutoff in [50, 60, 70]:
    dark = rgb.max(axis=2) < cutoff
    dark_labels, dark_sizes = components(dark, diagonal=True)
    # Opposite-bank quarter networks are physically disconnected in this map.
    # Retain whole sufficiently large original components, never join their gaps.
    selected_ids = [i for i, size in enumerate(dark_sizes) if size >= 1000]
    stroke = np.isin(dark_labels, selected_ids)
    free_labels, free_sizes = components(~stroke)
    arrays, features, results = {'stroke': stroke}, [], []
    geometries, inside_by_cutoff[cutoff] = {}, {}
    for unit in UNITS:
        sx, sy = unit['seedXY']
        ident = int(free_labels[sy, sx])
        inside = free_labels == ident if ident else np.zeros(stroke.shape, dtype=bool)
        edge = bool(inside[0].any() or inside[-1].any() or inside[:, 0].any() or inside[:, -1].any())
        record = {**unit, 'cutoffMaximumRgbExclusive': cutoff, 'seedRgb': rgb[sy, sx].tolist(),
                  'freeComponentId': ident, 'sourceInteriorPixels': int(inside.sum()),
                  'touchesRasterEdge': edge, 'seedIsOnSelectedStroke': not bool(ident)}
        arrays[f'unit{unit["number"]}'] = inside
        inside_by_cutoff[cutoff][unit['number']] = inside
        if edge or not ident:
            record.update({'status': 'literal_extraction_quarantine',
                           'reason': 'seed_component_leaks_to_raster_edge' if edge else 'seed_on_selected_stroke',
                           'sourceContourObserved': False})
        else:
            geom = exact_cell_union(inside)
            passing = geom.is_valid and geom.geom_type == 'Polygon' and not geom.interiors
            record.update({'status': 'closed_source_component_pending_visual_independent_review' if passing else 'literal_extraction_quarantine',
                           'geometryType': geom.geom_type, 'isValid': geom.is_valid,
                           'validityReason': explain_validity(geom), 'holes': len(geom.interiors) if geom.geom_type == 'Polygon' else None,
                           'areaSquarePixels': geom.area, 'boundsSourcePixelCellEdges': list(geom.bounds),
                           'sourceContourObserved': passing})
            geometries[unit['number']] = geom
            features.append({'type': 'Feature', 'id': f'working:henits2013:{unit["number"]}:black{cutoff}',
                             'properties': {**unit, 'sourceSchemaId': f'henits2013-ksh2003-map-unit{unit["number"]}',
                                            'sourcePdfPageOneBased': 24, 'sourceImageXref': 249,
                                            'coordinateSpace': 'Native image pixel cell corners, x right/y down; no world coordinates',
                                            'cutoffMaximumRgbExclusive': cutoff,
                                            'sourceContourObserved': passing, 'estimatedContour': False,
                                            'worldPlacementPresent': False, 'quarantined': not passing,
                                            'workingOnly': True}, 'geometry': mapping(geom)})
        results.append(record)
    np.savez_compressed(SCRATCH / f'black{cutoff}-masks.npz', **arrays)
    path = ROOT / f'henits-five-black{cutoff}-source-pixels-working.geojson'
    write_json(path, {'type': 'FeatureCollection', 'features': features})
    all_geometries[cutoff] = geometries
    all_results.append({'cutoffMaximumRgbExclusive': cutoff,
                        'allDarkPixelCount': int(dark.sum()),
                        'selected8NeighborStrokeComponentMinimumPixels': 1000,
                        'selected8NeighborStrokeComponentSizes': [dark_sizes[i] for i in selected_ids],
                        'selected8NeighborStrokePixels': int(stroke.sum()),
                        'darkComponentSizesTop8': sorted(dark_sizes[1:], reverse=True)[:8],
                        'free4NeighborComponentSizesTop12': sorted(free_sizes[1:], reverse=True)[:12],
                        'masksPath': str((SCRATCH / f'black{cutoff}-masks.npz').relative_to(REPO)),
                        'sourceGeometryPath': path.name, 'results': results})

# One visualization of the selected60threshold and exact masks, no geography.
preview = rgb.copy()
colors = {19: [25, 180, 220], 20: [250, 140, 30], 28: [140, 80, 220], 11: [220, 80, 140], 27: [50, 190, 150]}
for unit in UNITS:
    mask = inside_by_cutoff[60][unit['number']]
    result = next(z for z in all_results[1]['results'] if z['number'] == unit['number'])
    if result['status'] != 'literal_extraction_quarantine':
        preview[mask] = (preview[mask] * .4 + np.array(colors[unit['number']]) * .6).astype('uint8')
Image.fromarray(preview).save(SCRATCH / 'five-black60-overlay.png')
for unit in UNITS:
    record = next(z for z in all_results[1]['results'] if z['number'] == unit['number'])
    if record['status'] == 'literal_extraction_quarantine':
        continue
    x0, y0, x1, y1 = record['boundsSourcePixelCellEdges']
    crop = (int(x0) - 12, int(y0) - 12, int(x1) + 12, int(y1) + 12)
    image = Image.fromarray(preview).crop(crop)
    image.resize((image.width * 4, image.height * 4), Image.Resampling.NEAREST).save(SCRATCH / f'unit{unit["number"]}-black60-overlay.png')

sensitivity = []
for unit in UNITS:
    selected = inside_by_cutoff[60][unit['number']]
    sensitivity.append({'number': unit['number'], 'name': unit['name'],
                        'black50Vs60SymmetricDifferencePixels': int(np.logical_xor(selected, inside_by_cutoff[50][unit['number']]).sum()),
                        'black70Vs60SymmetricDifferencePixels': int(np.logical_xor(selected, inside_by_cutoff[70][unit['number']]).sum())})

proof = {
    'schemaVersion': 1, 'status': 'working_source_only_traces_no_admission_no_world_registration',
    'source': {'localOriginalPath': str(RAW.relative_to(REPO)), 'sha256': EXPECTED_RAW,
               'nativeImagePath': str(SOURCE.relative_to(REPO)), 'nativeImageSha256': sha(SOURCE),
               'nativeImageSizePixels': [1174, 1018], 'sourcePdfPageOneBased': 24, 'nativeImageXref': 249},
    'method': 'For each cutoff, retain complete original8-neighbor maxRGB<cutoff components with at least1000pixels. Disconnected east/west quarter networks remain disconnected; no joins are drawn. Select4-neighbor non-stroke component from explicitly recorded color-fill seed. Exact union of unit pixel cells by row runs, without repair, caps, bridges, snapping, dilation, clipping, simplification or synthetic closure.',
    'componentSelectionReason': 'A globally largest-only component omits the physically separate east-bank quarter network. Retaining the whole large original components restores its existing native bands without joining them. Smaller disconnected numeric annotations are omitted; distant scale/legend strokes do not affect the selected neighborhood interiors.',
    'initialLargestOnlyExperimentPreservedLocally': str((SCRATCH / 'largest-only-initial-experiment-proof.json').relative_to(REPO)),
    'annotationHandling': 'Disconnected black number annotations are excluded from selected perimeter component, so they remain ordinary cells in source interior. Any annotation that erases a perimeter can cause a literal failure; no missing stroke is drawn.',
    'resultsByCutoff': all_results, 'thresholdSensitivity': sensitivity,
    'identityNotes': ['Unit19 is printed Klebersberg-telep in the dissertation body; correction toKlebelsberg is explicit and corroborated by separate sources, never a new identity.',
                      'Unit27 is Újszőreg by repeated body evidence. A conflicting Bodomi(27)text key is quarantined; it is not used here.'],
    'sourcePixelMasksAndPreview': str(SCRATCH.relative_to(REPO)),
    'worldCoordinatesProduced': False, 'georeferencingPerformed': False,
    'claimedAbsoluteAccuracyMetres': None, 'usableForAddressAssignment': False,
    'independentVisualTopologyReviewPending': True,
    'strictWorldCoordinateValidatorApplicable': False,
    'strictWorldCoordinateValidatorReason': 'Source pixels are not WGS84; geographic admission validator remains pending world registration. A separate normalized in-memory topology check may be run without producing world geometry.',
    'directNarrativeQuotationWords': 0, 'networkCallsPerformed': False,
    'globalRegistryModified': False, 'frozenPacketsModified': False,
    'scriptSha256': sha(Path(__file__)),
}
write_json(ROOT / 'henits-five-trace-proof-working.json', proof)
print(json.dumps({'status': proof['status'], 'results': all_results,
                  'thresholdSensitivity': sensitivity}, ensure_ascii=False, indent=2))
