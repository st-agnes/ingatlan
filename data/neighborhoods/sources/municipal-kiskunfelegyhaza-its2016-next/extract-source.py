#!/usr/bin/env python3
"""Preserve the map and literal pixel interiors, with the one explicit cap."""
from pathlib import Path
import hashlib
import json

import fitz
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely.geometry import box, mapping
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PDF = ROOT / '.local/neighborhoods/next-towns/kiskunfelegyhaza-its2016.pdf'
PDF_SHA = '5a32552dc02e2bca986d27d97e41633549b5d1f23147f8e00b6abbe7c421b48b'
URL = 'https://kiskunfelegyhaza.hu/wp-content/uploads/2017/03/its_kiskunfelegyhaza_2016_felulvizsgalt.pdf'
NAMES = ['Központi belterület', 'Kossuthváros', 'Petőfi lakótelep', 'Bankfalu',
         'Liget utca - Vásártér', 'Déli Kertváros – Móraváros - Bikahegy',
         'Déli Iparterület', 'Ipari Park', 'Molnár telep', 'Halesz (külterület)',
         'Selymes (külterület)', 'Külterületi tanya', 'Arany-hegyi lakótelep',
         'Zöldmező lakótelep', 'Északi új lakóterület (külterület)']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def interior(barrier, seed):
    labels, _ = ndimage.label(~barrier, ndimage.generate_binary_structure(2, 1))
    region = labels == labels[seed[1], seed[0]]
    assert not (region[0].any() or region[-1].any() or region[:, 0].any() or region[:, -1].any())
    return region

def outline_component(barrier, pixel):
    labels, _ = ndimage.label(barrier, ndimage.generate_binary_structure(2, 2))
    label = labels[pixel[1], pixel[0]]
    assert label != 0
    return labels == label

def pixels_geometry(mask):
    # Exact union of source pixel cells; row runs only reduce union input count.
    runs = []
    for y, row in enumerate(mask):
        changes = np.diff(np.r_[False, row, False].astype(np.int8))
        for x0, x1 in zip(np.where(changes == 1)[0], np.where(changes == -1)[0]):
            runs.append(box(int(x0), y, int(x1), y + 1))
    geom = unary_union(runs)
    assert geom.geom_type == 'Polygon' and geom.is_valid and not geom.interiors
    assert geom.area == int(mask.sum())
    return mapping(geom)

