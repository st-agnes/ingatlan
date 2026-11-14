#!/usr/bin/env python3
"""Reproduce selected actual Győr ITS PDF vector outlines, entirely offline.

The 2014 municipal document depicts a 2006 planning division. Its table maps
46 planning circuits into21 named quarters. Eleven single-circuit quarters,
five explicitly source-defined quarter groups and one explicitly distinct
historical Kisbácsa planning extent are exported here. The five groups are
literal valid MultiPolygons or exact set unions of valid source components.
Raw closed blue paths are never repaired, clipped, snapped or closed.
An actual OPEN black source stroke supplies calibration endpoint samples only.
Its alignment residuals do not establish independent boundary accuracy.
"""
import hashlib
import json
from pathlib import Path

import fitz
import numpy as np
import shapely
from pyproj import Geod, Transformer
from shapely.geometry import Polygon, MultiPolygon, shape, mapping
from shapely.ops import transform, unary_union


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/neighborhoods/sources/municipal-gyor-next'
PDF = OUT / 'gyor-its.source.pdf'
MUNICIPALITY = OUT / 'calibration-municipality.geojson'
MUNICIPALITY_SHA = '093e12543bbd557f5aad2d6687ed4b6135e06f55770b71a0a0b404ca8fc719fa'
INDEPENDENT_REVIEW = OUT / 'independent-review.json'
NAME_POINTS = OUT / 'name-control-points.geojson'
PDF_SHA = '40f318435f5719cb5a06b253d6e15fbd5acc7d5a6bec53fc38ae1e199b6ca21d'
URL = 'https://gyor.hu/easy-docs/5dc9829cb6d4c'
PAGE = 268
CONTROL_DRAW = 217
# Circuit numbers come from the source's figure97 and table23, pp271–272.
# Parent/reviewer visually read each corresponding printed number on the map.
SELECTION = [
    (1, 'Belváros', 92), (12, 'Sziget', 93), (18, 'Pinnyéd', 97),
    (19, 'Kisbácsa', 44), (20, 'Bácsa', 43), (26, 'Sárás', 31),
    (21, 'Likócs', 86), (37, 'Rabkert', 27), (27, 'Góré-dűlő', 30),
    (7, 'Adyváros', 83), (22, 'Kismegyer', 73), (24, 'Gyirmót', 28),
]
GROUPS = [
    ('Révfalu', [6,13], [41,90], ['Révfalu']),
    ('Marcalváros', [8,9,45], [78,45,33], ['Marcalváros I.','Marcalváros II.']),
    ('Gyárváros', [29,30,31,14,35], [89,91,39,88,87], ['Gyárváros']),
    ('Szabadhegy', [16,42,36,33,32], [75,38,85,72,34], ['Szabadhegy']),
    ('Ménfőcsanak', [25,46,38], [24,32,29], ['Ménfőcsanak']),
]
RIGHTS = 'source_map_reuse_not_established; OSM controls ODbL-1.0'
METHOD = ('Actual closed blue PDF vector path from figure97 of the January2014 '
          'Győr ITS, showing the2006 division; affine registration to EPSG:23700 '
          'by robust closest-point alignment of actual OPEN black source-stroke '
          'endpoints to the current OSM municipal exterior; vertexwise inverse '
          'projection to WGS84. No outline repair, clipping, snapping, '
          'synthetic closing edge or physical-boundary inference. Explicit '
          'source-defined circuit aggregation, where used, is recorded per feature.')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(document):
    return json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def points(drawing):
    """Retain exact PDF straight-segment coordinates; refuse discontinuities."""
    result = []
    for item in drawing['items']:
        if item[0] != 'l':
            raise ValueError('Unsupported PDF segment: only actual straight paths accepted')
        start, end = tuple(item[1]), tuple(item[2])
        if not result:
            result.append(start)
        if result[-1] != start:
            raise ValueError('Discontinuous source path; no joining chord allowed')
        result.append(end)
    return result


