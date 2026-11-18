#!/usr/bin/env python3
"""Exact decimal PDF fill extraction; original map only, no world registration."""
from pathlib import Path
from decimal import Decimal
import json,re,hashlib
import fitz
from shapely.geometry import Polygon,MultiPolygon
from shapely.validation import explain_validity
P=Path(__file__).resolve().parent;ROOT=P.parents[3];SOURCE=ROOT/'.local/neighborhoods/quarter-map-batch/ksh-hodmezovasarhely-2005.pdf';EXPECTED='3dc2a4f4fcf3afd1b387a278be6a7fc7dcccdb75db8f1d4af3a5f07d811d8342';URL='https://www.ksh.hu/docs/hun/xftp/idoszaki/regiok/hodmezov.pdf'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert sha(SOURCE)==EXPECTED;D=fitz.open(SOURCE);page=D[8];raw=D.xref_stream(26).decode('latin1');graphics=re.sub(r'BT\b[\s\S]*?ET\b',' ',raw)
assert not re.search(r'(?<!\S)cm(?!\S)',graphics),'Nonidentity transform requires explicit evaluation'
number=r'[-+]?(?:\d+\.?\d*|\.\d+)';pair=re.compile(r'^('+number+r')\s+('+number+r')\s+([ml])$')
paint=[];paths=[];current=None;fill=[0,0,0];stroke=[0,0,0];ops=[]
for line in graphics.splitlines():
 line=line.strip();m=pair.fullmatch(line)
 if m:
  a,b,op=m.groups();v=[a,b]
  if op=='m':
   if current is not None:paths.append(current)
   current={'rawPdfOperands':[v],'commands':[line],'explicitCloseOperator':False}
  else:
   assert current is not None;current['rawPdfOperands'].append(v);current['commands'].append(line)
  continue
 if line=='h':
  assert current is not None;current['explicitCloseOperator']=True;current['commands'].append(line);continue
 if line in ['b*','b','B*','B','f*','f','S','s']:
  if current is not None:paths.append(current)
  if paths:
   paint.append({'paintIndex':len(paint),'paintOperator':line,'fillRgbOperands':fill[:],'strokeRgbOperands':stroke[:],'subpaths':paths})
  paths=[];current=None;continue
 c=re.fullmatch('('+number+r')\s+('+number+r')\s+('+number+r')\s+(scn|SCN)',line)
 if c:
  vals=list(c.groups()[:3]);
  if c.group(4)=='scn':fill=vals
  else:stroke=vals
  continue
assert current is None and not paths
names=['Belváros','Tarján','Tabán','Csúcs','Béketelep','Kertváros','Hódtó','Susán','Újváros','Kishomok','Batida','Szikáncs','Erzsébet','Kútvölgy','Kiskertek']
fills=[r for r in paint if r['paintOperator']!='S'];print('paints',len(paint),'fills',len(fills))
assert len(fills)==15
spans=[s for b in page.get_text('dict')['blocks']if 'lines'in b for l in b['lines']for s in l['spans']if 200<s['bbox'][1]<460]
records=[]
for i,(f,name) in enumerate(zip(fills,names)):
 rings=[];pathsproof=[]
 for j,sub in enumerate(f['subpaths']):
  points=[[float(Decimal(a)),float(Decimal('842')-Decimal(b))]for a,b in sub['rawPdfOperands']]
  rawclosed=points[0]==points[-1];closing=f['paintOperator']in ['b*','b','s'] or sub['explicitCloseOperator']
  assert rawclosed or closing,'Open unclosed source path'
  # Only an actual PDF close/paint edge is evaluated, never a missing-edge repair.
  if not rawclosed:points.append(points[0][:])
  rings.append(points);pathsproof.append({'subpathIndex':j,'inputCoordinates':len(sub['rawPdfOperands']),'inputFirstEqualsLast':rawclosed,'actualPdfCloseOperator':sub['explicitCloseOperator'],'actualClosingPaintOperator':f['paintOperator'],'rawPdfDecimalOperands':sub['rawPdfOperands'],'sourceCommands':sub['commands'],'sourceAreaPdfPointsSquared':Polygon(points).area})
 polygons=[Polygon(r)for r in rings];geom=polygons[0]if len(polygons)==1 else MultiPolygon(polygons)
 labels=[s for s in spans if s['text']==name];assert len(labels)==1
 rect=labels[0]['bbox'];point=[(rect[0]+rect[2])/2,(rect[1]+rect[3])/2]
 # Kútvölgy's long label may extend outside its small source contour.
 rec={'sourceFillOrdinal':i,'sourcePaintIndex':f['paintIndex'],'name':name,'sourceCategory':'central_quarter'if i<9 else('garden_area'if name in ['Kishomok','Kiskertek']else'attached_former_farm_centre'),'geometry':{'type':'Polygon','coordinates':[rings[0]]}if len(rings)==1 else{'type':'MultiPolygon','coordinates':[[r]for r in rings]},'coordinateSpace':'Exact original PDF decimal path operands, x right/y down after y=842−rawPDFy; unit PDFpoint. These are not world coordinates.','sourceFillRgb':f['fillRgbOperands'],'sourceStrokeRgb':f['strokeRgbOperands'],'fillRule':'even-odd'if '*'in f['paintOperator']else'nonzero','sourcePaintOperator':f['paintOperator'],'subpathCount':len(rings),'subpathProof':pathsproof,'geometryValid':geom.is_valid,'validityReason':explain_validity(geom),'sourceLabelRectanglePdfPoints':list(rect),'sourceLabelCenterPdfPoints':point,'sourceLabelUsedForFit':False,'sourceLabelMatchesLiteralText':True,'newFineCoverageCredit':0,'usableForAddressAssignment':False}
 if name=='Hódtó':rec['disposition']='quarantine_invalid_literal_source_path_and_existing_estimated_identity'
 elif name in ['Kishomok','Kiskertek']:rec['disposition']='garden_local_area_source_geometry_only_pending_geographic_registration'
 else:rec['disposition']='historical_named_quarter_candidate_pending_geographic_registration'
 records.append(rec)
