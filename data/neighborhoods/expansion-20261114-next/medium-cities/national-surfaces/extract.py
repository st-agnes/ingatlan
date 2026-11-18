#!/usr/bin/env python3
"""Extract actual mapped named estates and multi-label residential footprints.

Offline, throughput-first extension of the earlier one-label scans.  Native
source rings are retained without clipping, buffering, hulls or simplification.
The source area and its association to a quarter name are separate evidence.
"""
from collections import Counter
from datetime import datetime, timezone
import gzip, hashlib, json, math, os, re, sys, tempfile, time, unicodedata
from pathlib import Path

import osmium
from shapely import from_wkb
from shapely.geometry import mapping, shape
from shapely.strtree import STRtree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
DATA = ROOT / 'data/neighborhoods'
PBF = Path(os.environ.get('OTTHONRA_NEIGHBORHOOD_PBF', '/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf'))


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', str(value)).casefold() if c.isalnum())


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value)).casefold() if not unicodedata.combining(c))


def encode(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode()


def write(name, value):
    (HERE / name).write_bytes(encode(value))


def main():
    start = time.monotonic()
    manifest = json.loads((DATA / 'sources/country-osm/manifest.json').read_text())
    pbf_sha = hashlib.file_digest(PBF.open('rb'), 'sha256').hexdigest()
    if pbf_sha != manifest['input']['sha256']:
        raise ValueError('PBF differs from preserved municipal/name-point source')
    node_path = DATA / 'sources/country-osm/named-nodes.geojson.gz'
    nodes = [f for f in json.loads(gzip.decompress(node_path.read_bytes()))['features']
             if f['properties'].get('municipality') and f['properties'].get('place') in {'quarter', 'suburb', 'neighbourhood'}]
    points = [shape(f['geometry']) for f in nodes]
    point_index = STRtree(points)
    municipal_path = DATA / 'sources/country-osm/municipalities.geojson.gz'
    municipalities = [f for f in json.loads(gzip.decompress(municipal_path.read_bytes()))['features']
                      if f['properties'].get('usedForAssociation')]
    municipal_shapes = [shape(f['geometry']) for f in municipalities]
    municipal_index = STRtree(municipal_shapes)
    core_path = DATA / 'search-areas.geojson'
    known = set()
    if (HERE/'baseline-keys.json').exists():
        known = {tuple(key) for key in json.loads((HERE/'baseline-keys.json').read_text())['knownKeys']}
    else:
        core = json.loads(core_path.read_bytes())['features']
        for feature in core:
            p = feature['properties']
            for name in [p['name']] + p.get('aliases', []):
                known.add((p['municipality'], norm(name)))
        for row in json.loads((DATA / 'expansion-20261114/name-aliases.json').read_text())['aliases']:
            keys = [(row['municipality'], norm(name)) for name in [row['name']] + row['aliases']]
            if any(key in known for key in keys):
                known.update(keys)
        write('baseline-keys.json', {'corePath': str(core_path.relative_to(ROOT)),
            'coreSha256': hashlib.sha256(core_path.read_bytes()).hexdigest(),
            'knownKeys': sorted([list(key) for key in known])})
    factory = osmium.geom.WKBFactory()
    areas, associations, rejected, stats = {}, [], [], Counter()
    place_kind = {'quarter', 'suburb', 'neighbourhood', 'city_block', 'subdivision'}
    branded = re.compile(r'lako(?:telep|park|kert|negyed|ovezet|terulet)\b|ipari[ -]?park\b|iparpark\b|iparterulet\b|gazdasagi[ -]?(?:ovezet|park)\b|logisztikai[ -]?park\b')
    industrial = re.compile(r'ipari[ -]?park|iparpark|iparterulet|gazdasagi[ -]?(?:ovezet|park)|logisztikai[ -]?park')
    generic = {'lakotelep', 'lakopark', 'lakoterulet', 'iparipark', 'iparterulet', 'kertek', 'kiskertek', 'zartkertek'}

    class Handler(osmium.SimpleHandler):
        def area(self, obj):
            tags = dict(obj.tags)
            raw_name = tags.get('name:hu') or tags.get('name') or tags.get('official_name') or ''
            source_name = raw_name.split(';')[0].strip()
            landuse = tags.get('landuse')
            named_kind = None
            excluded_named_object = (tags.get('building') or tags.get('shop') or tags.get('tourism')
                or tags.get('amenity') or tags.get('power') or tags.get('leisure')
                or tags.get('water') or tags.get('waterway') or tags.get('man_made')
                or tags.get('landuse') in {'basin', 'reservoir', 'cemetery', 'garages', 'railway'})
            if source_name and not excluded_named_object:
                if landuse in {'residential', 'allotments'}:
                    named_kind = 'named_' + landuse
                elif tags.get('place') in place_kind or tags.get('residential') in {'neighbourhood', 'neighborhood', 'district'}:
                    named_kind = 'named_' + (tags.get('place') or 'residential')
                elif branded.search(fold(source_name)):
                    named_kind = 'named_industrial_park' if industrial.search(fold(source_name)) else 'named_housing_estate'
            point_eligible = landuse in {'residential', 'allotments'} and not tags.get('building') and not tags.get('tourism')
            if not named_kind and not point_eligible:
                return
            stats['candidateSourceAreasExamined'] += 1
            if stats['candidateSourceAreasExamined'] % 10000 == 0:
                print(json.dumps({'progress': dict(stats), 'elapsedSeconds': round(time.monotonic()-start, 1)}), flush=True)
            kind = 'way' if obj.from_way() else 'relation'
            ident = f'osm:{kind}:{obj.orig_id()}'
            try:
                geom = from_wkb(bytes.fromhex(factory.create_multipolygon(obj)))
                if geom.is_empty or not geom.is_valid or geom.geom_type not in {'Polygon', 'MultiPolygon'}:
                    stats['invalidOriginalSourceAreas'] += 1
                    rejected.append({'id': ident, 'reason': 'invalid_original_source_area'})
                    return
                minx, miny, maxx, maxy = geom.bounds
                area_m2 = geom.area * 111320 ** 2 * math.cos(math.radians((miny + maxy) / 2))
                hits = [int(i) for i in point_index.query(geom, predicate='covers')]
                local = []
                if named_kind and area_m2 >= 1000:
                    municipal_hits = [int(i) for i in municipal_index.query(geom.representative_point(), predicate='within')]
                    if len(municipal_hits) == 1:
                        mi = municipal_hits[0]
                        mp = municipalities[mi]['properties']
                        city = mp['name']
                        if norm(source_name) != norm(city) and norm(fold(source_name)) not in generic:
                            aliases = [n.strip() for n in tags.get('alt_name', '').split(';') if n.strip()]
                            aliases += [n.strip() for n in raw_name.split(';')[1:] if n.strip()]
                            if not any((city, norm(n)) in known for n in [source_name] + aliases):
                                local.append({'name': source_name, 'municipality': city, 'aliases': aliases,
                                    'associationKind': 'source_area_name', 'sourceRole': named_kind,
                                    'municipalityEvidence': 'representative_point_in_source_municipality',
                                    'municipalityOsmId': municipalities[mi]['id'],
                                    'sourceSurfaceEntirelyInsideMunicipality': municipal_shapes[mi].covers(geom),
                                    'containedNamePoints': [nodes[i]['id'] for i in hits],
                                    'namePoint': None})
                    else:
                        stats['namedSurfaceUnresolvedMunicipality'] += 1
                if point_eligible and 3000 <= area_m2 <= 10_000_000:
                    distinct = {(nodes[i]['properties']['municipality'], norm(nodes[i]['properties']['name'])) for i in hits}
                    seen = set()
                    for i in hits:
                        point = nodes[i]
                        p = point['properties']
                        key = (p['municipality'], norm(p['name']))
                        if key in known or key in seen:
                            continue
                        seen.add(key)
                        local.append({'name': p['name'], 'municipality': p['municipality'], 'aliases': [],
                            'associationKind': 'contained_named_place', 'sourceRole': 'landuse_' + landuse,
                            'municipalityEvidence': p.get('municipalityEvidence'),
                            'municipalityOsmId': p.get('municipalityOsmId'),
                            'distinctContainedQuarterNames': len(distinct),
                            'containedNamePoints': [nodes[j]['id'] for j in hits],
                            'namePoint': {'id': point['id'], 'name': p['name'], 'place': p['place'],
                                'coordinates': point['geometry']['coordinates'], 'sourceUrl': p['source']['url'],
                                'path': str(node_path.relative_to(ROOT))}})
                if not local:
                    return
                source = {'provider': 'openstreetmap', 'osmType': kind, 'osmId': obj.orig_id(),
                    'url': f'https://www.openstreetmap.org/{kind}/{obj.orig_id()}', 'tags': tags,
                    'objectVersion': obj.version, 'objectTimestamp': str(obj.timestamp),
                    'pbfSha256': pbf_sha, 'osmTimestamp': manifest['input']['header'].get('osmosis_replication_timestamp'),
                    'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors'}
                areas[ident] = {'type': 'Feature', 'id': ident, 'geometry': mapping(geom),
                    'properties': {'source': source, 'sourceAreaSquareMetresApprox': round(area_m2, 1),
                        'sourceName': source_name, 'sourceGeometryUnmodified': True}}
                for association in local:
                    associations.append({'sourceAreaId': ident, **association})
                stats['preservedSourceAreas'] += 1
                stats['preservedNameAssociations'] += len(local)
            except (RuntimeError, ValueError) as error:
                rejected.append({'id': ident, 'reason': str(error)[:140]})
                stats['assemblyErrors'] += 1

    if '--saved-sources' in sys.argv:
        areas = {f['id']: f for f in json.loads((HERE/'raw-source-areas.geojson').read_text())['features']}
        associations = json.loads((HERE/'raw-associations.json').read_text())['associations']
        prior = json.loads((HERE/'summary.json').read_text())
        stats.update(prior['extractionStats'])
        rejected = prior['rejected']
    else:
        with tempfile.TemporaryDirectory(prefix='national-named-surfaces-') as temporary:
            Handler().apply_file(str(PBF), locations=True,
                idx='sparse_file_array,' + str(Path(temporary) / 'nodes.idx'),
                filters=[osmium.filter.KeyFilter('landuse', 'place', 'residential', 'name', 'name:hu', 'official_name')])
    point_lookup = {point['id']: point for point in nodes}
    for row in associations:
        row['containedQuarterLabels'] = [{'id': ident,
            'name': point_lookup[ident]['properties']['name'],
            'municipality': point_lookup[ident]['properties']['municipality']}
            for ident in row['containedNamePoints']]
    write('raw-source-areas.geojson', {'type': 'FeatureCollection', 'features': list(areas.values())})
    write('raw-associations.json', {'schemaVersion': 1, 'associations': associations})
    selected = {}
    def priority(row):
        source = areas[row['sourceAreaId']]['properties']
        # A source's own name is stronger than point containment. Among nested
        # containing surfaces, keep the smallest actual footprint so a broad
        # whole-city residential area cannot displace a local estate footprint.
        return (row['associationKind'] != 'source_area_name',
                row.get('distinctContainedQuarterNames', 0),
                source['sourceAreaSquareMetresApprox'], row['sourceAreaId'])
    scale_rejected = []
    for row in sorted(associations, key=priority):
        area_m2 = areas[row['sourceAreaId']]['properties']['sourceAreaSquareMetresApprox']
        lower_name = fold(row['name'])
        cap = 250_000 if 'lakopark' in lower_name else (750_000 if 'lakotelep' in lower_name else None)
        if row['associationKind'] != 'source_area_name' and cap is not None and area_m2 > cap:
            scale_rejected.append({**row, 'sourceAreaSquareMetresApprox': area_m2,
                'selectionRejectedReason': 'Source surface is too broad for a small housing-estate name.',
                'coarseAreaCapSquareMetres': cap})
            continue
        key = (row['municipality'], norm(row['name']))
        selected.setdefault(key, row)
    write('scale-rejected-associations.json', {'schemaVersion': 1, 'associations': scale_rejected,
        'sourceGeometryPreservedIn': 'raw-source-areas.geojson'})
    features = []
    for key, row in sorted(selected.items()):
        raw = areas[row['sourceAreaId']]
        own_name = row['associationKind'] == 'source_area_name'
        ident = 'national-surface:' + hashlib.sha256(encode(list(key))).hexdigest()[:22]
        features.append({'type': 'Feature', 'id': ident, 'geometry': raw['geometry'],
            'properties': {**row, 'method': 'named_source_footprint' if own_name else 'named_point_source_footprint_estimate',
                'estimated': True, 'semanticFootprint': True, 'searchable': True,
                'qualityScore': 55 if own_name else (35 if row.get('distinctContainedQuarterNames', 1) == 1 else 25),
                'sourceGeometryUnmodified': True, 'source': raw['properties']['source'],
                'sourceAreaSquareMetresApprox': raw['properties']['sourceAreaSquareMetresApprox'],
                'approximationNote': ('The actual named residential/allotment/estate/industrial-park surface is a useful named search footprint; it is not asserted to cover the entire conventional neighbourhood.' if own_name else
                    'The original mapped residential/allotment surface contains this named-place point. Multiple local names may share one actual source surface. This is an approximate search footprint, not an official quarter border.')}})
    metadata = {'schemaVersion': 1, 'policy': '20261114-throughput-first',
        'source': 'OpenStreetMap native unchanged areas from preserved national PBF',
        'pbfSha256': pbf_sha, 'sourceGeometryUnmodified': True, 'circlesGenerated': 0}
    write('features.geojson', {'type': 'FeatureCollection', **metadata, 'features': features})
    counts = Counter(f['properties']['municipality'] for f in features)
    summary = {**metadata, 'featureCount': len(features), 'municipalityCount': len(counts),
        'municipalities': dict(sorted(counts.items())), 'sourceAreaCount': len(areas),
        'sourceAssociationCount': len(associations), 'associationKinds': dict(Counter(f['properties']['associationKind'] for f in features)),
        'scaleRejectedAssociationCount': len(scale_rejected),
        'multipleLabelFootprintCount': sum(f['properties'].get('distinctContainedQuarterNames', 0) > 1 for f in features),
        'extractionStats': dict(stats), 'rejected': rejected, 'elapsedSeconds': round(time.monotonic()-start, 2),
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'coordinatePolicy': 'Original source ring assembly, no repair, clipping, circles, hull, buffer, Voronoi, snapping or simplification.',
        'coveragePercentage': None,
        'files': [{'path': name, 'sha256': hashlib.sha256((HERE/name).read_bytes()).hexdigest(),
                   'bytes': (HERE/name).stat().st_size} for name in ['features.geojson', 'raw-source-areas.geojson', 'raw-associations.json', 'baseline-keys.json']]}
    write('summary.json', summary)
    print(json.dumps({k: summary[k] for k in ['featureCount', 'municipalityCount', 'sourceAreaCount', 'sourceAssociationCount', 'associationKinds', 'multipleLabelFootprintCount', 'elapsedSeconds']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
