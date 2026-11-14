#!/usr/bin/env python3
"""Audit possible Wesselényi-telep cycles without assigning an unproven name.

Requires Shapely and pyproj. The residential outline is merely a possible
proxy for the legal belterület edge, whose geometry remains unidentified.
"""
import hashlib
import json
from pathlib import Path
from pyproj import Geod, Transformer
from shapely.geometry import shape, mapping
from shapely.ops import polygonize, transform, unary_union

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/neighborhoods/manual/sources/budapest-wesselenyi-input.geojson'
OUTPUT = ROOT / 'data/neighborhoods/manual/budapest-wesselenyi-audit.json'
RAIL_IDS = {'osm:way:' + str(i) for i in [108784285, 91784641, 1334612902,
    1485317551, 1486494726, 348178874]}


def build():
    ff = json.loads(SOURCE.read_text())['features']
    by_id = {f['id']: f for f in ff}
    district = shape(by_id['osm:relation:1550597']['geometry'])
    groups = {
        'rail': unary_union([shape(by_id[i]['geometry']) for i in sorted(RAIL_IDS)]),
        'vecses': unary_union([shape(f['geometry']) for f in ff if f['properties'].get('name') == 'Vecsés út']),
        'residential': unary_union([shape(by_id[i]['geometry']).boundary for i in ['osm:relation:4638166', 'osm:relation:6996922']]),
        'district': district.boundary
    }
    to_eov = Transformer.from_crs(4326, 23700, always_xy=True).transform
    geod = Geod(ellps='WGS84')
    source_network = unary_union(list(groups.values()))
    faces = []
    for polygon in polygonize(source_network):
        if not district.covers(polygon):
            continue
        lengths = {name: polygon.boundary.intersection(g).length for name, g in groups.items()}
        if not all(lengths[name] > 1e-9 for name in ['rail', 'vecses', 'residential']):
            continue
        metres = {name: transform(to_eov, polygon.boundary.intersection(g)).length for name, g in groups.items()}
        faces.append({'geometry': mapping(polygon),
            'validGeometry': polygon.is_valid,
            'areaSquareMetres': round(abs(geod.geometry_area_perimeter(polygon)[0]), 3),
            'boundaryClassLengthMetres': {k: round(v, 3) for k, v in metres.items()},
            'unsupportedBoundaryLength': polygon.boundary.difference(source_network).length,
            'nameAssigned': False, 'acceptedForExport': False})
    assert len(faces) == 1, 'Review changed source topology before interpreting cycles.'
    north = shape(by_id['osm:relation:4638166']['geometry']).boundary
    definition = next(r for r in json.loads((ROOT / 'data/neighborhoods/manual/budapest-definitions.json').read_text())['records']
        if r['referenceName'] == 'Wesselényi-telep')
    return {'schemaVersion': 1, 'name': 'Wesselényi-telep', 'municipality': 'Budapest', 'district': 23,
        'sourceParagraph': definition['sourceParagraph'], 'boundaryText': definition['boundaryText'],
        'sourceDocuments': definition['sourceDocuments'],
        'status': 'residential_proxy_cycle_exists_but_neighborhood_identity_unresolved',
        'polygonCreatedForNeighborhood': False, 'usableForAddressAssignment': False,
        'sourceGeometry': {'path': str(SOURCE.relative_to(ROOT)),
            'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'railSourceLineIds': sorted(RAIL_IDS),
            'railChoice': 'One actual continuous main-track source chain of railway ref=150; the parallel track is not used to manufacture narrow faces.',
            'osmTimestamp': '2026-11-12T21:23:05Z',
            'pbfSha256': '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'},
        'unidentifiedSourceFaces': faces,
        'northernResidentialToVecsesDistanceMetres': round(transform(to_eov, north).distance(transform(to_eov, groups['vecses'])), 3),
        'reasonsForExclusion': [
            'No retained source supplies the legal belterület boundary or an independent locality observation placing Wesselényi-telep in the computed face.',
            'The sole contained cycle lies west of the railway and touches Vecsés út only for a few metres at its railway crossing; its remaining residential edge winds south toward current Csendes utca.',
            'The northern residential multipolygon 4638166 does not meet Vecsés út, so it cannot close the legal three-class cycle without inventing a connector.',
            'A mathematically closed source face alone does not prove the named neighborhood identity.'
        ],
        'requiredEvidence': 'Municipal map identifying Wesselényi-telep and the cited belterület edge, or another independently reusable boundary description.',
        'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors'}


if __name__ == '__main__':
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n')
    print(OUTPUT.relative_to(ROOT))
