#!/usr/bin/env python3
"""Reconstruct the interpreted Donner circuit from pinned literal OSM segments."""
from __future__ import annotations
import argparse
import hashlib
import heapq
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, box, mapping, shape
from shapely.ops import transform, unary_union

HERE = Path(__file__).resolve().parent
INPUT = HERE / 'literal-roads-waterways.geojson'
INPUT_SHA256 = 'b0ad88c5a517f9ddd58ec890a27992544af7853bb6ae235e89d38489e25049a6'
PROJECT = Transformer.from_crs('EPSG:4326', 'EPSG:23700', always_xy=True).transform
ORDER = ['Kapos', 'Zselic', 'Szigetvári', '67']


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def groups(features):
    def selected(feature, key):
        name = feature['properties']['name']
        tags = feature['properties']['source']['tags']
        return ((key == '67' and tags.get('ref') == '67' and 'highway' in tags)
                or (key == 'Szigetvári' and name == 'Szigetvári utca' and 'highway' in tags)
                or (key == 'Kapos' and name == 'Kapos' and 'waterway' in tags)
                or (key == 'Zselic' and name == 'Zselic-patak' and 'waterway' in tags))
    return {key: [feature for feature in features if selected(feature, key)] for key in ORDER}


def exact_junctions(source_groups):
    geometries = {key: unary_union([shape(f['geometry']) for f in value])
                  for key, value in source_groups.items()}
    result = []
    for before, after in [('67', 'Kapos'), ('Kapos', 'Zselic'),
                          ('Zselic', 'Szigetvári'), ('Szigetvári', '67')]:
        cross = geometries[before].intersection(geometries[after])
        assert cross.geom_type == 'Point', (before, after, cross.wkt)
        coordinate = tuple(cross.coords[0])
        refs = []
        for group in [before, after]:
            matches = {int(ref) for feature in source_groups[group]
                       for ref, xy in zip(feature['properties']['source']['nodeRefs'],
                                          feature['geometry']['coordinates'])
                       if Point(xy).distance(cross) < 1e-12}
            refs.append(matches)
        common = refs[0] & refs[1]
        assert len(common) <= 1
        result.append({
            'id': f'{before}/{after}', 'before': before, 'after': after,
            'coordinate': list(coordinate),
            'type': 'shared_osm_node' if common else 'analytical_road_water_crossing',
            'nodeRef': next(iter(common)) if common else None,
            'method': ('Exact common original OSM node' if common else
                       'Intersection of actual OSM polyline segments in WGS84 longitude/latitude; no snapping or extension'),
        })
    return result


def physical_arc(key, features, start, end):
    """Shortest actual node-ref path, splitting only the two chosen arc ends."""
    adjacency = {}
    coordinates = {}
    end_ids = []
    for junction in [start, end]:
        end_ids.append(f'osm:{junction["nodeRef"]}' if junction['nodeRef'] is not None
                       else 'intersection:' + junction['id'])
        coordinates[end_ids[-1]] = tuple(junction['coordinate'])

    def connect(a, b, axy, bxy, detail):
        for node, xy in [(a, axy), (b, bxy)]:
            if node in coordinates:
                assert Point(coordinates[node]).distance(Point(xy)) < 1e-12
            coordinates[node] = tuple(xy)
        weight = transform(PROJECT, LineString([axy, bxy])).length
        adjacency.setdefault(a, []).append((b, weight, detail))
        reverse = detail | {'fromFraction': detail['toFraction'],
                            'toFraction': detail['fromFraction']}
        adjacency.setdefault(b, []).append((a, weight, reverse))

    for feature in features:
        source = feature['properties']['source']
        refs = source['nodeRefs']
        points = feature['geometry']['coordinates']
        for index, (first, second) in enumerate(zip(points, points[1:])):
            segment = LineString([first, second])
            if segment.length == 0:
                continue
            pieces = [(0.0, f'osm:{refs[index]}', first),
                      (1.0, f'osm:{refs[index + 1]}', second)]
            for junction, node_id in zip([start, end], end_ids):
                point = Point(junction['coordinate'])
                if point.distance(segment) < 1e-12:
                    fraction = segment.project(point, normalized=True)
                    if 1e-12 < fraction < 1 - 1e-12:
                        pieces.append((fraction, node_id, junction['coordinate']))
            pieces.sort()
            for (t0, a, axy), (t1, b, bxy) in zip(pieces, pieces[1:]):
                connect(a, b, axy, bxy, {
                    'sourceWayId': source['osmId'], 'sourceSegmentIndex': index,
                    'sourceNodeRefs': [refs[index], refs[index + 1]],
                    'fromFraction': t0, 'toFraction': t1,
                })
    first, last = end_ids
    distances = {first: 0.0}
    predecessor = {}
    queue = [(0.0, first)]
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances[node]:
            continue
        if node == last:
            break
        for adjacent, weight, detail in adjacency.get(node, []):
            candidate = distance + weight
            if candidate < distances.get(adjacent, float('inf')):
                distances[adjacent] = candidate
                predecessor[adjacent] = (node, detail)
                heapq.heappush(queue, (candidate, adjacent))
    assert last in distances, (key, 'No path along actual source node references')
    nodes = [last]
    segments = []
    while nodes[-1] != first:
        previous, detail = predecessor[nodes[-1]]
        segments.append(detail)
        nodes.append(previous)
    nodes.reverse()
    segments.reverse()
    points = [list(coordinates[node]) for node in nodes]
    return {
        'name': key, 'startJunction': start['id'], 'endJunction': end['id'],
        'pathRule': 'Shortest path on actual same-group OSM node-reference topology, split only at the intended end intersections. One-way traffic restrictions do not constrain a boundary trace.',
        'nodeIds': nodes, 'coordinates': points, 'segments': segments,
        'lengthMetresEov': transform(PROJECT, LineString(points)).length,
        'originalWayIds': sorted({segment['sourceWayId'] for segment in segments}),
    }