def main():
    assert sha(PDF) == PDF_SHA
    doc = fitz.open(PDF)
    assert len(doc) == 139
    image = doc.extract_image(365)
    assert (image['width'], image['height']) == (945, 1364)
    native = HERE / 'source-map-p25-xref365.jpeg'
    native.write_bytes(image['image'])
    # Archive only the selected original map image, not the narrative PDF pages.
    rgb = np.asarray(Image.open(native).convert('RGB')).astype(np.int16)
    r, g, b = np.moveaxis(rgb, -1, 0)
    barriers = {
        2: (r > 120) & (g > 115) & (b < 180) & (np.minimum(r, g) - b > 45),
        3: (g > 70) & (g - r > 35) & (g - b > 35),
        4: (g > 95) & (b > 100) & (np.minimum(g, b) - r > 35),
        13: (r - g > 15) & (r - b > 5) & (r > 100) & (g > 40) & (b > 40),
        14: (r > 120) & (r - g > 25) & (g - b > 15) & (g > 45),
    }
    seeds = {2: (350, 655), 3: (410, 632), 4: (450, 605), 13: (204, 297), 14: (552, 882)}
    raw_barriers = {i: m.copy() for i, m in barriers.items()}
    boundary_pixels = {2: (316, 655), 3: (396, 630), 4: (441, 576),
                       13: (195, 282), 14: (546, 874)}
    raw_green_labels, _ = ndimage.label(~barriers[3])
    open_green = raw_green_labels == raw_green_labels[632, 410]
    assert open_green[0].any() and open_green[-1].any()
    main_green = barriers[3].copy()
    main_green[618, 401:403] = True
    alternate_green = barriers[3].copy()
    alternate_green[617, 398:403] = True
    assert int((main_green & ~barriers[3]).sum()) == 2
    assert int((alternate_green & ~barriers[3]).sum()) == 5
    barriers = {i: outline_component(main_green if i == 3 else m, boundary_pixels[i])
                for i, m in barriers.items()}
    selected = {i: interior(m, seeds[i]) for i, m in barriers.items()}
    alternate = interior(outline_component(alternate_green, boundary_pixels[3]), seeds[3])
    assert [int(selected[i].sum()) for i in [2, 3, 4, 13, 14]] == [2963, 416, 2544, 284, 145]
    assert int(alternate.sum()) == 418
    features = []
    for i in [2, 3, 4, 13, 14]:
        features.append({'type': 'Feature', 'id': f'kiskun2016:source-unit-{i}',
                         'properties': {'name': NAMES[i - 1], 'sourceUnitNumber': i,
                                        'coordinateSpace': 'Native image pixel-cell corners, x right/y down',
                                        'sourcePixelArea': int(selected[i].sum()),
                                        'observedSourceContour': i != 3,
                                        'estimatedContour': i == 3,
                                        'estimatedGapCaps': 1 if i == 3 else 0,
                                        'worldCoordinatesPresent': False,
                                        'usableForAddressAssignment': False},
                         'geometry': pixels_geometry(selected[i])})
    write('source-pixel-contours.geojson', {'type': 'FeatureCollection', 'features': features})
    write('petofi-cap-alternative-source-pixels.geojson', {
        'type': 'FeatureCollection', 'countsAsAdditionalQuarter': False,
        'features': [{'type': 'Feature', 'properties': {
            'name': NAMES[2], 'sourceUnitNumber': 3, 'estimatedContour': True,
            'alternativeOnly': True, 'sourcePixelArea': int(alternate.sum())},
            'geometry': pixels_geometry(alternate)}]})
    np.savez_compressed(HERE / 'source-segmentation.npz',
                        **{f'raw_color_mask_{i}': m for i, m in raw_barriers.items()},
                        **{f'barrier_{i}': m for i, m in barriers.items()},
                        **{f'interior_{i}': m for i, m in selected.items()},
                        petofi_main_cap_barrier=main_green,
                        petofi_alternative_cap_barrier=alternate_green,
                        petofi_alternative_interior=alternate)
    cap_evidence = {
        'sourceUnitNumber': 3, 'rawColorBarrierIsOpen': True,
        'occlusion': 'The black numeric source label 3 interrupts the green top boundary.',
        'mainAddedBarrierCells': [[401, 618], [402, 618]],
        'mainObservedGreenEndpoints': [[400, 618], [403, 618]],
        'alternativeAddedBarrierCells': [[x, 617] for x in range(398, 403)],
        'alternativeObservedGreenEndpoints': [[397, 617], [403, 617]],
        'mainInteriorPixels': 416, 'alternativeInteriorPixels': 418,
        'mainGapCellsRgb': [rgb[y, x].tolist() for x, y in [[401, 618], [402, 618]]],
        'meaning': 'Explicit bounded manual source-contour hypothesis beneath the numeric label; not a literal observed edge or an accuracy envelope.',
        'newWorldCoordinatesInferredHere': False,
    }
    write('petofi-cap-evidence.json', cap_evidence)
    facts = {
        'schemaVersion': 1, 'sourceUrl': URL, 'sourcePdfPath': str(PDF.relative_to(ROOT)),
        'sourcePdfSha256': PDF_SHA, 'sourcePdfBytes': PDF.stat().st_size,
        'sourcePdfPages': len(doc), 'documentReviewPeriod': '2016, printed cover',
        'pdfMetadataCreation': doc.metadata['creationDate'],
        'municipalBoundarySubmissionPeriod': '2014 municipal submission used for KSH units according to physical PDF page 24',
        'statisticalPeriod': '2011 census for the subsequent quarter statistics, physical PDF pages 26–27',
        'periodsAreNotInterchangeable': True,
        'boundarySurveyDateAndCurrentExtent': 'Not established',
        'sourceMap': {'physicalPage': 25, 'printedPage': 25, 'mapNumber': 2,
                      'title': 'Városrészek lehatárolása', 'imageXref': 365,
                      'dimensionsPixels': [945, 1364], 'nativeJpegSha256': sha(native),
                      'attribution': 'Önkormányzati adatszolgáltatás'},
        'tableNumber': 4, 'tablePhysicalPage': 24,
        'literalUnitNames': [{'sourceUnitNumber': i + 1, 'name': n} for i, n in enumerate(NAMES)],
        'schemaFactsParaphrased': [
            'The 2016 review explains that 2008 IVS units differ from the KSH units based on municipal 2014 submission; it follows the latter for statistical compatibility.',
            'Unit 6 is one combined Déli Kertváros–Móraváros–Bikahegy source unit. No child boundaries are supplied or inferred.',
            'Unit 12 scattered farm territory is intentionally absent from the map.',
            'Unit 15 is shown only as a label without spatial extent; no polygon is supported.',
            'Units 13 and 14 are named detached residential parts; their native contours are retained and their world placement needs remote road checks.',
        ],
        'quotedNarrativeArchived': False, 'fullOriginalPdfIncluded': False,
        'rightsStatus': 'Official municipal publication and municipal-data map; unrestricted map redistribution rights not independently established.',
        'usableForAddressAssignment': False,
    }
    write('source-facts.json', facts)
    write('source-extraction-proof.json', {
        'schemaVersion': 1, 'sourcePdfSha256': PDF_SHA,
        'sourceImagePath': native.name, 'sourceImageSha256': sha(native),
        'method': 'Select the eight-connected literal RGB outline component at the documented boundary pixel, then its four-neighbor free interior. Exact union of source pixel cells. No morphology, smoothing, buffers, hulls, clipping, snapping or geometric repair. Petőfi has the separately documented bounded cap.',
        'sourceSeedsArePixelComponentSelectorsNotWorldFitControls': True,
        'sourceMasks': [{'unit': i, 'rawColorMaskPixels': int(raw_barriers[i].sum()),
                         'selectedBoundaryComponentPixels': int(barriers[i].sum()),
                         'selectedBoundaryPixel': list(boundary_pixels[i]),
                         'interiorPixels': int(selected[i].sum()),
                         'sourceContourClosedWithoutAddedCells': i != 3} for i in [2, 3, 4, 13, 14]],
        'petofiCapEvidence': 'petofi-cap-evidence.json',
        'petofiAlternativeNotAdditionalQuarter': True,
        'aranyDisconnectedInteriorColorPixelsNotQuarterExclusions': 9,
        'mapFrameEdgesUsedForClosure': False, 'coordinateRepairPerformed': False,
        'geometryFileSha256': sha(HERE / 'source-pixel-contours.geojson')})
    preview = Image.open(native).convert('RGB')
    overlay = np.asarray(preview).copy()
    for i, region in selected.items():
        overlay[region] = (0.6 * overlay[region] + 0.4 * np.array([255, 0, 255])).astype(np.uint8)
    preview = Image.fromarray(overlay)
    d = ImageDraw.Draw(preview)
    d.rectangle((400, 617, 404, 619), outline=(0, 0, 255), width=1)
    preview.save(HERE / 'source-contours-preview.png')
    Image.open(native).crop((390, 607, 421, 627)).resize((620, 400)).save(HERE / 'petofi-label-gap-preview.png')
    print('Extracted five source contours; Petőfi has one explicit two-pixel cap plus a separate alternative.')

if __name__ == '__main__':
    main()
