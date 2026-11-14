#!/usr/bin/env python3
"""Independent read-only producer audit; writes only independent-audit/review JSON.

Reproduce from project root:
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-szombathely-more/independent-audit.py --check
The already-local original country PBF and municipal PDF are required. No network.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import fitz
import osmium
from pyproj import Geod, Transformer
from shapely.geometry import LineString, shape
from shapely.ops import transform
from shapely.validation import explain_validity

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
GEO_SHA = '2f5286b40b1249281184ed9715c04b583c1de3cc2dbde3bd18a7ccc349501154'
PBF_SHA = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
PDF_SHA = 'aade0d35a60e4ecd230a26c2c7dabcfc26ec76466ab86310e6828f34db714500'
QA_FILENAMES = {'independent-audit.py', 'independent-audit.json', 'independent-review.json'}
MAINTENANCE = {
    'date': '2026-11-14',
    'by': 'producer agent, explicitly requested by root after independent geometry QA',
    'scope': 'Reproduction bookkeeping only: replace recursive final-manifest byte hash with a sorted producer path/SHA256 logical fingerprint. Original independent geometry/source checks and producer coordinates unchanged.',
    'originalIndependentGeometryReviewRetained': True,
    'freshIndependentReviewOfThisBookkeepingEditClaimed': False
}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(name):
    return json.loads((OUT/name).read_text())


def normalized_edge(a, b):
    return tuple(sorted((tuple(a), tuple(b))))


def polygon_rings(geometry):
    return geometry['coordinates'] if geometry['type'] == 'Polygon' else [r for p in geometry['coordinates'] for r in p]


def audit():
    manifest = read('manifest.json')
    producer_rows = [row for row in manifest['files'] if Path(row['path']).name not in QA_FILENAMES]
    frozen = {row['path']: row['sha256'] for row in producer_rows}
    frozen[manifest['converter']['path']] = manifest['converter']['sha256']
    logical_inputs = [{'path': name, 'sha256': expected} for name, expected in sorted(frozen.items())]
    logical_fingerprint = hashlib.sha256(json.dumps(logical_inputs, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    pre_qa_manifest_sha = manifest['reviewedPreQaManifestSha256']
    for name, expected in frozen.items():
        assert sha(ROOT/name) == expected, ('Changed producer artifact', name)
    for row in producer_rows:
        assert (ROOT/row['path']).stat().st_size == row['bytes']
    assert sha(OUT/'joskar-ola-inferred.geojson') == GEO_SHA
    current = read('existing-joskar-snapshot.geojson')['features'][0]
    inputs = read('source-ways.geojson')['features']
    expected = {f['properties']['source']['osmId']: f for f in inputs}
    current_source = current['properties']['source']
    current_member_ids = {m['ref'] for m in current_source['members'] if m['type']=='way' and m['role'] in ('outer','inner','')}
    all_ids = set(expected) | current_member_ids | {8356511}
    actual, found_relations = {}, {}
    pbf = ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
    assert sha(pbf) == PBF_SHA

    class Original(osmium.SimpleHandler):
        def way(self, w):
            if w.id not in expected and w.id not in current_member_ids:
                return
            assert all(n.location.valid() for n in w.nodes)
            actual[w.id] = {'nodeRefs':[n.ref for n in w.nodes],
                'coordinates':[[n.lon,n.lat] for n in w.nodes], 'tags':dict(w.tags),
                'objectVersion':w.version, 'objectTimestamp':str(w.timestamp)}
        def relation(self, r):
            if r.id == 8356511:
                found_relations[r.id] = {'tags':dict(r.tags), 'objectVersion':r.version,
                    'objectTimestamp':str(r.timestamp),
                    'members':[{'type':{'n':'node','w':'way','r':'relation'}[m.type],
                                'ref':m.ref,'role':m.role} for m in r.members]}

    with tempfile.TemporaryDirectory(prefix='independent-szombathely-pbf-') as temp:
        Original().apply_file(str(pbf), locations=True,
            idx='sparse_file_array,' + str(Path(temp)/'nodes.idx'),
            filters=[osmium.filter.IdFilter(all_ids)])
    assert set(expected) | current_member_ids <= set(actual)
    for wid, feature in expected.items():
        source=feature['properties']['source']; raw=actual[wid]
        assert raw['coordinates'] == feature['geometry']['coordinates'], ('Coordinates differ',wid)
        for key in ['nodeRefs','tags','objectVersion','objectTimestamp']:
            assert raw[key] == source[key], (key,wid)
    relation = found_relations[8356511]
    assert all(relation[k] == current_source[k] for k in relation)
    # Recheck existing-quarter snapshot edges against actual relation member ways.
    current_edge_set = {normalized_edge(a,b) for wid in current_member_ids
        for a,b in zip(actual[wid]['coordinates'],actual[wid]['coordinates'][1:])}
    current_edges = [(a,b) for ring in polygon_rings(current['geometry']) for a,b in zip(ring,ring[1:])]
    assert all(normalized_edge(a,b) in current_edge_set for a,b in current_edges)

    owners=defaultdict(list); node_coords={}
    for wid in expected:
        raw=actual[wid]
        for ref,coord in zip(raw['nodeRefs'],raw['coordinates']):
            assert ref not in node_coords or node_coords[ref] == coord
            node_coords[ref]=coord
        for a,b,na,nb in zip(raw['coordinates'],raw['coordinates'][1:],raw['nodeRefs'],raw['nodeRefs'][1:]):
            owners[normalized_edge(a,b)].append((wid,na,nb,a,b))
    feature=read('joskar-ola-inferred.geojson')['features'][0]
    ring=feature['geometry']['coordinates'][0]; geom=shape(feature['geometry']);props=feature['properties']
    assert ring[0] == ring[-1] and len(ring)==80
    assert len(set(map(tuple,ring[:-1])))==79
    assert geom.is_valid and geom.exterior.is_simple and not geom.interiors, explain_validity(geom)
    proof=read('conversion-proof.json'); ids=proof['nodeIdsInCircuit']
    assert ring == [node_coords[n] for n in ids]
    rows=[];used=set(); geod=Geod(ellps='WGS84')
    for i,(a,b,na,nb) in enumerate(zip(ring,ring[1:],ids,ids[1:])):
        matches=[m for m in owners[normalized_edge(a,b)] if {m[1],m[2]} == {na,nb}]
        assert len(matches)==1, ('Not a unique original OSM node edge',i)
        wid=matches[0][0]; used.add(wid); tags=actual[wid]['tags']
        assert tags.get('highway') not in ('proposed','construction')
        name=tags.get('name',''); inferred = wid==112539408
        assert inferred or name in {'Szent Márton utca','Barátság utca','Mikes Kelemen utca','Károlyi Antal utca','Hunyadi János út'}
        rows.append({'edgeIndex':i,'sourceWayId':wid,'nodeRefs':[na,nb],
            'lengthMetres':geod.inv(*a,*b)[2], 'roadName':name,'boundaryRoleUnproven':inferred})
    assert len(used)==35
    comp=read('inferred-completion.geojson')['features'][0]
    comp_coords=comp['geometry']['coordinates']; comp_refs=comp['properties']['nodeIds']
    assert comp_coords == [node_coords[n] for n in comp_refs]
    inferred_edges=[r for r in rows if r['boundaryRoleUnproven']]
    assert len(inferred_edges)==2
    assert len(comp_coords)==3 and comp['properties']['sourceWayId']==112539408
    assert {tuple(r['nodeRefs']) for r in inferred_edges} == set(zip(comp_refs,comp_refs[1:]))
    comp_len=sum(r['lengthMetres'] for r in inferred_edges)
    assert abs(comp_len-42.5669013906784)<1e-8
    assert actual[112539408]['tags'].get('name') is None
    assert actual[112539408]['tags']['highway']=='residential'
    assert not LineString(ring[:30]).is_ring
    # Independent alternate ring, edge membership, topology and area comparison.
    alternate=read('junction-alternative.geojson')['features'][0]
    alt_geom=shape(alternate['geometry']);alt_ring=alternate['geometry']['coordinates'][0]
    assert alt_geom.is_valid and alt_geom.exterior.is_simple and alt_ring[0]==alt_ring[-1]
    assert all(normalized_edge(a,b) in owners for a,b in zip(alt_ring,alt_ring[1:]))
    project=Transformer.from_crs(4326,23700,always_xy=True).transform
    delta=transform(project,geom.symmetric_difference(alt_geom)).area
    assert abs(delta-proof['junctionChoice']['symmetricDifferenceM2EPSG23700'])<1e-7
    assert tuple(node_coords[5324294304])==tuple(ring[0])
    assert tuple(node_coords[5324469828])==tuple(alt_ring[0])
    assert delta>0 and alternate['properties']['notAdditionalCoverage']
    parent=shape(read('municipality.geojson')['features'][0]['geometry']);old=shape(current['geometry'])
    assert parent.covers(geom)
    overlap=transform(project,geom.intersection(old)).area/transform(project,geom.union(old)).area
    assert abs(overlap-proof['existingQuarterComparison']['intersectionOverUnionEPSG23700'])<1e-12
    assert current['id']=='osm:relation:8356511' and current['properties']['name']==props['name']
    assert props['boundaryKind']=='inferred_area' and props['estimated'] and not props['canonicalNameIsNeighborhood']
    assert not props['usableForAddressAssignment'] and props['claimedAbsoluteAccuracyMetres'] is None
    assert not props['newDistinctQuarterCoverage']
    assert not read('inferred-registry-entry.json')['newDistinctQuarterCoverage']
    area,perimeter=geod.geometry_area_perimeter(geom)
    assert abs(abs(area)-296658.87809125055)<1e-6
    assert abs(perimeter-2526.2804259590694)<1e-7
    # Original municipal pages, not only factual transcription or producer claims.
    facts=read('source-facts.json');pdf_path=ROOT/facts['originalSourceFileLocal']
    assert sha(pdf_path)==PDF_SHA
    original=fitz.open(pdf_path);excerpt=fitz.open(OUT/'source-proof-pages.pdf')
    assert len(original)==179 and len(excerpt)==4
    page_checks=[]
    for i,n in enumerate([49,50,150,151]):
        assert original[n-1].get_text()==excerpt[i].get_text()
        a=original[n-1].get_pixmap();b=excerpt[i].get_pixmap()
        assert a.samples==b.samples and (a.width,a.height)==(b.width,b.height)
        page_checks.append({'originalPdfPageOneBased':n,'excerptPdfPageOneBased':i+1,
            'textExactlyMatches':True,'renderSamplesExactlyMatch':True,
            'renderSamplesSha256':hashlib.sha256(a.samples).hexdigest()})
    assert original.extract_image(282)['image']==(OUT/'source-overview.jpeg').read_bytes()
    text=original[149].get_text()
    assert all(t in text for t in ['Joskar-Ola','Barátság','Hunyadi','Károlyi'])
    cov=read('coverage-audit.json')
    assert len(cov['units'])==18 and sorted(u['sourceId'] for u in cov['units'])==list(range(1,19))
    assert cov['newDistinctQuarterNamesAdded']==0 and cov['newPrimaryPolygons']==0
    assert cov['sourceUnitExactLabelsStillMissing']==[2,10,16]
    run=subprocess.run(['python3','scripts/neighborhoods/derive-szombathely-more.py','--check'],
        cwd=ROOT,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    js="import fs from 'node:fs';import {validateGeometry} from './scripts/neighborhoods/build.mjs';const names=['joskar-ola-inferred.geojson','junction-alternative.geojson'];console.log(JSON.stringify(names.map(name=>({name,...validateGeometry(JSON.parse(fs.readFileSync('data/neighborhoods/sources/municipal-szombathely-more/'+name,'utf8')).features[0].geometry)}))));"
    command=subprocess.run(['node','--input-type=module','-e',js],cwd=ROOT,capture_output=True,text=True)
    assert command.returncode==0,command.stderr
    strict=json.loads(command.stdout);assert all(r['valid'] for r in strict)
    # No producer byte may change during an audit.
    assert all(sha(ROOT/n)==h for n,h in frozen.items())
    result={'schemaVersion':1,'auditDate':'2026-11-14','reviewer':'independent gyongyos_source_expand agent',
        'result':'pass_inferred_historical_alternative_only','geojsonSha256':GEO_SHA,
        'auditScriptSha256':sha(Path(__file__)),
        'producerInputFingerprintSha256':logical_fingerprint,
        'producerInputFingerprintDefinition':'SHA256 of UTF-8 JSON compact sorted path/SHA256 objects, including producer converter; excludes only the three QA files and manifest-wrapper metadata.',
        'producerInputFingerprints':logical_inputs,
        'reviewedPreQaManifestSha256':pre_qa_manifest_sha,
        'reproductionMetadataMaintenance':MAINTENANCE,
        'originalPbfSha256':PBF_SHA,'originalPdfSha256':PDF_SHA,
        'checkedCompleteArchivedWays':len(expected),'completeWayMetadataAndCoordinatesMatchedPbf':True,
        'originalRelation8356511MetadataAndMemberWaysMatched':True,
        'existingSnapshotEdgesMatchedOriginalRelationMemberNodePairs':len(current_edges),
        'boundaryCoordinatesIncludingClosure':len(ring),'boundaryOriginalNodeEdges':len(rows),
        'usedOriginalWays':len(used),'allEdgesAreConsecutiveOriginalPbfNodes':True,
        'syntheticVertices':0,'syntheticEdges':0,'clippingOrRepair':False,
        'geosValid':geom.is_valid,'strictExistingJsValidator':strict,'holes':0,
        'insideArchivedMunicipality':True,'areaM2':abs(area),'perimeterMetres':perimeter,
        'explicitUnprovenBoundaryCompletion':{'sourceWayId':112539408,'roadName':None,
            'actualHighway':'residential','originalNodeEdges':2,'lengthMetres':comp_len,
            'sourceBoundaryRoleNotEstablished':True},
        'junctionAlternative':{'selectedNode':5324294304,'alternativeNode':5324469828,
            'validAndEveryEdgeOriginal':True,'symmetricDifferenceM2EPSG23700':delta,
            'sourceDoesNotResolveChoice':True,'notAdditionalCoverage':True},
        'existingQuarterComparison':{'sourceId':current['id'],'name':current['properties']['name'],
            'intersectionOverUnionEPSG23700':overlap,'newDistinctQuarterNames':0,
            'newPrimaryFeatures':0,'historicalEstimatedAlternatives':1},
        'originalSourcePages':page_checks,'overviewExactlyOriginalXref282':True,
        'sourceSemantics':{'municipalTextExplicitlyNamesQuarterBoundary':True,
            'originalPdfPageOneBased':150,'proofPageOneBased':3,
            'namedCircuit':['Szent Márton','Barátság','Mikes Kelemen (vasúti sínek mellett végig)','Károlyi Antal','Hunyadi János','Szent Márton'],
            'unnamedCompletionAndCarriagewayChoiceNotProvenByText':True,
            'railwaySideClauseDoesNotProveCadastralRailOwnershipLine':True,
            'coverageUnitsChecked':18,'nameCorrespondenceDoesNotProveWholeBoundaryCoverage':True,
            'exactLabelUnresolvedUnits':[2,10,16]},
        'producerConverterCheckPassed':True,'producerManifestEntriesVerified':len(producer_rows),
        'producerArtifactsUnchanged':True,'networkUsed':False,
        'primaryAdmissionApproved':False,'usableForAddressAssignment':False,
        'claimedAbsoluteAccuracyMetres':None,'boundaryEdges':rows}
    review={'schemaVersion':1,'reviewDate':'2026-11-14','reviewer':result['reviewer'],
        'result':result['result'],'scope':'Independent original municipal PDF/page/image identity, full original-country-PBF way/edge audit, source semantics, alternative-junction and existing-quarter overlap validation. Producer code/geometry unchanged.',
        'geojsonSha256':GEO_SHA,
        'producerInputFingerprintSha256':logical_fingerprint,
        'reviewedPreQaManifestSha256':pre_qa_manifest_sha,
        'reproductionMetadataMaintenance':MAINTENANCE,
        'auditScriptPath':str(Path(__file__).relative_to(ROOT)),
        'auditScriptSha256':result['auditScriptSha256'],
        'auditDetailsPath':str((OUT/'independent-audit.json').relative_to(ROOT)),
        'originalPbfReprocessed':True,'completeArchivedWaysChecked':len(expected),
        'literalOriginalNodeBoundaryEdges':79,'strictJsValidatorPassed':True,
        'primaryAdmissionApproved':False,'inferredCandidateCountApproved':1,
        'newDistinctQuarterCoverageApproved':0,'sourceQuarterNameAuthentic':True,
        'sourceBoundaryRoleUnverifiedLengthMetres':comp_len,
        'junctionAlternativeAreaDifferenceM2':delta,
        'existingJoskar8356511IoU':overlap,
        'notes':['The five named roads are an authentic 2013 municipal quarter description. The modern unnamed residential road completion, road-centreline interpretation, railway-side clause and divided-road junction choice are not independently established quarter boundaries.',
                 'The inferred completion consists of two literal original PBF node edges; physical road existence does not establish its neighborhood-boundary role.',
                 'The alternative actual-node junction and the existing same-name Joskar-Ola polygon are preserved as separate comparisons. This historical estimate adds no new named-quarter coverage.',
                 'All 18 source-unit headings and page numbers received separate parallel read-only semantic review; 15 name correspondences are not 15 verified source-footprint equivalences.',
                 'No legal, current-exact, cadastral or address-assignment approval; absolute accuracy is unclaimed.'],
        'reproduce':'PYTHONPATH=.local/geodata python3 '+str(Path(__file__).relative_to(ROOT))+' --check',
        'producerFilesModified':False,'networkUsed':False}
    return result,review


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    args=parser.parse_args();details,review=audit()
    for name,value in [('independent-audit.json',details),('independent-review.json',review)]:
        value=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode();path=OUT/name
        if args.check:
            assert path.read_bytes()==value,('Stale independent audit',name)
        else:
            path.write_bytes(value)
    print(json.dumps({'result':review['result'],'originalPbfWays':details['checkedCompleteArchivedWays'],
        'originalBoundaryNodeEdges':details['boundaryOriginalNodeEdges'],'primaryAdmissionApproved':False,
        'geojsonSha256':GEO_SHA,'check':args.check}))