def svg_preview(features, polygon, arcs):
    projected = transform(PROJECT, polygon)
    left, bottom, right, top = projected.bounds
    padding = 200
    scale = min(900 / (right - left + 2 * padding), 850 / (top - bottom + 2 * padding))

    def point(xy):
        x, y = PROJECT(*xy)
        return (50 + (x - left + padding) * scale,
                100 + (top + padding - y) * scale)

    def path(points):
        return ' '.join(f'{x:.3f},{y:.3f}' for x, y in map(point, points))

    def projected_path(points):
        return ' '.join(f'{50 + (x - left + padding) * scale:.3f},{100 + (top + padding - y) * scale:.3f}'
                        for x, y in points)

    items = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1050" viewBox="0 0 1000 1050">',
             '<rect width="1000" height="1050" fill="white"/>',
             '<text x="35" y="35" font-family="sans-serif" font-size="22">Donner — interpreted 2023 physical-boundary candidate</text>',
             '<text x="35" y="65" font-family="sans-serif" font-size="15">Low confidence · current OSM routes · no address assignment</text>',
             '<defs><clipPath id="plot"><rect x="35" y="90" width="930" height="860"/></clipPath></defs>',
             '<g clip-path="url(#plot)">',
             f'<polygon points="{path(list(polygon.exterior.coords))}" fill="#e3daf9" stroke="none"/>']
    for feature in features:
        tags = feature['properties']['source']['tags']
        color = '#8ab8d4' if 'waterway' in tags else '#d0d0d0'
        # Crop background context only to the display viewport; candidate/source
        # artifacts are never clipped or altered by this presentation step.
        context = transform(PROJECT, shape(feature['geometry'])).intersection(
            box(left - padding, bottom - padding, right + padding, top + padding))
        lines = [context] if context.geom_type == 'LineString' else list(getattr(context, 'geoms', []))
        for line in lines:
            if line.geom_type == 'LineString' and not line.is_empty:
                items.append(f'<polyline points="{projected_path(line.coords)}" fill="none" stroke="{color}" stroke-width="1.5"/>')
    colors = {'Kapos': '#1976b4', 'Zselic': '#23a2ba', 'Szigetvári': '#ba7d13', '67': '#b93e51'}
    for arc in arcs:
        items.append(f'<polyline points="{path(arc["coordinates"])}" fill="none" stroke="{colors[arc["name"]]}" stroke-width="4"/>')
    items.append('</g>')
    for index, key in enumerate(ORDER):
        x = 35 + index * 235
        label = {'Kapos': 'Kapos', 'Zselic': 'Zselic-patak', 'Szigetvári': 'Szigetvári utca', '67': '67 / Zselici út'}[key]
        items.append(f'<rect x="{x}" y="980" width="18" height="4" fill="{colors[key]}"/><text x="{x + 25}" y="987" font-family="sans-serif" font-size="15">{label}</text>')
    items.append('<text x="35" y="1020" font-family="sans-serif" font-size="13">Display extent is a viewport only. All boundary edges follow archived OSM segments.</text></svg>')
    return ('\n'.join(items) + '\n').encode()


