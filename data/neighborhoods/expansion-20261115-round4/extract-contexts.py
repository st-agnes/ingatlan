#!/usr/bin/env python3
"""Archive actual OSM context for every outstanding name in one offline PBF pass.

Extraction viewports are deliberately NOT neighbourhood geometry. Full source
ways are retained. These files support separate, explicitly documented estimates.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip, hashlib, json, math, os, tempfile, time
from pathlib import Path

import osmium
from shapely import from_wkb
from shapely.geometry import Polygon, Point, box, mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA = ROOT / 'data/neighborhoods'
PBF = Path(os.environ.get('OTTHONRA_NEIGHBORHOOD_PBF', '/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf'))
OUT = HERE / 'contexts'

def load(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())

def encoded(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n').encode()

def save(path, value):
    raw = encoded(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)

def main():
    started = time.monotonic()
    manifest = load(DATA/'sources/country-osm/manifest.json')
    pbf_sha = hashlib.file_digest(PBF.open('rb'), 'sha256').hexdigest()
    assert pbf_sha == manifest['input']['sha256']
    cities = [c for p in sorted((HERE/'tasks').glob('shard-*.json')) for c in load(p)['municipalities']]
    municipal = {f['properties']['name']: f for f in load(DATA/'sources/country-osm/municipalities.geojson.gz')['features']}
    all_labels = load(DATA/'sources/country-osm/named-nodes.geojson.gz')['features']
    viewports = []
    for city in cities:
        native = municipal.get(city['municipality'])
        if not native:
            raise ValueError('Missing municipality: '+city['municipality'])
        parent = shape(native['geometry'])
        points = [p['coordinates'] for t in city['targets'] for p in t['pointCandidates']]
        if any(not t['hasKnownPoint'] for t in city['targets']):
            viewport = parent
            kind = 'whole_native_municipality_for_unlocated_target'
        else:
            squares = []
            for lon, lat in points:
                dy = 4000/111320
                dx = dy/math.cos(math.radians(lat))
                squares.append(box(lon-dx, lat-dy, lon+dx, lat+dy))
            viewport = unary_union(squares).intersection(parent)
            kind = 'four_kilometre_map_context_around_original_labels_clipped_to_municipality'
        viewports.append(viewport)
        folder = OUT/city['contextKey']
        save(folder/'municipality.geojson', {'type':'FeatureCollection','features':[native]})
        save(folder/'labels.geojson', {'type':'FeatureCollection','features':[
            f for f in all_labels if f['properties'].get('municipality') == city['municipality']]})
        save(folder/'viewport.geojson', {'type':'FeatureCollection','features':[{
            'type':'Feature','geometry':mapping(viewport),'properties':{
                'municipality':city['municipality'],'role':'SOURCE_EXTRACTION_VIEWPORT_ONLY',
                'notANeighbourhoodBoundary':True,'method':kind}}]})
    index = STRtree(viewports)
    data = [defaultdict(list) for _ in cities]
    stats = Counter()
    factory = osmium.geom.WKBFactory()

    def source(obj, tags, kind):
        return {'provider':'openstreetmap','osmType':kind,'osmId':obj.id,
            'url':f'https://www.openstreetmap.org/{kind}/{obj.id}', 'tags':tags,
            'objectVersion':obj.version,'objectTimestamp':str(obj.timestamp),
            'pbfSha256':pbf_sha,'osmTimestamp':manifest['input'].get('osmTimestamp', '2026-11-12T21:23:05Z'),
            'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}

    class Handler(osmium.SimpleHandler):
        def node(self, obj):
            if not any(k in obj.tags for k in ('addr:place','addr:suburb','addr:street','addr:housenumber')):
                return
            stats['eligibleAddressNodes'] += 1
            if not obj.location.valid():
                return
            point = Point(obj.location.lon, obj.location.lat)
            hits = index.query(point, predicate='intersects')
            if not len(hits):
                return
            tags = dict(obj.tags)
            f = {'type':'Feature','id':f'osm:node:{obj.id}','geometry':mapping(point),
                'properties':{'name':tags.get('name'),'tags':tags,'source':source(obj,tags,'node')}}
            for i in hits:
                data[int(i)]['addresses'].append(f)
            stats['retainedAddressNodes'] += 1

        def way(self, obj):
            line_kind = any(k in obj.tags for k in ('highway','railway','waterway'))
            area_kind = obj.is_closed() and (any(k in obj.tags for k in ('landuse','natural','leisure','amenity','place'))
                or obj.tags.get('area') == 'yes' or ('building' in obj.tags and any(k in obj.tags for k in ('name','addr:place','addr:suburb'))))
            if not (line_kind or area_kind):
                return
            stats['eligibleWays'] += 1
            try:
                line = from_wkb(bytes.fromhex(factory.create_linestring(obj)))
                hits = index.query(line, predicate='intersects')
                if not len(hits):
                    return
                tags = dict(obj.tags)
                base = {'type':'Feature','id':f'osm:way:{obj.id}',
                    'properties':{'name':tags.get('name'),'tags':tags,'source':source(obj,tags,'way')}}
                if line_kind:
                    f = {**base,'geometry':mapping(line)}
                    for i in hits:
                        data[int(i)]['roads'].append(f)
                    stats['retainedLineWays'] += 1
                if area_kind:
                    polygon = Polygon(line.coords)
                    if polygon.is_valid and not polygon.is_empty:
                        f = {**base,'geometry':mapping(polygon)}
                        for i in hits:
                            data[int(i)]['areas'].append(f)
                        stats['retainedAreaWays'] += 1
                    else:
                        stats['invalidNativeRingsSkipped'] += 1
            except (RuntimeError, ValueError):
                stats['unassemblableNativeWaysSkipped'] += 1

    print(json.dumps({'phase':'extracting_context','municipalities':len(cities),'targets':sum(len(c['targets']) for c in cities)}),flush=True)
    with tempfile.TemporaryDirectory(prefix='round4-context-') as temporary:
        Handler().apply_file(str(PBF), locations=True, idx='sparse_file_array,'+str(Path(temporary)/'nodes.idx'),
            filters=[osmium.filter.KeyFilter('highway','railway','waterway','landuse','natural','leisure','amenity','place','area',
                'addr:place','addr:suburb','addr:street','addr:housenumber')])
    rows = []
    for city, payload in zip(cities,data):
        folder = OUT/city['contextKey']
        paths = {}
        for kind in ('roads','areas','addresses'):
            path = folder/(kind+'.geojson.gz')
            save(path, {'type':'FeatureCollection','features':payload[kind]})
            paths[kind] = {'path':str(path.relative_to(ROOT)),'featureCount':len(payload[kind]),
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
        rows.append({'municipality':city['municipality'],'contextKey':city['contextKey'],
            'targets':len(city['targets']),'files':paths})
    save(OUT/'index.json', {'schemaVersion':1,'createdAt':datetime.now(timezone.utc).isoformat(),
        'input':{'path':str(PBF),'sha256':pbf_sha,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},
        'purpose':'Actual source context only, not inferred neighbourhood boundaries. Full native ways preserved, no geometric repair.',
        'stats':dict(stats),'elapsedSeconds':round(time.monotonic()-started,1),'municipalities':rows})
    print(json.dumps({'phase':'complete','municipalities':len(rows),'stats':dict(stats),'elapsedSeconds':round(time.monotonic()-started,1)}),flush=True)

if __name__ == '__main__':
    main()