# Retain the source map, excluding all surrounding narrative.
page.get_pixmap(matrix=fitz.Matrix(3,3),clip=fitz.Rect(102,206,467,452),alpha=False).save(P/'page9-map-only.png')
(P/'page9-inspection.png').unlink(missing_ok=True)
write('source-native-paths.json',{'schemaVersion':1,'sourceUrl':URL,'sourcePdfSha256':EXPECTED,'pdfPageOneBased':9,'printedPage':9,'sourceContentStreamXref':26,'contentStreamSha256':hashlib.sha256(D.xref_stream(26)).hexdigest(),'pageNativeDrawingCount':len(page.get_drawings()),'sourceFilledObjects':15,'sourceSubpaths':sum(r['subpathCount']for r in records),'sourceCoordinateOperation':'x=rawDecimalX,y=842−rawDecimalY, evaluated with Decimal before binary float serialization','graphicsCtm':'Identity; content stream has no cm operator outside text','geometryRepairPerformed':False,'sourceSubpathDiscarded':False,'sourceMicroTriangleDiscarded':False,'worldCoordinatesPresent':False,'records':records})
write('source-transport-paths.json',{'schemaVersion':1,'sourcePdfSha256':EXPECTED,'sourceContentStreamXref':26,'coordinateSpace':'Original raw PDF decimal points, y up; not world coordinates','sourcePaintRecords':[r for r in paint if r['paintOperator']=='S'],'meaning':'Transport overlays; the Kútvölgy outline shares its original fill paint operation and is not a separate S record. Source order remains literal. Identification requires visual source matching, not generic attribution to quarter boundaries.'})
write('source-extraction-proof.json',{'schemaVersion':1,'sourceUrl':URL,'originalLocalPath':str(SOURCE.relative_to(ROOT)),'sourcePdfSha256':EXPECTED,'sourceBytes':SOURCE.stat().st_size,'sourcePages':len(D),'documentTitle':D.metadata['title'],'publisher':'Központi Statisztikai Hivatal, Szegedi Igazgatóság','publicationPeriod':'July2005, issue8/2005','statisticsReferenceDate':'Principally2001-02-01 according to page4; other year-end values where specified','mapOriginalSurveyDate':None,'pdfMetadata':D.metadata,'mapPdfPageOneBased':9,'mapSourcePrimitive':'Native line/fill paths and machine-readable labels; no image on source page','sourceMapCropPdfPoints':[102,206,467,452],'sourceFilledObjects':15,'rawPdfPaintOperations':27,'muPdfDrawingRecords':28,'drawingCountExplanation':'One Kútvölgy fill/outline paint is represented by separate MuPDF fill/stroke records; it remains one named quarter object.','sourceNamedCentralQuarters':9,'sourceNamedAttachedVillages':4,'sourceGardenAreas':2,'sourceLabelsUsedAsFitControls':False,'sourceTopologicalCaveats':['Belváros and Kiskertek each have two closed subpaths including a small touching triangle; both preserved','Hódtó is an invalid self-intersecting source path and an already represented estimated identity; raw source only, no repair or additional identity'],'rightsStatus':'KSH2005 notice requires attribution for secondary publication and reserves data-transfer permission to KSHSzeged directorate. No unrestricted reuse/data-transfer permission has been established.','rightsEvidencePageOneBased':2,'rightsNoticeParaphrased':True,'fullOriginalPdfArchivedHere':False,'surroundingNarrativeArchived':False,'currentWholeQuarterBoundaryApproved':False,'usableForAddressAssignment':False})
print(json.dumps({'sourceFills':len(records),'sourceSubpaths':sum(r['subpathCount']for r in records),'valid':sum(r['geometryValid']for r in records),'invalid':[r['name']for r in records if not r['geometryValid']],'nativeComponentCounts':{r['name']:r['subpathCount']for r in records}},ensure_ascii=False))
