#!/usr/bin/env python3
"""Offline, explicit estimated interpretation of IVS2013 Joskar-Ola.

No geometry is fetched. Each polygon edge is a consecutive original OSM node
pair. The short unnamed connection and the divided-road junction choice are
manual interpretations, so the output is inferred only, never primary.
"""
import argparse
import hashlib
import heapq
import json
import tempfile
from pathlib import Path

from pyproj import Geod, Transformer
from shapely.geometry import LineString, Polygon, shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/neighborhoods/sources/municipal-szombathely-more'
GEOD = Geod(ellps='WGS84')
INPUT_HASHES = {
    'source-facts.json': '61082151fb44c012ccc18da141c0b8d2774275cd5a423abb488cab1e5614f095',
    'source-ways.geojson': '2477196a7bda272d802b7ee6bbd96843ab6c9b6594a3da128e469e4dcb7e8c6e',
    'source-proof-pages.pdf': 'a65645bea3cbcca2dd1a81105ce696b037a5fab1bd5a1a2cd94dcd2078cc8147',
    'source-overview.jpeg': '8056b84dd92a0347c497bd12c63a3f4ed88d1e3c98dfe959ab2fd4906eca47f0',
    'existing-joskar-snapshot.geojson': '972d51a3fcb57613841a2f59bb05db04063406fba9566634bd792b04d1c72369',
    'municipality.geojson': '88e248409bbf466d26e3443630d7b992f4b2c86ec496605841ea14f44ed311eb',
}
URL = 'https://kbr.szombathely.hu/kbrfile/46469.pdf'
METHOD = ('Estimated historical Joskar-Ola perimeter from IVS2013 annex 1, '
          'using named-road centreline paths plus a documented 42.567 m unnamed '
          'residential-road completion. Every edge is an original consecutive '
          'OSM node pair; divided-road junction choice remains unverified.')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def verify_pbf():
    """Optional provenance check against the already-local original country PBF."""
    import osmium
    path = ROOT / '.local/neighborhoods/hungary-latest.osm.pbf'
    expected_sha = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
    if sha(path) != expected_sha:
        raise ValueError('Original PBF changed')
    expected = {f['properties']['source']['osmId']: f for f in
                json.loads((OUT / 'source-ways.geojson').read_text())['features']}
    seen = set()

    class Check(osmium.SimpleHandler):
        def way(self, way):
            if way.id not in expected:
                return
            archived = expected[way.id]; s = archived['properties']['source']
            actual = {'nodeRefs': [n.ref for n in way.nodes], 'tags': dict(way.tags),
                      'objectVersion': way.version, 'objectTimestamp': str(way.timestamp)}
            if any(s[k] != value for k, value in actual.items()):
                raise ValueError('Original way metadata mismatch: ' + str(way.id))
            if not all(n.location.valid() for n in way.nodes):
                raise ValueError('Missing original node location')
            if archived['geometry']['coordinates'] != [[n.lon, n.lat] for n in way.nodes]:
                raise ValueError('Original way coordinates mismatch: ' + str(way.id))
            seen.add(way.id)

    with tempfile.TemporaryDirectory(prefix='szombathely-more-pbf-') as temp:
        Check().apply_file(str(path), locations=True,
            idx='sparse_file_array,' + str(Path(temp) / 'nodes.idx'),
            filters=[osmium.filter.IdFilter(expected)])
    if seen != set(expected):
        raise ValueError('Missing original ways')
    result = {'originalPbfSha256': expected_sha,
              'archivedWaysSha256': sha(OUT / 'source-ways.geojson'),
              'checkedCompleteOriginalWays': len(seen), 'originalWayIds': sorted(seen),
              'comparedFields': ['complete coordinate sequence', 'nodeRefs', 'complete tags',
                                 'objectVersion', 'objectTimestamp'],
              'allMatched': True, 'networkUsed': False}
    (OUT / 'pbf-way-verification.json').write_text(encode(result))
    print('Original PBF provenance verified for ' + str(len(seen)) + ' complete ways.')


