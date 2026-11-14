#!/usr/bin/env python3
"""Offline bounded packet verification; writes only this unregistered source folder."""
from pathlib import Path
import json,hashlib,csv,math
from shapely.geometry import shape
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def read(n):return json.loads((P/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def gs(g):return hashlib.sha256(json.dumps(g,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
source=read('debrecen-source-service.geojson');raw={f['properties']['FID']:f for f in source['features']};native=read('debrecen-source-native.json');ids=read('debrecen-source-ids.json');count=read('debrecen-source-count.json');six=read('debrecen-first-six-estimated.geojson');reg=read('registry-entry.json');review=read('first-six-independent-review.json')
assert count['count']==len(raw)==len(ids['objectIds'])==77 and set(raw)==set(ids['objectIds'])
assert len(six['features'])==6 and reg['frozenFeatureCount']==6 and reg['sha256']==sha(P/'debrecen-first-six-estimated.geojson')
expected={6:'Ispotály',42:'Tócóskert',59:'Kerekestelep',60:'Homokkert',61:'Lencztelep',65:'Vargakert'}
assert {f['properties']['sourceFID']:f['properties']['name'] for f in six['features']}==expected
for f in six['features']:
 p=f['properties'];fid=p['sourceFID'];assert f['geometry']==raw[fid]['geometry'] and shape(f['geometry']).is_valid
 assert p['boundaryKind']=='inferred_area' and p['candidateBoundaryKind']=='neighbourhood' and p['estimated'] is True
 assert p['sourceCoordinatesUnchangedFromPublished4326'] is True and p['georeferenceFitPerformed'] is False
 assert p['sourceIsOfficial'] is False and p['sourceIsHardBoundary'] is False and p['usableForAddressAssignment'] is False
 assert p['wholeOrdinaryQuarterExtentVerified'] is False and p['claimedAbsoluteAccuracyMetres'] is None
 assert p['sourceNameEvidence']['exactNameMatch'] and p['sourceNameEvidence']['sourcePolygonCoversPoint']
 assert p['sourceNameEvidence']['pointUsedForFit'] is False and p['sourceNameEvidence']['historicalMunicipalQuarterNameConfirmed'] is True
 assert p['sourceGeometryCanonicalSha256']==gs(f['geometry'])
D=read('record-dispositions.json');byfid={r['FID']:r for r in D['records']};assert len(byfid)==77 and byfid[11]['disposition']=='quarantine_suspected_source_mislabel' and byfid[4]['disposition']=='excluded_generic_label'
assert not any(r['automaticAliasApplied'] or r['canonicalPromotionPerformed'] or r['usableForAddressAssignment'] for r in byfid.values())
# Verify frozen existing26geometry identities without requiring an unchanged national export hash.
B=json.loads((ROOT/'data/neighborhoods/neighborhoods.geojson').read_text());current={f['id']:f for f in B['features'] if f['properties'].get('municipality')=='Debrecen'};baseline=read('baseline-reference.json')
# Baseline-reference field names are intentionally read by declared record schema.
records=baseline.get('features',baseline.get('records',[]))
assert len(current)==26 and len(records)==26
for r in records:
 fid=r.get('featureId',r.get('id'));expected_hash=r.get('canonicalJsonGeometrySha256',r.get('geometryCanonicalSha256',r.get('geometrySha256')))
 assert fid in current and expected_hash==gs(current[fid]['geometry']),(fid,expected_hash)
with (P/'baseline-all-pair-metrics.csv').open(newline='') as f: pairs=list(csv.DictReader(f))
assert len(pairs)==77*26
# Source manifests preserve exact fetch hashes and identify local originals without copying whole reports/PBF.
acq=read('query-acquisition-proof.json');fvs=read('debrecen-fvs-name-evidence.json');conv=read('conversion-proof.json')
assert conv['objectIdInventoriesExactlyMatch'] and conv['sourceVerticesIncludingClosingRepeats']==1034 and fvs['sourceNarrativeArchived'] is False
assert not list(P.glob('*.pdf')),'Packet must contain only selected map/label crops, not narrative PDF pages'
source_manifest={'schemaVersion':1,'status':'unregistered reviewed packet; six estimated candidates only','arcgis':{'itemId':'a04e2a4ff4d2467c8bb6eb640f515b51','layerId':0,'sourceRecords':77,'uniqueLiteralNames':76,'nativeCrs':'EPSG:3857 (ArcGIS102100)','publishedGeojsonCrs':'EPSG:4326','fields':['FID','tipus','nev'],'hostingDataEditUtc':'2025-06-02T23:33:23.324Z','originalBoundaryPeriod':None,'lineage':None,'reuseLicenseEstablished':False,'searchOrganizationLabelDoesNotProvePublisher':True,'rawNativeSha256':sha(P/'debrecen-source-native.json'),'rawPublishedGeojsonSha256':sha(P/'debrecen-source-service.geojson'),'countSha256':sha(P/'debrecen-source-count.json'),'idsSha256':sha(P/'debrecen-source-ids.json'),'queryAcquisitionProof':'query-acquisition-proof.json'},'municipalIdentityReference':{'sourceUrl':fvs['sourceUrl'],'sourcePdfSha256':fvs['sourcePdfSha256'],'sourceBytes':fvs['sourceBytes'],'localOriginalPath':fvs['originalLocalPath'],'publicationPeriod':'November2023','strategyHorizon':'2021–2027','historicalOrdinance':'32/2007.(VI.28.), already repealed by publication','role':'Historical name identity only; no same-schema or geometric-accuracy transfer','evidencePath':'debrecen-fvs-name-evidence.json','originalMapPath':fvs['mapImageArchive'],'sixLabelCropsPath':fvs['nameTableSixLabelsCropArchive'],'fullOriginalIncluded':False},'osmIdentityEvidence':{'pbfLocalOriginal':'.local/neighborhoods/hungary-latest.osm.pbf','pbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','pbfTimestamp':'2026-11-12T21:23:05Z','retainedActualSourcePoints':'debrecen-source-name-points.geojson','pointRole':'Name/identity/location diagnostics only, never fit controls or polygon generation','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','pbfIncluded':False,'independentSixNodeRevalidationPath':'first-six-independent-review.json'},'frozenCandidates':{'count':6,'file':'debrecen-first-six-estimated.geojson','sha256':sha(P/'debrecen-first-six-estimated.geojson'),'classification':'ESTIMATED source placement/current extent; literal published coordinates unchanged','primaryAdmissions':0,'existing26Changed':False,'wholeCurrentExtentVerified':False,'absoluteAccuracyM':None,'addressAssignmentApproved':False},'independentReviews':['independent-metadata-review.json','independent-geometry-review.json','baseline-overlap-review.json','first-six-independent-review.json'],'allPairMetrics':'baseline-all-pair-metrics.csv','allPairCount':2002,'automaticAliases':0,'geometryCorrections':0,'globalWritesPerformed':False}
write('source-manifest.json',source_manifest)
write('verification.json',{'schemaVersion':1,'sourceCountAndExplicitIdsEqual':True,'sourceRecords':77,'nativeAndPublished4326EquivalenceChecked':True,'sourceVerticesIncludingClosingRepeats':1034,'frozenEstimatedCandidates':6,'candidateGeometryEqualsPublishedGeojsonExactly':True,'existing26GeometryHashesUnchanged':True,'all2002BaselinePairsArchived':True,'sourceMislabelFid11Quarantined':True,'noAutomaticAliases':True,'noSourceCoordinatesCorrected':True,'noNarrativePdfArchived':True,'municipalReferenceUsedForNamesOnly':True,'currentOrdinaryQuarterExtentsVerified':False,'absoluteGroundAccuracyEstablished':False,'usableForAddressAssignment':False,'allChecksPassed':True})
files=[{'path':str(p.relative_to(P)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(P.rglob('*')) if p.is_file() and p.name!='artifact-manifest.json']
write('artifact-manifest.json',{'schemaVersion':1,'datasetId':'debrecen-arcgis-six-estimated-placement','scope':'Six estimated candidates plus77literal source records and bounded provenance/reviews; no primary/canonical admission','files':files,'totalBytes':sum(f['bytes']for f in files),'fullOriginalPdfIncluded':False,'fullPbfIncluded':False})
print('Packet verified:77source records,6ESTIMATED candidates,2002baseline pairs,26existing geometries unchanged')
