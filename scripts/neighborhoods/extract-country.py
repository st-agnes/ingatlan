#!/usr/bin/env python3
"""Extract actual nationwide OSM quarter polygons and a separate named-node inventory.

Requires osmium==4.1.1 and shapely==2.1.2. OSM multipolygon assembly retains
source vertices; invalid/incomplete geometry is audited, never repaired or
replaced by buffers. Municipality association requires whole-geometry coverage
by the same-snapshot municipality; mere intersection never assigns a city.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import sys
import tempfile
import time

PLACES = {'suburb', 'quarter', 'neighbourhood'}
LEVELS = {'9', '10', '11'}
ROOT = Path(__file__).resolve().parents[2]


def display_name(tags):
    return (tags.get('name:hu') or tags.get('name') or '').strip()


def classification(tags):
    if tags.get('place') in PLACES:
        return {'boundaryKind': 'neighbourhood', 'classificationReason': 'place_' + tags['place']}
    if tags.get('boundary') == 'administrative' and tags.get('admin_level') in LEVELS:
        return {'boundaryKind': 'administrative_subdivision',
                'classificationReason': 'admin_' + tags['admin_level']}
    return None


def municipality_tags(tags):
    return tags.get('boundary') == 'administrative' and (
        tags.get('admin_level') == '8' or
        (tags.get('admin_level') == '6' and display_name(tags) == 'Budapest'))


def source_record(obj, kind):
    tags = dict(obj.tags)
    result = {'osmType': kind, 'osmId': obj.id, 'tags': tags,
              'objectVersion': obj.version, 'objectTimestamp': str(obj.timestamp),
              'changeset': obj.changeset,
              'url': f'https://www.openstreetmap.org/{kind}/{obj.id}'}
    if kind == 'relation':
        result['members'] = [{'type': {'n': 'node', 'w': 'way', 'r': 'relation'}.get(m.type, m.type),
                              'ref': m.ref, 'role': m.role} for m in obj.members]
    elif kind == 'way':
        result['nodeRefs'] = [n.ref for n in obj.nodes]
    return result


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def hierarchy_municipalities(key, parents, municipality_keys):
    found, visited, pending = set(), set(), [key]
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        if current != key and current in municipality_keys:
            found.add(current)
        pending.extend(parents.get(current, ()))
    return found


def select_municipality_boundaries(records, polygons, canonical):
    """Choose source boundary identities without merging or changing geometry.

    Budapest's admin6 and admin8 objects describe the same city. A tagged outer
    way can also duplicate its municipality relation. Foreign name:hu aliases
    are never Hungarian municipality identity evidence.
    """
    groups, excluded = defaultdict(list), []
    for record in records:
        tags = record['source']['tags']
        primary = (tags.get('name') or '').strip()
        reason = None
        if primary not in canonical:
            reason = 'primary_name_not_canonical_hungarian_municipality'
        elif primary == 'Budapest' and tags.get('admin_level') != '6':
            reason = 'budapest_admin6_preferred'
        if reason:
            excluded.append({'id': record['key'], 'sourceName': tags.get('name'), 'reason': reason})
        else:
            groups[primary].append({**record, 'canonicalName': primary})
    selected = []
    for name, group in sorted(groups.items()):
        group.sort(key=lambda record: (record['source']['osmType'] != 'relation', record['key']))
        winner = group[0]
        if any(not polygons[winner['key']].equals(polygons[record['key']]) for record in group[1:]):
            excluded.extend({'id': record['key'], 'sourceName': name,
                             'reason': 'conflicting_same_name_municipality_boundaries'} for record in group)
            continue
        selected.append(winner)
        excluded.extend({'id': record['key'], 'sourceName': name,
                         'reason': 'duplicate_equal_source_municipality_geometry', 'aliasOf': winner['key']}
                        for record in group[1:])
    return selected, excluded


def associate(geometry, key, municipality_index, municipality_shapes, municipality_records, parents):
    """Associate using complete coverage, with source hierarchy as a constraint.

    A sliver overlap, centroid, label node or same-name city is never enough.
    Multiple covering municipalities or a hierarchy disagreement stay unresolved.
    """
    covering = {municipality_records[int(index)]['key']
                for index in municipality_index.query(geometry)
                if municipality_shapes[int(index)].covers(geometry)}
    explicit = hierarchy_municipalities(key, parents, {r['key'] for r in municipality_records})
    candidates = covering & explicit if explicit else covering
    if explicit and not candidates:
        return {'municipality': None, 'municipalityId': None,
                'municipalityEvidence': 'hierarchy_geometry_conflict',
                'coveringMunicipalityOsmIds': sorted(covering),
                'hierarchyMunicipalityOsmIds': sorted(explicit)}
    if len(candidates) != 1:
        return {'municipality': None, 'municipalityId': None,
                'municipalityEvidence': 'ambiguous_full_containment' if candidates else 'no_full_containment',
                'coveringMunicipalityOsmIds': sorted(covering),
                'hierarchyMunicipalityOsmIds': sorted(explicit)}
    winner = next(r for r in municipality_records if r['key'] in candidates)
    return {'municipality': winner['canonicalName'], 'municipalityId': 'city:' + winner['canonicalName'],
            'municipalityOsmId': winner['key'],
            'municipalityEvidence': 'source_subarea_hierarchy_and_full_containment' if explicit else 'source_full_containment',
            'coveringMunicipalityOsmIds': sorted(covering),
            'hierarchyMunicipalityOsmIds': sorted(explicit)}


def parse_bbox(text):
    values = [float(part) for part in text.split(',')]
    if len(values) != 4 or not (-180 <= values[0] < values[2] <= 180 and -90 <= values[1] < values[3] <= 90):
        raise argparse.ArgumentTypeError('Expected west,south,east,north within WGS84 bounds')
    return values


def read_construction_areas(path):
    document = json.loads(path.read_text(encoding='utf-8'))
    areas = document.get('areas')
    if not isinstance(areas, list) or not 1 <= len(areas) <= 100:
        raise ValueError('Construction areas must contain 1..100 area records')
    seen = set()
    for area in areas:
        ident = area.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', ident) or ident in seen:
            raise ValueError('Construction area IDs must be unique lowercase ASCII identifiers')
        seen.add(ident)
        if not isinstance(area.get('bbox'), list):
            raise ValueError('Construction area requires a bbox array')
        area['bbox'] = parse_bbox(','.join(str(value) for value in area['bbox']))
    return areas


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')


def extract(input_path, output, settlements_path, construction_bbox=None, construction_areas=None):
    import osmium
    from shapely import from_wkb
    from shapely.geometry import LineString, Point, box, mapping
    from shapely.strtree import STRtree

    if output.exists():
        raise FileExistsError(f'Output directory already exists: {output}')
    if not input_path.is_file():
        raise ValueError('Missing input PBF')
    canonical = set(json.loads(settlements_path.read_text(encoding='utf-8'))['settlements'])
    source_sha = file_hash(input_path)
    acquisition_path = input_path.with_name(input_path.name + '.source.json')
    acquisition = json.loads(acquisition_path.read_text(encoding='utf-8')) if acquisition_path.exists() else None
    if acquisition and (acquisition.get('sha256') != source_sha or acquisition.get('bytes') != input_path.stat().st_size):
        raise ValueError('Input PBF differs from its acquisition manifest')
    construction_areas = list(construction_areas or [])
    if construction_bbox:
        construction_areas.append({'id': 'bbox', 'bbox': construction_bbox})
    construction_windows = [box(*area['bbox']) for area in construction_areas]
    construction_index = STRtree(construction_windows)
    def construction_ids(geometry):
        return [construction_areas[int(index)]['id'] for index in construction_index.query(geometry)
                if construction_windows[int(index)].intersects(geometry)]
    records, polygons, node_inventory, municipalities, parents = {}, {}, [], {}, defaultdict(set)
    construction_sources = {}
    assembly_failures, construction_features, counts = [], [], Counter()
    factory = osmium.geom.WKBFactory()
    started = time.monotonic()

    def progress(stage):
        print(f'OSM {stage}: {counts["nodesRead"]:,} nodes, {counts["waysRead"]:,} ways, '
              f'{counts["relationsRead"]:,} relations, {counts["areasAssembled"]:,} assembled areas; '
              f'{time.monotonic() - started:.1f}s', file=sys.stderr, flush=True)

    class Collector(osmium.SimpleHandler):
        def node(self, obj):
            counts['nodesRead'] += 1
            if counts['nodesRead'] % 2_000_000 == 0:
                progress('node pass')
            tags = dict(obj.tags)
            if tags.get('place') not in PLACES or not display_name(tags):
                return
            record = source_record(obj, 'node')
            if not obj.location.valid():
                assembly_failures.append({'id': f'osm:node:{obj.id}', 'reason': 'invalid_node_location'})
                return
            record['coordinates'] = [obj.location.lon, obj.location.lat]
            node_inventory.append(record)

        def way(self, obj):
            counts['waysRead'] += 1
            if counts['waysRead'] % 100_000 == 0:
                progress('way pass')
            tags = dict(obj.tags)
            key = f'osm:way:{obj.id}'
            if display_name(tags) and (classification(tags) or municipality_tags(tags)):
                records[key] = source_record(obj, 'way')
            if construction_areas and (tags.get('natural') == 'water' or tags.get('water')):
                construction_sources[key] = source_record(obj, 'way')
            if not construction_areas or not (tags.get('waterway') or tags.get('railway') or tags.get('natural') == 'water' or tags.get('water') or
                                                   (tags.get('highway') and display_name(tags))):
                return
            try:
                coordinates = [(n.lon, n.lat) for n in obj.nodes]
                if len(coordinates) < 2:
                    return
                geometry = LineString(coordinates)
                area_ids = construction_ids(geometry)
                if area_ids:
                    construction_features.append({'type': 'Feature', 'id': key,
                        'properties': {'name': display_name(tags), 'constructionAreaIds': area_ids, 'source': source_record(obj, 'way'),
                                       'geometryProcessing': 'Actual complete OSM way vertices; no clipping or interpolation.'},
                        'geometry': mapping(geometry)})
            except (RuntimeError, ValueError):
                counts['constructionWaysWithMissingCoordinates'] += 1

        def relation(self, obj):
            counts['relationsRead'] += 1
            if counts['relationsRead'] % 50_000 == 0:
                progress('relation pass')
            tags = dict(obj.tags)
            key = f'osm:relation:{obj.id}'
            if tags.get('boundary') == 'administrative':
                for member in obj.members:
                    if member.type == 'r' and member.role == 'subarea':
                        parents[f'osm:relation:{member.ref}'].add(key)
            if display_name(tags) and (classification(tags) or municipality_tags(tags)):
                records[key] = source_record(obj, 'relation')
            if construction_areas and (tags.get('natural') == 'water' or tags.get('water')):
                construction_sources[key] = source_record(obj, 'relation')

        def area(self, obj):
            counts['areasAssembled'] += 1
            if counts['areasAssembled'] % 250_000 == 0:
                progress('area assembly')
            tags = dict(obj.tags)
            candidate = bool(display_name(tags) and classification(tags))
            municipality = bool(display_name(tags) and municipality_tags(tags))
            water = bool(construction_areas and (tags.get('natural') == 'water' or tags.get('water')))
            if not (candidate or municipality or water):
                return
            kind = 'way' if obj.from_way() else 'relation'
            key = f'osm:{kind}:{obj.orig_id()}'
            try:
                geometry = from_wkb(bytes.fromhex(factory.create_multipolygon(obj)))
                if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in {'Polygon', 'MultiPolygon'}:
                    raise ValueError('invalid_source_polygon')
                if candidate or municipality:
                    polygons[key] = geometry
                area_ids = construction_ids(geometry) if water else []
                if area_ids:
                    construction_features.append({'type': 'Feature', 'id': key,
                        'properties': {'name': display_name(tags), 'constructionAreaIds': area_ids, 'source': construction_sources.get(key) or {
                            'osmType': kind, 'osmId': obj.orig_id(), 'tags': tags,
                            'url': f'https://www.openstreetmap.org/{kind}/{obj.orig_id()}'},
                            'geometryProcessing': 'Actual OSM multipolygon vertices; no clipping or interpolation.'},
                        'geometry': mapping(geometry)})
            except (RuntimeError, ValueError) as exc:
                if candidate or municipality:
                    assembly_failures.append({'id': key, 'reason': type(exc).__name__ + ': ' + str(exc)[:120]})

    # libosmium performs its relation pass followed by a complete location/area
    # pass. The disk-backed sparse node index avoids allocating by maximum ID.
    reader = osmium.io.Reader(str(input_path))
    header = reader.header()
    header_metadata = {key: header.get(key) for key in (
        'generator', 'osmosis_replication_timestamp', 'osmosis_replication_sequence_number',
        'osmosis_replication_base_url') if header.get(key)}
    reader.close()
    print('OSM relation collection and location/area passes started; progress follows on stderr.',
          file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory(prefix='otthonra-country-index-') as temporary:
        Collector().apply_file(str(input_path), locations=True,
                               idx='sparse_file_array,' + str(Path(temporary) / 'nodes.idx'))
    progress('source passes complete')
    # Area callbacks precede raw relation/way callbacks in pyosmium. Attach the
    # complete source members now that all raw objects have been copied.
    for feature in construction_features:
        if feature['id'] in construction_sources:
            feature['properties']['source'] = construction_sources[feature['id']]
    for key, record in sorted(records.items()):
        tags = record['tags']
        name = display_name(tags)
        if municipality_tags(tags) and name in canonical and key in polygons:
            municipalities[key] = {'key': key, 'canonicalName': name, 'source': record}
    municipality_records, municipality_selection = select_municipality_boundaries(list(municipalities.values()), polygons, canonical)
    municipality_shapes = [polygons[record['key']] for record in municipality_records]
    municipality_index = STRtree(municipality_shapes)

    def provenance(record, geometry=None):
        result = {**record, 'provider': 'openstreetmap', 'pbfSha256': source_sha,
                  'osmTimestamp': header_metadata.get('osmosis_replication_timestamp'),
                  'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
                  'attributionUrl': 'https://www.openstreetmap.org/copyright',
                  'geometryProcessing': 'libosmium source-member ring assembly; no snapping, simplification, repair, clipping or generated closing edges.'}
        if geometry is not None:
            result['geometrySha256'] = hashlib.sha256(json.dumps(geometry, separators=(',', ':')).encode()).hexdigest()
        return result

    features, rejected = [], []
    for key, record in sorted(records.items()):
        tags = record['tags']
        kind = classification(tags)
        if not kind:
            continue
        if key not in polygons:
            rejected.append({'id': key, 'name': display_name(tags), 'reason': 'no_valid_assembled_source_polygon',
                             'source': provenance(record)})
            continue
        shape = polygons[key]
        geometry = mapping(shape)
        association = associate(shape, key, municipality_index, municipality_shapes, municipality_records, parents)
        if association.get('municipality') == 'Budapest' and tags.get('admin_level') == '9':
            kind = {'boundaryKind': 'district', 'classificationReason': 'budapest_admin_9'}
        features.append({'type': 'Feature', 'id': key, 'bbox': list(shape.bounds),
            'properties': {'id': key, 'name': display_name(tags), 'sourceName': tags.get('name'),
                'preferredHungarianName': tags.get('name:hu'), 'adminLevel': tags.get('admin_level'),
                **kind, **association, 'reviewStatus': 'unreviewed',
                'usableForAddressAssignment': False, 'sourceIsOfficial': False, 'sourceIsHardBoundary': False,
                'source': provenance(record, geometry)}, 'geometry': geometry})
    node_features = []
    for record in sorted(node_inventory, key=lambda value: value['osmId']):
        key = f'osm:node:{record["osmId"]}'
        coordinates = record.pop('coordinates')
        association = associate(Point(coordinates), key, municipality_index, municipality_shapes, municipality_records, parents)
        node_features.append({'type': 'Feature', 'id': key, 'properties': {
            'name': display_name(record['tags']), 'place': record['tags']['place'], **association,
            'reviewStatus': 'unreviewed', 'hasSourcePolygon': False,
            'source': provenance(record)}, 'geometry': {'type': 'Point', 'coordinates': coordinates}})
    selected_keys = {record['key'] for record in municipality_records}
    municipality_features = [{'type': 'Feature', 'id': record['key'],
        'properties': {'name': record['canonicalName'], 'municipalityId': 'city:' + record['canonicalName'],
                       'usedForAssociation': record['key'] in selected_keys,
                       'source': provenance(record['source'])},
        'geometry': mapping(polygons[record['key']])} for record in municipalities.values()]
    output.mkdir(parents=True)
    documents = {
        'polygons.geojson': {'type': 'FeatureCollection', 'features': features},
        'named-nodes.geojson': {'type': 'FeatureCollection', 'features': node_features},
        'municipalities.geojson': {'type': 'FeatureCollection', 'features': municipality_features},
        'audit.json': {'rejectedCandidates': rejected, 'assemblyFailures': assembly_failures,
                       'municipalitySelection': municipality_selection,
                       'missingCanonicalMunicipalities': sorted(canonical - {r['canonicalName'] for r in municipality_records})}}
    if construction_areas:
        documents['construction-lines.geojson'] = {'type': 'FeatureCollection', 'features': construction_features}
    outputs = []
    for filename, document in documents.items():
        path = output / filename
        write_json(path, document)
        outputs.append({'file': filename, 'bytes': path.stat().st_size, 'sha256': file_hash(path)})
    manifest = {
        'version': 1, 'scope': 'entire Geofabrik Hungary PBF; no city query whitelist',
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'input': {'file': input_path.name, 'bytes': input_path.stat().st_size, 'sha256': source_sha,
                  'header': header_metadata, 'acquisition': acquisition},
        'dependencies': {'osmium': version('osmium'), 'shapely': version('shapely')},
        'selection': {'polygons': 'Named place=suburb|quarter|neighbourhood or boundary=administrative admin_level=9|10|11',
                      'nodes': 'Named place=suburb|quarter|neighbourhood; retained as points only',
                      'municipalities': 'Canonical named admin_level=8 plus Budapest admin_level=6 from the same PBF'},
        'counts': {**counts, 'sourcePolygonCandidates': sum(bool(classification(r['tags'])) for r in records.values()),
                   'polygons': len(features), 'namedNodes': len(node_features), 'municipalityPolygons': len(municipality_features),
                   'municipalityAssociationPolygons': len(municipality_records),
                   'municipalitiesWithPolygons': len({f['properties']['municipality'] for f in features if f['properties']['municipality']}),
                   'unresolvedPolygonMunicipalities': sum(f['properties']['municipality'] is None for f in features),
                   'rejectedPolygonCandidates': len(rejected)},
        'polygonClassifications': dict(Counter(f['properties']['classificationReason'] for f in features)),
        'constructionBbox': construction_bbox, 'constructionAreas': construction_areas, 'outputs': outputs,
        'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
        'attributionUrl': 'https://www.openstreetmap.org/copyright',
        'notes': ['Source vertices and IDs are preserved; polygons are not authoritative legal boundaries.',
                  'No buffers, Voronoi cells, interpolation, geometry repairs or arbitrary residential estates are generated.',
                  'Whole source geometry must be covered by a municipality; overlaps or centroids cannot assign a city.',
                  'Named points do not establish quarter extents or nationwide completeness.']}
    write_json(output / 'manifest.json', manifest)
    print(json.dumps(manifest['counts'], ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path, help='Country .osm.pbf file')
    parser.add_argument('--output', required=True, type=Path, help='New output directory')
    parser.add_argument('--settlements', type=Path, default=ROOT / 'dist/data/settlements.json')
    parser.add_argument('--construction-bbox', type=parse_bbox, help='Optional west,south,east,north; preserve whole intersecting source ways/water polygons')
    parser.add_argument('--construction-areas', type=Path, help='JSON {areas:[{id,bbox:[west,south,east,north]}]}; aggregate geometry has constructionAreaIds')
    args = parser.parse_args()
    try:
        extract(args.input, args.output, args.settlements, args.construction_bbox,
                read_construction_areas(args.construction_areas) if args.construction_areas else None)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f'Country extraction failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
