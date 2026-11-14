#!/usr/bin/env python3
"""Offline, source-limited Kecskemét street-circuit derivation.

No nearest-center partition, arbitrary closure, source-polygon repair, or buffer.
Named OSM roads are noded and polygonized. A single full circuit must use every
municipally specified boundary street, with every resulting vertex present in
the actual source way coordinates. Tiny road-junction cells are not quarters.
"""
import argparse
import hashlib
import json
from pathlib import Path

from pyproj import Geod
from shapely.geometry import LineString, Point, mapping, shape
from shapely.ops import polygonize, unary_union

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / 'data/neighborhoods/sources/municipal-maps-next'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value, check):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    if check:
        if not path.exists() or path.read_bytes() != data:
            raise ValueError('Stale or missing output: ' + str(path))
    else:
        path.write_bytes(data)


def build(check=False):
    facts_path = DIR / 'kecskemet-circuit-source.json'
    facts = json.loads(facts_path.read_text())
    source_path = DIR / facts['constructionLines']['path']
    if sha(source_path) != facts['constructionLines']['sha256']:
        raise ValueError('Changed pinned OSM boundary linework')
    pdf = DIR / facts['archivedSourcePages']['path']
    if sha(pdf) != facts['archivedSourcePages']['sha256']:
        raise ValueError('Changed archived municipal source pages')
    features = json.loads(source_path.read_text())['features']
    names = facts['derivation']['sourceStreetNames']
    if set(f['properties']['name'] for f in features) != set(names):
        raise ValueError('Incomplete or extra boundary street name')
    if any('kecskemet' not in f['properties']['constructionAreaIds'] for f in features):
        raise ValueError('Source line belongs to another acquisition area')
    lines = [shape(f['geometry']) for f in features]
    if any(g.geom_type != 'LineString' or not g.is_valid for g in lines):
        raise ValueError('Invalid source street geometry')
    geod = Geod(ellps='WGS84')
    candidates = list(polygonize(unary_union(lines)))
    full_circuits = []
    for polygon in candidates:
        used = [(f, g) for f, g in zip(features, lines)
                if polygon.boundary.intersection(g).length > 1e-10]
        used_names = {f['properties']['name'] for f, _ in used}
        if used_names == set(names):
            full_circuits.append((polygon, used))
    if len(full_circuits) != 1:
        raise ValueError('Boundary facts do not establish one unambiguous full street circuit')
    polygon, used = full_circuits[0]
    if not polygon.is_valid or not polygon.exterior.is_closed or polygon.interiors:
        raise ValueError('Invalid, open, or holed circuit; no automatic repair allowed')
    vertices = {tuple(c) for _, g in used for c in g.coords}
    missing = [list(c) for c in polygon.exterior.coords if tuple(c) not in vertices]
    if missing:
        raise ValueError('A derived vertex is absent from source ways; possible grade crossing')
    if any(f['properties']['source']['tags'].get('bridge') not in [None, 'no']
           or f['properties']['source']['tags'].get('tunnel') not in [None, 'no']
           or f['properties']['source']['tags'].get('layer') not in [None, '0']
           for f, _ in used):
        raise ValueError('Grade-separated boundary requires independent junction review')
    covered = unary_union([g for _, g in used])
    if polygon.boundary.difference(covered).length > 1e-12:
        raise ValueError('A boundary edge is absent from actual source geometry')
    area, perimeter = geod.geometry_area_perimeter(polygon)
    source_ids = sorted({f['properties']['source']['osmId'] for f, _ in used})
    props = {
        'name': facts['derivation']['name'], 'municipality': facts['city'],
        'boundaryKind': 'neighbourhood', 'canonicalNameIsNeighborhood': True,
        'method': 'Manual municipal street-circuit interpretation; polygonized actual OSM street centerlines with exact source vertices and no inferred connector.',
        'evidenceUrls': [facts['sourceUrl']],
        'sourceDocuments': [{'url': facts['sourceUrl'], 'sha256': facts['sourcePdfSha256'],
                             'pdfPageOneBased': 152, 'printedPage': 150,
                             'corroboratingMapPdfPageOneBased': 143, 'mapFigure': 73}],
        'sourcePeriod': facts['sourcePeriod'],
        'sourceLineIds': ['way/' + str(x) for x in source_ids],
        'quality': 'manual-source-trace', 'estimated': False,
        'sourceIsOfficial': False, 'sourceIsHardBoundary': False,
        'usableForAddressAssignment': False,
        'reviewStatus': 'manual_source_trace_pending_independent_boundary_review',
        'geometryVerificationStatus': 'source_circuit_reproduced_not_surveyed',
        'reviewNotes': [
            'Municipal 2021 boundary facts are combined with 2026 OSM street centerlines; no cadastral or address-side precision is asserted.',
            'The source map and later textual definition describe this fine subquarter, not the whole Belváros planning parent.',
            'Source street-type variants Csongrádi utca and Bajcsy Zsilinszky Endre utca correspond to the same pictured boundary roads now named Csongrádi út and Bajcsy-Zsilinszky Endre körút.',
            'All street-junction cells except the unique full five-road circuit are excluded; source geometry was not buffered, simplified, or repaired.',
            'Current official boundary and parcel-side assignment have not been independently verified.'
        ],
        'areaM2': abs(area), 'perimeterM': perimeter,
        'license': 'ODbL-1.0',
        'attribution': '© OpenStreetMap contributors; municipal factual boundary definition: Kecskemét MJV, Megalapozó Vizsgálat II., 2021, printed150; figure73 printed141.'
    }
    out = {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'geometry': mapping(polygon), 'properties': props}]}
    save(DIR / 'kecskemet-manual.geojson', out, check)
    proof = {
        'schemaVersion': 1, 'municipality': facts['city'],
        'sourceFactsSha256': sha(facts_path),
        'sourceLineworkSha256': sha(source_path),
        'archivedSourcePagesSha256': sha(pdf),
        'sourcePdfSha256': facts['sourcePdfSha256'],
        'feature': facts['derivation']['name'],
        'sourceRoads': names, 'usedWayIds': source_ids,
        'allBoundaryVerticesAreExactSourceVertices': True,
        'allBoundarySegmentsAreCoveredByActualSourceWays': True,
        'gradeSeparatedUsedWays': 0, 'inferredConnectors': 0,
        'closed': True, 'valid': True, 'vertices': len(polygon.exterior.coords),
        'areaM2': abs(area), 'perimeterM': perimeter,
        'candidateCells': len(candidates),
        'nonQuarterJunctionCellsExcluded': len(candidates) - 1,
        'independentlySurveyed': False, 'usableForAddressAssignment': False,
        'reproduce': 'PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-municipal-maps-next.py',
        'limitations': props['reviewNotes']
    }
    save(DIR / 'kecskemet-trace-proof.json', proof, check)
    print(json.dumps({'quarter': facts['derivation']['name'], 'vertices': len(polygon.exterior.coords),
                      'areaM2': round(abs(area)), 'sourceWays': len(source_ids),
                      'inferredConnectors': 0, 'check': check}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    build(parser.parse_args().check)
