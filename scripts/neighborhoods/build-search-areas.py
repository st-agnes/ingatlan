#!/usr/bin/env python3
"""Build the municipality/name-deduplicated, overlap-preserving search dataset."""
from pathlib import Path
import argparse, collections, csv, gzip, hashlib, io, json, math, re, unicodedata

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data/neighborhoods'
EXPANSION = DATA / 'expansion-20261114'

def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()

def name_key(value):
    # Spaces, hyphens and letter case are spelling variants, not separate places.
    value = unicodedata.normalize('NFKC', value).casefold()
    return ''.join(c for c in value if c.isalnum())

def geometry_bounds(geometry):
    if not isinstance(geometry, dict) or geometry.get('type') not in ('Polygon', 'MultiPolygon'):
        raise ValueError('polygon_required')
    polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
    points = []
    if not polygons:
        raise ValueError('empty_geometry')
    for polygon in polygons:
        if not polygon:
            raise ValueError('empty_polygon')
        for ring in polygon:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError('unclosed_or_short_ring')
            for point in ring:
                if len(point) != 2 or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in point):
                    raise ValueError('invalid_position')
                lon, lat = point
                if not (15.5 <= lon <= 23.5 and 45 <= lat <= 49.5):
                    raise ValueError('not_hungarian_wgs84_coordinates')
                points.append(point)
    return [min(x[0] for x in points), min(x[1] for x in points), max(x[0] for x in points), max(x[1] for x in points)]

def source_metadata(properties):
    source = properties.get('source') or (properties.get('provenance') or {}).get('source')
    if source: return source
    return {key: value for key, value in {
        'url': properties.get('sourceUrl'), 'path': properties.get('sourcePath'),
        'sha256': properties.get('sourceSha256'), 'evidenceUrls': properties.get('evidenceUrls'),
        'paths': properties.get('sourcePaths')}.items() if value}

def source_priority(properties, layer):
    source = source_metadata(properties)
    method = str(properties.get('method') or source.get('method') or '')
    provider = str(source.get('provider') or '')
    tags = source.get('tags') or {}
    footprint = bool(properties.get('semanticFootprint') or properties.get('footprintOnly'))
    footprint |= properties.get('boundaryKind') in ('named_source_area', 'named_landuse_area')
    if 'radius' in method or 'circle' in method:
        return 90, 'point_radius_fallback'
    if footprint:
        return 40, 'named_source_footprint'
    if method == 'source_polygon' or provider in ('openstreetmap', 'public-arcgis', 'whosonfirst'):
        administrative = tags.get('boundary') == 'administrative' or properties.get('sourceRole') == 'district'
        return (10 if administrative else 20), 'source_polygon'
    if layer == 'neighborhoods.geojson' and source.get('osmType'):
        return 10, 'source_polygon'
    if layer == 'estimated-candidates.geojson' or any(x in method.lower() for x in ('infer', 'trace', 'raster', 'approx', 'estimate')):
        return 30, 'map_or_text_estimate'
    return 25, 'source_map_polygon'

def relative_quality(candidate):
    value = candidate['feature']['properties'].get('qualityScore')
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else 50.0

def input_paths():
    paths = [DATA / x for x in ('neighborhoods.geojson', 'planning-units.geojson', 'estimated-candidates.geojson')]
    # Only completed packets are registered; in-progress agent files must not affect releases.
    registry = json.loads((EXPANSION / 'input-registry.json').read_text())
    for entry in registry['datasets']:
        path = ROOT / entry['path']
        if sha(path.read_bytes()) != entry['sha256']:
            raise ValueError('Changed registered source packet: ' + entry['path'])
        paths.append(path)
    return paths

class Names:
    def __init__(self): self.parent = {}
    def find(self, key):
        self.parent.setdefault(key, key)
        if self.parent[key] != key: self.parent[key] = self.find(self.parent[key])
        return self.parent[key]
    def merge(self, left, right):
        a, b = self.find(left), self.find(right)
        self.parent[max(a, b)] = min(a, b)

