#!/usr/bin/env python3
"""Offline, read-only independent audit of the four Sopron source faces.

Only --write-review writes independent-review.json. Producer files are untouched.
The audit reopens original PDF paths and recomputes endpoint fits and projection.
"""
import argparse,gzip,hashlib,json,subprocess
from pathlib import Path
import fitz,numpy as np,shapely
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer,Geod

P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def read(name):return json.loads((P/name).read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def encoded(value):return json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def summary(values):return {str(q):float(np.percentile(values,q)) for q in [0,50,80,90,95,99,100]}
def source_segment(drawings,entry):
 d=drawings[entry['drawingIndex']];item=d['items'][entry['segmentIndex']]
 assert item[0]=='l','A paired source control is not an original line segment'
 points=np.array([list(item[1]),list(item[2])],dtype=float)
 assert np.array_equal(points,np.array(entry['coordinates'])),'Archived endpoint differs from literal PDF endpoint'
 return points,d

def audit():
 reg=read('registration.json');native=read('native-source-polygons.json');fc=read('source-vector.geojson');cal=read('calibration-native-perimeter.json');src=read('source-extraction-proof.json');reference=read('calibration-reference-origin.json')
 for entry in reg['inputs']:assert sha(P/entry['path'])==entry['sha256'],entry['path']
 source_hash=sha(P/'source-vector.geojson');archived=fitz.open(P/'source-pages1-2.pdf');assert len(archived)==2
 assert sha(P/'source-pages1-2.pdf')==src['archivedSourcePdfSha256']
 d1=archived[0].get_drawings();d2=archived[1].get_drawings();assert len(d1)==94182 and len(d2)==38892
 original_path=ROOT/'.local/neighborhoods/nationwide-docs/originals/sopron-map.pdf';original_checked=False
 if original_path.exists():
  assert sha(original_path)==src['originalPdfSha256'];original=fitz.open(original_path);od1=original[0].get_drawings();od2=original[1].get_drawings();original_checked=True
 else:od1=od2=None
 # Real page1 municipality stroke endpoints, not a snapped or closed proxy polygon.
 all_perimeter=[]
 for entry in cal['segments']:
  xy,d=source_segment(d1,entry);assert entry['drawingIndex'] in [91995,91996]
  assert d['color']==(.4470210075378418,0.,0.)
  if od1 is not None:source_segment(od1,entry)
  all_perimeter.extend(xy)
 points=np.unique(np.array(all_perimeter),axis=0);assert np.array_equal(points,np.array(reg['sourcePerimeterControlPointsPage1PdfPoints']))
 assert len(points)==3867
 parent_obj=read('calibration-municipality.geojson');assert parent_obj['id']=='osm:relation:1491393'
 assert sha(P/'calibration-municipality.geojson')==reference['archivedReferenceSha256'];assert parent_obj['properties']==reference['sourceProperties']
 origin=ROOT/reference['sourceLocalPath'];origin_exact=None
 if origin.exists() and sha(origin)==reference['sourceLocalSha256']:
  origin_doc=json.loads(origin.read_text());candidates=[f for f in origin_doc['features'] if f.get('id')==reference['sourceFeatureId']];assert len(candidates)==1 and candidates[0]==parent_obj;origin_exact=True
 geographic_parent=shape(parent_obj['geometry']);metric=Transformer.from_crs(4326,23700,always_xy=True).transform;eov_parent=transform(metric,geographic_parent);outer=max(eov_parent.geoms,key=lambda g:g.area).exterior
 m1=np.array(reg['page1PdfPointsToEovMatrix']);mapped=np.c_[points,np.ones(len(points))]@m1;residual=shapely.distance(shapely.points(mapped),outer)
 assert np.allclose(residual,reg['sourcePerimeterExactResidualsMetres'],rtol=1e-11,atol=1e-7)
 # Every archived paired CAD segment is literally present in both original pages.
 payload=gzip.decompress((P/'cross-page-cad-controls.json.gz').read_bytes());cad=json.loads(payload);small=read('cross-page-cad-controls.json')
 assert cad['sourcePdfSha256']==sha(P/'source-pages1-2.pdf')
 assert small['fullControlPairsArchiveSha256']==sha(P/'cross-page-cad-controls.json.gz')
 pairs=cad['controlPairs'];assert len(pairs)==4888 and cad['matchedActualSourceSegmentPairs']==4888 and cad['matchedActualEndpointPairs']==9776
 A=[];B=[];indices1=[];indices2=[]
 for pair in pairs:
  a,ad=source_segment(d1,pair['page1']);b,bd=source_segment(d2,pair['page2'])
  assert ad.get('fill') is None and bd.get('fill') is None
  assert ad['color'] is not None and max(ad['color'])-min(ad['color'])<=.001
  assert bd['color'] is not None and max(bd['color'])-min(bd['color'])<=.001
  assert ad['width']<=.3 and bd['width']<=.2
  if od1 is not None:source_segment(od1,pair['page1']);source_segment(od2,pair['page2'])
  indices1.append((pair['page1']['drawingIndex'],pair['page1']['segmentIndex']));indices2.append((pair['page2']['drawingIndex'],pair['page2']['segmentIndex']))
  if pair['page2EndpointOrderReversed']:b=b[::-1]
  A.extend(a);B.extend(b)
 A=np.array(A);B=np.array(B);m12=np.linalg.lstsq(np.c_[A,np.ones(len(A))],B,rcond=None)[0]
 assert np.allclose(m12,cad['page1PdfPointsToPage2PdfPointsMatrix'],rtol=0,atol=1e-9)
 assert np.allclose(m12,reg['page1PdfPointsToPage2PdfPointsMatrix'],rtol=0,atol=1e-9)
 endpoints=np.linalg.norm(np.c_[A,np.ones(len(A))]@m12-B,axis=1)
 for i,pair in enumerate(pairs):assert np.allclose(endpoints[2*i:2*i+2],pair['pairedEndpointResidualsPage2PdfPoints'],rtol=0,atol=1e-9)
 for q,value in summary(endpoints).items():
  assert abs(value-cad['pairedEndpointResidualPercentilesPage2PdfPoints'][q])<1e-9
 unique_selected=[];seen_targets=set()
 for idx,pair in enumerate(pairs):
  key=(pair['page2']['drawingIndex'],pair['page2']['segmentIndex'])
  if key not in seen_targets:seen_targets.add(key);unique_selected.extend([2*idx,2*idx+1])
 unique_a=np.c_[A[unique_selected],np.ones(len(unique_selected))];unique_b=B[unique_selected];unique_m=np.linalg.lstsq(unique_a,unique_b,rcond=None)[0]
 unique_change=np.linalg.norm(unique_a@unique_m-unique_a@m12,axis=1);assert max(unique_change)<.01
 # The coarse shared scope consists of literal original fill vertices only.
 fill=read('cross-page-native-fill-scope.json');fill_points=[]
 for item in fill['sourceFillShapes']:
  drawing=d1[item['drawingIndex']];assert list(drawing['fill'])==fill['sourceFillColor'] and drawing['rect'].y0>300
  actual=[[[float(z) for z in seg[1]], [float(z) for z in seg[2]]] for seg in drawing['items'] if seg[0]=='l']
  assert actual==item['sourceSegmentsPdfPoints']
  fill_points.extend(v for segment in actual for v in segment)
 actual_scope=np.unique(np.array(fill_points),axis=0);assert np.array_equal(actual_scope,np.array(fill['actualSourceFillVertexPointCloud']))
 assert np.array_equal(actual_scope,np.array(reg['crossPageSourceFillVertexPointsPage1']))
 native_scope=shapely.union_all([shape(item['nativeGeometry']) for item in native['records']])
 scope_error=shapely.distance(shapely.points(np.c_[actual_scope,np.ones(len(actual_scope))]@m12),native_scope.boundary)
 assert np.allclose(scope_error,reg['crossPageSourceVertexResidualsPage2PdfPoints'],rtol=0,atol=1e-8)
 # Cross-page inverses and page2-to-EOV composition, computed independently.
 inv=np.linalg.inv(m12[:2]);m21=np.vstack([inv,-m12[2]@inv]);m2=np.vstack([inv@m1[:2],m21[2]@m1[:2]+m1[2]])
 assert np.allclose(m21,reg['page2PdfPointsToPage1PdfPointsMatrix'],rtol=0,atol=1e-9)
 assert np.allclose(m2,reg['page2PdfPointsToEovMatrix'],rtol=0,atol=1e-8)
 printed_scale_text='M = 1 : 60.000';assert printed_scale_text in archived[1].get_text()
 expected_metres_per_pdf_point=60000*.0254/72;actual_axis_scale=np.linalg.norm(m2[:2],axis=1);assert np.all(np.abs(actual_axis_scale/expected_metres_per_pdf_point-1)<.005)
 project=Transformer.from_crs(23700,4326,always_xy=True);geod=Geod(ellps='WGS84');records=[];geoms=[]
 assert len(fc['features'])==len(native['records'])==4
 for item in native['records']:
  n=item['sourceUnitNumber'];f=next(f for f in fc['features'] if f['properties']['sourceUnitNumber']==n);p=f['properties'];g=shape(f['geometry']);npdf=shape(item['nativeGeometry']);geoms.append(g)
  assert f['geometry']['type']=='Polygon' and g.is_valid and npdf.is_valid
  max_delta=0.
  assert len(f['geometry']['coordinates'])==len(item['nativeGeometry']['coordinates'])
  for nr,wr in zip(item['nativeGeometry']['coordinates'],f['geometry']['coordinates']):
   pix=np.array(nr);metric_points=pix@m2[:2]+m2[2];lon,lat=project.transform(metric_points[:,0],metric_points[:,1]);expected=np.c_[lon,lat];actual=np.array(wr);assert expected.shape==actual.shape
   delta=float(np.max(np.abs(expected-actual)));max_delta=max(max_delta,delta);assert delta<1e-12
  outside=transform(metric,g.difference(geographic_parent)).area;area=transform(metric,g).area;overlap=1-outside/area
  assert abs(outside-p['outsideCurrentMunicipalityAreaM2'])<.0001 and abs(overlap-p['municipalityOverlapFraction'])<1e-12
  assert abs(abs(geod.geometry_area_perimeter(g)[0])-p['areaM2'])<.001
  assert p['boundaryKind']=='planning_unit' and p['canonicalNameIsNeighborhood'] is False and p['constituentFootprintsInvented'] is False
  assert p['usableForAddressAssignment'] is False and p['claimedAbsoluteAccuracyMetres'] is None and p['sourceIsHardBoundary'] is False
  if n==5:assert 9000<outside<10000
  else:assert outside<1e-7
  records.append({'sourceUnitNumber':n,'name':p['name'],'nativeAndGeographicVertexCountsEqual':True,'maximumCoordinateDifferenceDegrees':max_delta,'geometryValid':True,'outsideCurrentMunicipalityAreaM2':outside,'municipalityOverlapFraction':overlap,'coordinatesUnclippedAndUnrepaired':True,'geometrySha256':hashlib.sha256(json.dumps(f['geometry'],separators=(',',':'),ensure_ascii=False).encode()).hexdigest()})
 overlaps=[a.intersection(b).area for i,a in enumerate(geoms) for b in geoms[:i]];assert max(overlaps)<1e-16
 nodecode="import {readFileSync} from 'node:fs'; import {validateGeometry} from './scripts/neighborhoods/build.mjs'; const d=JSON.parse(readFileSync('data/neighborhoods/sources/municipal-sopron-next/source-vector.geojson')); console.log(JSON.stringify(d.features.map(f=>({number:f.properties.sourceUnitNumber,name:f.properties.name,...validateGeometry(f.geometry)}))));"
 js=json.loads(subprocess.run(['node','--input-type=module','-e',nodecode],cwd=ROOT,check=True,text=True,capture_output=True).stdout);assert len(js)==4 and all(v['valid'] for v in js)
 assert reg['registrationGeographicNamePointCount']==0 and reg['independentSurveyOrInteriorWorldControlCount']==0 and reg['absoluteBoundaryAccuracyMetres'] is None
 # Source date/status corrections are documentary, not a reason to alter coordinates.
 correction=read('metadata-correction-proof.json');assert correction['finalSourceFeatureCollectionSha256']==source_hash
 assert correction['geographicGeometryHashesBefore']==correction['geographicGeometryHashesAfter']
 for f in fc['features']:
  actual=hashlib.sha256(json.dumps(f['geometry'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest();assert actual==correction['geographicGeometryHashesAfter'][f['id']]
 assert sha(P/'native-source-polygons.json')==correction['nativeSourcePolygonsSha256BeforeAndAfter'] and sha(P/'native-source-segments.json')==correction['nativeSourceSegmentsSha256BeforeAndAfter']
 periods=[f['properties']['sourcePeriod'] for f in fc['features']];date_correction_needed=any('2024.I' in v for v in periods) or '2024. I' in (P/'README.txt').read_text()
 native_review_path=P/'review-native-check.json';native_review=json.loads(native_review_path.read_text()) if native_review_path.exists() else None
 fingerprints=[{'path':str((P/name).relative_to(ROOT)),'sha256':sha(P/name)} for name in ['source-pages1-2.pdf','native-source-segments.json','native-source-polygons.json','source-vector.geojson','registration.json','calibration-native-perimeter.json','calibration-municipality.geojson','cross-page-cad-controls.json','cross-page-cad-controls.json.gz','source-extraction-proof.json','metadata-correction-proof.json']]
 result={'schemaVersion':1,'reviewDate':'2026-11-13','reviewer':'Independent sopron_independent_review agent, with separate native_faces_check source audit','sourceSha256':source_hash,'overallVerdict':'geometry_and_calculation_pass; documentary_source_date_status_correction_required' if date_correction_needed else 'source_defined_planning_geometry_and_calculation_pass_unknown_absolute_accuracy','networkUsed':False,'producerFilesModified':False,'fingerprints':fingerprints,'originalLocalPdfCrossChecked':original_checked,'archivedReferenceExactlyMatchesOriginalLocalMunicipalityFeature':origin_exact,'nativeSourceIndependentReview':native_review,'georeferencingChecks':{'actualOriginalPage1PerimeterSourceVertices':len(points),'allPerimeterEndpointCoordinatesExactlyPresentInArchivedAndOriginalPdf':True,'sourcePerimeterResidualMetresRecomputed':summary(residual),'realCrossPageSegmentPairs':len(pairs),'realCrossPageEndpointPairs':len(A),'uniquePage1SegmentIndices':len(set(indices1)),'uniquePage2SegmentIndices':len(set(indices2)),'uniqueTargetOnlyFitSanity':{'segmentPairs':len(unique_selected)//2,'maximumPredictedEndpointChangePdfPoints':float(max(unique_change)),'originalPairCountNotClaimedAsIndependentSurveyControls':True},'allPairedEndpointsExactlyPresentInArchivedAndOriginalPdf':True,'affineLeastSquaresMatrixRecomputedFromAllPairedEndpoints':True,'cadEndpointResidualsPdfPointsRecomputed':summary(endpoints),'pageTransformInverseAndCompositionVerified':True,'printedSourceScaleSanity':{'verbatim':printed_scale_text,'nominalMetresPerPdfPoint':expected_metres_per_pdf_point,'fittedMetresPerPdfPointAxes':actual_axis_scale.tolist(),'relativeScaleDifferences':(actual_axis_scale/expected_metres_per_pdf_point-1).tolist(),'independentSurveyAccuracyClaimed':False},'sharedNativeFillVertexPointsVerified':len(actual_scope),'sharedScopeBoundaryResidualsPdfPointsRecomputed':summary(scope_error),'quarterNameGeographicCoordinatesUsed':False,'independentInteriorWorldOrSurveyControls':0,'claimedAbsoluteAccuracyMetres':None},'geometryChecks':{'fourWholePlanningUnits':4,'fineNeighbourhoodCount':0,'everyGeographicVertexReconstructedFromOriginalNativeSourceVertex':True,'maximumPairwiseOverlapDegreesSquared':max(overlaps),'strictExistingJsValidatorAccepted':4,'strictExistingJsValidatorResults':js,'sourceOverhangPreservedWithoutClipping':True,'records':records},'metadataReview':{'sourceDateCorrectionStillNeeded':date_correction_needed,'sourceIssueLiteral':'2024. 11.','sourceIssueYearMonth':'2024-11','metadataCorrectionFourCoordinateGeometryHashesUnchanged':True,'sourceIssueDateVerbatimAndDraftStatusSee':'review-native-check.json','requiredCorrection':'Correct the source issue month to the verbatim rendered 2024. 11.; preserve the extracted-only .../2024 placeholder as an unresolved hidden/CAD text artifact rather than proof of visible draft or approval status. Current legal validity remains unverified.' if date_correction_needed else None},'restrictions':{'usableForAddressAssignment':False,'sourceIsHardBoundary':False,'currentLegalOrCadastralValidityCertified':False,'municipalMapUnrestrictedReuseLicenceEstablished':False,'perimeterFitResidualIsIndependentAccuracy':False,'crossPageFitResidualIsIndependentGeographicAccuracy':False}}
 return result

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-review',action='store_true');ap.add_argument('--check',action='store_true');args=ap.parse_args();result=audit();text=encoded(result)
 if args.write_review:(P/'independent-review.json').write_text(text)
 if args.check:assert (P/'independent-review.json').read_text()==text,'Independent review differs; regenerate it only after inspecting changed inputs.'
 print(encoded({'verdict':result['overallVerdict'],'sourceSha256':result['sourceSha256'],'nativeReviewPresent':result['nativeSourceIndependentReview'] is not None,'planningUnits':4,'fineNeighbourhoodCount':0,'readOnly':not args.write_review}))
if __name__=='__main__':main()
