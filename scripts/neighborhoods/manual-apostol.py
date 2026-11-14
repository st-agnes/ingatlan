#!/usr/bin/env python3
"""Derive Apostolhegy from the legal street/stream/river/district boundary list.

Requires Shapely. Uses source edges and their actual 2D intersections only.
The modern Haraszti junction has unnamed ref=510 approaches, retained explicitly.
"""
import hashlib
import json
from pathlib import Path
from shapely.geometry import shape, mapping
from shapely.ops import polygonize, unary_union

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/neighborhoods/manual/sources/budapest-apostolhegy-input.geojson'
OUTPUT = ROOT / 'data/neighborhoods/manual/budapest-apostolhegy.geojson'
JUNCTION_IDS = {'osm:way:24188811', 'osm:way:662525383', 'osm:way:79701205', 'osm:way:79701206'}


def build():
    features = json.loads(SOURCE.read_text())['features']
    by_id = {f['id']: f for f in features}
    district = shape(by_id['osm:relation:1550597']['geometry'])
    groups = {}
    for name in ['Grassalkovich út', 'Haraszti út']:
        groups[name] = unary_union([shape(f['geometry']) for f in features
            if f['properties'].get('name') == name])
    groups['junction'] = unary_union([shape(by_id[i]['geometry']) for i in sorted(JUNCTION_IDS)])
    groups['creek'] = shape(by_id['osm:way:43001647']['geometry'])
    groups['river'] = shape(by_id['osm:relation:417508']['geometry']).boundary
    groups['district'] = district.boundary
    # Noding computes only true intersections on the original source segments.
    network = unary_union(list(groups.values()))
    candidates = []
    for polygon in polygonize(network):
        if polygon.intersection(district).area / polygon.area < 0.999999:
            continue
        lengths = {name: polygon.boundary.intersection(line).length
            for name, line in groups.items()}
        if all(lengths[name] > 1e-9 for name in ['Haraszti út', 'junction', 'creek', 'river', 'district']):
            candidates.append((polygon, lengths))
    assert len(candidates) == 2, 'Unexpected topology; review source junctions and face selection.'
    # The complementary face follows the district's entire northern/eastern
    # perimeter; the local cycle bounded by the five cited features is smaller.
    candidates.sort(key=lambda pair: pair[0].area)
    polygon, lengths = candidates[0]
    assert len(polygon.interiors) == 0 and polygon.is_valid
    assert polygon.area < candidates[1][0].area / 10
    ids = []
    for f in features:
        geometry = shape(f['geometry'])
        boundary = geometry.boundary if geometry.geom_type in ['Polygon', 'MultiPolygon'] else geometry
        if polygon.boundary.intersection(boundary).length > 1e-9:
            ids.append(f['id'])
    law = 'https://net.jogtar.hu/rendelet?council=fovaros&dbnum=104&docid=A1200094.FOV'
    documents = [{'url': law, 'sha256': 'fb61b865266990e43e6407f7d46e8421a17541b5efa4962bcff3cd8f9f0ecfac',
        'paragraph': '3. melléklet 23.1.'}]
    properties = {
        'name': 'Apostolhegy', 'municipality': 'Budapest', 'district': 23,
        'boundaryKind': 'neighbourhood',
        'method': 'legal_boundary_classes_polygonized_from_osm_segments_and_actual_intersections',
        'evidenceUrls': [law] + [by_id[i]['properties']['source']['url'] for i in ids],
        'sourceDocuments': documents,
        'sourceLineIds': ids,
        'sourceGeometry': {'path': str(SOURCE.relative_to(ROOT)),
            'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'geometryOperation': 'Node true 2D source-segment intersections and polygonize; select the local closed face touching each legal boundary class.',
            'addedConnectingSegments': 0, 'buffersUsed': False,
            'boundaryClassLengthsDegrees': lengths,
            'candidateFaceAreasSquareDegrees': [pair[0].area for pair in candidates],
            'faceSelection': 'The smaller local face bounded by creek, road/junction, southern district boundary and mainland river shoreline; the other face is the complement extending around the district northern/eastern perimeter.',
            'junctionSourceLineIds': sorted(JUNCTION_IDS)},
        'quality': 'source_based_inferred_boundary_candidate',
        'reviewNotes': [
            'Legal Gyáli-patak is mapped as Gyáli (1.)-csatorna (way 43001647).',
            'The modern Grassalkovich–Haraszti interchange has unnamed ref=510 approaches. The source ref=510 southbound approach and main Haraszti roadway form the selected road boundary; the mapped highway=primary Grassalkovich centerline crosses the creek about 9 m east of this approach.',
            'This junction interpretation is an explicit approximation; the legal street-corridor edge and source road centerlines may differ.',
            'The mapped mainland shoreline is used at the Duna. The polygon does not include the neighboring Molnár-sziget.',
            'No arbitrary segment closes the ring; every edge lies on a retained road, creek, river shoreline or district boundary segment.'
        ],
        'usableForAddressAssignment': False,
        'source': {'provider': 'OpenStreetMap via Geofabrik Hungary extract',
            'url': 'https://download.geofabrik.de/europe/hungary-261112.osm.pbf',
            'pbfSha256': '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a',
            'timestamp': '2026-11-12T21:23:05Z',
            'districtSnapshot': by_id['osm:relation:1550597']['properties']['source']['timestamp']},
        'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
        'attributionUrl': 'https://www.openstreetmap.org/copyright'
    }
    return {'type': 'FeatureCollection', 'features': [{'type': 'Feature',
        'id': 'manual:Budapest:Apostolhegy', 'properties': properties, 'geometry': mapping(polygon)}]}


if __name__ == '__main__':
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n')
    print(OUTPUT.relative_to(ROOT))
