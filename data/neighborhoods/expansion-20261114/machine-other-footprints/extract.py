#!/usr/bin/env python3
"""Name existing OSM land-use outlines from a single contained quarter label.

This is an explicitly estimated association.  It never fabricates a boundary:
coordinates come unchanged from actual assembled source ways/relations.
Dependencies already supplied in the research workspace: osmium, shapely.
"""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
import unicodedata

import osmium
from shapely import from_wkb
from shapely.geometry import mapping, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT/'data/neighborhoods'
OUT = Path(__file__).resolve().parent
PBF = Path(os.environ.get('OTTHONRA_NEIGHBORHOOD_PBF', str(ROOT/'.local/neighborhoods/hungary-latest.osm.pbf')))


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFC', value).casefold() if c.isalnum())


def encode(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n').encode()


def write(name, value):
    (OUT/name).write_bytes(encode(value))


def main():
    start = time.monotonic()
    pbf_hash = hashlib.file_digest(PBF.open('rb'), 'sha256').hexdigest()
    manifest = json.loads((DATA/'sources/country-osm/manifest.json').read_text())
    if pbf_hash != manifest['input']['sha256']:
        raise ValueError('PBF differs from preserved named-point source')
    node_path = DATA/'sources/country-osm/named-nodes.geojson.gz'
    nodes = json.loads(gzip.decompress(node_path.read_bytes()))['features']
    nodes = [f for f in nodes if f['properties'].get('municipality') and f['properties'].get('place') in {'quarter','suburb','neighbourhood'}]
    points = [shape(f['geometry']) for f in nodes]
    index = STRtree(points)
    factory = osmium.geom.WKBFactory()
    stats, candidates, rejected = Counter(), [], []

    class Handler(osmium.SimpleHandler):
        def area(self, obj):
            tags = dict(obj.tags)
            kind = tags.get('landuse')
            if kind not in {'industrial', 'commercial', 'retail', 'forest', 'recreation_ground', 'brownfield', 'construction', 'military'}:
                return
            if any(tags.get(k) for k in ['name', 'name:hu', 'official_name']):
                return
            stats['unnamedLanduseAreasExamined'] += 1
            if stats['unnamedLanduseAreasExamined'] % 10000 == 0:
                print(json.dumps({'progress': dict(stats), 'elapsedSeconds': round(time.monotonic()-start,1)}), flush=True)
            ident = 'osm:'+('way' if obj.from_way() else 'relation')+':'+str(obj.orig_id())
            try:
                geom = from_wkb(bytes.fromhex(factory.create_multipolygon(obj)))
                if geom.is_empty or not geom.is_valid:
                    stats['invalidSourceAreas'] += 1
                    rejected.append({'id': ident, 'reason': 'invalid_original_source_area'})
                    return
                minx,miny,maxx,maxy = geom.bounds
                area_m2 = geom.area*111320**2*math.cos(math.radians((miny+maxy)/2))
                if area_m2 < 3000 or area_m2 > 10_000_000:
                    stats['outsideAreaBounds'] += 1
                    return
                hits = [int(i) for i in index.query(geom, predicate='covers')]
                identities = {(nodes[i]['properties']['municipality'], norm(nodes[i]['properties']['name'])) for i in hits}
                if len(identities) != 1:
                    stats['noQuarterLabel' if not identities else 'multipleQuarterLabels'] += 1
                    return
                point = nodes[hits[0]]
                p = point['properties']
                source = {'provider': 'openstreetmap', 'osmType': 'way' if obj.from_way() else 'relation',
                    'osmId': obj.orig_id(), 'url': 'https://www.openstreetmap.org/'+('way' if obj.from_way() else 'relation')+'/'+str(obj.orig_id()),
                    'tags': tags, 'objectVersion': obj.version, 'objectTimestamp': str(obj.timestamp),
                    'pbfSha256': pbf_hash, 'osmTimestamp': manifest['input']['header'].get('osmosis_replication_timestamp'),
                    'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors'}
                feature = {'type':'Feature','id':ident,'bbox':list(geom.bounds),'geometry':mapping(geom),
                    'properties': {'name': p['name'], 'municipality':p['municipality'], 'municipalityId':'city:'+p['municipality'],
                        'method':'named_point_source_footprint_estimate', 'estimated':True, 'semanticFootprint':True,
                        'sourceRole':'landuse_'+kind, 'searchable':True, 'sourceGeometryUnmodified':True,
                        'sourceUrl':source['url'], 'source':source,
                        'sourceAreaSquareMetresApprox':round(area_m2,1),
                        'namePoint':{'id':point['id'],'name':p['name'],'place':p['place'],'coordinates':point['geometry']['coordinates'],
                            'sourceUrl':p['source'].get('url'),'path':'data/neighborhoods/sources/country-osm/named-nodes.geojson.gz'},
                        'containedDistinctQuarterNames':len(identities),
                        'containedNamePointIds':[nodes[i]['id'] for i in hits],
                        'coordinateAccuracyNote':'Actual unchanged unnamed industrial/commercial/retail/forest/recreation/brownfield/construction/military source outline containing exactly one distinct named quarter/suburb/neighbourhood point. Assigning that name to the containing footprint is an approximation; source outline is not asserted to be a full or official neighbourhood boundary. No circle, Voronoi, clipping, hull or shape fitting.',
                        'license':'ODbL-1.0'}}
                candidates.append(feature)
                stats['qualifyingSourceFootprints'] += 1
            except (RuntimeError, ValueError) as error:
                stats['assemblyErrors'] += 1
                rejected.append({'id':ident,'reason':str(error)[:120]})

    with tempfile.TemporaryDirectory(prefix='quarter-source-footprints-') as tmp:
        Handler().apply_file(str(PBF), locations=True, idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),
            filters=[osmium.filter.KeyFilter('landuse')])
    # For nested candidates prefer the largest residential footprint, then the
    # largest allotment footprint.  Keep every alternative in a separate raw
    # layer so no useful source shape is lost during name deduplication.
    candidates.sort(key=lambda f:(f['properties']['sourceRole']=='landuse_residential',
                                  f['properties']['sourceAreaSquareMetresApprox'],f['id']), reverse=True)
    chosen = {}
    for f in candidates:
        p=f['properties']; key=(p['municipality'], norm(p['name']))
        if key not in chosen:
            chosen[key]=f
    features = sorted(chosen.values(), key=lambda f:(f['properties']['municipality'],f['properties']['name']))
    known = set()
    for filename in ['neighborhoods.geojson','estimated-candidates.geojson','planning-units.geojson']:
        for f in json.loads((DATA/filename).read_text())['features']:
            p=f['properties'];known.add((p['municipality'],norm(p['name'])))
    for path in [DATA/'expansion-20261114/machine/features.geojson', DATA/'expansion-20261114/machine-footprints/features.geojson']:
        for f in json.loads(path.read_text())['features']:
            p=f['properties'];known.add((p['municipality'],norm(p['name'])))
    metadata={'schemaVersion':1, 'policy':'20261114-throughput-first', 'method':'named_point_source_footprint_estimate',
        'geometryPolicy':'Actual unchanged OSM source member ring assembly; estimated name-to-footprint association only.',
        'pbfSha256':pbf_hash,'namePointFile':'data/neighborhoods/sources/country-osm/named-nodes.geojson.gz',
        'namePointFileSha256':hashlib.sha256(node_path.read_bytes()).hexdigest(),
        'landuseTypes':['industrial','commercial','retail','forest','recreation_ground','brownfield','construction','military'], 'areaRangeSquareMetres':[3000,10_000_000], 'distinctContainedNameCount':1,
        'alternativeSelection':'Maximum footprint area; keep all alternatives in raw-source-footprints.geojson.'}
    write('raw-source-footprints.geojson', {'type':'FeatureCollection',**metadata,'features':candidates})
    write('features.geojson', {'type':'FeatureCollection',**metadata,'features':features})
    counts=Counter(f['properties']['municipality'] for f in features)
    summary={**metadata,'extractionStats':dict(stats),'featureCount':len(features),'sourceAlternativeCount':len(candidates),
        'municipalityCount':len(counts),'municipalities':dict(sorted(counts.items())),
        'additionalNamesBeyondPreviousPolygons':sum(key not in known for key in chosen),
        'elapsedSeconds':round(time.monotonic()-start,2),'generatedAt':datetime.now(timezone.utc).isoformat(),
        'rejected':rejected,'nationalCoveragePercentage':None,
        'caveat':'A source footprint containing a quarter label is an estimated search area, not evidence that the footprint is the whole conventional quarter.'}
    summary['files']=[{'path':name,'bytes':(OUT/name).stat().st_size,'sha256':hashlib.sha256((OUT/name).read_bytes()).hexdigest()} for name in ['features.geojson','raw-source-footprints.geojson']]
    write('summary.json',summary)
    print(json.dumps({k:summary[k] for k in ['featureCount','sourceAlternativeCount','municipalityCount','additionalNamesBeyondPreviousPolygons','elapsedSeconds','extractionStats']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
