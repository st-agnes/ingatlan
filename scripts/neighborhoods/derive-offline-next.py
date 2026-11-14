#!/usr/bin/env python3
"""Offline continuation of municipal source circuits using literal source ways."""
import argparse, hashlib, json, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/neighborhoods/sources/municipal-offline-next'
PBF=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
BBOX=(19.675,46.892,19.717,46.928)

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def extract():
 import osmium
 start=time.monotonic();features=[];stats={'filteredWays':0,'selectedWays':0};xmin,ymin,xmax,ymax=BBOX
 class Collector(osmium.SimpleHandler):
  def way(self,obj):
   stats['filteredWays']+=1
   if not any(n.location.valid() and xmin<=n.lon<=xmax and ymin<=n.lat<=ymax for n in obj.nodes):return
   tags=dict(obj.tags)
   if tags.get('highway') in ['construction','proposed']:return
   coords=[[n.lon,n.lat] for n in obj.nodes]
   f={'type':'Feature','id':f'osm:way:{obj.id}','properties':{'name':tags.get('name:hu',tags.get('name','')),
     'source':{'provider':'openstreetmap','osmType':'way','osmId':obj.id,'url':f'https://www.openstreetmap.org/way/{obj.id}',
     'tags':tags,'nodeRefs':[n.ref for n in obj.nodes],'objectVersion':obj.version,'objectTimestamp':str(obj.timestamp),
     'geometryUnmodified':True,'geometryProcessing':'Actual complete source way node sequence; bbox is acquisition only, never a polygon boundary.',
     'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}},'geometry':{'type':'LineString','coordinates':coords}}
   features.append(f);stats['selectedWays']+=1
 with tempfile.TemporaryDirectory(prefix='otthonra-local-roads-') as temp:
  Collector().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(temp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway')])
 OUT.mkdir(parents=True,exist_ok=True);path=OUT/'kecskemet-all-local-roads.geojson';write(path,{'type':'FeatureCollection','features':features})
 write(OUT/'extraction-proof.json',{'sourcePbfSha256':sha(PBF),'bboxAcquisitionOnly':BBOX,'statistics':stats,'outputSha256':sha(path),'nativeFilter':'KeyFilter(highway) after actual node location cache','includesUnnamedWays':True,'elapsedSeconds':round(time.monotonic()-start,3)})
 print(json.dumps(stats))

# Four/five named core streets come from the printed municipal description.
# Extra current names resolve the same corridors depicted in figure73; see the
# independently reviewed source-map controls and explicitly rejected shortcut.
SPECS = [
    {'name': 'Bethlenváros', 'printedPage': 147, 'pdfPageOneBased': 149,
     'literalBoundaryText': 'Bethlen körút - Rákóczi út - Koháry István körút - Jókai utca',
     'coreNames': ['Bethlen körút', 'Rákóczi út', 'Koháry István körút', 'Jókai utca'],
     'transitionNames': ['Piaristák tere'], 'labelId': 'osm:node:984225151'},
    {'name': 'Homoki-domb', 'printedPage': 146, 'pdfPageOneBased': 148,
     'literalBoundaryText': 'Széchenyi körút - Jókai utca - Hornyik János körút – Petőfi Sándor utca.',
     'coreNames': ['Széchenyi körút', 'Jókai utca', 'Hornyik János körút', 'Petőfi Sándor utca'],
     'transitionNames': ['Piaristák tere', 'Széchenyi tér', 'Szilády Károly utca',
                         'Kölcsey utca', 'Gáspár András körút', 'Mária körút'], 'labelId': None},
    {'name': 'Rákócziváros', 'printedPage': 148, 'pdfPageOneBased': 150,
     'literalBoundaryText': 'Rákóczi út - Kuruc körút - Csongrádi utca - Csányi János körút',
     'coreNames': ['Rákóczi út', 'Kuruc körút', 'Csongrádi út', 'Csányi János körút'],
     'transitionNames': ['Nap utca', 'Kurucz tér'], 'labelId': 'osm:node:984225154'},
]
SOURCE_URL = 'https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf'
SOURCE_PDF_SHA = '83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939'
ROADS_SHA = 'c8a1efef355fa22f676098d5dbf557bf2f308920c4af6da42ad58fce80c77a86'
EXCLUDED_UNNAMED_CLASSES = {'steps', 'footway', 'path', 'cycleway', 'corridor', 'platform'}


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def save(path, value, check):
    content = encode(value)
    if check:
        if not path.exists() or path.read_bytes() != content:
            raise ValueError('Stale or missing derived file: ' + str(path))
    else:
        path.write_bytes(content)


def build(check=False):
    import gzip
    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union, polygonize
    from pyproj import Geod

    roads_path = OUT / 'kecskemet-all-local-roads.geojson'
    if sha(roads_path) != ROADS_SHA:
        raise ValueError('Changed pinned literal OSM road input')
    extraction_path = OUT / 'extraction-proof.json'
    extraction = json.loads(extraction_path.read_text())
    if extraction['outputSha256'] != ROADS_SHA:
        raise ValueError('Extraction proof no longer binds the actual road bytes')
    road_features = json.loads(roads_path.read_text())['features']
    review_path = OUT / 'north-review.json'
    review = json.loads(review_path.read_text())
    if review['actualRoadInput']['sha256'] != ROADS_SHA:
        raise ValueError('Source-map review refers to another road snapshot')
    archive = ROOT / 'data/neighborhoods/sources/municipal-maps-next/kecskemet-source-pages.pdf'
    if sha(archive) != '9b8663136f085c0c7ec307c3e92cbad02937336b5c5265f67128d623b45df2ee':
        raise ValueError('Changed archived municipal page subset')

    country = ROOT / 'data/neighborhoods/sources/country-osm'
    point_bytes = gzip.decompress((country / 'named-nodes.geojson.gz').read_bytes())
    parent_bytes = gzip.decompress((country / 'municipalities.geojson.gz').read_bytes())
    points = {f['id']: f for f in json.loads(point_bytes)['features']}
    parent_feature = next(f for f in json.loads(parent_bytes)['features']
                          if f['properties']['name'] == 'Kecskemét'
                          and f['properties'].get('usedForAssociation'))
    parent = shape(parent_feature['geometry'])
    geod = Geod(ellps='WGS84')
    output, traces, used_ids, label_features = [], [], set(), []

    for spec in SPECS:
        allowed = set(spec['coreNames'] + spec['transitionNames'])
        selected = [f for f in road_features if f['properties']['name'] in allowed]
        named_context = unary_union([shape(f['geometry']) for f in selected])
        # This distance only acquires possible source junction lines. It never
        # becomes a buffer/extent, boundary vertex, or inferred closing edge.
        selected += [f for f in road_features
                     if not f['properties']['name']
                     and f['properties']['source']['tags']['highway'] not in EXCLUDED_UNNAMED_CLASSES
                     and shape(f['geometry']).distance(named_context) < 0.0008]
        geometries = [shape(f['geometry']) for f in selected]
        cells = list(polygonize(unary_union(geometries)))
        candidates = []
        for polygon in cells:
            used = [(f, g) for f, g in zip(selected, geometries)
                    if polygon.boundary.intersection(g).length > 1e-10]
            names = {f['properties']['name'] for f, _ in used}
            if set(spec['coreNames']) <= names:
                candidates.append((polygon, used, names))
        if len(candidates) != 1:
            raise ValueError('Expected one full actual street circuit: ' + spec['name'])
        polygon, used, names = candidates[0]
        if not polygon.is_valid or polygon.interiors or not polygon.exterior.is_closed:
            raise ValueError('Invalid, holed or open circuit; no repair is permitted')
        source_edges = {tuple(sorted((tuple(a), tuple(b))))
                        for f, _ in used
                        for a, b in zip(f['geometry']['coordinates'], f['geometry']['coordinates'][1:])}
        for a, b in zip(polygon.exterior.coords, list(polygon.exterior.coords)[1:]):
            if tuple(sorted((tuple(a), tuple(b)))) not in source_edges:
                raise ValueError('Output edge is not consecutive actual source nodes')
        if any(f['properties']['source']['tags'].get('bridge') not in [None, 'no']
               or f['properties']['source']['tags'].get('tunnel') not in [None, 'no']
               or f['properties']['source']['tags'].get('layer') not in [None, '0']
               for f, _ in used):
            raise ValueError('Grade-separated source corridor needs separate review')
        if not parent.covers(polygon):
            raise ValueError('Quarter is not wholly inside actual Kecskemét municipality')
        area, perimeter = geod.geometry_area_perimeter(polygon)
        source_ids = sorted({f['id'] for f, _ in used})
        used_ids.update(source_ids)
        label = points.get(spec['labelId'])
        if label:
            if label['properties']['municipality'] != 'Kecskemét' or not polygon.covers(shape(label['geometry'])):
                raise ValueError('Named source point is outside quarter/municipality')
            label_features.append(label)
        name_evidence = ({'status': 'same_snapshot_label_inside', 'sourceId': label['id'],
                          'name': label['properties']['name'], 'independentOfOsmProvider': False}
                         if label else {'status': 'municipal_document_name_only',
                                        'matchingCurrentOsmLabelFound': False,
                                        'currentNameIndependentlyConfirmed': False})
        docs = [{'url': SOURCE_URL, 'sha256': SOURCE_PDF_SHA,
                 'pdfPageOneBased': spec['pdfPageOneBased'], 'printedPage': spec['printedPage'],
                 'corroboratingMapPdfPageOneBased': 143, 'mapFigure': 73}]
        notes = [
            'Municipal2021 street facts and source-map corridors interpreted on actual2026 OSM node geometry; this is not a cadastral/legal/current-boundary survey.',
            'Short descriptions omit square/name transitions and some unnamed road-junction/carriageway pieces; the cited independent visual source-map review documents them.',
            'No output vertex or edge is synthetic: every boundary edge is a consecutive-node edge in one actual source way.',
            'Road-side and divided-carriageway choices remain approximate at junctions; absolute boundary accuracy is unknown.',
            'A manually aligned map preview is visual evidence only and supplies no output geographical coordinates or metre-accuracy claim.'
        ]
        if spec['name'] == 'Rákócziváros':
            notes.append('The source-map outer cap follows actual Nap utca/Kurucz tér ways. The shorter Búzaszentelő residential connector is explicitly rejected as a source-inconsistent interior shortcut.')
        if not label:
            notes.append('The2021 source documents Homoki-domb, but no exact current same-snapshot OSM label was found; current-name confirmation remains unverified.')
        properties = {'name': spec['name'], 'municipality': 'Kecskemét',
            'boundaryKind': 'neighbourhood', 'canonicalNameIsNeighborhood': True,
            'method': 'Manual municipal street-circuit interpretation using source-map-confirmed current square/name transitions and actual unnamed junction/carriageway ways; polygonized only actual source linework. Every output edge is consecutive original OSM nodes, with no inferred closure or repair.',
            'sourceDocuments': docs, 'evidenceUrls': [SOURCE_URL],
            'sourcePeriod': 'Municipal egyeztetési változat2021május, published under126/2021(XII.16); source linework Hungary2026-11-12.',
            'sourceLineIds': source_ids, 'sourceNameEvidence': name_evidence,
            'quality': 'manual-source-map-corroborated-street-trace',
            'estimated': False, 'sourceIsOfficial': False, 'sourceIsHardBoundary': False,
            'usableForAddressAssignment': False, 'claimedAbsoluteAccuracyMetres': None,
            'geometryVerificationStatus': 'source_circuit_reproduced_not_surveyed',
            'reviewStatus': 'source_map_corroborated_boundary_review_required',
            'reviewNotes': notes, 'areaM2': abs(area), 'perimeterM': perimeter,
            'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors; municipal boundary facts Kecskemét MJV2021, figure73 and cited descriptions.'}
        output.append({'type': 'Feature', 'id': 'manual:kecskemet-offline-next:' + spec['name'],
                       'properties': properties, 'geometry': mapping(polygon)})
        unnamed = []
        for feature, geom in used:
            if not feature['properties']['name']:
                unnamed.append({'sourceId': feature['id'],
                                'lengthUsedM': geod.geometry_length(polygon.boundary.intersection(geom)),
                                'tags': feature['properties']['source']['tags']})
        traces.append({'name': spec['name'], 'literalSourceBoundaryText': spec['literalBoundaryText'],
            'currentCoreStreetNames': spec['coreNames'],
            'mapConfirmedTransitionNames': spec['transitionNames'], 'actualBoundaryNamesUsed': sorted(names),
            'sourceWayIdsUsed': source_ids, 'unnamedSourceWaysUsed': unnamed,
            'valid': True, 'closed': True, 'holes': 0, 'vertices': len(polygon.exterior.coords),
            'allEdgesAreOriginalConsecutiveNodeEdges': True, 'inferredConnectors': 0,
            'gradeSeparatedSourceWaysUsed': 0, 'fullyInsideCanonicalMunicipality': True,
            'areaM2': abs(area), 'sourceNameEvidence': name_evidence})

    for i, left in enumerate(output):
        for right in output[i + 1:]:
            if shape(left['geometry']).intersection(shape(right['geometry'])).area > 1e-16:
                raise ValueError('Quarter source circuits overlap in their interiors')
    path = OUT / 'kecskemet-next.geojson'
    save(path, {'type': 'FeatureCollection', 'features': output}, check)
    save(OUT / 'source-way-subset.geojson', {'type': 'FeatureCollection',
         'features': [f for f in road_features if f['id'] in used_ids]}, check)
    save(OUT / 'source-label-points.geojson', {'type': 'FeatureCollection', 'features': label_features}, check)
    proof = {'schemaVersion': 1, 'purpose': 'Three further fine Kecskemét quarter source circuits, not complete city coverage.',
        'inputs': [{'path': roads_path.name, 'sha256': sha(roads_path)},
                   {'path': str(archive.relative_to(ROOT)), 'sha256': sha(archive)},
                   {'path': review_path.name, 'sha256': sha(review_path)}],
        'sourcePbfSha256': extraction['sourcePbfSha256'], 'sourcePdfSha256': SOURCE_PDF_SHA,
        'namePointSnapshotDecompressedSha256': hashlib.sha256(point_bytes).hexdigest(),
        'municipalitySnapshotDecompressedSha256': hashlib.sha256(parent_bytes).hexdigest(),
        'municipalitySourceId': parent_feature['id'], 'featureCount': len(output), 'features': traces,
        'outputSha256': sha(path), 'usableForAddressAssignment': False,
        'reproduce': 'PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-offline-next.py --check',
        'limits': ['Source geometry, municipal facts and visual corridor matching do not establish present official/legal boundaries.',
                   'Homoki-domb current-name status remains explicitly unverified.',
                   'The raw road acquisition rectangle and junction-neighborhood selection distance never define quarter extents.']}
    save(OUT / 'trace-proof.json', proof, check)
    entry = {'id': 'kecskemet-offline-next', 'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
        'municipality': 'Kecskemét', 'method': 'Municipal source-map-corroborated actual OSM street circuits with exact consecutive-node edges.',
        'evidenceUrls': [SOURCE_URL], 'license': 'ODbL-1.0',
        'propertyOverrides': {'boundaryKind': 'neighbourhood', 'canonicalNameIsNeighborhood': True,
                              'usableForAddressAssignment': False},
        'reviewPath': str((OUT / 'trace-proof.json').relative_to(ROOT)),
        'rightsStatus': 'OSM road geometry ODbL-1.0; municipal illustration/document reuse rights not independently established.'}
    save(OUT / 'registry-entry.json', entry, check)
    print(json.dumps({'features': len(output), 'names': [p['properties']['name'] for p in output],
                      'sourceWays': len(used_ids), 'inferredConnectors': 0, 'check': check}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true', help='Re-extract literal full OSM road ways from the local pinned PBF')
    parser.add_argument('--check', action='store_true', help='Read-only byte-level reproduction check')
    args = parser.parse_args()
    if args.extract:
        extract()
    else:
        build(args.check)
