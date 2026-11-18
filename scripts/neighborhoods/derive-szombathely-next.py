#!/usr/bin/env python3
"""Trace a documentary perimeter using only consecutive original OSM node edges.

Offline input is archived alongside the result. No clipping, snapping, synthetic
closing chords, nearest-junction guess, planar crossing noding or buffers occur.
Each successive named road must have exactly one shared actual OSM node.
"""
import hashlib
import heapq
import json
from pathlib import Path

from pyproj import Geod
from shapely.geometry import Polygon, shape


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/neighborhoods/sources/municipal-szombathely-next'
INPUT = OUT / 'source-ways.geojson'
PDF = OUT / 'szombathely-ivs.source.pdf'
URL = 'https://kbr.szombathely.hu/kbrfile/46469.pdf'
GEOD = Geod(ellps='WGS84')
NAMES = ['Alkotás utca', 'Sas utca', 'Zanati út', 'Vépi út', 'Ikervár utca',
         'Zanati út', 'Bártfa utca', 'Hámor utca', 'Vas utca']
METHOD = ('Official 2013 perimeter text interpreted as an ordered road-centreline '
          'circuit on actual 2026 OSM node geometry. Every junction is the unique '
          'shared OSM node of successive named roads; every edge is consecutive '
          'in an original OSM way. No inferred connectors or geometry repair.')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def main():
    source = json.loads(INPUT.read_text())
    ways = source['features']
    nodes, by_name, graphs = {}, {}, {}
    edge_proofs = {}
    for feature in ways:
        prop = feature['properties']
        name = prop['name']
        references = prop['source']['nodeRefs']
        coordinates = feature['geometry']['coordinates']
        if len(references) != len(coordinates):
            raise ValueError('Source node coordinate correspondence is incomplete')
        by_name.setdefault(name, set()).update(references)
        graph = graphs.setdefault(name, {})
        for reference, coordinate in zip(references, coordinates):
            coordinate = tuple(coordinate)
            if reference in nodes and nodes[reference] != coordinate:
                raise ValueError('Conflicting coordinates for an actual OSM node')
            nodes[reference] = coordinate
        for start, end in zip(references, references[1:]):
            distance = abs(GEOD.inv(*nodes[start], *nodes[end])[2])
            if distance == 0:
                continue
            way_id = prop['source']['osmId']
            graph.setdefault(start, []).append((end, distance, way_id))
            graph.setdefault(end, []).append((start, distance, way_id))
            edge_proofs.setdefault((start, end), set()).add(way_id)
            edge_proofs.setdefault((end, start), set()).add(way_id)
    junctions = []
    for first, second in zip(NAMES, NAMES[1:] + NAMES[:1]):
        shared = by_name[first] & by_name[second]
        if len(shared) != 1:
            raise ValueError(f'Ambiguous/missing original shared junction: {first}, {second}: {shared}')
        junctions.append(next(iter(shared)))

    def trace(name, start, end):
        graph = graphs[name]
        best, back, queue = {start: 0}, {}, [(0, start)]
        while queue:
            distance, node = heapq.heappop(queue)
            if distance != best.get(node):
                continue
            if node == end:
                break
            for following, length, way_id in sorted(graph[node]):
                candidate = distance + length
                if candidate < best.get(following, float('inf')):
                    best[following] = candidate
                    back[following] = (node, way_id)
                    heapq.heappush(queue, (candidate, following))
        if end not in best:
            raise ValueError('Documented road is disconnected in the archived source: ' + name)
        result, used = [end], []
        while result[-1] != start:
            previous, way_id = back[result[-1]]
            used.append(way_id)
            result.append(previous)
        result.reverse()
        return result, {'road': name, 'startNodeId': start, 'endNodeId': end,
                        'nodeIds': result, 'sourceWayIds': sorted(set(used)),
                        'lengthM': round(best[end], 3)}

    circuit, sections = [], []
    for index, name in enumerate(NAMES):
        segment, proof = trace(name, junctions[index-1], junctions[index])
        if circuit and circuit[-1] != segment[0]:
            raise ValueError('Circuit continuity violated')
        circuit += segment if not circuit else segment[1:]
        sections.append(proof)
    if circuit[0] != circuit[-1]:
        raise ValueError('Perimeter is open: no synthetic closure is allowed')
    coordinates = [list(nodes[node]) for node in circuit]
    polygon = Polygon(coordinates)
    if not polygon.is_valid or polygon.is_empty:
        raise ValueError('Constructed source circuit is not a valid polygon')
    for start, end in zip(circuit, circuit[1:]):
        if (start, end) not in edge_proofs:
            raise ValueError('Non-source edge in constructed polygon')
    area = abs(GEOD.geometry_area_perimeter(polygon)[0])
    documents = [{'url': URL, 'path': str(PDF.relative_to(ROOT)), 'sha256': sha(PDF),
                  'page': 151, 'pdfPageZeroBased': 150, 'section': '15. Éhen Gyula kertváros'}]
    properties = {
        'name': 'Éhen Gyula kertváros', 'municipality': 'Szombathely',
        'boundaryKind': 'neighbourhood', 'canonicalNameIsNeighborhood': True,
        'method': METHOD, 'estimated': False, 'sourceIsOfficial': False,
        'evidenceUrls': [URL], 'sourceDocuments': documents,
        'sourceLineIds': ['way/' + str(identifier) for identifier in sorted({
            value for section in sections for value in section['sourceWayIds']})],
        'sourcePeriod': '2013 municipal IVS boundary description; 2026-11-12 OSM geometry',
        'geometryVerificationStatus': 'documentary_trace_requires_review',
        'reviewStatus': 'unreviewed', 'usableForAddressAssignment': False,
        'areaM2': area, 'inferredConnectorCount': 0,
        'license': 'ODbL-1.0',
        'attribution': '© OpenStreetMap contributors; perimeter facts: Szombathely MJV IVS annex1,2013-06-06',
        'reviewNotes': [
            'The PDF describes an actual named residential quarter, rather than an action area or multi-quarter planning cluster.',
            'Source normalizations: Hámor u. -> Hámor utca; Vas u. -> Vas utca; source typo Akotás u. -> Alkotás utca.',
            'The repeated Zanati út segments are retained in their specified order and form the southern projection visible on source map page50, quarter15.',
            'The 480x476-pixel source map was visually checked only as a coarse topology/name check; no map pixels contribute coordinates.',
            'Road centrelines are an interpretation of textual road boundaries. Parcel-side inclusion, current legal status and address assignment are not verified.'
        ]
    }
    output = OUT / 'szombathely-ehen-gyula.geojson'
    output.write_text(encode({'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'id': 'manual:szombathely:ehen-gyula',
         'properties': properties, 'geometry': {'type': 'Polygon', 'coordinates': [coordinates]}}
    ]}))
    proof = {
        'schemaVersion': 1, 'name': properties['name'], 'municipality': 'Szombathely',
        'method': METHOD, 'sourceDocuments': documents,
        'linework': {'path': str(INPUT.relative_to(ROOT)), 'sha256': sha(INPUT),
                     'upstreamSource': source['source'], 'geometriesUnchanged': True},
        'junctionCount': len(junctions), 'nodeIdsInCircuit': circuit,
        'coordinateCountIncludingClosure': len(coordinates), 'sections': sections,
        'allCoordinatesAreOriginalSourceNodes': True,
        'allEdgesAreConsecutiveOriginalSourceNodePairs': True,
        'inferredConnectors': [], 'planarCrossingIntersectionsInserted': 0,
        'closedWithoutSyntheticEdge': True, 'geometryValid': True, 'areaM2': area,
        'sourceMapVisualCheck': {'printedPage': 50, 'pdfPageZeroBased': 49,
                                 'label': '15', 'role': 'topology only, no coordinates'},
        'limitations': properties['reviewNotes'], 'usableForAddressAssignment': False,
        'output': {'path': str(output.relative_to(ROOT)), 'sha256': sha(output)},
        'reproduce': 'PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-szombathely-next.py'
    }
    (OUT / 'trace-proof.json').write_text(encode(proof))
    print(encode({'features': 1, 'name': properties['name'],
                  'coordinates': len(coordinates), 'sourceNodeEdges': len(circuit)-1,
                  'areaM2': round(area), 'inferredConnectors': 0,
                  'sha256': sha(output)}).strip())


if __name__ == '__main__':
    main()
