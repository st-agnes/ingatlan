"""Reconstruct one historical Hódtó quarter candidate from named OSM linework.

No endpoint snapping, synthetic connector, buffer, rectangle, or point-generated
perimeter is used. Current junction arcs are explicit inferred choices.
"""
import hashlib
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import shape, mapping, LineString, Point
from shapely.ops import transform, unary_union, polygonize

OUT = Path(__file__).resolve().parent
FWD = Transformer.from_crs(4326, 23700, always_xy=True)
NAMES = ['Kaszap utca', 'Andrássy út', 'Bajcsy-Zsilinszky Endre utca']
EXCLUDED = ['footway', 'cycleway', 'path', 'steps', None]


def write(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def main():
    lines = json.loads((OUT / 'hod-local-lines.geojson').read_text())['features']
    names = json.loads((OUT / 'hod-local-name-points.geojson').read_text())['features']
    cited = [f for f in lines if (
        f['properties']['tags'].get('name') in NAMES and f['properties']['tags'].get('highway') not in EXCLUDED
        or f['properties']['tags'].get('railway') == 'rail' and f['properties']['tags'].get('ref') == '135'
        and f['properties']['tags'].get('usage') == 'main' and not f['properties']['tags'].get('service'))]
    roundabouts = [f for f in lines if f['properties']['tags'].get('junction') == 'roundabout'
                   and f['properties']['tags'].get('highway') not in EXCLUDED]
    graph = unary_union([shape(f['geometry']) for f in cited])
    added = []
    while True:
        more = [f for f in roundabouts if f not in added and shape(f['geometry']).intersects(graph)]
        if not more:
            break
        added += more
        graph = unary_union([graph] + [shape(f['geometry']) for f in more])
    controls = cited + added
    faces = list(polygonize(graph))
    current_name = [f for f in names if f['properties']['tags'].get('name') == 'Hódtó']
    assert len(current_name) == 1
    hint = shape(current_name[0]['geometry'])

    def uses_all_cited_groups(polygon):
        border = polygon.boundary
        return all(border.intersection(unary_union([shape(f['geometry']) for f in cited if
                   f['properties']['tags'].get('name') == name])).length > 0 for name in NAMES) and \
            border.intersection(unary_union([shape(f['geometry']) for f in cited if
                   f['properties']['tags'].get('railway') == 'rail'])).length > 0

    matches = [g for g in faces if uses_all_cited_groups(g) and g.covers(hint)]
    assert len(matches) == 1, 'The physical source graph does not identify one candidate'
    candidate = matches[0]
    assert candidate.is_valid and not candidate.interiors
    ordered = []
    coords = list(candidate.exterior.coords)
    for index, (a, b) in enumerate(zip(coords, coords[1:])):
        segment = LineString([a, b])
        probes = [Point(a), segment.interpolate(.5, normalized=True), Point(b)]
        matches = [f for f in controls if max(shape(f['geometry']).distance(pt) for pt in probes) < 1e-11]
        assert matches, 'A boundary edge has no original OSM line support'
        choices = []
        for f in matches:
            tags = f['properties']['tags']
            choices.append({'osmWayId': f['properties']['osmWayId'], 'name': tags.get('name'),
                            'railwayRef': tags.get('ref') if tags.get('railway') else None,
                            'role': 'inferred_physical_junction_arc' if f in added else 'explicit_circuit_road_or_rail'})
        ordered.append({'edgeIndex': index, 'coordinates': [list(a), list(b)], 'sourceChoices': choices,
                        'lengthMeters': transform(FWD.transform, segment).length})
    supported_ids = sorted({choice['osmWayId'] for row in ordered for choice in row['sourceChoices']})
    junction_ids = sorted({choice['osmWayId'] for row in ordered for choice in row['sourceChoices']
                           if choice['role'] == 'inferred_physical_junction_arc'})
    used_controls = [f for f in controls if f['properties']['osmWayId'] in supported_ids]
    properties = {'name': 'Hódtó', 'municipality': 'Hódmezővásárhely', 'estimated': True,
                  'confidence': 'low', 'status': 'historical_explicit_circuit_candidate_pending_independent_review',
                  'sourceDate': '2014-09-17', 'sourceSection': '2.3.4', 'sourcePrintedPage': 61,
                  'sourceUrl': 'https://hodmezovasarhely.hu/wp-content/uploads/strategiak_koncepciok/Integr%C3%A1lt-Telfejli-Stra%C3%A9gia_2014.pdf',
                  'method': 'Polygonized cited road/rail centerlines and connected physical roundabout arcs from OSM. Junction arcs are explicit manual inference.',
                  'geometryLicense': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
                  'usableForAddressAssignment': False, 'accuracyMeters': None}
    write('hod-hodto-first-candidate.geojson', {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': properties, 'geometry': mapping(candidate)}]})
    write('hod-hodto-boundary-controls.geojson', {'type': 'FeatureCollection', 'features': used_controls})
    metric = transform(FWD.transform, candidate)
    proof = {'schemaVersion': 1, 'candidateName': 'Hódtó', 'municipality': 'Hódmezővásárhely',
             'sourcePbfSha256': '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a',
             'polygonCount': 1, 'uniqueFaceUsesAllFourCitedCircuitGroupsAndContainsCurrentNamePoint': True,
             'currentNamePoint': current_name[0], 'namePointRole': 'Semantic cross-check only; never used to generate any perimeter coordinate.',
             'valid': candidate.is_valid, 'holeCount': len(candidate.interiors), 'vertexCount': len(coords),
             'areaSquareMeters': metric.area, 'perimeterMeters': metric.length,
             'allBoundaryEdgesHaveOriginalOsmLineSupport': True,
             'maximumSupportToleranceDegrees': 1e-11,
             'sourceWayIds': supported_ids, 'inferredJunctionWayIds': junction_ids,
             'inferredJunctionLengthMeters': sum(row['lengthMeters'] for row in ordered if
                 all(choice['role'] == 'inferred_physical_junction_arc' for choice in row['sourceChoices'])),
             'orderedEdges': ordered,
             'syntheticConnectors': 0, 'endpointSnapping': False,
             'geometryDerivedFromSourcePdfMap': False,
             'limitations': [
                 'Explicit quarter circuit is from2014, while open linework is a2026 snapshot. Historical alignment was not independently georeferenced.',
                 'Road and rail centerlines implement a stated tracing convention; source text does not specify road/rail width ownership.',
                 'Modern roundabout arcs close physical junctions missing from the street-name chain; these arcs are inferred and fully identified.',
                 'Subsequent FVS action-area definitions differ and are not treated as full-quarter definitions.',
                 'Municipal PDF text was verified through the web tool; original PDF bytes/screenshot of the selected section were blocked byHTTP403 on subsequent fetch.',
                 'No independent geometry/source review has yet approved this candidate; it is not in any global registry/export.'
             ], 'usableForAddressAssignment': False}
    proof['files'] = {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in [
        'hod-local-lines.geojson', 'hod-local-name-points.geojson', 'hod-source-research.json',
        'hod-hodto-first-candidate.geojson', 'hod-hodto-boundary-controls.geojson']}
    write('hod-hodto-first-candidate-proof.json', proof)
    print(json.dumps({k: v for k, v in proof.items() if k not in ['orderedEdges', 'currentNamePoint', 'limitations', 'files']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
