#!/usr/bin/env python3
"""Observed native contours, interpreted road-junction placement; no primary approval."""
from pathlib import Path
import json,hashlib,copy,math
import numpy as np
from shapely.geometry import shape,mapping,Point,Polygon,LineString
from shapely.ops import transform,unary_union
from pyproj import Transformer
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def read(n):return json.loads((P/n).read_text())
def write(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def gs(g):return hashlib.sha256(json.dumps(g,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
S=read('source-native-paths.json');R=read('road-control-specification.json');W=read('road-source-ways.geojson');NP=read('source-name-points.geojson');TO=Transformer.from_crs(4326,23700,always_xy=True);BACK=Transformer.from_crs(23700,4326,always_xy=True)
NODES={};STREETS={}
for f in W['features']:
 for n,c in zip(f['properties']['nodeRefs'],f['geometry']['coordinates']):
  if n in NODES:assert NODES[n]==c
  NODES[n]=c
 name=f['properties']['tags'].get('name')
 if name:STREETS.setdefault(name,set()).update(f['properties']['nodeRefs'])
G={r['name']:shape(r['geometry'])for r in S['records']}
for c in R['controls']:
 assert NODES[c['targetOsmNodeId']]==c['targetWgs84'] and all(c['targetOsmNodeId']in STREETS[n]for n in c['roads'])
 assert all(G[n].boundary.distance(Point(c['sourcePdfPoint']))<1e-10 for n in c['sourceQuarterJunction'])
for c in R['heldOutAmbiguousChecks']:assert NODES[c['targetOsmNodeId']]==c['targetWgs84'] and all(c['targetOsmNodeId']in STREETS[n]for n in c['roads'])
def solve(controls):
 A=[];z=[]
 for c in controls:
  x,y=c['sourcePdfPoint'];e,n=TO.transform(*c['targetWgs84']);A.extend([[x,y,1,0],[-y,x,0,1]]);z.extend([e,n])
 a,b,tx,ty=np.linalg.lstsq(np.asarray(A),np.asarray(z),rcond=None)[0]
 return np.array([[a,b],[b,-a],[tx,ty]])
M=solve(R['controls']);ALT=solve([R['controls'][0],R['controls'][2]])
def op(M):return lambda x,y,z=None:(M[0,0]*x+M[1,0]*y+M[2,0],M[0,1]*x+M[1,1]*y+M[2,1])
def world(g,M):return transform(BACK.transform,transform(op(M),g))
control_metrics=[]
for c in R['controls']+R['heldOutAmbiguousChecks']:
 pred=np.array([*c['sourcePdfPoint'],1])@M;target=np.array(TO.transform(*c['targetWgs84']));control_metrics.append({'id':c['id'],'role':c['role'],'sourcePdfPoint':c['sourcePdfPoint'],'targetOsmNodeId':c['targetOsmNodeId'],'residualEastNorthM':(pred-target).tolist(),'distanceM':float(np.linalg.norm(pred-target))})
HULL=Polygon([c['sourcePdfPoint']for c in R['controls']]);SELECT=['Belváros','Tarján','Tabán','Csúcs','Béketelep','Kertváros','Susán','Újváros','Kishomok'];features=[];alternatives=[];rows=[]
CAVEAT='Geographic placement is estimated from three interpreted source-boundary road junctions, not surveyed source controls. C2 has historical/current street-name ambiguity. Main fit RMS15.03m is not an accuracy bound; an ambiguous held-out junction differs55.76–74.73m. The control triangle covers only small portions ofBelváros/Tabán; other candidate footprints are extrapolated. Source cartographic generalization, road-centre convention,2005/current change and unknown survey/CRS remain material. Literal current-street-name line checks diverge up to1014m where simplified historical descriptions do not match the whole mapped border under current names; no aliases or source corrections are inferred. Independent source Susán/Újváros rail135 check differs by up to84.21m. These diagnostics do not establish absolute accuracy or whole current extents. Four detached village depictions are schematic/compressed and are retained only in native source coordinates.'
METHOD='Literal closed source fill contours from the original July2005KSH PDF page9, including all actual native subpaths and touching micro-triangles. Original decimal PDF vertices are evaluated exactly, then mapped by a three-road-junction EOV similarity and vertexwise EPSG23700→4326. No polygon repair, dropped component, smoothing, buffer, clipping, snapping, missing-edge cap, frame closure or current-name-point fit. Placement remains estimated; one two-control alternative is retained separately. Hódtó is invalid in source and already represented, so it is quarantined rather than repaired or counted again.'
for r in S['records']:
 name=r['name'];g=G[name];matches=[]
 for f in NP['features']:
  if f['properties']['name']!=name:continue
  p=transform(TO.transform,shape(f['geometry']));eg=transform(op(M),g);matches.append({'id':f['id'],'name':name,'place':f['properties'].get('place'),'sourcePolygonCoversPoint':eg.covers(p),'distanceOutsideM':eg.distance(p),'usedForFit':False})
 row={'name':name,'sourceFillOrdinal':r['sourceFillOrdinal'],'sourcePaintIndex':r['sourcePaintIndex'],'nativeGeometryValid':r['geometryValid'],'nativePartCount':r['subpathCount'],'currentNamePointDiagnostics':matches,'rawSourceGeometryCanonicalSha256':gs(r['geometry'])}
 if name not in SELECT:
  row['worldCandidateExported']=False;row['reason']='Invalid literal path and duplicate existing Hódtó estimate'if name=='Hódtó'else('Garden/local-area identity only, not a distinct fine statistical quarter row'if name=='Kiskertek'else'Detached village schematic position/scale cannot use central road fit; no source-to-world polygon emitted')
  rows.append(row);continue
 assert r['geometryValid'] and matches and any(m['sourcePolygonCoversPoint']for m in matches)
 wg=world(g,M);ag=world(g,ALT);assert wg.is_valid and ag.is_valid
 nativeCoords=[]
 if g.geom_type=='Polygon':nativeCoords=list(g.exterior.coords)
 else:
  for a in g.geoms:nativeCoords.extend(a.exterior.coords)
 arr=np.c_[np.array(nativeCoords),np.ones(len(nativeCoords))];shift=np.linalg.norm(arr@M-arr@ALT,axis=1);coverage=g.intersection(HULL).area/g.area
 props={'name':name,'municipality':'Hódmezővásárhely','municipalityId':'city:Hódmezővásárhely','boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','estimated':True,'estimatedContour':False,'estimatedPlacement':True,'canonicalNameIsNeighborhood':False,'sourceContourIsObserved':True,'sourceContourObserved':True,'sourceNativeFillOrdinal':r['sourceFillOrdinal'],'sourceNativePaintIndex':r['sourcePaintIndex'],'sourceNativePartCount':r['subpathCount'],'sourceNativeGeometryCanonicalSha256':gs(r['geometry']),'sourceContourCoordinatesPreservedVertexwise':True,'sourceHistoricalQuarterIdentitySupported':True,'sourceNameEvidence':{'literalSourceName':name,'sourcePageOneBased':9,'sourceLabelRectanglePdfPoints':r['sourceLabelRectanglePdfPoints'],'sourceLabelUsedForFit':False,'currentNamePointDiagnostics':matches,'currentNamePointsUsedForFit':False,'identityOnly':True,'sourceCategory':'named_statistical_city_part_with_garden_character'if name=='Kishomok'else'central_historical_quarter','currentWholeExtentVerified':False},'sourcePeriod':'KSH issue8/2005, publishedJuly2005; statistics principally2001-02-01; map survey/reference date unknown','georeferencingStatus':'estimated_three_interpreted_road_junction_similarity','georeferencingIsApproximate':True,'georeferenceConfidence':'low_unquantified_absolute_accuracy','claimedAbsoluteAccuracyMetres':None,'absoluteBoundaryAccuracyM':None,'wholeOrdinaryQuarterExtentVerified':False,'controlHullCoveredFraction':coverage,'mainVsTwoControlAlternativeVertexShiftM':{'minimum':float(shift.min()),'median':float(np.median(shift)),'maximum':float(shift.max()),'notAnAccuracyBound':True},'sourceDocumentIsOfficialStatisticalPublication':True,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,'reviewStatus':'estimated_historical_source_candidate_pending_independent_world_review','method':METHOD,'placementUncertainty':CAVEAT,'evidenceUrls':['https://www.ksh.hu/docs/hun/xftp/idoszaki/regiok/hodmezov.pdf'],'sourceDocuments':[{'url':'https://www.ksh.hu/docs/hun/xftp/idoszaki/regiok/hodmezov.pdf','sha256':S['sourcePdfSha256'],'pdfPageOneBased':9,'publicationPeriod':'July2005','sourceNameStreetFactsPages':[8,9],'statisticsReferenceEvidencePage':4}],'license':'KSH2005 requires source attribution for secondary publication and reserves data-transfer permission toKSHSzeged. Unrestricted reuse permission is not established. Actual OSM control/name-point evidence ODbL-1.0.','rightsStatus':'Source attribution and separate KSH data-transfer permission conditions retained; no unrestricted data-transfer/reuse permission established.'}
 fid=f'manual:hodmezovasarhely-ksh2005-native:{r["sourceFillOrdinal"]}'
 features.append({'type':'Feature','id':fid,'properties':props,'geometry':mapping(wg)})
 altprops=copy.deepcopy(props);altprops['georeferencingStatus']='alternative_two_interpreted_road_junction_similarity_C1_C3';altprops['notAnAdditionalQuarter']=True
 alternatives.append({'type':'Feature','id':fid+':alternative-C1-C3','properties':altprops,'geometry':mapping(ag)})
 row.update({'worldCandidateExported':True,'mainGeometryValid':wg.is_valid,'mainWorldGeometryCanonicalSha256':gs(mapping(wg)),'sourceVerticesIncludingClosingRepeats':len(nativeCoords),'controlHullCoveredFraction':coverage,'twoControlAlternativeMaximumVertexShiftM':float(shift.max()),'usableForAddressAssignment':False});rows.append(row)
# Independent continuous-border checks against actual roads. Interpolation is measurement only.
checks=[]
for a,b,roads in [('Tarján','Tabán',['László utca','Imre utca']),('Tarján','Belváros',['Damjanich utca']),('Tarján','Kertváros',['Kodály Zoltán utca']),('Tabán','Csúcs',['Szántó Kovács János utca']),('Csúcs','Béketelep',['Jókai utca']),('Belváros','Csúcs',['Teleki utca'])]:
 src=G[a].boundary.intersection(G[b].boundary);eg=transform(op(M),src);targets=[transform(TO.transform,shape(f['geometry']))for f in W['features']if f['properties']['tags'].get('name')in roads];target=unary_union(targets)
 if eg.length:
  distances=[eg.interpolate(v).distance(target)for v in np.linspace(0,eg.length,max(2,int(eg.length/10)+1))];checks.append({'sourcePair':[a,b],'roadNames':roads,'sourceSharedBoundaryGeometryCanonicalSha256':gs(mapping(src)),'sourceSharedLengthPdfPoints':src.length,'measurementSampleCount':len(distances),'sourceToRoadDistancePercentilesM':dict(zip(['p0','p50','p90','p100'],np.percentile(distances,[0,50,90,100]).tolist())),'meaning':'Actual source shared border compared to complete current road ways; source/current naming and centreline convention may differ. Samples do not alter exported geometry.','independentOfFitEndpoints':roads==['Kodály Zoltán utca']})
# The Susán/Újváros edge is a visibly drawn rail boundary; this is a held-out physical-line diagnostic.
src=G['Susán'].boundary.intersection(G['Újváros'].boundary);eg=transform(op(M),src);rail=unary_union([transform(TO.transform,shape(f['geometry']))for f in W['features']if f['properties']['tags'].get('railway')=='rail'and f['properties']['tags'].get('ref')=='135'])
dist=[eg.interpolate(v).distance(rail)for v in np.linspace(0,eg.length,max(2,int(eg.length/10)+1))]
checks.append({'sourcePair':['Susán','Újváros'],'physicalLine':'Actual current rail135, independently held out of road fit','sourceSharedLengthPdfPoints':src.length,'measurementSampleCount':len(dist),'sourceToRailDistancePercentilesM':dict(zip(['p0','p50','p90','p100'],np.percentile(dist,[0,50,90,100]).tolist())),'independentOfFitControls':True,'notAnAbsoluteAccuracyBound':True})
write('estimated-world-candidates.geojson',{'type':'FeatureCollection','status':'estimated_historical_source_placement_candidates_only','completeNationalCoverage':False,'usableForAddressAssignment':False,'features':features})
write('alternative-two-control-world.geojson',{'type':'FeatureCollection','status':'placement_alternative_not_additional_quarters','notForRegistryAdmission':True,'features':alternatives})
write('registration-and-uncertainty.json',{'schemaVersion':1,'sourcePdfSha256':S['sourcePdfSha256'],'method':METHOD,'sourceToEovCoordinateOperation':'[PDFx,PDFy,1] @ matrix = [EOVeast,EOVnorth]','mainMatrixPdfToEov':M.tolist(),'mainControlIds':['C1','C2','C3'],'mainScaleMPerPdfPoint':float(np.linalg.norm(M[0])),'mainControlRmsM':float(np.sqrt(np.mean([r['distanceM']**2 for r in control_metrics if r['role']=='fit']))),'controlMetrics':control_metrics,'controlSemantics':'Observed native quarter-boundary vertices interpreted as named-road junctions from source text. These are not surveyed source control points.','C2HistoricalStreetNameAmbiguity':'Current junction includes Teleki east,Pálffy west,Dr.Rapcsák south,Szántó north. Source simplified street description does not establish unchanged naming/geometry.','alternativeMatrixPdfToEov':ALT.tolist(),'alternativeControlIds':['C1','C3'],'alternativeMeaning':'Omit ambiguousC2; exact two-correspondence similarity. Model differences are not confidence bounds.','sourceNamePointFitControls':0,'municipalityPerimeterFit':False,'sourceFramesUsedForClosure':False,'geometryRepairs':0,'droppedNativeSubpaths':0,'controlHullPdfGeometry':mapping(HULL),'absoluteGroundAccuracyM':None,'wholeCurrentExtentConfirmed':False,'placementUncertainty':CAVEAT,'roadAndRailChecks':checks,'features':rows,'retainedOnlyNativeVillages':['Batida','Szikáncs','Erzsébet','Kútvölgy'],'invalidAndDuplicateHodtoNotAdded':True,'estimatedNeighbourhoodCandidateCount':len(features),'primarySourceAdmissionCount':0,'rightsStatus':'KSH attribution requirement and separate data-transfer permission restriction preserved. Permission status not established.','usableForAddressAssignment':False})
entry={'id':'hodmezovasarhely-ksh2005-native-estimated-placement','path':str((P/'estimated-world-candidates.geojson').relative_to(ROOT)),'sha256':sha(P/'estimated-world-candidates.geojson'),'municipality':'Hódmezővásárhely','featureCount':len(features),'method':METHOD,'evidenceUrls':['https://www.ksh.hu/docs/hun/xftp/idoszaki/regiok/hodmezov.pdf'],'license':'KSH2005 attribution required; separate data-transfer permission not established. ODbL-1.0 actual OSM controls/name evidence.','propertyOverrides':{'boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','estimated':True,'canonicalNameIsNeighborhood':False,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'georeferencingIsApproximate':True,'claimedAbsoluteAccuracyMetres':None,'usableForAddressAssignment':False},'reviewPath':str((P/'registration-and-uncertainty.json').relative_to(ROOT)),'independentSourceReviewPath':str((P/'independent-source-review.json').relative_to(ROOT)),'independentReviewPath':str((P/'independent-world-review.json').relative_to(ROOT)),'placementAlternativePath':str((P/'alternative-two-control-world.geojson').relative_to(ROOT)),'uncertainties':[CAVEAT,'Nine historical identities do not establish present complete extents; KSH reuse/data-transfer conditions are not treated as an open licence.'],'rightsStatus':'KSH2005 source-attribution and data-transfer-permission conditions; unrestricted permission unestablished.','globalRegistryAdmissionPerformed':False}
write('registry-entry.json',entry)
print(json.dumps({'estimatedCandidates':len(features),'mainControlRmsM':float(np.sqrt(np.mean([r['distanceM']**2 for r in control_metrics if r['role']=='fit']))),'heldOutDistanceM':[r['distanceM']for r in control_metrics if r['role']!='fit'],'independentRoadRailChecks':checks},ensure_ascii=False))