def build():
    municipalities = set(json.loads((ROOT / 'dist/data/settlements.json').read_text())['settlements'])
    candidates, rejected, inputs, names = [], [], {}, Names()
    for path in input_paths():
        raw = path.read_bytes(); relative = path.relative_to(ROOT).as_posix()
        inputs[relative] = sha(raw)
        for index, feature in enumerate(json.loads(raw)['features']):
            p = feature.get('properties') or {}
            city, name = p.get('municipality'), p.get('name')
            try:
                if city not in municipalities: raise ValueError('unknown_municipality')
                if not isinstance(name, str) or not name.strip(): raise ValueError('missing_name')
                bbox = geometry_bounds(feature.get('geometry'))
            except (KeyError, TypeError, ValueError) as error:
                rejected.append({'path': relative, 'index': index, 'name': name, 'reason': str(error)})
                continue
            aliases = p.get('aliases') or []
            aliases = [x for x in aliases if isinstance(x, str) and x.strip()]
            key = (city, name_key(name))
            names.find(key)
            for alias in aliases: names.merge(key, (city, name_key(alias)))
            priority, method = source_priority(p, path.name)
            candidates.append({'feature': feature, 'path': relative, 'index': index, 'key': key,
                               'bbox': bbox, 'priority': priority, 'method': method, 'aliases': aliases,
                               'geometrySha256': sha(packed(feature['geometry']))})
    groups = collections.defaultdict(list)
    for candidate in candidates: groups[names.find(candidate['key'])].append(candidate)
    features, duplicate_groups = [], []
    for key, group in sorted(groups.items()):
        # Whole named boundary > source footprint > point radius. Stable ties preserve baseline.
        group.sort(key=lambda c: (c['priority'],
                                  0 if c['feature']['properties'].get('sourceSubdivisionKind') == 'parent_quarter' else 1,
                                  -relative_quality(c),
                                  0 if c['path'].endswith('/neighborhoods.geojson') else 1,
                                  c['path'], str(c['feature'].get('id', '')), c['index']))
        selected = group[0]; feature = selected['feature']; p = feature['properties']
        all_names = sorted({p['name']} | {x['feature']['properties']['name'] for x in group} |
                           {alias for x in group for alias in x['aliases']})
        city, norm = key; identifier = 'neighborhood:' + sha(city + '\0' + norm)[:24]
        alternatives = [{'path': x['path'], 'featureId': x['feature'].get('id'), 'featureIndex': x['index'],
                         'name': x['feature']['properties']['name'], 'geometrySha256': x['geometrySha256'],
                         'method': x['method'], 'priority': x['priority']} for x in group]
        properties = {'id': identifier, 'municipality': city, 'municipalityId': 'city:' + city,
                      'name': p['name'], 'label': p['name'] + ' (' + city + ')', 'canonicalNameKey': norm,
                      'aliases': [x for x in all_names if x != p['name']], 'method': selected['method'],
                      'boundaryKind': p.get('candidateBoundaryKind') or p.get('boundaryKind') or 'named_area',
                      'estimated': selected['method'] != 'source_polygon', 'source': source_metadata(p),
                      'sourceProperties': p, 'selectedSource': alternatives[0], 'sourceAlternatives': alternatives,
                      'geometrySha256': selected['geometrySha256'],
                      'usableForApproximateAddressFiltering': True,
                      'exactOrOfficialBoundaryGuaranteed': False}
        features.append({'type': 'Feature', 'id': identifier, 'bbox': selected['bbox'],
                         'properties': properties, 'geometry': feature['geometry']})
        if len(group) > 1:
            duplicate_groups.append({'id': identifier, 'municipality': city, 'name': p['name'],
                                     'selected': alternatives[0], 'alternatives': alternatives[1:]})
    counts = collections.Counter(f['properties']['method'] for f in features)
    per_city = collections.defaultdict(collections.Counter)
    for f in features: per_city[f['properties']['municipality']][f['properties']['method']] += 1
    collection = {'type': 'FeatureCollection', 'schemaVersion': 1, 'policyVersion': '20261114-throughput',
                  'coordinateSystem': 'EPSG:4326', 'coordinateOrder': 'longitude,latitude',
                  'featureCount': len(features), 'completeNationalCoverage': False,
                  'overlappingAreasAllowed': True, 'features': features}
    report = {'schemaVersion': 1, 'policyVersion': collection['policyVersion'], 'featureCount': len(features),
              'municipalityCount': len(per_city), 'methods': dict(sorted(counts.items())),
              'inputFeatureCount': len(candidates), 'duplicateVariantsPreserved': len(candidates) - len(features),
              'duplicateNameGroups': len(duplicate_groups), 'rejectedTechnicalRecords': rejected,
              'completeNationalCoverage': False, 'nationalCoveragePercentage': None,
              'inputsSha256': inputs,
              'selectionOrder': ['OSM administrative named boundary', 'native named source polygon',
                                 'native georeferenced source map polygon', 'map/text approximation',
                                 'named land-use footprint', 'point-radius fallback'],
              'notes': ['No current-name or geographic-accuracy review required by this collection policy.',
                        'Overlap between distinct names and different subdivision levels is intentional.',
                        'Names deduplicate only within municipality; explicit aliases and punctuation variants merge.',
                        'Historical and approximate borders support approximate location filtering, not legal boundary claims.'],
              'cities': [{'municipality': city, 'count': sum(c.values()), 'methods': dict(sorted(c.items()))}
                         for city, c in sorted(per_city.items())]}
    csv_file = io.StringIO(newline=''); writer = csv.writer(csv_file, delimiter=';', lineterminator='\n')
    writer.writerow(['Település', 'Kereshető területek', 'Gépi forráspoligon', 'Forrástérkép poligon',
                     'Térkép/leírás becslés', 'Elnevezett felszín körvonala', 'Kör alapú tartalék'])
    for row in report['cities']:
        m = row['methods']; writer.writerow([row['municipality'], row['count']] +
            [m.get(x, 0) for x in ('source_polygon', 'source_map_polygon', 'map_or_text_estimate',
                                  'named_source_footprint', 'point_radius_fallback')])
    content = packed(collection) + '\n'
    report['outputGeojsonSha256'] = sha(content)
    names_export = [{'id': f['id'], **{k: f['properties'][k] for k in
                    ('municipality', 'name', 'label', 'aliases', 'method')}, 'bbox': f['bbox']} for f in features]
    files = {'search-areas.geojson': content.encode(), 'search-areas.geojson.gz': gzip.compress(content.encode(), mtime=0),
             'search-area-names.json': (packed({'schemaVersion': 1, 'items': names_export}) + '\n').encode(),
             'search-areas-report.json': (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode(),
             'search-areas-report.csv': csv_file.getvalue().encode('utf-8-sig'),
             'search-areas-deduplication.json': (packed({'groups': duplicate_groups}) + '\n').encode()}
    files['search-areas.mysql.sql.gz'] = gzip.compress(mysql_export(features).encode(), mtime=0)
    return files, report

def sql_text(value):
    # Hex strings avoid SQL-mode-dependent backslash escaping and preserve UTF-8 exactly.
    return "CONVERT(X'" + value.encode('utf-8').hex() + "' USING utf8mb4)"

def mysql_export(features):
    lines = ['-- Generated data only. Does not alter application tables or delete existing rows.',
             '-- MySQL 8.0/8.4; GeoJSON positions are longitude,latitude; EPSG:4326.',
             'SET NAMES utf8mb4;',
             'CREATE TABLE IF NOT EXISTS NeighborhoodSearchAreas (',
             '  Id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,',
             '  Municipality VARCHAR(128) NOT NULL, Name VARCHAR(255) NOT NULL,',
             '  CanonicalNameKey VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,',
             '  Method VARCHAR(48) NOT NULL, Metadata JSON NOT NULL,',
             '  Boundary GEOMETRY NOT NULL SRID 4326,',
             '  UNIQUE KEY UX_NeighborhoodSearchAreas_Name (Municipality, CanonicalNameKey),',
             '  KEY IX_NeighborhoodSearchAreas_Municipality (Municipality),',
             '  SPATIAL INDEX SX_NeighborhoodSearchAreas_Boundary (Boundary)',
             ') ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_hungarian_ci;',
             'START TRANSACTION;']
    for feature in features:
        p = feature['properties']; values = [p['id'], p['municipality'], p['name'], p['canonicalNameKey'], p['method']]
        values = [sql_text(x) for x in values]
        values += ["CAST(" + sql_text(packed(p)) + " AS JSON)",
                   'ST_GeomFromGeoJSON(' + sql_text(packed(feature['geometry'])) + ',1,4326)']
        lines += ['INSERT INTO NeighborhoodSearchAreas (Id,Municipality,Name,CanonicalNameKey,Method,Metadata,Boundary) VALUES (' +
                  ','.join(values) + ') ON DUPLICATE KEY UPDATE Name=VALUES(Name),Method=VALUES(Method),Metadata=VALUES(Metadata),Boundary=VALUES(Boundary);']
    lines += ['COMMIT;', '-- Address lookup example (use bound parameters in the application):',
              "-- SET @address = ST_GeomFromText('POINT(21.61 47.55)',4326,'axis-order=long-lat');",
              "-- SELECT Id,Name FROM NeighborhoodSearchAreas WHERE Municipality='Debrecen' AND MBRIntersects(Boundary,@address) AND ST_Intersects(Boundary,@address);",
              '-- ST_Intersects includes points on an area boundary; one address may match several named areas.']
    return '\n'.join(lines) + '\n'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--check', action='store_true')
    args = parser.parse_args(); files, report = build()
    for filename, content in files.items():
        path = DATA / filename
        if args.check:
            if path.read_bytes() != content: raise SystemExit('Stale search area export: ' + filename)
        else: path.write_bytes(content)
    print(packed({k: report[k] for k in ('featureCount', 'municipalityCount', 'methods', 'duplicateVariantsPreserved')}))
