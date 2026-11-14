#!/usr/bin/env python3
"""Verify only this unregistered packet and immutable input sources."""
from pathlib import Path
from decimal import Decimal
import json,hashlib,math,subprocess
import numpy as np
from shapely.geometry import shape,mapping
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def read(n):return json.loads((P/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(g):return json.dumps(g,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def write(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
S=read('source-native-paths.json');E=read('source-extraction-proof.json');D=read('estimated-world-candidates.geojson');A=read('alternative-two-control-world.geojson');R=read('registration-and-uncertainty.json');B=read('road-pbf-verification.json');ENTRY=read('registry-entry.json');controls=read('road-control-specification.json')
assert len(S['records'])==15 and sum(r['subpathCount']for r in S['records'])==17
for r in S['records']:
 rings=[r['geometry']['coordinates'][0]]if r['geometry']['type']=='Polygon'else[p[0]for p in r['geometry']['coordinates']]
 assert len(rings)==r['subpathCount']
 for ring,proof in zip(rings,r['subpathProof']):
  original=[[float(Decimal(x)),float(Decimal('842')-Decimal(y))]for x,y in proof['rawPdfDecimalOperands']]
  assert original[0]==original[-1] and ring==original
 assert shape(r['geometry']).is_valid==r['geometryValid']
source={r['name']:r for r in S['records']};assert source['Belváros']['subpathCount']==source['Kiskertek']['subpathCount']==2
assert source['Hódtó']['geometryValid']is False and sum(r['geometryValid']for r in S['records'])==14
expected={'Belváros','Tarján','Tabán','Csúcs','Béketelep','Kertváros','Susán','Újváros','Kishomok'};assert {f['properties']['name']for f in D['features']}==expected and len(D['features'])==9
assert {f['properties']['name']for f in A['features']}==expected and len(A['features'])==9
BACK=Transformer.from_crs(23700,4326,always_xy=True);M=np.array(R['mainMatrixPdfToEov']);ALT=np.array(R['alternativeMatrixPdfToEov'])
for dataset,matrix in [(D,M),(A,ALT)]:
 for f in dataset['features']:
  p=f['properties'];native=shape(source[p['name']]['geometry']);eg=transform(lambda x,y:(matrix[0,0]*x+matrix[1,0]*y+matrix[2,0],matrix[0,1]*x+matrix[1,1]*y+matrix[2,1]),native);computed=mapping(transform(BACK.transform,eg))
  assert canonical(computed)==canonical(f['geometry']) and shape(f['geometry']).is_valid
  assert p['estimated']is True and p['estimatedContour']is False and p['estimatedPlacement']is True
  assert p['sourceContourIsObserved']is True and p['wholeOrdinaryQuarterExtentVerified']is False
  assert all(p[k]is False for k in ['canonicalNameIsNeighborhood','sourceIsOfficial','sourceIsHardBoundary','usableForAddressAssignment'])
  assert p['sourceNameEvidence']['sourceLabelUsedForFit']is False and p['sourceNameEvidence']['currentNamePointsUsedForFit']is False
assert ENTRY['sha256']==sha(P/'estimated-world-candidates.geojson')and ENTRY['featureCount']==9
assert len(controls['controls'])==3 and len(controls['heldOutAmbiguousChecks'])==2
assert B['completeWaysVerified']==98 and B['allReferencedNodeCoordinatesVerified']==512 and B['sourceNamePointsVerified']==12
assert B['sourcePbfSha256']=='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
assert math.isclose(R['mainControlRmsM'],15.02818441175499,abs_tol=1e-8)and R['absoluteGroundAccuracyM']is None
assert R['retainedOnlyNativeVillages']==['Batida','Szikáncs','Erzsébet','Kútvölgy'] and R['invalidAndDuplicateHodtoNotAdded']
assert sha(ROOT/E['originalLocalPath'])==E['sourcePdfSha256']
assert sha(ROOT/'data/neighborhoods/sources/municipal-hodmezovasarhely-hodto-first/hod-hodto-first-candidate.geojson')=='5b201c8a8c632f6096934b57d618beaf66db24b3492b0f2eece5d2d4b937d6ff'
node="""import {readFileSync} from 'node:fs'; import {validateGeometry} from './scripts/neighborhoods/build.mjs'; const d=JSON.parse(readFileSync(process.argv[1],'utf8')); const rows=d.features.map(f=>({name:f.properties.name,...validateGeometry(f.geometry)})); if(rows.some(r=>!r.valid))throw new Error(JSON.stringify(rows)); console.log(JSON.stringify(rows));"""
r=subprocess.run(['node','--input-type=module','-e',node,str(P/'estimated-world-candidates.geojson')],cwd=ROOT,check=True,capture_output=True,text=True);strict=json.loads(r.stdout)
independent=P/'independent-world-review.json'
if independent.exists():
 review=read('independent-world-review.json');assert review['accepted']is True and review['featureCount']==9
 for n,h in review['pinnedInputs'].items():assert sha(P/n)==h,(n,h,sha(P/n))
write('verification.json',{'schemaVersion':1,'status':'passed_source_and_math_checks_world_review_recorded'if independent.exists()else'passed_source_and_math_checks_pending_independent_world_review','nativeFilledObjects':15,'nativeClosedSubpaths':17,'validNativeObjects':14,'worldEstimatedCandidates':9,'worldParts':10,'nativeSubpathsAndVerticesPreserved':True,'sourceMicroTrianglesPreserved':True,'sourceAndWorldGeometryRepairs':0,'independentWorldReviewPresent':independent.exists(),'sourceRoadAndRailWaysFreshPbfVerified':98,'sourceNodeCoordinatesFreshPbfVerified':512,'sourceNamePointsFreshPbfVerified':12,'sourceOrCurrentNamePointsFitControls':0,'strictProjectValidatorResults':strict,'nativeHodtoQuarantined':True,'existingHodtoSourceHashUnchanged':True,'detachedVillagesWorldExported':0,'genericKiskertekWorldExported':False,'alternativeIsAdditionalQuarter':False,'primarySourceAdmissions':0,'globalRegistryChanged':False,'absoluteAccuracyEstablished':False,'wholeCurrentExtentsVerified':False,'usableForAddressAssignment':False,'sourceRightsPermissionEstablished':False})
write('source-manifest.json',{'schemaVersion':1,'sourcePdf':{'url':E['sourceUrl'],'sha256':E['sourcePdfSha256'],'bytes':E['sourceBytes'],'originalLocalPath':E['originalLocalPath'],'pages':E['sourcePages'],'mapPage':9,'mapPublication':'July2005','statisticsReference':'Principally2001-02-01','mapSurveyDate':None,'rights':'KSH attribution required for secondary publication; separate data-transfer permission reserved toKSHSzeged, not established here','fullOriginalIncluded':False},'sourceGeometry':{'nativeObjects':15,'nativeSubpaths':17,'nativeValidObjects':14,'exactDecimalOperandProof':'source-native-paths.json','sourceTransportPaths':'source-transport-paths.json','sourceMapOnlyCrop':'page9-map-only.png','sourceContoursRepaired':False,'sourcePartsDiscarded':False},'osmInputs':{'pbfLocalPath':'.local/neighborhoods/hungary-latest.osm.pbf','pbfSha256':B['sourcePbfSha256'],'pbfBytes':B['sourcePbfBytes'],'timestamp':'2026-11-12T21:23:05Z','waysPath':'road-source-ways.geojson','waysSha256':sha(P/'road-source-ways.geojson'),'namePointPath':'source-name-points.geojson','namePointSha256':sha(P/'source-name-points.geojson'),'freshPbfRevalidation':'road-pbf-verification.json','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','namePointsUsedForFit':False},'worldEstimate':{'candidateFile':'estimated-world-candidates.geojson','sha256':sha(P/'estimated-world-candidates.geojson'),'features':9,'parts':10,'classification':'Observed source contours with estimated placement; not primary/official/current complete quarter boundaries','registrationAndFullUncertainty':'registration-and-uncertainty.json','alternativePath':'alternative-two-control-world.geojson','alternativeIsAdditionalQuarter':False,'sourceFitControls':'road-control-specification.json','absoluteGroundAccuracyM':None,'detachedVillageGeometriesOnlyNative':True,'HodtoDuplicateAndInvalidSourceNotExported':True,'KiskertekGenericGardenOnlyNative':True},'reviews':{'independentSourceReview':'independent-source-review.json','independentWorldReview':'independent-world-review.json','independentWorldReviewPresent':independent.exists(),'independentWorldReviewSha256':sha(independent) if independent.exists()else None},'curatedUnregisteredEntry':'registry-entry.json','fullOriginalPdfOrBulkNarrativeIncluded':False,'globalRegistryAdmissionPerformed':False})
files=[{'path':str(p.relative_to(P)),'bytes':p.stat().st_size,'sha256':sha(p)}for p in sorted(P.rglob('*'))if p.is_file()and p.name!='artifact-manifest.json']
write('artifact-manifest.json',{'schemaVersion':1,'packetId':'hodmezovasarhely-ksh2005-native-estimated-placement','status':'unregistered_estimated_candidates_only','sourceSurveyDateUnknown':True,'files':files,'totalBytes':sum(r['bytes']for r in files),'nativeContours':15,'worldEstimatedCandidates':9,'primaryAdmissions':0,'fullOriginalPdfIncluded':False,'bulkPdfTextIncluded':False})
print('Verified15native fills/17subpaths;9estimated world candidates;98ways/512nodes;sourceHodtounchanged;worldreview',independent.exists())