def calibrate(source_points, target_border):
    source = np.asarray(source_points)
    design = np.c_[source, np.ones(len(source))]
    sx = (target_border.bounds[2]-target_border.bounds[0]) / (source[:,0].max()-source[:,0].min())
    sy = (target_border.bounds[3]-target_border.bounds[1]) / (source[:,1].max()-source[:,1].min())
    matrix = np.array([[sx, 0], [0, -sy],
                       [target_border.bounds[0]-source[:,0].min()*sx,
                        target_border.bounds[3]+source[:,1].min()*sy]])
    for iteration in range(80):
        predicted = design @ matrix
        sample = shapely.points(predicted)
        nearest = shapely.get_coordinates(shapely.line_interpolate_point(
            target_border, shapely.line_locate_point(target_border, sample)))
        errors = np.linalg.norm(predicted-nearest, axis=1)
        keep = errors <= np.quantile(errors, .8)
        fitted = np.linalg.lstsq(design[keep], nearest[keep], rcond=None)[0]
        # Match the archived exploratory registration's convergence convention.
        if np.max(np.abs(fitted-matrix)) < 1e-6:
            break
        matrix = fitted
    errors = shapely.distance(shapely.points(design @ matrix), target_border)
    return matrix, iteration, np.percentile(errors, [0,50,80,90,95,99,100]).tolist()