def build():
    raw = INPUT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == INPUT_SHA256
    features = json.loads(raw)['features']
    source_groups = groups(features)
    junctions = exact_junctions(source_groups)
    arcs = [physical_arc(key, source_groups[key], junctions[index],
                         junctions[(index + 1) % 4]) for index, key in enumerate(ORDER)]
    ring = arcs[0]['coordinates'][:]
    for arc in arcs[1:]:
        assert ring[-1] == arc['coordinates'][0]
        ring.extend(arc['coordinates'][1:])
    assert ring[0] == ring[-1]
    polygon = Polygon(ring)
    assert polygon.is_valid and polygon.exterior.is_simple
    projected = transform(PROJECT, polygon)
    properties = {
        'name': 'Donner', 'municipality': 'Kaposvár', 'estimated': True,
        'boundaryKind': 'inferred_area', 'candidateBoundaryKind': 'neighborhood',
        'canonicalNameIsNeighborhood': False, 'usableForAddressAssignment': False,
        'confidence': 'low', 'reviewStatus': 'interpreted_source_candidate_not_primary',
        'sourceDate': '2023-07', 'currentNameIndependentlyConfirmed': False,
        'sourceTextRequiresInterpretation': True, 'georeferenceStatus': 'literal_modern_physical_features',
        'claimedAbsoluteAccuracyMetres': None,
        'sourceAgeAndRouteUncertainty': 'The July 2023 municipal prose is grammatically malformed. The four-boundary interpretation and equivalence of the 2023 physical routes with this PBF snapshot are explicit inferences; no statistical accuracy bound is established.',
        'method': 'Ordered Kapos → Zselic-patak → Szigetvári utca → route 67 circuit. Every edge follows actual archived OSM segments. Two real common OSM nodes and two analytical intersections at road/water crossings close the circuit. Source page 185 equates road 67 with Zselici út. No compound-unit cloning, missing-edge extension, snapping, buffer, hull, map-frame edge or municipality clipping.',
        'sourceUrl': 'https://kph.kaposvar.hu/data/adattar/fvs21-27/fvs21-27.pdf',
        'sourcePdfSha256': '291aba20ffcc41e604ad737bb6d132ae51b51d70303285e36702e4fc04e6901e',
        'sourcePdfPages': [185, 186], 'sourcePlanningPeriod': '2021–2027',
        'areaMetresSquaredEov': projected.area, 'perimeterMetresEov': projected.length,
        'sourceWayCount': len(set().union(*(set(arc['originalWayIds']) for arc in arcs))),
        'license': 'ODbL-1.0 for OSM geometry. Municipal source reuse rights unverified.',
        'attribution': '© OpenStreetMap contributors; Kaposvár FVS July 2023, pages 185–186.',
    }
    geometry = {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'id': 'kaposvar-donner-interpreted-2023',
         'properties': properties, 'geometry': mapping(polygon)}]}
    proof = {
        'schemaVersion': 1, 'inputPath': INPUT.name, 'inputSha256': INPUT_SHA256,
        'junctions': junctions, 'arcs': arcs, 'validSimpleRing': True,
        'ringCoordinateCount': len(ring), 'areaMetresSquaredEov': projected.area,
        'perimeterMetresEov': projected.length, 'geographicCoordinateCrs': 'EPSG:4326',
        'measurementCrs': 'EPSG:23700',
        'topologyUsesSourceNodeReferences': True,
        'analyticalIntersectionModel': 'Straight source-polyline segments in WGS84 longitude/latitude; original node coordinates retained verbatim. EOV used only for path-length weighting and measurements.',
        'minorJunctionCapsUsed': False, 'unprovedConnectingEdgesAdded': False,
        'selfIntersectionRepairApplied': False, 'parentUnitGeometryUsed': False,
        'claimedAbsoluteAccuracyMetres': None, 'usableForAddressAssignment': False,
    }
    return {'donner-candidate.geojson': encoded(geometry),
            'construction-proof.json': encoded(proof),
            'candidate-preview.svg': svg_preview(features, polygon, arcs)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    outputs = build()
    for name, raw in outputs.items():
        if args.check:
            assert (HERE / name).read_bytes() == raw, (name, 'reproduction mismatch')
        else:
            (HERE / name).write_bytes(raw)
    proof = json.loads(outputs['construction-proof.json'])
    print(json.dumps({key: proof[key] for key in ['validSimpleRing', 'ringCoordinateCount',
                                                'areaMetresSquaredEov', 'perimeterMetresEov']}))
