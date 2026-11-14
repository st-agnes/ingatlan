#!/usr/bin/env python3
"""Archive exact native blue source segments and their four closed faces.

All coordinates produced here are PDF page points, not longitude/latitude.
Unmodified source segments are noded/unioned and polygonized. No missing
boundary is added, buffered, snapped, simplified or repaired.
"""
import argparse,hashlib,json,shutil
from pathlib import Path
import fitz,numpy as np
from shapely.geometry import LineString,Polygon,Point,mapping
from shapely.ops import unary_union,polygonize_full
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
ORIGINAL=ROOT/'.local/neighborhoods/nationwide-docs/originals/sopron-map.pdf'
ARCHIVE=P/'source-pages1-2.pdf'
URL='https://njt.jog.gov.hu/document/4f/4fb0LL_EJR_84883813-Sopron_-_HESZmod_1_melleklet__SZT-Atnezeti_tervlapok.pdf'
BLUE=[38799,38800,38801,38802];OUTER=[91995,91996]
UNITS={1:('Észak-nyugati városrész','Észak-nyugat'),4:('Bánfalva, Kutyahegy városrész','Bánfalva, Kutyahegy'),5:('Lővereki városrész','Lőverek'),13:('Dél-keleti gazdasági terület városrész','Dél-keleti gazdasági terület')}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(o):return json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def line_segments(ds,indices):
 result=[]
 for i in indices:
  d=ds[i];assert all(x[0]=='l' for x in d['items'])
  result.extend({'drawingIndex':i,'segmentIndex':j,'coordinates':[list(x[1]),list(x[2])]} for j,x in enumerate(d['items']))
 return result


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
 inventory=json.loads((ROOT/'data/neighborhoods/research/local-pdf-inventory-north-scout.json').read_text());expected=next(s['sha256'] for s in inventory['sources'] if s['id']=='sopron-map')
 if not ARCHIVE.exists():
  assert ORIGINAL.exists() and sha(ORIGINAL)==expected
  original=fitz.open(ORIGINAL);out=fitz.open();out.insert_pdf(original);out.save(ARCHIVE,garbage=4,deflate=True)
 doc=fitz.open(ARCHIVE);assert len(doc)==2
 print('Reading original page2 native paths',flush=True);d2=doc[1].get_drawings();assert len(d2)==38892
 for i in BLUE:assert d2[i]['color']==(0.,0.,1.) and abs(d2[i]['width']-2.820000171661377)<1e-10
 segments=line_segments(d2,BLUE);network=unary_union([LineString(x['coordinates']) for x in segments]);faces,cuts,dangles,invalid=polygonize_full(network)
 assert len(faces.geoms)==4 and cuts.is_empty and dangles.is_empty and invalid.is_empty
 assert all(g.is_valid for g in faces.geoms)
 assert unary_union([g.boundary for g in faces.geoms]).symmetric_difference(network).length==0
 spans=[s for b in doc[1].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']]
 records=[];used=[]
 for number,(name,short) in UNITS.items():
  labels=[s for s in spans if s['text'].strip()==str(number)+'.' and s['bbox'][0]>400 and s['bbox'][2]<735 and 300<s['bbox'][1]<650];assert len(labels)==1
  s=labels[0];b=s['bbox'];center=Point((b[0]+b[2])/2,(b[1]+b[3])/2);containing=[i for i,g in enumerate(faces.geoms) if g.covers(center)];assert len(containing)==1 and containing[0] not in used;idx=containing[0];used.append(idx);g=faces.geoms[idx]
  records.append({'id':f'sopron-native-plan:{number}','sourceUnitNumber':number,'name':name,'shortSourceLabel':short,'boundaryKind':'planning_unit','canonicalNameIsNeighborhood':False,'constituentFootprintsInvented':False,'sourceLabel':{'text':s['text'],'bboxPdfPoints':list(s['bbox']),'colorRgbInteger':s['color'],'pointInsideActualSourceFacePdfPoints':list(center.coords)[0]},'nativeGeometry':mapping(g),'nativeAreaPdfPointsSquared':g.area,'nativeGeometryValid':g.is_valid,'sourceIsHardBoundary':False,'sourceIsOfficialCurrentGeometry':False,'usableForAddressAssignment':False,'absoluteBoundaryAccuracyMetres':None,'sourceSemantics':'One whole irregular geographic unit explicitly delimited in blue in Annex1/B of municipal ordinance39/2021. The plan also depicts the regulation territorial scope. Retain its whole source label; do not copy its footprint onto contained component names.','reviewStatus':'native_source_geometry_verified_geographic_registration_pending'})
 print('Reading page1 actual municipal perimeter and cross-page source scope',flush=True);d1=doc[0].get_drawings();assert len(d1)==94182
 for i in OUTER:assert abs(d1[i]['color'][0]-.4470210075378418)<1e-10 and d1[i]['color'][1:]==(0.,0.)
 outer_segments=line_segments(d1,OUTER);outer_net=unary_union([LineString(x['coordinates']) for x in outer_segments]);outer_faces,oc,od,oi=polygonize_full(outer_net)
 print('Municipal source faces',len(outer_faces.geoms),'cuts',len(oc.geoms),'dangles',len(od.geoms),'invalid',len(oi.geoms),flush=True)
 fills=[];fill_indices=[];fill_points=[]
 for i,d in enumerate(d1):
  if d.get('fill') and tuple(d['fill'])==(.49804699420928955,1.,.875) and d['rect'].y0>300:
   assert all(x[0]=='l' for x in d['items']);fill_indices.append(i);coords=[[list(x[1]),list(x[2])] for x in d['items']];fill_points.extend(p for segment in coords for p in segment);fills.append({'drawingIndex':i,'sourceFillType':d['type'],'sourceFillColor':list(d['fill']),'sourceSegmentsPdfPoints':coords})
 aqua_points=sorted(set(tuple(x) for x in fill_points));print('Cross-page source scope strips',len(fill_indices),'actual original source vertices',len(aqua_points),flush=True)
 geoobj=[]
 for i in range(1,doc.xref_length()):
  ob=doc.xref_object(i)
  if any(t in ob for t in ['/GPTS','/LPTS','/GCS','/Measure','/EPSG','/LGIDict']):geoobj.append(i)
 outputs={
  'native-source-segments.json':{'schemaVersion':1,'coordinateSystem':'PDF page2 points, origin top-left, y down; not geographic coordinates','sourcePdfPageOneBased':2,'drawingIndices':BLUE,'segments':segments},
  'native-source-polygons.json':{'schemaVersion':1,'coordinateSystem':'PDF page2 points, origin top-left, y down; not geographic coordinates','records':records},
  'calibration-native-perimeter.json':{'schemaVersion':1,'coordinateSystem':'PDF page1 points, origin top-left, y down; not geographic coordinates','sourcePdfPageOneBased':1,'drawingIndices':OUTER,'segments':outer_segments,'sourceNetworkDiagnostic':{'tinyClosedSubcycles':len(outer_faces.geoms),'cuts':len(oc.geoms),'dangles':len(od.geoms),'invalidRings':len(oi.geoms),'noClosedFullMunicipalityPolygonClaimed':True,'interpretation':'Original stroke-segment samples only. Native CAD endpoint quantization produces open segment graphs; no closure or coordinate snapping is imposed. These are registration controls, not exported municipal geometry.'}},
  'cross-page-native-fill-scope.json':{'schemaVersion':1,'coordinateSystem':'PDF page1 points','sourceFillColor':[.49804699420928955,1.,.875],'legendExcludedBySourceRectY0GreaterThan':300,'drawingIndices':fill_indices,'sourceFillShapes':fills,'actualSourceFillVertexPointCloud':[list(x) for x in aqua_points],'sourceFillGeometryRepair':False,'scope':'Original fill strips/vertices retained as cross-page calibration evidence only. No Polygon constructor closure or repair is used; PDF fill graphics need not be GEOS-valid polygons.'},
  'source-extraction-proof.json':{'schemaVersion':1,'originalUrl':URL,'originalPdfSha256':expected,'archivedSourcePdfSha256':sha(ARCHIVE),'archivedSourcePdfPages':2,'nativeGeographicMetadataObjectHits':geoobj,'noNativeGeographicCoordinatesClaimed':True,'selectedBlueNativeDrawingIndices':BLUE,'legendBlueDrawingExcluded':38815,'selectedOriginalNativeLineSegments':len(segments),'sourceFaceCount':4,'polygonizationCuts':len(cuts.geoms),'polygonizationDangles':len(dangles.geoms),'polygonizationInvalidRings':len(invalid.geoms),'actualNativeGraphEqualsSourceFaceBoundaryUnion':True,'inventedClosureSegments':0,'geometryRepairOrSnapping':False,'sameFootprintCopiedToComponentNames':False,'nativeMapLabelPointsGiveOneToOneFaceAssignment':True,'sourceMunicipalityNativeDrawingIndices':OUTER,'sourceMunicipalityNativeFaces':len(outer_faces.geoms),'sourceMunicipalityCuts':len(oc.geoms),'sourceMunicipalityDangles':len(od.geoms),'sourceMunicipalityInvalidRings':len(oi.geoms),'crossPageActualSourceFillCount':len(fill_indices),'sourceDocumentMunicipalPublication':True,'sourceReuseRightsEstablished':False,'usableForAddressAssignment':False}}
 for name,obj in outputs.items():
  dest=P/name;data=enc(obj)
  if args.check:assert dest.read_text()==data,name
  else:dest.write_text(data)
 print(enc({'nativeSourceUnits':4,'sourceSegments':len(segments),'municipalityFaces':len(outer_faces.geoms),'sourcePdfBytes':ARCHIVE.stat().st_size,'check':args.check}),flush=True)
if __name__=='__main__':main()
