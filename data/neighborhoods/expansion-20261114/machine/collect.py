#!/usr/bin/env python3
"""Admit already acquired source polygons using the 2026-11-14 collection policy.

No source is downloaded and no shape is repaired.  This intentionally does not
repeat the former neighbourhood-role/current-name review.  Input files and their
source URLs remain pinned in the output for subsequent catalogue deduplication.
"""
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path
import unicodedata

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / 'data/neighborhoods'
OUT = Path(__file__).resolve().parent


def read(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFC', value).casefold() if c.isalnum())


def polygons(geometry):
    return [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']


def points(geometry):
    return [p for poly in polygons(geometry) for ring in poly for p in ring]


def bbox(geometry):
    pp = points(geometry)
    return [min(p[0] for p in pp), min(p[1] for p in pp), max(p[0] for p in pp), max(p[1] for p in pp)]


def in_box(p, b):
    return b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]


def in_ring(point, ring):
    x, y = point
    inside = False
    for a, b in zip(ring, ring[1:]):
        if (a[1] > y) != (b[1] > y):
            if x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                inside = not inside
    return inside


def inside(point, geometry):
    return any(in_ring(point, poly[0]) and not any(in_ring(point, hole) for hole in poly[1:]) for poly in polygons(geometry))


def representative(geometry):
    # A horizontal scanline midpoint is inside the largest source component.
    # It associates an unbound source area with a town; it never changes shape.
    candidates = []
    for poly in polygons(geometry):
        outer = poly[0]
        yy = [p[1] for p in outer]
        for fraction in (0.5, 0.37, 0.63):
            y = min(yy) + (max(yy)-min(yy))*fraction
            xx = []
            for a, b in zip(outer, outer[1:]):
                if (a[1] > y) != (b[1] > y):
                    xx.append(a[0] + (y-a[1]) * (b[0]-a[0]) / (b[1]-a[1]))
            xx.sort()
            for left, right in zip(xx[::2], xx[1::2]):
                p = [(left+right)/2, y]
                if inside(p, geometry):
                    candidates.append((right-left, p))
    return max(candidates, key=lambda x: x[0])[1] if candidates else points(geometry)[0]


def structural_error(geometry):
    if not geometry or geometry.get('type') not in ('Polygon', 'MultiPolygon'):
        return 'not_polygon'
    try:
        if not polygons(geometry):
            return 'empty_polygon'
        for poly in polygons(geometry):
            if not poly:
                return 'empty_component'
            for ring in poly:
                if len(ring) < 4 or ring[0] != ring[-1]:
                    return 'short_or_open_ring'
                for p in ring:
                    if len(p) < 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in p[:2]):
                        return 'nonfinite_coordinate'
                    if not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90):
                        return 'not_wgs84_coordinate_range'
        return None
    except (TypeError, KeyError):
        return 'malformed_geometry'


