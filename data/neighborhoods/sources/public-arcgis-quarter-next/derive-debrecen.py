#!/usr/bin/env python3
"""Strict offline ArcGIS geometry preservation; no canonical/global admission."""
from pathlib import Path
import json,hashlib,gzip,shutil,collections,math
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,Point,shape
from shapely.ops import transform
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
Q=ROOT/'.local/neighborhoods/supplement-feature-services/debrecen-quarter-queries'
ITEM='a04e2a4ff4d2467c8bb6eb640f515b51';PBF='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
def read(p):return json.loads(p.read_text())
def write(n,x): (P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical_sha(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
for record in read(Q/'download-manifest.json'):
 assert record['status']=='downloaded' and record['httpStatus']==200
 assert sha(Q/(record['id']+'.json'))==record['sha256']
native=read(Q/'debrecen-native-page0.json');service=read(Q/'debrecen-geojson-page0.json');count=read(Q/'debrecen-count.json');ids=read(Q/'debrecen-ids.json')
assert count['count']==77 and ids['objectIdFieldName']=='FID' and native['objectIdFieldName']=='FID'
assert native['geometryType']=='esriGeometryPolygon' and native['spatialReference']['latestWkid']==3857
assert {f['name'] for f in native['fields']}=={'FID','tipus','nev'}
assert not native.get('exceededTransferLimit',False)
expected=set(ids['objectIds']);retrieved=[f['attributes']['FID'] for f in native['features']];service_ids=[f['properties']['FID'] for f in service['features']]
assert len(expected)==len(retrieved)==len(set(retrieved))==len(service_ids)==len(set(service_ids))==count['count']
assert expected==set(retrieved)==set(service_ids)==set(range(1,78))
assert service['crs']['properties']['name']=='EPSG:4326'
BY={f['properties']['FID']:f for f in service['features']};to4326=Transformer.from_crs(3857,4326,always_xy=True);to3857=Transformer.from_crs(4326,3857,always_xy=True);toEov=Transformer.from_crs(4326,23700,always_xy=True)
features=[];proof=[];native_geoms={};eov_geoms={}
for f in native['features']:
 a=f['attributes'];fid=a['FID'];g=f['geometry'];assert set(g)=={'rings'} and len(g['rings'])==1
 r=g['rings'][0];assert len(r)>=4 and r[0]==r[-1] and all(len(c)==2 and all(math.isfinite(v) for v in c) for c in r)
 signed=sum(x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(r,r[1:]))/2;assert signed<0
 pn=Polygon(r);assert pn.is_valid and not pn.is_empty and pn.area>0
 w=[[list(to4326.transform(x,y)) for x,y in r]];derived={'type':'Polygon','coordinates':w};pd=shape(derived);ps=shape(BY[fid]['geometry']);assert BY[fid]['geometry']['type']=='Polygon'
 assert len(BY[fid]['geometry']['coordinates'])==1 and len(BY[fid]['geometry']['coordinates'][0])==len(r)
 assert a==BY[fid]['properties'] and BY[fid].get('id')==fid
 dif=np.max(np.abs(np.array(w)-np.array(BY[fid]['geometry']['coordinates'])))
 assert dif<1e-11
 ps_native=transform(to3857.transform,ps);haus=pn.hausdorff_distance(ps_native);assert haus<.00001
 props={'name':a['nev'],'municipality':'Debrecen','sourceFID':fid,'sourceCategory':a['tipus'],'reviewStatus':'research_quarantine','geometryRole':'published_thematic_named_area','wholeQuarterIdentityProven':False,'hardBoundary':False,'sourceIsOfficial':False,'usableForAddressAssignment':False,'source':{'provider':'public_arcgis_feature_service','serviceItemId':ITEM,'layerId':0,'objectIdField':'FID','objectId':fid,'nameField':'nev','categoryField':'tipus','nativeCrs':'EPSG:3857 (ArcGIS102100)','outputCrs':'EPSG:4326','dataLastEditUtc':'2025-06-02T23:33:23.324Z','originalBoundaryReferencePeriod':None,'copyrightText':'','licenseInfo':'','rightsStatus':'Reuse rights and original polygon lineage unestablished','geometryProcessing':'One native closed clockwise shell; original vertex order and count preserved; pyprojEPSG3857→4326 per vertex. No repair, simplification, clipping, snapping, buffering, inferred edges, densification or closure.','nativeGeometryCanonicalSha256':canonical_sha(g),'nativeResponseSha256':sha(Q/'debrecen-native-page0.json'),'geometryGenerated':False,'sourceRecordTitleContext':'Debrecen nehézfémszennyezés városrészek szerint_WFL1'}}
 features.append({'type':'Feature','id':f'arcgis:{ITEM}:0:{fid}','properties':props,'geometry':derived})
 eg=transform(toEov.transform,pd);native_geoms[fid]=pn;eov_geoms[fid]=eg
 proof.append({'FID':fid,'name':a['nev'],'category':a['tipus'],'nativeRings':1,'nativeHoles':0,'nativeClosed':True,'nativeClockwise':True,'sourceVerticesIncludingClosingRepeat':len(r),'sourceValid':True,'outputValid':pd.is_valid,'nativeGeometryCanonicalSha256':canonical_sha(g),'outputGeometryCanonicalSha256':canonical_sha(derived),'serviceSameProperties':True,'serviceSameVertexCount':True,'serviceVertexMaximumAbsoluteDifferenceDegrees':float(dif),'serviceBackProjectionHausdorffM3857':float(haus),'areaM2Epsg23700':eg.area,'sourceConvexHullAreaRatio':pn.area/pn.convex_hull.area,'sourceCircularityDiagnostic':4*math.pi*pn.area/(pn.length**2),'shapeDiagnosticsAreNotSourceLineageProof':True})
for src,dst in [('debrecen-native-page0.json','debrecen-source-native.json'),('debrecen-geojson-page0.json','debrecen-source-service.geojson'),('debrecen-count.json','debrecen-source-count.json'),('debrecen-ids.json','debrecen-source-ids.json')]:shutil.copyfile(Q/src,P/dst)
write('debrecen-source-normalized.geojson',{'type':'FeatureCollection','geometryScope':'All77 literal published source records; no canonical whole-quarter admission. Mixed source categories/names remain intact.','sourceNativeCrs':'EPSG:3857','outputCrs':'EPSG:4326','features':features})
write('conversion-proof.json',{'schemaVersion':1,'sourceItemId':ITEM,'nativeQuerySha256':sha(Q/'debrecen-native-page0.json'),'serviceGeojsonSha256':sha(Q/'debrecen-geojson-page0.json'),'canonicalHashSerialization':'UTF8 JSON ensure_ascii=False, sort_keys=True, separators=(comma,colon), allow_nan=False','countResponse':count['count'],'objectIdInventoryCount':len(expected),'nativeRetrievedCount':len(retrieved),'geojsonRetrievedCount':len(service_ids),'objectIdInventoriesExactlyMatch':True,'noDuplicateFID':True,'completeFIDRange':[1,77],'nativeExceedsTransferLimitPropertyPresent':'exceededTransferLimit'in native,'nativeExceedsTransferLimitValue':native.get('exceededTransferLimit'),'completenessProof':'Full explicit objectId set equals count and every retrievedFID in both formats; completeness does not rely on absent transfer-limit property.','sourceFieldsKept':['FID','tipus','nev'],'soilMeasurementsRetrieved':False,'nativeGeometryType':native['geometryType'],'nativeSpatialReference':native['spatialReference'],'coordinateOperation':to4326.description,'sourceRings':77,'sourceHoles':0,'sourceCurveRings':0,'sourceVerticesIncludingClosingRepeats':sum(r['sourceVerticesIncludingClosingRepeat'] for r in proof),'unclosedNativeRings':0,'invalidNativeFeatures':0,'invalidOutputFeatures':0,'modifiedVertexCounts':0,'sourceRingOrientationAndStartVertexPreserved':True,'geometryRepairs':0,'simplifications':0,'generatedClosingEdges':0,'inferredGeometry':0,'georeferencingFitPerformed':False,'geometricAccuracyEstablished':False,'coordinateEquivalenceIsNotBoundaryAccuracy':True,'features':proof})
# Actual current OSM name points are identity/location diagnostics only; never fit controls.
NP=ROOT/'.local/neighborhoods/country-osm-preserved-initial/named-nodes.geojson.gz'
allpoints=read_gz=json.loads(gzip.decompress(NP.read_bytes()))['features'];points=[f for f in allpoints if f['properties'].get('municipality')=='Debrecen']
# Three literal orthographic variants are recorded as diagnostic comparisons, not adopted aliases.
variants={'Veres Péter kert':['Veres Péter-kert'],'József Attila telep':['József Attila-telep'],'Wesselényi lakótelep':['Wesselényi-lakótelep']}
rows=[];used={}
for f in features:
 fid=f['properties']['sourceFID'];name=f['properties']['name'];g=eov_geoms[fid];matches=[]
 for pt in points:
  pn=pt['properties']['name'];kind='exact_source_name' if pn==name else ('explicit_spacing_or_hyphen_variant_diagnostic_only' if pn in variants.get(name,[]) else None)
  if not kind:continue
  po=transform(toEov.transform,shape(pt['geometry']));src=pt['properties']['source'];matches.append({'name':pn,'id':pt['id'],'place':pt['properties'].get('place'),'matchRule':kind,'sourcePolygonCoversPoint':g.covers(po),'distanceOutsidePolygonM':g.distance(po),'sourceObjectVersion':src['objectVersion'],'sourceObjectTimestamp':src['objectTimestamp'],'usedForFit':False});used[pt['id']]=pt
 rows.append({'FID':fid,'name':name,'matches':matches,'pointMatchAloneDoesNotProveWholeQuarterGeometry':True,'noAutomaticAliasAdopted':True})
write('debrecen-name-point-diagnostics.json',{'schemaVersion':1,'sourceArchivePath':str(NP.relative_to(ROOT)),'sourceArchiveSha256':sha(NP),'sourcePbfSha256':PBF,'osmTimestamp':'2026-11-12T21:23:05Z','municipalityNamePointsInspected':len(points),'sourcePointFeaturesRetained':len(used),'matchedRecords':sum(bool(r['matches'])for r in rows),'coordinateOperation':'Actual point EPSG4326→23700; containment/distance only. No fitting, snapping or outline inference.','fitControls':0,'pointOnlyGeometryGenerated':False,'records':rows})
write('debrecen-source-name-points.geojson',{'type':'FeatureCollection','sourcePbfSha256':PBF,'diagnosticOnly':True,'usedAsFitControls':False,'features':list(used.values())})
write('query-acquisition-proof.json',{'schemaVersion':1,'readOnlyPublicGet':True,'downloadManifestPath':str((Q/'download-manifest.json').relative_to(ROOT)),'downloadManifestSha256':sha(Q/'download-manifest.json'),'requests':read(Q/'download-manifest.json'),'fullGenericMetadataKeptInIgnoredLocalPath':True,'rawNativeResponsePreservedByteForByte':True,'rawGeojsonResponsePreservedByteForByte':True,'countAndIdsResponsesPreservedByteForByte':True,'additionalNetworkCallsByDeriver':0})
print(json.dumps({'records':len(features),'sourceVertices':sum(r['sourceVerticesIncludingClosingRepeat']for r in proof),'allValid':True,'namePoints':len(used),'nameMatchedRecords':sum(bool(r['matches'])for r in rows),'maxServiceVertexDiffDegrees':max(r['serviceVertexMaximumAbsoluteDifferenceDegrees']for r in proof),'maxServiceBackprojectDiffM':max(r['serviceBackProjectionHausdorffM3857']for r in proof)}))
