#!/usr/bin/env python3
"""Read-only independent reconstruction of Sopron's original blue native faces.

Default prints a short result. --write writes only review-native-check.json;
--check compares that report. Producer geometry and manifests are never written.
"""
import argparse
import hashlib
import json
from pathlib import Path

import fitz
from shapely.geometry import LineString, Point, shape
from shapely.ops import polygonize_full, unary_union

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
ORIGINAL = ROOT / '.local/neighborhoods/nationwide-docs/originals/sopron-map.pdf'
ARCHIVE = P / 'source-pages1-2.pdf'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def audit():
    # Reopen the actual full original, not the producer's JSON extraction.
    original = fitz.open(ORIGINAL)
    archived = fitz.open(ARCHIVE)
    assert len(original) == len(archived) == 2
    drawings = original[1].get_drawings()
    archived_drawings = archived[1].get_drawings()
    all_blue = [(i, d) for i, d in enumerate(drawings)
                if d.get('color') == (0., 0., 1.)]
    assert [i for i, d in all_blue] == [38799, 38800, 38801, 38802, 38815]

    # Source map strokes are wholly left of the legend. This independently
    # separates the four irregular map paths from the one legend swatch.
    selected = [(i, d) for i, d in all_blue if d['rect'].x1 < 750]
    legend = [(i, d) for i, d in all_blue if d['rect'].x0 > 780]
    assert len(selected) == 4 and len(legend) == 1
    original_segments = []
    drawing_records = []
    for index, drawing in selected:
        assert drawing['type'] == 's'
        assert all(item[0] == 'l' for item in drawing['items'])
        assert abs(drawing['width'] - 2.820000171661377) < 1e-12
        assert drawing['items'] == archived_drawings[index]['items']
        for segment_index, item in enumerate(drawing['items']):
            original_segments.append({
                'drawingIndex': index,
                'segmentIndex': segment_index,
                'coordinates': [list(item[1]), list(item[2])],
            })
        drawing_records.append({
            'drawingIndex': index,
            'originalSegmentCount': len(drawing['items']),
            'bboxPdfPoints': list(drawing['rect']),
            'declaredClosePath': drawing['closePath'],
            'firstEndpointEqualsFinalEndpoint':
                tuple(drawing['items'][0][1]) == tuple(drawing['items'][-1][2]),
        })
    assert len(original_segments) == 1238
    saved_segments = json.loads((P / 'native-source-segments.json').read_text())['segments']
    assert original_segments == saved_segments

    # Polygonize the original source network without Polygon(path), endpoint
    # snapping, buffers or supplied closure segments.
    source_network = unary_union([LineString(s['coordinates'])
                                 for s in original_segments])
    faces, cuts, dangles, invalid = polygonize_full(source_network)
    assert len(faces.geoms) == 4
    assert cuts.is_empty and dangles.is_empty and invalid.is_empty
    assert all(g.is_valid for g in faces.geoms)
    face_boundaries = unary_union([g.boundary for g in faces.geoms])
    extra_source_length = source_network.difference(face_boundaries).length
    extra_output_length = face_boundaries.difference(source_network).length
    assert extra_source_length == extra_output_length == 0

    spans = [s for block in original[1].get_text('dict')['blocks']
             for line in block.get('lines', []) for s in line['spans']]
    native = json.loads((P / 'native-source-polygons.json').read_text())['records']
    geo = json.loads((P / 'source-vector.geojson').read_text())['features']
    full_text = original[1].get_text()
    expected_short_labels = {1: ['Észak-nyugat'], 4: ['Bánfalva, Kutyahegy'],
                             5: ['Lőverek'], 13: ['Dél-keleti', 'gazdasági terület']}
    used_faces = set()
    rows = []
    for record in native:
        number = record['sourceUnitNumber']
        number_spans = [s for s in spans if s['text'].strip() == f'{number}.'
                        and s['color'] == 11960]
        assert len(number_spans) == 1
        bbox = number_spans[0]['bbox']
        center = Point((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
        containing = [i for i, g in enumerate(faces.geoms) if g.covers(center)]
        assert len(containing) == 1 and containing[0] not in used_faces
        face = faces.geoms[containing[0]]
        used_faces.add(containing[0])
        stored = shape(record['nativeGeometry'])
        difference_area = stored.symmetric_difference(face).area
        hausdorff = stored.hausdorff_distance(face)
        assert difference_area == hausdorff == 0
        assert stored.equals_exact(face, 0)
        assert list(bbox) == record['sourceLabel']['bboxPdfPoints']
        label_checks = []
        for label in expected_short_labels[number]:
            matching = [s for s in spans if s['text'].strip() == label and s['color'] == 11960]
            assert len(matching) == 1
            b = matching[0]['bbox']
            point = Point((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
            assert face.covers(point)
            label_checks.append({'literalText': label, 'bboxPdfPoints': list(b),
                                 'textCenterInsideSameSourceFace': True})
        assert record['boundaryKind'] == 'planning_unit'
        assert record['canonicalNameIsNeighborhood'] is False
        assert record['constituentFootprintsInvented'] is False
        assert record['usableForAddressAssignment'] is False
        # Geographic properties should preserve the same cautious semantics.
        feature = next(f for f in geo
                       if f['properties']['sourceUnitNumber'] == number)
        assert feature['properties']['boundaryKind'] == 'planning_unit'
        assert feature['properties']['canonicalNameIsNeighborhood'] is False
        assert feature['properties']['usableForAddressAssignment'] is False
        rows.append({
            'sourceUnitNumber': number,
            'name': record['name'],
            'literalNumberText': number_spans[0]['text'],
            'numberCenterInsideExactlyOneOriginalFace': True,
            'literalNameChecks': label_checks,
            'nativeFootprintSymmetricDifferencePdfPointsSquared': difference_area,
            'nativeFootprintHausdorffDistancePdfPoints': hausdorff,
            'nativeCoordinateSequenceExactlyReproduced': True,
            'nativeAreaPdfPointsSquared': face.area,
            'nativeGeometryValid': face.is_valid,
            'nativeGeometryInteriorRingCount': len(face.interiors),
            'conservativeWholePlanningUnitPreserved': True,
        })
    assert len(rows) == len(used_faces) == 4
    page2_text = original[1].get_text()
    page1_text = original[0].get_text()
    assert 'városrészek határa' in page2_text
    assert 'tervezési terület határa' in page2_text
    assert '1/B melléklet a 39/2021.' in page2_text
    assert '2024. 11.' in page1_text
    assert 'TT08518-M1/24' in page1_text and 'TT08518-M1/24' in page2_text
    assert '2. melléklet a .../2024.' in page1_text
    placeholder_spans = [s for block in original[0].get_text('dict')['blocks']
                         for line in block.get('lines', []) for s in line['spans']
                         if '2. melléklet a .../2024.' in s['text']]
    assert len(placeholder_spans) == 1 and placeholder_spans[0]['color'] == 16777215
    render_checks = []
    for index in range(2):
        a = original[index].get_pixmap(matrix=fitz.Matrix(.6, .6))
        b = archived[index].get_pixmap(matrix=fitz.Matrix(.6, .6))
        same = (a.width, a.height, a.n) == (b.width, b.height, b.n) and a.samples == b.samples
        assert same
        render_checks.append({'pdfPageOneBased': index + 1, 'renderScale': .6,
                              'archivedAndOriginalRenderedSamplesIdentical': True})

    checked = [ORIGINAL, ARCHIVE, P / 'native-source-segments.json',
               P / 'native-source-polygons.json', P / 'source-vector.geojson']
    return {
        'schemaVersion': 1,
        'reviewer': 'independent sopron_independent_review/native_faces_check agent',
        'reviewDate': '2026-11-13',
        'scope': 'Native source geometry and literal source semantics only; geographic registration is audited separately.',
        'verdict': 'pass_exact_native_source_faces_and_conservative_planning_semantics',
        'networkUsed': False,
        'producerFilesModified': False,
        'inputFingerprints': [{'path': str(f.relative_to(ROOT)), 'sha256': digest(f)}
                              for f in checked],
        'allPureBlueSourceDrawingIndices': [i for i, d in all_blue],
        'originalMapDrawingRecords': drawing_records,
        'legendBlueDrawingExcluded': legend[0][0],
        'sourceMapSegments': len(original_segments),
        'sourceSegmentCoordinatesExactlyMatchArchivedOriginal': True,
        'originalAndArchivedVisiblePageRenders': render_checks,
        'savedNativeSegmentsExactlyMatchOriginalPdf': True,
        'polygonizedFaceCount': len(faces.geoms),
        'polygonizationCuts': len(cuts.geoms),
        'polygonizationDangles': len(dangles.geoms),
        'polygonizationInvalidRings': len(invalid.geoms),
        'sourceLengthMissingFromAllFaceBoundariesPdfPoints': extra_source_length,
        'outputBoundaryLengthNotCoveredByOriginalSourcePdfPoints': extra_output_length,
        'inventedClosingEdgesObserved': False,
        'sourceNameAndNumberPointsAssignOneToOne': True,
        'fineConstituentFootprintsInferredOrDuplicated': False,
        'sourceDatingAndLegalStatus': {
            'page1LiteralDate': '2024. 11.',
            'page1DateVisuallyConfirmedAsArabicEleven': True,
            'dateDirectOriginalPdfRender': 'review-native-date-block.png',
            'page2WorkNumber': 'TT08518-M1/24',
            'page2LiteralAnnexReference': '1/B melléklet a 39/2021. (XII.28.) önkormányzati rendelethez',
            'page1ExtractedTextContainsPlaceholderReference': True,
            'page1PlaceholderLiteralExtractedText': '2. melléklet a .../2024. (... ...) önkormányzati rendelethez',
            'page1PlaceholderNativeTextColorRgbInteger': placeholder_spans[0]['color'],
            'page1PlaceholderNativeTextColor': 'white (#FFFFFF)',
            'page1PlaceholderReferenceVisiblyRendered': False,
            'placeholderOriginalPdfRender': 'review-native-draft-block.png',
            'placeholderInterpretation': 'White CAD text in the extraction layer, not visibly printed on the default white-background rendering. Its current legal significance is unresolved; no draft or approval status is inferred from this text artifact.',
            'readmeDateCorrectionStillNeeded': '2024. I.' in (P / 'README.txt').read_text(),
            'sourceDateRecommendation': 'Keep the directly printed page1 literal date 2024. 11.; page2 does not independently print a month.',
            'currentLegalValidityEstablishedByThisReview': False,
        },
        'records': rows,
        'restrictions': {
            'geographicCalibrationOrAbsoluteAccuracyAuditedHere': False,
            'usableForAddressAssignment': False,
            'sourceReuseRightsEstablished': False,
            'wholeSopronNeighbourhoodCoverageClaimed': False,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    assert not (args.write and args.check)
    result = audit()
    path = P / 'review-native-check.json'
    text = encode(result)
    if args.write:
        path.write_text(text)
    elif args.check:
        assert path.read_text() == text
    print(encode({'verdict': result['verdict'], 'sourceSegments': 1238,
                  'nativeFaces': 4, 'reportWritten': args.write,
                  'reportCompared': args.check}))


if __name__ == '__main__':
    main()