def main():
    if sha(PDF) != PDF_SHA:
        raise ValueError('Archived municipal PDF differs from the pinned original')
    if sha(MUNICIPALITY) != MUNICIPALITY_SHA:
        raise ValueError('Archived municipality differs from the pinned original')
    source_municipality = json.loads(MUNICIPALITY.read_text())
    reviews = {item['sourceMapCircuitNumber']:item for item in
               json.loads(INDEPENDENT_REVIEW.read_text())['quarterReviews']}
    source_points = {item['id']:item for item in json.loads(NAME_POINTS.read_text())['features']}
    if source_municipality['properties']['name'] != 'Győr':
        raise ValueError('Wrong municipality calibration input')
    to_eov = Transformer.from_crs(4326, 23700, always_xy=True)
    to_wgs = Transformer.from_crs(23700, 4326, always_xy=True)
    municipality = transform(to_eov.transform, shape(source_municipality['geometry']))
    components = list(municipality.geoms) if hasattr(municipality, 'geoms') else [municipality]
    target = max(components, key=lambda polygon: polygon.area).exterior
    document = fitz.open(PDF)
    drawings = document[PAGE].get_drawings()
    control = drawings[CONTROL_DRAW]
    if tuple(control['color']) != (0,0,0):
        raise ValueError('Calibration source stroke classification changed')
    control_points = points(control)
    matrix, iterations, percentiles = calibrate(control_points, target)
    transformed_control = np.c_[np.asarray(control_points), np.ones(len(control_points))] @ matrix
    control_endpoint_gap = float(np.linalg.norm(transformed_control[-1]-transformed_control[0]))
    raw_paths = {'schemaVersion':1, 'sourcePdfSha256':sha(PDF),
                 'pdfPageZeroBased':PAGE, 'printedPage':269,
                 'sourceCoordinateSystem':'PyMuPDF PDF page points; xright, ydown',
                 'calibrationSourceStroke':{
                     'drawingIndex':CONTROL_DRAW, 'coordinates':control_points,
                     'sourceClosed':control_points[0] == control_points[-1],
                     'purpose':'Calibration sample cloud only; never converted to a polygon or closed.',
                 }, 'selectedPaths':[]}
    source_documents = [{'url':URL, 'path':str(PDF.relative_to(ROOT)), 'sha256':sha(PDF),
                         'documentDate':'2014-01', 'depictedDivisionYear':2006,
                         'printedMapPage':269, 'pdfPageZeroBased':268, 'figure':97,
                         'printedQuarterCircuitTablePages':[271,272]}]
    features, proofs = [], []
    for number, original_name, drawing_index in SELECTION:
        drawing = drawings[drawing_index]
        color = drawing.get('color')
        if not color or not (.3 < color[1] < .4) or not (.6 < color[2] < .7):
            raise ValueError('Selected outline is no longer the blue source boundary')
        pdf_coordinates = points(drawing)
        if pdf_coordinates[0] != pdf_coordinates[-1]:
            raise ValueError('Original selected blue path is open; no closure allowed')
        original = Polygon(pdf_coordinates)
        if original.is_empty or not original.is_valid:
            raise ValueError('Invalid original blue outline; no repair allowed')
        eov_coordinates = (np.c_[np.asarray(pdf_coordinates), np.ones(len(pdf_coordinates))] @ matrix).tolist()
        eov_polygon = Polygon(eov_coordinates)
        if not eov_polygon.is_valid:
            raise ValueError('Affine outline failed validation')
        coordinates = [list(to_wgs.transform(*point)) for point in eov_coordinates]
        geometry = {'type':'Polygon', 'coordinates':[coordinates]}
        if coordinates[0] != coordinates[-1] or not shape(geometry).is_valid:
            raise ValueError('Transformed original outline failed validation')
        name_review = reviews[number]
        if name_review['drawingIndex'] != drawing_index or name_review['tableQuarterName'] != original_name:
            raise ValueError('Independent source label review and selected outline differ')
        label = name_review['labelNode']
        actual_point = source_points[label['id']]
        if actual_point['geometry']['coordinates'] != label['coordinates'] or actual_point['properties']['name'] != label['name']:
            raise ValueError('Independent label evidence differs from the original actual point record')
        if not shape(geometry).covers(shapely.Point(label['coordinates'])):
            raise ValueError('Archived current label point is outside the selected outline')
        fraction = eov_polygon.intersection(municipality).area / eov_polygon.area
        planning = original_name == 'Kisbácsa'
        name = 'Kisbácsa – 2006-os tervezési kiterjedés' if planning else original_name
        boundary_kind = 'planning_unit' if planning else 'neighbourhood'
        notes = [
            'The 2006 circuit is mapped to this single named quarter in the source table; multi-circuit quarters are not split or inferred here.',
            'Source outlines are historical. Registration to the current municipal perimeter does not make them current or legally authoritative.',
            'Residuals describe the calibration sample fit only; independent interior boundary-position accuracy is unknown.',
            'No source outline was clipped to the current municipality; geometric outside-parent fractions are retained for review.',
            'Municipal source-map reuse rights are unverified; ODbL applies to the OSM calibration data, not automatically to the PDF or derived municipal map.'
        ]
        if planning:
            notes.append('The source itself extends this circuit beyond the municipal outline; printed p285 discusses the planned adjoining Vámosszabadi housing area and a proposed future transfer to Győr. Retained only as a historical planning extent, not an ordinary current Kisbácsa quarter.')
        if original_name == 'Sárás':
            notes.append('About1% lies outside the current calibration municipality; do not treat its inferred position as parent-contained or address-ready.')
        props = {
            'name':name, 'municipality':'Győr', 'boundaryKind':boundary_kind,
            'canonicalNameIsNeighborhood':not planning, 'sourceCircuitNumber':number,
            'sourceCircuitName':original_name, 'sourceDrawingIndex':drawing_index,
            'sourcePeriod':'2006 division in municipal ITS,January2014',
            'method':METHOD, 'sourceDocuments':source_documents, 'evidenceUrls':[URL],
            'sourceIsOfficial':False, 'estimated':False, 'reviewStatus':'unreviewed',
            'geometryVerificationStatus':'historical_source_outline_georeferenced_not_boundary_verified',
            'usableForAddressAssignment':False, 'areaM2':eov_polygon.area,
            'currentMunicipalityContainedFraction':fraction,
            'outsideCurrentMunicipalityAreaM2':eov_polygon.difference(municipality).area,
            'independentBoundaryAccuracyKnown':False, 'registrationFitP95M':percentiles[4],
            'currentNamePointEvidence':{
                'id':label['id'], 'name':label['name'], 'coordinates':label['coordinates'],
                'pointInsideDerivedOutline':True,
                'meaning':'Current OSM name/placement only; does not verify the historical boundary or independent positional accuracy.',
                'sourceReview':str(INDEPENDENT_REVIEW.relative_to(ROOT))},
            'license':RIGHTS,
            'attribution':'Municipal source: Győr ITS,January2014,figure97 and table23; OSM calibration ©OpenStreetMap contributors.',
            'reviewNotes':notes,
        }
        feature_id = 'manual:gyor:source-circuit-' + str(number)
        features.append({'type':'Feature', 'id':feature_id, 'properties':props, 'geometry':geometry})
        raw_paths['selectedPaths'].append({'drawingIndex':drawing_index, 'sourceCircuitNumber':number,
                                          'sourceName':original_name, 'coordinates':pdf_coordinates,
                                          'sourceClosed':True, 'sourceValid':True,
                                          'sourceColor':list(color)})
        proofs.append({'id':feature_id, 'name':name, 'sourceCircuitNumber':number,
                       'boundaryKind':boundary_kind, 'drawingIndex':drawing_index,
                       'sourceCoordinateCount':len(pdf_coordinates),
                       'outputCoordinateCount':len(coordinates), 'sourceExplicitlyClosed':True,
                       'noSourceVerticesRemoved':True, 'noSourceVerticesAdded':True,
                       'sourceValid':True, 'outputValid':True,
                       'areaM2':eov_polygon.area,
                       'currentMunicipalityContainedFraction':fraction,
                       'outsideCurrentMunicipalityAreaM2':eov_polygon.difference(municipality).area,
                       'usableForAddressAssignment':False})

    # Source-defined aggregation is distinct from repairing a broken source path.
    # Every component below must itself already be explicitly closed and valid.
    # Preserve all real road-corridor gaps and archive every original component.
    def affine(x, y, z=None):
        x, y = np.asarray(x), np.asarray(y)
        return (x*matrix[0,0]+y*matrix[1,0]+matrix[2,0],
                x*matrix[0,1]+y*matrix[1,1]+matrix[2,1])

    for name, numbers, indices, label_names in GROUPS:
        components, raw_component_records = [], []
        for number, index in zip(numbers, indices):
            drawing = drawings[index]
            color = drawing.get('color')
            if not color or not (.3 < color[1] < .4) or not (.6 < color[2] < .7):
                raise ValueError('A grouped component is not the original blue source outline')
            source_coordinates = points(drawing)
            if source_coordinates[0] != source_coordinates[-1]:
                raise ValueError('Open grouped source path; no closure is allowed')
            component = Polygon(source_coordinates)
            if component.is_empty or not component.is_valid:
                raise ValueError('Invalid grouped source path; no repair is allowed')
            components.append(component)
            record = {'drawingIndex':index, 'sourceCircuitNumber':number,
                      'sourceQuarterGroupName':name, 'coordinates':source_coordinates,
                      'sourceClosed':True, 'sourceValid':True, 'sourceColor':list(color)}
            raw_paths['selectedPaths'].append(record)
            raw_component_records.append({'drawingIndex':index, 'sourceCircuitNumber':number,
                                          'sourceCoordinateCount':len(source_coordinates),
                                          'sourceExplicitlyClosed':True, 'sourceValid':True})
        literal = MultiPolygon(components)
        exact_union = unary_union(components)
        if literal.is_valid:
            grouped = literal
            operation = 'Literal valid MultiPolygon of original closed valid source components; no set union needed.'
        else:
            grouped = exact_union
            operation = 'Exact geometric set union of original closed valid source components; removes shared internal edges/overlaps, retains road-corridor gaps.'
        if grouped.is_empty or not grouped.is_valid or grouped.geom_type not in ('Polygon','MultiPolygon'):
            raise ValueError('Source-defined group has no valid unchanged set-union result')
        input_edges = unary_union([component.boundary for component in components])
        uncovered_length = grouped.boundary.difference(input_edges).length
        symmetric_difference_area = grouped.symmetric_difference(exact_union).area
        if uncovered_length != 0 or symmetric_difference_area != 0:
            raise ValueError('Group result contains a non-source boundary or changes the source component set')
        eov_group = transform(affine, grouped)
        wgs_group = transform(to_wgs.transform, eov_group)
        if not eov_group.is_valid or not wgs_group.is_valid:
            raise ValueError('Source-defined group transformation failed validation')
        selected_points = []
        for label_name in label_names:
            candidates = [point for point in source_points.values()
                          if point['properties']['name'] == label_name
                          and point['properties'].get('municipality') == 'Győr']
            if len(candidates) != 1:
                raise ValueError('Missing/ambiguous actual current group name point: '+label_name)
            point = candidates[0]
            if not wgs_group.covers(shape(point['geometry'])):
                raise ValueError('Actual current group name point is outside its source-defined group')
            selected_points.append({'id':point['id'], 'name':label_name,
                                    'coordinates':point['geometry']['coordinates'],
                                    'pointInsideDerivedOutline':True})
        fraction = eov_group.intersection(municipality).area/eov_group.area
        method = METHOD + ' Source-defined quarter aggregation: ' + operation + ' New intersection vertices, if present, lie on original source edges; no buffer, make-valid, snapping or bridging.'
        notes = [
            'The exact component circuit numbers are explicitly grouped into this named quarter by table23, printed pp271–272; this is not a guessed geographic grouping.',
            operation,
            'Every output boundary edge is covered by original component boundary linework; source-space uncovered length and symmetric-difference area are both exactly zero.',
            'All primitive source paths and vertices remain archived; internal source vertices/edges may disappear from a set-union output, and genuine line intersections may create new boundary vertices.',
            'Current name points corroborate names/placement only. They do not independently verify historical boundaries or positional accuracy.',
            'The2006division is historical. Registration residuals do not establish independent interior accuracy, current legal boundaries or address assignment.',
            'Municipal source-map reuse rights are unverified; ODbL applies to OSM controls only.'
        ]
        if name == 'Marcalváros':
            notes.append('No exact whole-quarter Marcalváros point exists in the archived current OSM name cohort. The original table supplies the whole name; current Marcalváros I. and II. points support its two named residential components.')
        feature_id = 'manual:gyor:source-quarter-group-'+'-'.join(map(str,numbers))
        props = {
            'name':name, 'municipality':'Győr', 'boundaryKind':'neighbourhood',
            'canonicalNameIsNeighborhood':True, 'sourceCircuitNumbers':numbers,
            'sourceDrawingIndices':indices, 'sourcePeriod':'2006 division in municipal ITS,January2014',
            'method':method, 'sourceDocuments':source_documents, 'evidenceUrls':[URL],
            'sourceIsOfficial':False, 'estimated':False, 'reviewStatus':'unreviewed',
            'geometryVerificationStatus':'historical_source_defined_group_georeferenced_not_boundary_verified',
            'usableForAddressAssignment':False, 'areaM2':eov_group.area,
            'currentMunicipalityContainedFraction':fraction,
            'outsideCurrentMunicipalityAreaM2':eov_group.difference(municipality).area,
            'independentBoundaryAccuracyKnown':False, 'registrationFitP95M':percentiles[4],
            'sourceAggregationOperation':operation,
            'outputBoundaryCoveredByOriginalSourceEdges':True,
            'outputEqualsExactSourceComponentSetUnion':True,
            'currentNamePointEvidence':selected_points,
            'license':RIGHTS,
            'attribution':'Municipal source: Győr ITS,January2014,figure97 and table23; OSM calibration ©OpenStreetMap contributors.',
            'reviewNotes':notes,
        }
        features.append({'type':'Feature', 'id':feature_id, 'properties':props, 'geometry':mapping(wgs_group)})
        proofs.append({'id':feature_id, 'name':name, 'boundaryKind':'neighbourhood',
                       'sourceComponents':raw_component_records, 'aggregation':operation,
                       'allOriginalSourceComponentsValidAndExplicitlyClosed':True,
                       'literalMultiPolygonValid':literal.is_valid,
                       'outputEqualsExactSourceComponentSetUnion':True,
                       'sourceSpaceSymmetricDifferenceAreaPDFPoints2':symmetric_difference_area,
                       'outputBoundaryCoveredByOriginalSourceEdges':True,
                       'sourceSpaceUncoveredBoundaryLengthPDFPoints':uncovered_length,
                       'componentSumAreaPDFPoints2':sum(component.area for component in components),
                       'unionAreaPDFPoints2':exact_union.area,
                       'sourceVerticesArchivedUnchanged':True,
                       'outputValid':True, 'areaM2':eov_group.area,
                       'currentMunicipalityContainedFraction':fraction,
                       'outsideCurrentMunicipalityAreaM2':eov_group.difference(municipality).area,
                       'actualCurrentNamePointControls':selected_points,
                       'usableForAddressAssignment':False})
    output = OUT / 'gyor-source-candidates.geojson'
    output.write_text(encode({'type':'FeatureCollection', 'features':features}))
    raw_path_file = OUT / 'original-pdf-paths.json'
    raw_path_file.write_text(encode(raw_paths))
    registration = {
        'schemaVersion':1, 'method':METHOD,
        'coordinateOperation':'[PDFx,PDFy,1] @ matrix = [EOVx,EOVy]; EPSG23700 ->EPSG4326(always_xy)',
        'matrix':matrix.tolist(), 'matrixUnits':'EOVmetres per PDFpoint',
        'sourcePdfSha256':sha(PDF), 'sourceCalibrationDrawingIndex':CONTROL_DRAW,
        'sourceCalibrationCoordinates':len(control_points),
        'sourceCalibrationStrokeClosed':control_points[0] == control_points[-1],
        'sourceCalibrationEndpointGapM':control_endpoint_gap,
        'sourceCalibrationStrokeClosedForFit':False,
        'targetMunicipality':{'path':str(MUNICIPALITY.relative_to(ROOT)), 'sha256':sha(MUNICIPALITY),
                              'source':source_municipality['properties']['source'],
                              'target':'Largest actual municipality component exterior inEPSG23700'},
        'algorithm':{'initialization':'Independent source/target bounding scales with y-axis inversion; translation by bounding minima/maxima',
                     'iteration':'Closest target exterior points; retain lowest80%current distances; fit2Daffine leastsquares',
                     'maximumIterations':80, 'convergenceMaximumParameterDelta':1e-6,
                     'completedIterationIndex':iterations},
        'fitDiagnostics':{'percentiles':[0,50,80,90,95,99,100], 'distancesM':percentiles,
                          'independentAccuracyEstimate':False},
        'independentInteriorBoundaryAccuracyM':None,
        'limits':['The source black calibration stroke remains open; no invented closing edge is used in alignment.',
                  'Current municipality edges may differ from the2006source boundaries.',
                  'Alignment residuals are not positional confidence limits or independent interior checks.']
    }
    registration_file = OUT / 'registration.json'
    registration_file.write_text(encode(registration))
    proof = {'schemaVersion':1, 'sourceDocuments':source_documents,
             'method':METHOD, 'featureCount':len(features), 'quarterCandidates':16,
             'historicalPlanningCandidates':1, 'nationwideCoverageComplete':False,
             'municipalityQuarterCoverageComplete':False,
             'sourcePaths':{'path':str(raw_path_file.relative_to(ROOT)), 'sha256':sha(raw_path_file)},
             'registration':{'path':str(registration_file.relative_to(ROOT)), 'sha256':sha(registration_file)},
             'independentReview':{'path':str(INDEPENDENT_REVIEW.relative_to(ROOT)),
                                  'sha256':sha(INDEPENDENT_REVIEW),
                                  'scope':'Source classification, original path validity and current point-name placement; no independent interior boundary survey.'},
             'actualNamePointSource':{'path':str(NAME_POINTS.relative_to(ROOT)), 'sha256':sha(NAME_POINTS),
                                       'sourceGeometriesUnchanged':True, 'independentBoundaryEvidence':False},
             'selectionMeaning':'Eleven single-component source table quarters and five explicitly source-defined circuit groups; Kisbácsa is separated as a historical planning extent.',
             'notSelected':{'invalidBlueDrawingIndices':[76,79,94],
                            'otherPaths':'Remaining unselected source circuits require separate named-quarter assembly/classification. No aggregation or guessed assignment of those remaining circuits was performed.'},
             'features':proofs, 'rightsStatus':RIGHTS, 'usableForAddressAssignment':False,
             'output':{'path':str(output.relative_to(ROOT)), 'sha256':sha(output)},
             'reproduce':'PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-gyor-next.py'}
    aggregation_review = OUT / 'aggregation-independent-review.json'
    if aggregation_review.is_file():
        proof['independentAggregationReview'] = {'path':str(aggregation_review.relative_to(ROOT)),
                                                'sha256':sha(aggregation_review)}
    (OUT / 'conversion-proof.json').write_text(encode(proof))
    print(encode({'features':len(features), 'quarters':16, 'planningUnits':1,
                  'registrationFitDistancesM':percentiles,
                  'calibrationStrokeClosed':False, 'sourceNoRepair':True,
                  'sha256':sha(output)}).strip())


if __name__ == '__main__':
    main()