def generate():
    for filename, expected in INPUT_HASHES.items():
        if sha(OUT / filename) != expected:
            raise ValueError('Frozen input changed; source review required: ' + filename)
    source = json.loads((OUT / 'source-ways.geojson').read_text())
    nodes, graphs, edge_ways = {}, {}, {}
    for f in source['features']:
        p = f['properties']; s = p['source']
        ids = s['nodeRefs']; coords = f['geometry']['coordinates']
        if len(ids) != len(coords):
            raise ValueError('Incomplete original node correspondence')
        for node, coord in zip(ids, coords):
            coord = tuple(coord)
            if node in nodes and nodes[node] != coord:
                raise ValueError('Conflicting source node coordinates')
            nodes[node] = coord
        name = 'UNNAMED_COMPLETION' if s['osmId'] == 112539408 else p['name']
        graph = graphs.setdefault(name, {})
        for first, second in zip(ids, ids[1:]):
            length = abs(GEOD.inv(*nodes[first], *nodes[second])[2])
            graph.setdefault(first, []).append((second, length, s['osmId']))
            graph.setdefault(second, []).append((first, length, s['osmId']))
            edge_ways.setdefault((first, second), set()).add(s['osmId'])
            edge_ways.setdefault((second, first), set()).add(s['osmId'])

    def trace(name, start, end):
        graph = graphs[name]
        best, previous, queue = {start: 0}, {}, [(0, start)]
        while queue:
            distance, node = heapq.heappop(queue)
            if distance != best.get(node):
                continue
            if node == end:
                break
            for nxt, length, way in sorted(graph.get(node, [])):
                candidate = distance + length
                if candidate < best.get(nxt, float('inf')):
                    best[nxt] = candidate; previous[nxt] = (node, way)
                    heapq.heappush(queue, (candidate, nxt))
        if end not in best:
            raise ValueError('Disconnected documented road: ' + name)
        route, ways = [end], []
        while route[-1] != start:
            node, way = previous[route[-1]]
            route.append(node); ways.append(way)
        route.reverse(); ways.reverse()
        return route, {'road': name, 'startNodeId': start, 'endNodeId': end,
                       'nodeIds': route, 'sourceWayIds': sorted(set(ways)),
                       'lengthM': best[end],
                       'boundaryRole': 'inferred' if name == 'UNNAMED_COMPLETION' else 'source_named_road_centreline_interpretation'}

    def circuit(top_junction):
        plan = [('Szent Márton utca', top_junction, 1280828428),
                ('Barátság utca', 1280828428, 1280828325),
                ('UNNAMED_COMPLETION', 1280828325, 1278848008),
                ('Mikes Kelemen utca', 1278848008, 2066555798),
                ('Károlyi Antal utca', 2066555798, 2385528777),
                ('Hunyadi János út', 2385528777, top_junction)]
        route, sections = [], []
        for name, first, last in plan:
            ids, proof = trace(name, first, last)
            if route and route[-1] != ids[0]:
                raise ValueError('Discontinuous circuit')
            route += ids if not route else ids[1:]
            sections.append(proof)
        if route[0] != route[-1]:
            raise ValueError('Open circuit; synthetic closure prohibited')
        polygon = Polygon([nodes[n] for n in route])
        if not polygon.is_valid or polygon.is_empty or len(polygon.interiors):
            raise ValueError('Invalid source-node circuit')
        if len(set(route[:-1])) != len(route)-1:
            raise ValueError('Repeated non-closing node')
        for a, b in zip(route, route[1:]):
            if (a, b) not in edge_ways:
                raise ValueError('Invented boundary edge')
        return polygon, route, sections

    polygon, route, sections = circuit(5324294304)
    alternative, alternative_route, alternative_sections = circuit(5324469828)
    coordinates = [list(nodes[n]) for n in route]
    area, perimeter = GEOD.geometry_area_perimeter(polygon)
    projected = Transformer.from_crs(4326, 23700, always_xy=True).transform
    old = shape(json.loads((OUT / 'existing-joskar-snapshot.geojson').read_text())['features'][0]['geometry'])
    existing_iou = transform(projected, polygon.intersection(old)).area / transform(projected, polygon.union(old)).area
    parent = shape(json.loads((OUT / 'municipality.geojson').read_text())['features'][0]['geometry'])
    if not parent.covers(polygon):
        raise ValueError('Candidate leaves municipality; no clipping permitted')
    inferred = sections[2]
    documents = [{'url': URL, 'title': 'Szombathely MJV – Integrált Városfejlesztési Stratégia 2008–13',
                  'sourceDate': '2013-06-06', 'originalPdfPageOneBased': 150,
                  'printedPage': 150, 'section': 'IX. Mellékletek, 1. sz melléklet, 5. Joskar-Ola-lakótelep',
                  'archivedExcerptPath': str((OUT / 'source-proof-pages.pdf').relative_to(ROOT)),
                  'excerptPdfPageOneBased': 3,
                  'originalPdfSha256': 'aade0d35a60e4ecd230a26c2c7dabcfc26ec76466ab86310e6828f34db714500'}]
    properties = {
        'name': 'Joskar-Ola-lakótelep', 'municipality': 'Szombathely',
        'boundaryKind': 'inferred_area', 'candidateBoundaryKind': 'neighbourhood',
        'estimated': True, 'canonicalNameIsNeighborhood': False,
        'method': METHOD, 'sourcePeriod': '2013 IVS perimeter / original OSM ways 2026-11-12',
        'sourceDocuments': documents, 'evidenceUrls': [URL],
        'sourceLineIds': ['osm:way:' + str(w) for w in sorted({w for s in sections for w in s['sourceWayIds']})],
        'sourceIsOfficial': False, 'sourceIsHardBoundary': False,
        'geometryVerificationStatus': 'inferred_not_verified', 'reviewStatus': 'estimated_candidate_not_verified',
        'usableForAddressAssignment': False, 'claimedAbsoluteAccuracyMetres': None,
        'areaM2': abs(area), 'perimeterM': perimeter,
        'inferredRoadCompletionMetres': inferred['lengthM'],
        'existingNamedQuarterId': 'osm:relation:8356511', 'newDistinctQuarterCoverage': False,
        'reviewNotes': [
            'The historical named quarter is explicitly defined by the municipal source; the modern whole-quarter footprint is not verified.',
            'Unnamed residential way 112539408 closes the 42.567 m Barátság/Mikes gap. Its boundary role is not explicitly named in the PDF.',
            'The eastern Hunyadi/Szent Márton carriageway junction is an explicit manual choice; the alternative actual-node junction changes the polygon by about 300 m².',
            'The source Mikes Kelemen railway-side clause is interpreted along the named Mikes road, not as an independently reconstructed railway ownership boundary.',
            'Current OSM Joskar-Ola already exists and has a substantially different footprint. This alternate historical interpretation adds no new distinct-quarter coverage.',
            'Source overview map is only a coarse topology check; no map pixel contributes coordinates. No chord, snapping, buffer, hull, clipping, geometry repair or planar-intersection vertex.',
            'Road centreline and street-side inclusion remain interpretations. No legal boundary, current address assignment or absolute positional accuracy is asserted.'
        ],
        'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors; factual perimeter: Szombathely MJV IVS2013 annex 1'
    }
    output = {'type': 'FeatureCollection', 'status': 'estimated_candidates_only', 'features': [
        {'type': 'Feature', 'id': 'manual:szombathely:joskar-ola-2013-inference', 'properties': properties,
         'geometry': {'type': 'Polygon', 'coordinates': [coordinates]}}
    ]}
    inferred_coords = [list(nodes[n]) for n in inferred['nodeIds']]
    completion = {'type': 'FeatureCollection', 'features': [{
        'type': 'Feature', 'id': 'manual:szombathely:joskar-inferred-completion',
        'properties': {'sourceWayId': 112539408, 'boundaryRole': 'inferred_not_source_named',
                       'lengthM': inferred['lengthM'], 'nodeIds': inferred['nodeIds'],
                       'geometryUnmodified': True, 'usableForAddressAssignment': False},
        'geometry': {'type': 'LineString', 'coordinates': inferred_coords}
    }]}
    alternative_output = {'type': 'FeatureCollection', 'status': 'estimated_alternative_not_separate_quarter', 'features': [{
        'type': 'Feature', 'id': 'manual:szombathely:joskar-western-junction-alternative',
        'properties': {'name': 'Joskar-Ola divided-road junction alternative', 'boundaryKind': 'inferred_area',
                       'estimated': True, 'usableForAddressAssignment': False, 'notAdditionalCoverage': True},
        'geometry': {'type': 'Polygon', 'coordinates': [[list(nodes[n]) for n in alternative_route]]}
    }]}
    proof = {
        'schemaVersion': 1, 'name': properties['name'], 'status': 'estimated_only', 'method': METHOD,
        'inputsSha256': INPUT_HASHES, 'sourceDocuments': documents,
        'nodeIdsInCircuit': route, 'coordinateCountIncludingClosure': len(route), 'sections': sections,
        'allCoordinatesAreOriginalSourceNodes': True, 'allEdgesAreConsecutiveOriginalSourceNodePairs': True,
        'closedWithoutSyntheticEdge': True, 'planarCrossingIntersectionsInserted': 0,
        'geometryValid': True, 'holes': 0, 'containedByMunicipalityWithoutClipping': True,
        'areaM2': abs(area), 'perimeterM': perimeter,
        'inferredBoundaryLengthM': inferred['lengthM'],
        'junctionChoice': {'selectedNodeId': 5324294304, 'alternativeNodeId': 5324469828,
                           'alternativeSections': alternative_sections,
                           'symmetricDifferenceM2EPSG23700': transform(projected, polygon.symmetric_difference(alternative)).area,
                           'sourceDoesNotResolveCarriagewayChoice': True},
        'existingQuarterComparison': {'id': 'osm:relation:8356511', 'intersectionOverUnionEPSG23700': existing_iou,
                                      'sameNameDoesNotProveSameFootprint': True, 'newDistinctQuarterCoverage': 0},
        'coarseSourceMapCheck': {'originalPdfPageOneBased': 50, 'sourceImagePixels': [480, 476],
                                'regionLabel': '5', 'role': 'topology only, no coordinates'},
        'usableForAddressAssignment': False, 'claimedAbsoluteAccuracyMetres': None,
        'reproduce': 'PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-szombathely-more.py --check'
    }
    return {'joskar-ola-inferred.geojson': encode(output),
            'inferred-completion.geojson': encode(completion),
            'junction-alternative.geojson': encode(alternative_output),
            'conversion-proof.json': encode(proof)}


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--check', action='store_true')
    args.add_argument('--verify-pbf', action='store_true')
    opts = args.parse_args()
    if opts.verify_pbf:
        verify_pbf()
        return
    for filename, value in generate().items():
        path = OUT / filename
        if opts.check:
            if not path.exists() or path.read_text() != value:
                raise ValueError('Reproduction differs: ' + filename)
        else:
            path.write_text(value)
    print('Szombathely: 1 historical inferred alternative, 0 primary, 0 new distinct-quarter names; ' + ('check passed.' if opts.check else 'written.'))


if __name__ == '__main__':
    main()
