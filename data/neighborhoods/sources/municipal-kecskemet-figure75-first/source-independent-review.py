#!/usr/bin/env python3
"""Audit the source contour from literal pixels and archived prose, no producer import."""
import argparse,hashlib,json,math
from pathlib import Path
from collections import deque
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,Point
import fitz
OUT=Path(__file__).resolve().parent
COHORT=next(p for p in [OUT,*OUT.parents]if(p/'source-pixel-trace.json').is_file())

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encode(v):return(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def neighbors(a,b):return max(abs(a[0]-b[0]),abs(a[1]-b[1]))==1

def review(check=False):
 trace=json.loads((COHORT/'source-pixel-trace.json').read_text());semantics=json.loads((COHORT/'source-semantics.json').read_text());image=Image.open(COHORT/'figure75-p158-xref180.jpeg').convert('RGB');rgb=np.asarray(image);value=rgb.max(2);height,width=value.shape
 if sha(COHORT/'figure75-p158-xref180.jpeg')!=trace['sourceImageSha256']or[width,height]!=trace['sourceImageSize']:raise ValueError('source JPEG identity differs')
 if set(trace['rings'])!={'Reptéri lakótelep'}:raise ValueError('expected proper source cell differs')
 ring=trace['rings']['Reptéri lakótelep'];polygon=Polygon(ring)
 if ring[0]!=ring[-1]or not polygon.is_valid or polygon.interiors:raise ValueError('source ring open, invalid or holed')
 if any(not isinstance(x,int)or not isinstance(y,int)or not(0<=x<width and 0<=y<height)for x,y in ring):raise ValueError('nonliteral pixel index')
 if any(not neighbors(a,b)for a,b in zip(ring,ring[1:])):raise ValueError('unlisted nonlocal edge')
 frame_distance=min(min(x,y,width-1-x,height-1-y)for x,y in ring)
 if frame_distance<=0:raise ValueError('frame closure implicated')
 joined=[]
 for name in ['north','east','south','west']:
  part=trace['sections'][name]
  if joined and joined[-1]!=part[0]:raise ValueError('source section endpoints differ')
  joined+=part if not joined else part[1:]
 if joined!=ring:raise ValueError('ring not exactly archived section concatenation')
 actual_nonblack=[(x,y)for x,y in ring if value[y,x]>45];declared_nonblack=[];gaps=[]
 for gap in trace['sourceTextOverprintInferences']:
  path=gap['inferredPixelPath'];a,b=gap['sourceBlackEndpoints'];window=gap['sourcePixelWindow']
  if path[0]!=a or path[-1]!=b or value[a[1],a[0]]>45 or value[b[1],b[0]]>45 or gap['confidence']!='low':raise ValueError('gap endpoint/low-confidence policy differs')
  if any(not neighbors(u,v)for u,v in zip(path,path[1:])):raise ValueError('gap is not a bounded dense 8-neighbor hypothesis')
  positions=[i for i in range(len(ring)-len(path)+1)if ring[i:i+len(path)]==path]
  if len(positions)!=1:raise ValueError('gap path missing, duplicated or changed')
  if any(not(window[0]<=x<=window[2]and window[1]<=y<=window[3])for x,y in path):raise ValueError('gap outside declared window')
  nonblack=[(x,y)for x,y in path if value[y,x]>45];declared_nonblack+=nonblack
  if not all(int(rgb[y,x,2])>int(rgb[y,x,0])and int(rgb[y,x,2])>int(rgb[y,x,1])for x,y in nonblack):raise ValueError('gap nonblack colors are not blue-dominant annotation')
  start,end=tuple(a),tuple(b);lo=[min(a[k],b[k])-14 for k in (0,1)];hi=[max(a[k],b[k])+14 for k in (0,1)];visited={start};queue=deque([start])
  while queue:
   u=queue.popleft()
   for dx,dy in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
    v=(u[0]+dx,u[1]+dy)
    if lo[0]<=v[0]<=hi[0]and lo[1]<=v[1]<=hi[1]and value[v[1],v[0]]<=45 and v not in visited:visited.add(v);queue.append(v)
  if end in visited:raise ValueError('declared local black-stroke disconnection not reproduced')
  alternatives=[]
  for alternative in gap['alternativePixelPaths']:
   dense=alternative[0]==a and alternative[-1]==b and all(neighbors(u,v)for u,v in zip(alternative,alternative[1:]));bounded=all(window[0]<=x<=window[2]and window[1]<=y<=window[3]for x,y in alternative);i=positions[0];variant=Polygon(ring[:i]+alternative+ring[i+len(path):]);alternatives.append({'sameEndpointsAndAll8Neighbor':dense,'insideDeclaredWindow':bounded,'replacementSourcePolygonValid':bool(variant.is_valid),'replacementSourceAreaDifferenceSquarePixels':float(variant.area-polygon.area),'notAnAccuracyBoundOrChosenOutput':True})
   if not dense or not bounded:raise ValueError('unbounded/nonadjacent alternative diagnostic')
  gaps.append({'id':gap['id'],'literalBlackEndpoints':[a,b],'chosenPathVertexCountIncludingEndpoints':len(path),'chosenPathNonBlackVertexCount':len(nonblack),'chosenPathEuclideanLengthPixels':sum(math.dist(u,v)for u,v in zip(path,path[1:])),'localStrictBlack8NeighborConnectionWithinEndpointBoxPlus14Pixels':False,'allNonBlackPixelsBlueDominant':True,'confidence':'low','inferredPathNotObservedBoundary':True,'alternativeDiagnostics':alternatives})
 if sorted(actual_nonblack)!=sorted(declared_nonblack)or len(actual_nonblack)!=20 or len(ring)!=366:raise ValueError('unlisted gap or source count differs')
 if trace['everyDenseVertexIsActualBlackSourcePixel']is not False or trace['manualSourceTextOverprintGapInferenceUsed']is not True or trace['absoluteAccuracyMeters']is not None or trace['usableForAddressAssignment']is not False:raise ValueError('explicit inference policy differs')
 record=trace['records'][0]
 if record['strictBlackSourceVertexCountIncludingClosure']!=len(ring)-len(actual_nonblack)or record['inferredNonBlackVertexCount']!=len(actual_nonblack)or record['areaSourcePixelsSquared']!=polygon.area:raise ValueError('source numeric record differs')
 failed=json.loads((COHORT/'exploratory-diagnostics/strict-trace-attempt.json').read_text())
 if failed['initialStrictTraceSucceeded']is not False or failed['initialScriptSha256']!=sha(COHORT/'exploratory-diagnostics/initial-strict-black-trace.py'):raise ValueError('failed strict-source attempt not pinned')
 pdf=fitz.open(COHORT/'source-pages158-160.pdf');prose=[' '.join(p.get_text().split())for p in pdf]
 if len(pdf)!=3:raise ValueError('source prose pages differ')
 info=next(x for x in pdf[0].get_image_info(xrefs=True)if(x['width'],x['height'])==(width,height))
 if hashlib.sha256(pdf.extract_image(info['xref'])['image']).hexdigest()!=trace['sourceImageSha256']:raise ValueError('archived PDF original image differs')
 for q in semantics['literalSourceQuotes']:
  if q['quote']not in prose[q['pdfPageOneBased']-158]:raise ValueError('source semantic quote differs')
 if not all(n in prose[0]for n in ['reptéri lakónegyedek','külső Rákócziváros','Kisfái és Parasztfőiskola']):raise ValueError('distinct source residential identity absent')
 samples=[('repteriResidentialSourceCellInterior',(1420,215),True),('airportAirfieldOutsideSmallCell',(1400,100),False),('broadSzolnokihegyInterior',(800,350),False),('economicSourceCellInterior',(1450,410),False),('kulsoRakoczivarosSourceCellInterior',(280,325),False)]
 cell_checks=[]
 for name,point,expected in samples:
  covered=polygon.covers(Point(*point))
  if covered!=expected:raise ValueError('source scope sample differs '+name)
  cell_checks.append({'diagnostic':name,'originalImagePixel':point,'insideProperSourceCell':covered,'notAGeographicControl':True})
 files=['figure75-p158-xref180.jpeg','source-pixel-trace.json','source-pixel-preview.png','75-repteri-grid.png','source-pages158-160.pdf','source-semantics.json','exploratory-diagnostics/strict-trace-attempt.json','exploratory-diagnostics/initial-strict-black-trace.py']
 result={'schemaVersion':1,'status':'PASS_AS_EXPLICIT_GAP_INFERRED_SOURCE_CANDIDATE_ONLY','independentOfSourceProducerCodeExecution':True,'producerSourceModuleImported':False,'sourceInputsSha256':{n:sha(COHORT/n)for n in files},'auditScriptSha256':sha(Path(__file__)),'sourceOriginalJpegPreservedInArchivedPdf':True,'sourceImageSize':[width,height],'sourceDenseVertexCountIncludingClosure':len(ring),'strictBlackVertexCountIncludingClosure':len(ring)-len(actual_nonblack),'nonBlackInferredVertexCount':len(actual_nonblack),'all20NonBlackVerticesListedInExactlyFourDeclaredGapPaths':True,'allSourceAndGapEdgesDense8Neighbor':True,'closedValidSourcePolygon':True,'sourceHoleCount':len(polygon.interiors),'sourceAreaSquarePixels':polygon.area,'minimumDistanceFromImageFramePixels':frame_distance,'frameClosureOrUnlistedGapDetected':False,'allFourArchivedSectionsRecomposeExactRing':True,'sourceContourFullyObserved':False,'sourceGaps':gaps,'failedStrictTraceAttemptPreservedAndHashed':True,'properSourceScopeSampleChecks':cell_checks,'semanticEvidence':{'sourcePdfPagesOneBased':[158,159,160],'printedPages':[156,157,158],'repteriResidentialSourceCellDistinctFromUmbrellaAirportAndEconomicCells':True,'mapLabelRepteriLakotelepAndProseRepteriLakonegyedScopeFormsPreserved':True,'kulsoRakoczivarosDistinctFromCentralRakoczivaros':True,'otherEconomicCellsNotRejectedForFunctionalUse':True,'noWholeSzolnokihegyShapeAssignedToMukertvaros':True},'visualReview':'Original Figure75, the source-pixel preview and original-pixel Reptéri grid were visually inspected. The selected compact quadrilateral follows the separately labeled residential cell. The airport, broad Szolnokihegy source cell, western Külső Rákócziváros and distinct economic cells are not substituted. Four short blue-label-overprinted intervals remain explicit low-confidence continuations.','primaryLayerApproved':False,'explicitInferredSourceCandidateSupported':True,'geographicRegistrationVerified':False,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,'rightsStatus':'Municipal consultation draft source-map open reuse rights unverified.','limits':['The four missing source intervals are low-confidence manual hypotheses with alternatives, not observed black strokes.','This source review does not validate geographic conversion, current exact neighborhood scope, legal/cadastral extent or absolute accuracy.','Alternative pixel paths are diagnostic hypotheses and not accuracy bounds.']}
 data=encode(result);target=OUT/'source-independent-review.json'
 if check:
  if target.read_bytes()!=data:raise ValueError('source independent review stale')
 else:target.write_bytes(data)
 print(json.dumps({k:result[k]for k in ['status','sourceDenseVertexCountIncludingClosure','strictBlackVertexCountIncludingClosure','nonBlackInferredVertexCount','sourceContourFullyObserved','minimumDistanceFromImageFramePixels']},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');review(p.parse_args().check)
