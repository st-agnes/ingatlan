#!/usr/bin/env python3
"""Audit actual local-PBF area tags omitted by the primary quarter selector.

No network, generated polygons, repair, snapping, or quarter inference. Named
residential areas are always research proxies, never admitted quarter borders.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip, hashlib, importlib.util, json
from pathlib import Path
import sys, tempfile, time, unicodedata

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('country_source', Path(__file__).with_name('extract-country.py'))
country = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(country)
OUT = ROOT/'data/neighborhoods/sources/extra-osm-candidates'
PBF = ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
SOURCE = ROOT/'data/neighborhoods/sources/country-osm'


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value)).casefold() if c.isalnum())


def extra_kind(tags):
    if not country.display_name(tags) or country.classification(tags):
        return None
    if tags.get('boundary') in {'neighbourhood','neighborhood','suburb','quarter','district'}:
        return 'explicit_nonstandard_quarter_boundary'
    if tags.get('boundary') == 'place':
        return 'other_place_boundary'
    if tags.get('boundary') == 'administrative' and tags.get('admin_level') in {'12','13','14','15'}:
        return 'administrative_level_' + tags['admin_level']
    if tags.get('place') in {'borough','city_block','subdivision'}:
        return 'other_urban_place_' + tags['place']
    if tags.get('place') in {'hamlet','village','locality','isolated_dwelling'}:
        return 'other_locality_surface_' + tags['place']
    if tags.get('landuse') in {'residential','allotments'}:
        return 'landuse_proxy_' + tags['landuse']
    if tags.get('residential') in {'neighbourhood','neighborhood','district'}:
        return 'residential_proxy_' + tags['residential']
    return None


def encode(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n').encode()


def write(path, value):
    path.write_bytes(encode(value))


def load_geo(name):
    path=SOURCE/(name+'.gz'); raw=gzip.decompress(path.read_bytes())
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    expected=next(row for row in manifest['outputs'] if row['file']==name)
    if len(raw)!=expected['bytes'] or hashlib.sha256(raw).hexdigest()!=expected['sha256']:
        raise ValueError('Preserved country source fingerprint mismatch: '+name)
    return json.loads(raw), {'path':str(path.relative_to(ROOT)), 'decompressedSha256':hashlib.sha256(raw).hexdigest()}


def write_research_layers(output, document):
    """Retain actual footprint coordinates while explicitly withholding quarter semantics."""
    proxies=[]; settlements=[]
    for original in document['features']:
        p=original['properties']; decision=p['recommendation']
        if decision=='corroborated_landuse_proxy_only':
            properties={**p,'boundaryKind':'landuse_proxy','estimated':True,
                        'canonicalNameIsNeighborhood':False,'usableForAddressAssignment':False,
                        'geometryVerificationStatus':'actual_landuse_surface_not_a_verified_quarter_boundary',
                        'interpretationStatus':'name_correlated_landuse_proxy_requiring_manual_boundary_research',
                        'countsTowardQuarterCoverage':False,
                        'proxyLimitations':['A matching name or label locates the named area but does not establish its extent.',
                                            'Residential/allotment footprint may cover only part of a quarter or include land outside it.',
                                            'No municipal, cadastral or address-side boundary accuracy is asserted.']}
            proxies.append({**original,'properties':properties})
        elif decision=='settlement_residential_surface_not_quarter':
            settlements.append({**original,'properties':{**p,'boundaryKind':'settlement_surface',
                'estimated':False,'canonicalNameIsNeighborhood':False,'usableForAddressAssignment':False,
                'countsTowardQuarterCoverage':False,
                'interpretationStatus':'Actual hamlet/residential surface; not admitted as an urban-quarter boundary.'}})
    metadata={'scope':'Research-only actual source surface proxies; never a primary or estimated-quarter catalogue admission.',
              'method':'Normalized same-name or explicit-alias quarter label inside the actual source surface and canonical municipality, or a normalized same-name municipal reference; original geometry copied unchanged.',
              'quarterCoverageCredit':0,'geometryChanged':False,'newEdgesGenerated':False}
    write(output/'landuse-proxies.geojson',{'type':'FeatureCollection','metadata':metadata,'features':proxies})
    write(output/'settlement-surfaces.geojson',{'type':'FeatureCollection','metadata':{'scope':'Non-quarter settlement surface research only','quarterCoverageCredit':0},'features':settlements})
    from shapely.geometry import shape
    reread=json.loads((output/'landuse-proxies.geojson').read_text())['features']
    originals={f['id']:f for f in document['features']}
    same_geometry=all(encode(f['geometry'])==encode(originals[f['id']]['geometry']) for f in reread)
    valid=all(shape(f['geometry']).is_valid and not shape(f['geometry']).is_empty for f in reread)
    disabled=all(f['properties']['boundaryKind']=='landuse_proxy' and f['properties']['estimated'] is True
                 and f['properties']['canonicalNameIsNeighborhood'] is False
                 and f['properties']['usableForAddressAssignment'] is False for f in reread)
    hotel_absent=all(f['properties']['source']['tags'].get('tourism') not in {'hotel','guest_house','motel','resort','hostel','camp_site'} for f in reread)
    if not(same_geometry and valid and disabled and hotel_absent):
        raise ValueError('Research proxy readback/semantic safeguards failed')
    write(output/'proxy-validation.json',{'schemaVersion':1,'proxyFeatureCount':len(reread),
        'municipalities':sorted({f['properties']['municipality'] for f in reread}),
        'sourceAreaSha256':country.file_hash(output/'source-areas.geojson'),
        'proxyLayerSha256':country.file_hash(output/'landuse-proxies.geojson'),
        'allOriginalGeometriesUnchanged':same_geometry,'allGeometriesValid':valid,
        'allQuarterAdmissionAndAddressAssignmentDisabled':disabled,'commercialTourismExcluded':hotel_absent,
        'featuresWithCorroboratingQuarterLabel':sum(bool(f['properties']['matchingQuarterLabels']) for f in reread),
        'municipalReferenceOnlyFeatures':sum(not f['properties']['matchingQuarterLabels'] and bool(f['properties']['matchingMunicipalReferences']) for f in reread),
        'quarterCoverageCredit':0})
    return {'landuseProxyFeatures':len(proxies),'landuseProxyMunicipalities':len({f['properties']['municipality'] for f in proxies}),
            'settlementSurfaceFeatures':len(settlements),'newPrimaryQuarterBoundaries':0}


def scan(pbf, output, geometries):
    import osmium
    from shapely import from_wkb
    from shapely.geometry import Point, mapping, shape
    from shapely.strtree import STRtree
    pbf_sha=country.file_hash(pbf)
    country_manifest=json.loads((SOURCE/'manifest.json').read_text())
    if pbf_sha!=country_manifest['input']['sha256']:
        raise ValueError('PBF differs from the preserved municipality/label snapshot')
    start=time.monotonic(); records={}; polygons={}; rejected=[]; stats=Counter(); factory=osmium.geom.WKBFactory()
    with osmium.io.Reader(str(pbf), osmium.osm.osm_entity_bits.NOTHING) as reader:
        header=reader.header(); snapshot=header.get('osmosis_replication_timestamp')
    class Collector(osmium.SimpleHandler):
        def way(self, obj):
            stats['nativeFilteredWays']+=1
            tags=dict(obj.tags); kind=extra_kind(tags)
            if kind:
                record=country.source_record(obj,'way');record['extraClassification']=kind
                record['sourceClosedWay']=obj.is_closed()
                records['osm:way:'+str(obj.id)]=record
        def relation(self,obj):
            stats['nativeFilteredRelations']+=1
            tags=dict(obj.tags);kind=extra_kind(tags)
            if kind:
                record=country.source_record(obj,'relation');record['extraClassification']=kind
                records['osm:relation:'+str(obj.id)]=record
    if geometries:
        class Areas(Collector):
            def area(self,obj):
                tags=dict(obj.tags); kind=extra_kind(tags)
                if not kind:return
                ident='osm:'+('way' if obj.from_way() else 'relation')+':'+str(obj.orig_id())
                stats['selectedAssembledAreas']+=1
                try:
                    g=from_wkb(bytes.fromhex(factory.create_multipolygon(obj)))
                    if g.is_empty or not g.is_valid or g.geom_type not in {'Polygon','MultiPolygon'}:
                        raise ValueError('invalid_original_area')
                    polygons[ident]=g
                except (RuntimeError,ValueError) as error:
                    rejected.append({'id':ident,'reason':str(error)[:120]})
        with tempfile.TemporaryDirectory(prefix='extra-areas-index-') as temporary:
            Areas().apply_file(str(pbf),locations=True,idx='sparse_file_array,'+str(Path(temporary)/'nodes.idx'),
                               filters=[osmium.filter.KeyFilter('place','boundary','admin_level','landuse','residential')])
    else:
        Collector().apply_file(str(pbf),filters=[osmium.filter.KeyFilter('place','boundary','admin_level','landuse','residential')])
    print(json.dumps({'sourceRecords':len(records),'assembledGeometries':len(polygons),'elapsedSeconds':round(time.monotonic()-start,2)},ensure_ascii=False),flush=True)
    output.mkdir(parents=True,exist_ok=True)
    source={'provider':'openstreetmap','pbfSha256':pbf_sha,'osmTimestamp':snapshot,
            'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}
    inventory={'schemaVersion':1,'source':source,'scope':'Named alternative area tags omitted by the primary selector; includes non-quarter surface proxies.',
               'geometryAssemblyAttempted':geometries,
               'counts':dict(stats),'recordsByClassification':dict(Counter(r['extraClassification'] for r in records.values())),
               'records':[{'id':ident,**r,'geometryAssembled':ident in polygons} for ident,r in sorted(records.items())]}
    write(output/('inventory.json' if geometries else 'tag-inventory.json'),inventory)
    if not geometries:return
    mun_doc,mun_input=load_geo('municipalities.geojson');node_doc,node_input=load_geo('named-nodes.geojson')
    municipalities=[f for f in mun_doc['features'] if f['properties'].get('usedForAssociation')]
    m_shapes=[shape(f['geometry']) for f in municipalities];m_index=STRtree(m_shapes)
    nodes=node_doc['features'];n_shapes=[shape(f['geometry']) for f in nodes];n_index=STRtree(n_shapes)
    references=json.loads((ROOT/'data/neighborhoods/nationwide-inventory.json').read_text())
    refs={r['municipality']:r['nameReferences'] for r in references['municipalities']}
    main=json.loads((ROOT/'data/neighborhoods/neighborhoods.geojson').read_text())
    existing={(f['properties']['municipality'],normalized(f['properties']['name'])) for f in main['features']}
    features=[];audits=[];recommendations=Counter()
    for ident,r in sorted(records.items()):
        if ident not in polygons:
            rejected.append({'id':ident,'reason':'no_original_closed_area_assembled','extraClassification':r['extraClassification']});continue
        g=polygons[ident];name=country.display_name(r['tags']);key=normalized(name)
        covering=[int(i) for i in m_index.query(g) if m_shapes[int(i)].covers(g)]
        city=municipalities[covering[0]]['properties']['name'] if len(covering)==1 else None
        matching=[]
        for i in n_index.query(g):
            f=nodes[int(i)];p=f['properties'];tags=p['source']['tags']
            aliases=[p.get('name',''),tags.get('official_name','')]+tags.get('alt_name','').split(';')
            if key not in {normalized(x) for x in aliases}:continue
            if not g.covers(n_shapes[int(i)]):continue
            if city and p.get('municipality')!=city:continue
            matching.append({'id':f['id'],'name':p['name'],'place':tags.get('place'),'municipality':p.get('municipality'),
                             'coordinates':f['geometry']['coordinates'],'exactNameOrExplicitAlias':True})
        matched_refs=[]
        for ref in refs.get(city,[]):
            for ref_name in ref.get('names',[]):
                if key==normalized(ref_name):
                    matched_refs.append({'referenceId':ref['id'],'name':ref_name,'category':ref['category'],
                                         'sourceUrl':ref['sourceUrl'],'sourceIsOfficial':ref.get('sourceIsOfficial',False)})
        kind=r['extraClassification']; recommendation='other_local_area_only'
        if city is None: recommendation='unresolved_municipality'
        elif key==normalized(city):recommendation='whole_settlement_not_quarter'
        elif (city,key) in existing:recommendation='name_already_has_primary_polygon'
        elif r['tags'].get('tourism') in {'hotel','guest_house','motel','resort','hostel','camp_site'}:
            recommendation='commercial_tourism_surface_not_quarter'
        elif kind.startswith(('landuse_proxy','residential_proxy')):
            recommendation='corroborated_landuse_proxy_only' if matching or matched_refs else 'unconfirmed_landuse_proxy'
        elif kind in {'explicit_nonstandard_quarter_boundary','other_place_boundary'} or kind.startswith(('administrative_level_','other_urban_place_')):
            recommendation='explicit_boundary_with_quarter_name_evidence_review' if matching or matched_refs else 'boundary_name_semantics_unconfirmed'
        elif matching and any(ref['category']=='urban_neighborhood' for ref in matched_refs):
            recommendation='locality_surface_with_municipal_quarter_reference_review'
        elif matching and r['tags'].get('landuse') in {'residential','allotments'}:
            recommendation='settlement_residential_surface_not_quarter'
        elif matching:recommendation='locality_surface_with_quarter_label_review'
        elif matched_refs:recommendation='locality_surface_with_reference_review'
        recommendations[recommendation]+=1
        geometry=mapping(g)
        properties={'name':name,'municipality':city,'extraClassification':kind,'recommendation':recommendation,
                    'matchingQuarterLabels':matching,'matchingMunicipalReferences':matched_refs,
                    'estimated':kind.startswith(('landuse_proxy','residential_proxy')),'boundaryKind':'research_source_area',
                    'canonicalNameIsNeighborhood':False,'sourceIsOfficial':False,'usableForAddressAssignment':False,
                    'geometryVerificationStatus':'actual_original_osm_area_unreviewed_semantics',
                    'source':{**r,**source,'geometryProcessing':'Actual libosmium original-member ring assembly; no clipping, repair, buffer, snapping, simplification, invented closure or inferred geometry.'}}
        features.append({'type':'Feature','id':ident,'properties':properties,'geometry':geometry})
        audits.append({'id':ident,'name':name,'municipality':city,'extraClassification':kind,'recommendation':recommendation,
                       'matchingQuarterLabels':matching,'matchingMunicipalReferences':matched_refs,
                       'coordinatesUnmodified':True})
    document={'type':'FeatureCollection','features':features}
    write(output/'source-areas.geojson',document)
    research_layers=write_research_layers(output,document)
    write(output/'audit.json',{'schemaVersion':1,'recommendations':dict(recommendations),'records':audits,'rejected':rejected,
                             'limitations':['These are actual source surface outlines, not verified quarter boundaries.','Residential land-use is always proxy-only even when a same-name label exists.','No catalogue or registry is changed.']})
    files=[{'file':p.name,'bytes':p.stat().st_size,'sha256':country.file_hash(p)} for p in sorted(output.glob('*')) if p.is_file() and p.name!='manifest.json']
    manifest={'schemaVersion':1,'scope':'Alternative OSM source-area audit; not a released quarter layer','generatedAt':datetime.now(timezone.utc).isoformat(),
              'source':source,'inputs':[mun_input,node_input], 'sourceRecords':len(records),'actualValidAreas':len(features),
              'recommendations':dict(recommendations),'researchLayers':research_layers,'files':files,'scriptSha256':country.file_hash(Path(__file__)),
              'allSourceGeometriesPreserved':True,'allUsableForAddressAssignment':False}
    write(output/'manifest.json',manifest)
    print(json.dumps({'features':len(features),'recommendations':dict(recommendations)},ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,default=PBF);p.add_argument('--output',type=Path,default=OUT);p.add_argument('--scan-only',action='store_true');a=p.parse_args()
    scan(a.input,a.output,not a.scan_only)
if __name__=='__main__':main()