def main():
    known = set(read(ROOT / 'dist/data/settlements.json')['settlements'])
    existing = set()
    for filename in ('neighborhoods.geojson', 'estimated-candidates.geojson', 'planning-units.geojson'):
        for f in read(DATA / filename)['features']:
            p = f['properties']
            existing.add((p.get('municipality'), norm(p['name'])))

    municipalities = []
    for f in read(DATA/'sources/country-osm/municipalities.geojson.gz')['features']:
        if f['properties']['name'] in known:
            municipalities.append((f['properties']['name'], bbox(f['geometry']), f['geometry']))

    source_paths = [
        'catalog.geojson',
        'sources/country-osm/polygons.geojson.gz',
        'sources/extra-osm-candidates/source-areas.geojson',
        'sources/national-osm-2025/admin10.geojson',
        'sources/country-parent-review/named-crossing-quarters.geojson',
        'sources/public-vector-next/esztergom-candidates.geojson',
    ]
    features, skipped, rejected, inputs = [], [], [], []
    seen = set()
    for relative in source_paths:
        path = DATA / relative
        document = read(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        inputs.append({'path': str(path.relative_to(ROOT)), 'sha256': digest, 'records': len(document['features'])})
        for index, original in enumerate(document['features']):
            p = original['properties']
            name = p.get('name') or p.get('sourceName')
            city = p.get('municipality') or p.get('city')
            record = {'path': str(path.relative_to(ROOT)), 'index': index, 'name': name, 'municipality': city}
            if city == 'Debrecen':
                skipped.append({**record, 'reason': 'separate_debrecen_workstream'})
                continue
            if not name or not isinstance(name, str):
                rejected.append({**record, 'reason': 'missing_name'})
                continue
            geometry = original.get('geometry')
            error = structural_error(geometry)
            if error:
                rejected.append({**record, 'reason': error})
                continue
            association = 'source_municipality'
            if city not in known:
                point = representative(geometry)
                matches = [name for name, box, geom in municipalities if in_box(point, box) and inside(point, geom)]
                if len(matches) != 1:
                    rejected.append({**record, 'reason': 'no_unique_hungarian_municipality', 'representativePoint': point, 'matches': matches})
                    continue
                city = matches[0]
                association = 'source_shape_interior_point_in_municipality'
            if city == 'Debrecen':
                skipped.append({**record, 'municipality': city, 'reason': 'separate_debrecen_workstream'})
                continue
            key = city, norm(name)
            if key in existing:
                skipped.append({**record, 'municipality': city, 'reason': 'already_selected_same_city_name'})
                continue
            if key in seen:
                skipped.append({**record, 'municipality': city, 'reason': 'another_machine_source_for_same_city_name'})
                continue
            seen.add(key)
            source = p.get('source')
            source = source if isinstance(source, dict) else {'provider': source} if source else {}
            if relative == 'sources/national-osm-2025/admin10.geojson':
                source = {**source, 'url': 'https://github.com/ferenci-tamas/BudapestiElerhetoseg/blob/2f7a91ee1f320e6a08488ef8413715be13abf226/kozighatarok.zip', 'license': 'ODbL-1.0'}
            source_url = source.get('url') or next(iter(p.get('evidenceUrls', [])), None)
            geometry_hash = hashlib.sha256(json.dumps(geometry, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
            feature_id = 'machine-20261114:' + hashlib.sha256((city+'\0'+name).encode()).hexdigest()[:20]
            is_manual = source.get('provider') == 'manual-derived'
            area_role = p.get('extraClassification') or p.get('boundaryKind') or 'source_named_subdivision'
            features.append({'type': 'Feature', 'id': feature_id, 'bbox': bbox(geometry), 'geometry': geometry,
                'properties': {'id': feature_id, 'name': name, 'municipality': city, 'municipalityId': 'city:'+city,
                    'method': 'source_map_polygon' if is_manual else 'source_polygon',
                    'sourceRole': area_role, 'estimated': is_manual,
                    'semanticFootprint': bool(p.get('extraClassification')),
                    'searchable': True, 'sourceGeometryUnmodified': True,
                    'sourceUrl': source_url, 'provenance': {'path': str(path.relative_to(ROOT)), 'sha256': digest,
                        'featureIndex': index, 'originalId': original.get('id', p.get('id')), 'source': source},
                    'sourceGeometrySha256': geometry_hash,
                    'municipalityAssociation': association,
                    'coordinateAccuracyNote': 'Source outline adopted without a new boundary or current-name review. Named landuse/locality surfaces are their source footprints and may differ from everyday whole-quarter extents. Overlap and historical alternative subdivisions are intentional.',
                    'semanticReviewRequired': False, 'license': source.get('license', p.get('license', 'See preserved source attribution'))}})

    features.sort(key=lambda f: (f['properties']['municipality'], f['properties']['name']))
    output = {'type': 'FeatureCollection', 'schemaVersion': 1, 'policy': '20261114-throughput-first',
              'crsNote': 'RFC7946 longitude/latitude WGS84 (EPSG:4326)', 'features': features}
    (OUT/'features.geojson').write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':'))+'\n')
    counts = collections.Counter(f['properties']['municipality'] for f in features)
    summary = {'schemaVersion': 1, 'policyDate': '2026-11-14', 'scope': 'Additional already-acquired source polygons excluding the separate Debrecen workstream.',
        'featureCount': len(features), 'municipalityCount': len(counts), 'municipalities': dict(sorted(counts.items())),
        'inputs': inputs, 'skippedCount': len(skipped), 'skipReasons': dict(collections.Counter(r['reason'] for r in skipped)),
        'skipped': skipped, 'rejectedCount': len(rejected), 'rejected': rejected,
        'outputSha256': hashlib.sha256((OUT/'features.geojson').read_bytes()).hexdigest(),
        'geometryPolicy': 'Original source polygon coordinate arrays are preserved. No clipping, fitting, buffer, simplification, snapping, or manual repair. Municipality association of previously unbound geometries uses an interior scanline point; it is recorded explicitly.',
        'deferredLeads': [
            {'path': 'data/neighborhoods/sources/public-vector-next/wof-alt/quarantined-source-polygons.geojson', 'records': 2,
             'reason': 'These two upstream polygons are already known provider-generated point buffers, not observed source boundaries; they are candidates for the separately labelled last-resort point-based fallback only.'},
            {'path': 'data/neighborhoods/research/new-national-gis-sources.json', 'reason': 'Szentendre public GIS explicitly advertises a quarter layer; raw application/API lead remains worth acquiring.'},
            {'path': 'data/neighborhoods/research/new-municipal-gis-sources.json', 'reason': 'Additional municipal public GIS and map leads remain available; no claim that all machine sources are exhausted.'},
        ], 'nationalCoveragePercentage': None,
        'caveat': 'Counts include useful named residential/allotment/locality extents, parent areas and local subdivisions. They are not a count of independently confirmed official conventional neighbourhoods.'}
    (OUT/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: summary[k] for k in ['featureCount', 'municipalityCount', 'skipReasons', 'rejectedCount']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
