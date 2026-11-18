#!/usr/bin/env python3
"""Independent typed-ID PBF readback and exact same-city/name-evidence audit."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import unicodedata

os.environ['PROJ_NETWORK'] = 'OFF'
import osmium
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, shape

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'data/neighborhoods'
RESEARCH = BASE/'research'
PBF = ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
EVIDENCE = RESEARCH/'pecs-current-name-osm-evidence.json'
CITY = BASE/'sources/municipal-pecs-grounded-next/source-municipality.geojson'
CITY_PROOF = BASE/'sources/municipal-pecs-grounded-next/boundary-source-proof.json'
COHORT = BASE/'sources/municipal-pecs-final-gaps-review/source-coverage-accounting.json'
NODE_ARCHIVE = BASE/'sources/country-osm/named-nodes.geojson.gz'
OUTPUT = RESEARCH/'pecs-current-name-independent-osm-review.json'
FIELDS = ['name','name:hu','official_name','short_name','loc_name','alt_name','old_name','was:name']
ALIASES = {'short_name','loc_name','alt_name','old_name','was:name'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFD',value.casefold()) if c.isalnum())


def join_original_rings(ways):
    remaining = [list(v) for v in ways]
    result = []
    while remaining:
        ring = remaining.pop(0)
        while ring[0] != ring[-1]:
            options = [(i,v if v[0]==ring[-1] else list(reversed(v)))
                       for i,v in enumerate(remaining) if v[0]==ring[-1] or v[-1]==ring[-1]]
            assert len(options)==1
            i,next_part = options[0]
            remaining.pop(i)
            ring.extend(next_part[1:])
        result.append(ring)
    return result


def build():
    data = json.loads(EVIDENCE.read_text())
    city_feature = json.loads(CITY.read_text())
    city_proof = json.loads(CITY_PROOF.read_text())
    source_names = [r['sourceName'] for r in json.loads(COHORT.read_text())['records']]
    assert len(source_names)==len(set(source_names))==67
    assert data['sourceNames']==source_names
    wanted = {norm(v):v for v in source_names}
    assert len(wanted)==67
    assert sha(PBF)==data['pbf']['sha256']==city_proof['sourcePbfSha256']=='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
    assert sha(CITY)==data['municipalityGeometryReference']['sha256']=='f88ce9a098698c26775574013b687dc1e1a15b0b4a3f5c40ff7ec1fceeb3a305'
    original = data['sameCityObjects']
    assert len(original)==135
    requested = {(r['osmType'],r['osmId']) for r in original}
    expected_ways = {('way',r['osmId']):r for r in original if r['osmType']=='way'}
    expected_nodes = {('node',r['osmId']):r for r in original if r['osmType']=='node'}
    for r in original:
        for w in r.get('originalMemberWays',[]):
            expected_ways[('way',w['osmId'])]=w
        for n in r.get('originalMemberNodes',[]):
            expected_nodes[('node',n['osmId'])]=n
        requested.update((m['type'],m['ref']) for m in r.get('members',[]))
    requested.update(expected_ways)
    requested.update(expected_nodes)
    requested.update(('node',v) for w in expected_ways.values() for v in w['nodeRefs'])
    requested.add(('relation',575380))
    requested.update(('way',w['osmWayId']) for w in city_proof['rawMemberWays'])
    requested.update(('node',n['osmNodeId']) for n in city_proof['rawBoundaryNodes'])
    raw = {}
    numeric_ids = {key[1] for key in requested}
    for obj in osmium.FileProcessor(str(PBF)).with_filter(osmium.filter.IdFilter(numeric_ids)):
        typ = 'node' if isinstance(obj,osmium.osm.Node) else 'way' if isinstance(obj,osmium.osm.Way) else 'relation' if isinstance(obj,osmium.osm.Relation) else None
        key = (typ,obj.id)
        if key not in requested:
            continue
        record = {'osmType':typ,'osmId':obj.id,'objectVersion':obj.version,'objectTimestamp':str(obj.timestamp),'tags':dict(obj.tags)}
        if typ=='node':
            assert obj.location.valid()
            record['coordinates']=[obj.lon,obj.lat]
        elif typ=='way':
            record['nodeRefs']=[v.ref for v in obj.nodes]
        else:
            record['members']=[{'type':{'n':'node','w':'way','r':'relation'}.get(v.type,v.type),'ref':v.ref,'role':v.role} for v in obj.members]
        raw[key]=record
    assert requested==set(raw), sorted(requested-set(raw))

    def metadata_equal(expected,actual):
        assert expected['objectVersion']==actual['objectVersion']
        assert expected['objectTimestamp']==actual['objectTimestamp']
        if 'tags' in expected:
            assert expected['tags']==actual['tags']
        if 'nodeRefs' in expected:
            assert expected['nodeRefs']==actual['nodeRefs']
        if 'coordinates' in expected:
            assert expected['coordinates']==actual['coordinates']
        if 'members' in expected:
            assert expected['members']==actual['members']

    for key,expected in list(expected_nodes.items())+list(expected_ways.items()):
        metadata_equal(expected,raw[key])
    city_rel = raw[('relation',575380)]
    cp = city_proof['sourceRelation']
    assert city_rel['members']==cp['members'] and city_rel['tags']==cp['tags']
    assert city_rel['objectVersion']==cp['version'] and city_rel['objectTimestamp']==cp['timestamp']
    for w in city_proof['rawMemberWays']:
        actual = raw[('way',w['osmWayId'])]
        assert actual['nodeRefs']==w['nodeRefs'] and actual['tags']==w['tags']
        assert actual['objectVersion']==w['version'] and actual['objectTimestamp']==w['timestamp']
    for n in city_proof['rawBoundaryNodes']:
        actual = raw[('node',n['osmNodeId'])]
        assert actual['coordinates']==n['coordinates'] and actual['objectVersion']==n['version'] and actual['objectTimestamp']==n['timestamp']

    def coordinates(refs):
        return [raw[('node',n)]['coordinates'] for n in refs]

    boundary_rings = join_original_rings([raw[('way',m['ref'])]['nodeRefs'] for m in city_rel['members'] if m['type']=='way' and m['role']=='outer'])
    assert len(boundary_rings)==1
    raw_city = Polygon(coordinates(boundary_rings[0]))
    city = shape(city_feature['geometry'])
    assert raw_city.is_valid and raw_city.equals(city)

    def geometry(record):
        typ = record['osmType']
        if typ=='node':
            return Point(record['coordinates'])
        if typ=='way':
            refs=record['nodeRefs']
            cs=coordinates(refs)
            if refs[0]==refs[-1] and len(cs)>3:
                area=Polygon(cs)
                assert area.is_valid, ('invalid_closed_named_way',record['osmId'])
                return area
            return LineString(cs)
        assert record['tags'].get('type') in ('multipolygon','boundary')
        assert all(m['type']=='way' for m in record['members'])
        assert all(m['role'] in ('','outer','inner') for m in record['members'])
        outs=join_original_rings([raw[('way',m['ref'])]['nodeRefs'] for m in record['members'] if m['role'] in ('','outer')])
        ins=join_original_rings([raw[('way',m['ref'])]['nodeRefs'] for m in record['members'] if m['role']=='inner'])
        outer_polys=[Polygon(coordinates(r)) for r in outs]
        inner_polys=[Polygon(coordinates(r)) for r in ins]
        assert all(v.is_valid for v in outer_polys+inner_polys)
        assert all(sum(o.contains(i) for o in outer_polys)==1 for i in inner_polys)
        polys=[Polygon(o.exterior.coords,[i.exterior.coords for i in inner_polys if o.contains(i)]) for o in outer_polys]
        result=polys[0] if len(polys)==1 else MultiPolygon(polys)
        assert result.is_valid
        return result

    def name_matches(tags):
        result=[]
        for key in FIELDS:
            if key not in tags:
                continue
            tokens=tags[key].split(';') if key in ALIASES else [tags[key]]
            for token in tokens:
                token=token.strip()
                if norm(token) not in wanted:
                    continue
                name=wanted[norm(token)]
                role='historical_name_only' if key in ('old_name','was:name') else 'explicit_current_alias_tag' if key in ALIASES else 'current_name_tag'
                result.append({'sourceName':name,'tagKey':key,'literalTagValue':tags[key],'matchedLiteralToken':token,'matchType':'literal_exact' if token==name else 'orthographic_normalized_exact','role':role})
        return result

    archive_bytes=gzip.decompress(NODE_ARCHIVE.read_bytes())
    archive=json.loads(archive_bytes)
    archive_by_id={f['properties']['source']['osmId']:f for f in archive['features']}
    records=[]
    historical=[]
    archive_checks=[]
    for expected in original:
        key=(expected['osmType'],expected['osmId'])
        record=raw[key]
        metadata_equal(expected,record)
        matches=name_matches(record['tags'])
        assert matches==expected['nameMatches']
        assert city.covers(geometry(record))
        assert expected['sameCityAssociation']['completeObjectGeometryCovered'] is True
        category=expected['evidenceCategory']
        if record['tags'].get('highway')=='bus_stop':
            assert category=='transport_stop_name_only'
        if category=='place_or_quarter_label':
            assert record['tags'].get('place') in ('suburb','quarter','neighbourhood')
            assert record['osmType']=='node'
            saved=archive_by_id[record['osmId']]
            ss=saved['properties']['source']
            assert ss['tags']==record['tags'] and ss['objectVersion']==record['objectVersion'] and ss['objectTimestamp']==record['objectTimestamp']
            assert saved['geometry']['coordinates']==record['coordinates']
            assert ss['pbfSha256']==data['pbf']['sha256']
            assert saved['properties']['municipality']=='Pécs'
            assert saved['properties']['municipalityOsmId']=='osm:relation:575380'
            archive_checks.append(record['osmId'])
        current=[v for v in matches if v['role']!='historical_name_only']
        old=[v for v in matches if v['role']=='historical_name_only']
        if old:
            historical.append({'osmType':key[0],'osmId':key[1],'currentOsmName':record['tags'].get('name'),'historicalMatches':old,'countsAsCurrentNameSupportForTheseMatches':False})
        records.append({'osmType':key[0],'osmId':key[1],'originalObjectVersion':record['objectVersion'],'originalObjectTimestamp':record['objectTimestamp'],'originalTagsSha256':digest(record['tags']),'allOriginalTagsExactlyMatch':True,'originalNodeCoordinatesOrRefsAndMembersExactlyMatch':True,'completeGeometryIndependentlyReconstructedFromFreshPbfReferences':True,'freshGeometryFullyCoveredByFreshPecsMunicipality':True,'evidenceCategory':category,'currentNameMatches':current,'historicalOnlyMatches':old,'quarterNameSupportCategory':category=='place_or_quarter_label','streetStopPoiOrLanduseDoesNotBecomeQuarterGeometry':True})
        if key[0]=='way':
            assert expected['originalNodeCoordinates']==coordinates(record['nodeRefs'])
    assert len(archive_checks)==54
    assert all(not r['quarterNameSupportCategory'] for r in records if r['evidenceCategory']!='place_or_quarter_label')
    excluded=data['excludedCandidateEvidence']
    assert all('reason' in r and r['reason'] for r in excluded)
    assert len(excluded)+len(original)==data['candidateCounts']['exactNameCandidatesRead']
    assert data['countryExtractMissingWayRefCountInAllCountryExactCandidates']==5
    assert data['countryExtractMissingNodeRefCountInAllCountryExactCandidates']==1
    return {'schemaVersion':1,'auditDate':'2026-11-14','status':'fresh_typed_id_pbf_metadata_reference_geometry_and_name_roles_pass',
            'scope':'Independent fresh local PBF readback for all135same-city exact-name/explicit-alias objects,complete original node/way/member references,and the Pecs municipality reference. No producer extractor imported or invoked.',
            'inputFingerprints':[{'path':str(q.relative_to(ROOT)),'sha256':sha(q),'bytes':q.stat().st_size} for q in [EVIDENCE,CITY,CITY_PROOF,COHORT,NODE_ARCHIVE]],
            'pbf':data['pbf'],'pbfSha256IndependentlyRecomputed':True,
            'freshReadMethod':'One new osmium.FileProcessor pass with IdFilter over the union of required IDs;retain typed IDs only. No missing coordinate,way,relation or geometry is invented.',
            'freshReadTypedObjectCount':len(raw),'freshReadCounts':dict(Counter(v['osmType'] for v in raw.values())),
            'allRequestedTypedObjectsPresent':True,'freshRawReadbackCanonicalSha256':digest([raw[k] for k in sorted(raw)]),
            'municipalityReview':{'name':'Pécs','relationId':575380,'originalRelationTagsMembersVersionTimeExactlyMatch':True,'originalWayCount':32,'originalBoundaryNodeCount':535,'allOriginalRefsCoordinatesVersionTimeExactlyMatch':True,'freshExactEndpointRingGeometryEqualsArchivedF88Geometry':True,'fullObjectCoverageUsesThisFreshMunicipality':True,'legalOrSurveyBoundaryAccuracyApproved':False},
            'sourceNameCount':67,'matchingReview':{'fullNormalizedStringOnly':True,'normalization':'Unicode NFD/casefold followed by alphanumeric characters;combining diacritics,punctuation and whitespace ignored. No spelling replacement,fuzzy matching,substring,nearest name point or invented alias.','explicitAliasFieldsOnly':list(sorted(ALIASES)),'oldNameAndWasNameNeverCurrentSupport':True},
            'sameCityObjectCount':len(records),'sameCityEvidenceCategoryCounts':dict(Counter(r['evidenceCategory'] for r in records)),
            'records':records,'historicalNameOnlyObjects':historical,
            'earlierNamedNodeArchiveReview':{'path':str(NODE_ARCHIVE.relative_to(ROOT)),'gzipSha256':sha(NODE_ARCHIVE),'uncompressedSha256':hashlib.sha256(archive_bytes).hexdigest(),'matchedPlaceNodeCount':len(archive_checks),'allPlaceTagsCoordinatesVersionTimeAndPecsAssociationExactlyMatchFreshPbf':True,'nodeIds':archive_checks},
            'excludedCountryCandidates':{'count':len(excluded),'authorMissingMemberWayRefCount':5,'authorMissingNodeRefCount':1,'allKeptSameCityObjectsCompleteInFreshRead':True,'excludedObjectsDoNotProvideCurrentPecsSupport':True,'excludedCountryObjectsIndependentlyRescannedByThisAudit':False,'scope':'Fresh PBF pass covers all retained same-city objects and their dependencies;no claim of a second whole-country name-completeness extraction.'},
            'limits':['CurrentOSMplace labels are community name evidence,not an official complete urban-neighbourhood inventory.','A street,bus stop,POI,functional area or historicalold_name match does not become current quarter-name/footprint approval.','Fresh city association confirms complete object geometry inside this PBF municipality;it does not certify legal jurisdiction,source-quarter extent or absolute boundary accuracy.'],
            'producerScriptImportedOrInvoked':False,'newGeometriesOrRegistriesWritten':False,'georeferenceChanged':False,'claimedAbsoluteAccuracy':None,'usableForAddressAssignment':False,'networkUsed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    report=build()
    expected=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.check:
        assert OUTPUT.read_text()==expected
    else:
        OUTPUT.write_text(expected)
    print(json.dumps({'check':args.check,'freshReadCounts':report['freshReadCounts'],'sameCityObjects':135,'placeArchiveMatches':54,'outputSha256':sha(OUTPUT)},ensure_ascii=False))


if __name__=='__main__':
    main()
