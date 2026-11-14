#!/usr/bin/env python3
"""Independent mixed-source final-gap audit; no producer code is imported/invoked."""
from pathlib import Path
import argparse,hashlib,json,math,os,subprocess,unicodedata
os.environ['PROJ_NETWORK']='OFF'
import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import Polygon,Point,shape
from pyproj import Transformer
P=Path(__file__).resolve().parent
EXPECTED={'pecs-p48-names.jpeg':'75758682472a880dee3488068f324d3feb4ba916237de33d36734696ed1d78f8','pecs-p63-density.jpeg':'08ec2a2ffe63222113424c7353ab502399b20b4e8d41f7262545ee4483283788'}
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
def read(n):return json.loads((P/n).read_text())
def enc(q):return json.dumps(q,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def jhash(q):return hashlib.sha256(json.dumps(q,separators=(',',':')).encode()).hexdigest()
def ph(q):return jhash(sorted(q))
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.lower())if c.isalnum())
def mask_faces(region,stroke):
 edges=set();missing=0;edge=False
 for y,x in np.transpose(np.nonzero(region)).tolist():
  for nx,ny,a,b in [(x,y-1,(2*x-1,2*y-1),(2*x+1,2*y-1)),(x+1,y,(2*x+1,2*y-1),(2*x+1,2*y+1)),(x,y+1,(2*x-1,2*y+1),(2*x+1,2*y+1)),(x-1,y,(2*x-1,2*y-1),(2*x-1,2*y+1))]:
   valid=0<=nx<region.shape[1]and 0<=ny<region.shape[0]
   if valid and region[ny,nx]:continue
   if b<a:a,b=b,a
   edges.add((*a,*b));edge|=not valid;missing+=not valid or not stroke[ny,nx]
 return edges,int(missing),edge

def grid_faces(g):
 assert g['type']=='Polygon';edges=set();duplicate=0
 for ring in g['coordinates']:
  q=np.asarray(ring)*2;assert np.array_equal(q,np.rint(q));q=np.rint(q).astype(int);assert np.all(q%2==1)and np.array_equal(q[0],q[-1])
  for a,b in zip(q[:-1],q[1:]):
   delta=b-a;assert(delta[0]==0)!=(delta[1]==0);length=int(abs(delta[0])+abs(delta[1]));assert length>0 and length%2==0;step=np.sign(delta)*2
   for i in range(length//2):
    x,y=tuple(a+i*step),tuple(a+(i+1)*step)
    if y<x:x,y=y,x
    e=(*x,*y);duplicate+=e in edges;edges.add(e)
 return edges,duplicate

def cross(a,b,c):return(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def on(a,b,p):return cross(a,b,p)==0 and min(a[0],b[0])<=p[0]<=max(a[0],b[0])and min(a[1],b[1])<=p[1]<=max(a[1],b[1])
def intersect(a,b,c,d):
 p,q,r,s=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
 if ((p>0 and q<0)or(p<0 and q>0))and((r>0 and s<0)or(r<0 and s>0)):return True
 return(p==0 and on(a,b,c))or(q==0 and on(a,b,d))or(r==0 and on(c,d,a))or(s==0 and on(c,d,b))
def manual_path_check(path):
 assert path[0]==path[-1]and len({tuple(p)for p in path[:-1]})==len(path)-1
 for a,b in zip(path[:-1],path[1:]):assert max(abs(a[0]-b[0]),abs(a[1]-b[1]))==1
 N=len(path)-1
 for i in range(N):
  for j in range(i+1,N):
   if j==i+1 or(i==0 and j==N-1):continue
   assert not intersect(path[i],path[i+1],path[j],path[j+1]),(i,j)
 twice=sum(a[0]*b[1]-a[1]*b[0]for a,b in zip(path[:-1],path[1:]));assert twice!=0
 return abs(twice)/2

def strict(fc):
 text="import fs from 'node:fs';import {validateGeometry} from "+json.dumps((P/'strict-validator-snapshot.mjs').as_uri())+";let f=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(f.features.map(x=>({id:x.id,name:x.properties.name,...validateGeometry(x.geometry)}))));"
 r=subprocess.run(['node','--input-type=module','-e',text],input=json.dumps(fc),text=True,capture_output=True,check=True,cwd=P);return json.loads(r.stdout)

def audit():
 base=['source-inferred.geojson','conversion-proof.json','central-raw-pixel-cells.json','central-cell-cartographic-hole-decisions.json','central-cells-raw-pixel-evidence.json','independent-kisbalokany-siklosi-name-review.json','manual-islands-author-paths.json','independent-manual-islands-review.json','manual-hatched-stroke-candidates.json','independent-manual-hatched-review.json','pecs-p48-names.jpeg','pecs-p63-density.jpeg','pecs-image-alignment.json','pecs-registration-northwest-only-diagnostic.json','first-source-inferred.geojson','remaining-source-inferred.geojson','first-conversion-proof.json','remaining-conversion-proof.json','admitted-cohort-exclusions.json','strict-validator-snapshot.mjs','independent-final-gap-audit.py']
 nameqa=read('independent-kisbalokany-siklosi-name-review.json');islandqa=read('independent-manual-islands-review.json');hatchqa=read('independent-manual-hatched-review.json')
 extra={c['path']for r in nameqa['records']for c in r['nativeCropEvidence']}
 extra|={c['path']for r in hatchqa['records']for c in r['evidenceFiles']}
 extra|={r[k]['path']for r in islandqa['records']for k in ['nativePixelGridEvidence','pathOverlayEvidence']}
 paths=[P/n for n in sorted(set(base)|extra)];hashes={q:sha(q)for q in paths}
 for n,h in EXPECTED.items():assert sha(P/n)==h
 assert sha(P/'first-source-inferred.geojson')=='3de4d89461e243563c5bd99d2bc33914f6ca059bdc97548e8f7ee0b41c968a95'
 assert sha(P/'strict-validator-snapshot.mjs')=='abf1b564180d9b33593f9ce0d711eb996bf8f3a1d9cbb03b7527167ac515f3d7'
 fc,proof,raw=map(read,['source-inferred.geojson','conversion-proof.json','central-raw-pixel-cells.json']);assert len(fc['features'])==len(proof['records'])==len(proof['sourceNativeContourRecords'])==5
 assert fc['status']=='estimated_geographic_placement_only'and fc['claimedAbsoluteAccuracy']is None and proof['primaryApprovedCount']==0 and proof['geographicPlacementVerified']is False and proof['newGeographicModelFitted']is False
 excluded=read('admitted-cohort-exclusions.json');assert len(excluded['records'])==60
 for h in excluded['frozenSourceGeometryInputs']:assert sha(P/h['path'])==h['sha256']
 oldfc=read('first-source-inferred.geojson')['features']+read('remaining-source-inferred.geojson')['features'];assert len(oldfc)==60
 oldproofs=[read('first-conversion-proof.json'),read('remaining-conversion-proof.json')];oldnative=[r['interpretedPixelCellGeometry']for d in oldproofs for r in d['records']];assert len(oldnative)==60
 oldids={r['sourceCellId']for r in excluded['records']};oldnames={norm(r['sourceName'])for r in excluded['records']};assert not oldids&{89,92};assert not oldnames&{norm(f['properties']['name'])for f in fc['features']}
 # Same frozen source12->source9 and source9->EOV frame; independently compose matrices.
 A=np.c_[np.asarray(read('pecs-image-alignment.json')['matrixNamesPixelsToDensityPixels']),[0.,0.,1.]];B=np.c_[np.asarray(read('pecs-registration-northwest-only-diagnostic.json')['matrixPixelToEov']),[0.,0.,1.]];D=np.linalg.inv(A)@B
 for oldp in oldproofs:
  oldhash={v['path']:v['sha256']for v in oldp['inputs']}
  assert sha(P/'pecs-image-alignment.json')==oldhash['pecs-image-alignment.json'];assert sha(P/'pecs-registration-northwest-only-diagnostic.json')==oldhash['pecs-registration-northwest-only-diagnostic.json']
 t=Transformer.from_crs(23700,4326,always_xy=True)
 ims={9:Image.open(P/'pecs-p48-names.jpeg').convert('RGB'),12:Image.open(P/'pecs-p63-density.jpeg').convert('RGB')};rgb={k:np.asarray(v,dtype=int)for k,v in ims.items()};a=rgb[12];stroke=((a.max(2)<200)&(a.max(2)-a.min(2)<110))|(a[:,:,0]<ndimage.median_filter(a[:,:,0],7)-16);labels,n=ndimage.label(~stroke);assert n==221
 named={r['reviewedSourceComponentId']:r for r in nameqa['records']};originals={r['sourceCellId']:r for r in raw['records']};approvals={r['sourcePixelSetSha256']:r for r in read('central-cell-cartographic-hole-decisions.json')['records']};assert len(approvals)==3
 for r in nameqa['records']:
  for c in r['nativeCropEvidence']:
   actual=Image.open(P/c['path']).convert('RGB');expected=ims[c['figure']].crop(c['sourcePixelBox']);assert actual.size==expected.size and actual.tobytes()==expected.tobytes()and sha(P/c['path'])==c['sha256']
 for r in hatchqa['records']:
  for c in r['evidenceFiles']:assert sha(P/c['path'])==c['sha256']
 for r in islandqa['records']:
  for k in ['nativePixelGridEvidence','pathOverlayEvidence']:assert sha(P/r[k]['path'])==r[k]['sha256']
 pby={r['name']:r for r in proof['records']};nby={r['sourceName']:r for r in proof['sourceNativeContourRecords']};validations=strict(fc);assert len(validations)==5 and all(v['valid']for v in validations);jby={v['id']:v for v in validations}
 oldrestored={tuple(p)for d in oldproofs for r in d['records']for h in r['restorations']for p in h['pixels']};assert len(oldrestored)==1498
 oldsource=[shape(g)for g in oldnative];oldworld=[shape(f['geometry'])for f in oldfc];sourcegeoms=[];worldgeoms=[];records=[];used=set();manual_count=free_count=0;rawfacecount=interpretedfacecount=0
 for f in fc['features']:
  props=f['properties'];name=props['name'];r=pby[name];native=nby[name];g=native['nativePixelGeometry'];poly=shape(g);assert poly.is_valid and not poly.interiors and r['nativePixelGeometry']==g;figure=native['sourceFigure'];assert sha(P/native['sourceImage'])==native['sourceImageSha256']==EXPECTED[native['sourceImage']];assert native['sourceQuarterWholeExtentApproved']and props['sourceQuarterWholeExtentApproved'];assert props['sourceContourAuthority']==native['sourceContourAuthority']and props['sourceContourType']==native['method']and props['sourceNameEvidence']==native['sourceNameEvidence'];method=native['method'];details={}
  if method=='original_closed_figure12_free_cell_with_exact_approved_internal_spots':
   free_count+=1;cid=native['sourceCellId'];assert cid in [89,92];namer=named[cid];assert native['sourceNameEvidence']==namer and namer['canUseUnchangedSourceCell']and namer['sourceFigure9NameReadingIndependentlyChecked']and namer['sourceFineShapeAndAdjacencyComparedToFigure12'];seed=namer['verifiedDensityInteriorPixel'];assert labels[seed[1],seed[0]]==cid
   region=labels==cid;pix=[[int(x),int(y)]for y,x in np.transpose(np.nonzero(region))];assert ph(pix)==namer['sourceComponentPixelSetSha256'];rawg=originals[cid]['rawPixelCellGeometry'];rawpoly=shape(rawg);assert rawpoly.area==len(pix)==native['rawPixelCount'];faces,miss,edge=mask_faces(region,stroke);saved,dup=grid_faces(rawg);assert faces==saved and not miss and not edge and not dup;interpret=region.copy();removed=set();restore=[]
   for ring in rawpoly.interiors:
    hole=Polygon(ring);x0,y0,x1,y1=hole.bounds;points=[[x,y]for y in range(math.ceil(y0),math.floor(y1)+1)for x in range(math.ceil(x0),math.floor(x1)+1)if hole.contains(Point(x,y))];h=ph(points);d=approvals[h];assert d['restorationApproved']and d['sourceComponentId']==cid and len(points)==d['sourcePixelCount']==1
    for x,y in points:
     assert stroke[y,x]and labels[y,x]==0 and(x,y)not in used and(x,y)not in oldrestored;assert all(int(labels[ny,nx])in[0,cid]for nx,ny in[(x-1,y),(x+1,y),(x,y-1),(x,y+1)]);used.add((x,y));interpret[y,x]=True
    hfaces,dup=grid_faces({'type':'Polygon','coordinates':[list(ring.coords)]});assert not dup;removed|=hfaces;restore.append(h)
   actual,miss,edge=mask_faces(interpret,stroke);saved,dup=grid_faces(g);outer,_=grid_faces({'type':'Polygon','coordinates':[rawg['coordinates'][0]]});assert saved==actual==outer==faces-removed and not miss and not edge and not dup;assert poly.area==int(interpret.sum());assert int(interpret.sum()-region.sum())==native['restoredOriginalPixelCount']==props['cartographicRestoredPixelCount'];assert g==originals[cid]['interpretedPixelCellGeometry'];rawfacecount+=len(faces);interpretedfacecount+=len(saved);details={'sourceCellId':cid,'rawIncludedOriginalPixels':len(pix),'restoredOriginalMaskPixels':int(interpret.sum()-region.sum()),'rawUnitFaceCount':len(faces),'interpretedUnitFaceCount':len(saved),'externalSourceFaceChanges':0,'rawAndInterpretedFaceSetsIndependentlyVerified':True,'independentLiteralNameShapeReviewMatched':True}
  else:
   assert method=='manual_closed_original_graphic_stroke_pixel_centres';manual_count+=1;path=native['literalStrokePixelPath'];assert g['coordinates']==[path]and jhash(path)==native['strokePixelPathSha256'];area=manual_path_check(path);assert poly.area==area;assert all(0<x<ims[figure].width-1 and 0<y<ims[figure].height-1 for x,y in path)
   if figure==9:
    assert name=='M utca';authority=next(q for q in islandqa['records']if q['sourceName']==name);assert authority['completeLiteralSourceContourCertified']and authority['sourceContourApprovedForInferredDerivation']and authority['sourceQuarterMapWholeFineUnitIdentitySupported']and authority['allOuterGraphicStrokeVerticesIndependentlyApproved']and not authority['pendingStrokeVertexIndices'];assert authority['path']==path and authority['approvedPixelGeometry']==g and authority['sourcePixelPathSha256']==jhash(path)
    assert len(authority['vertexReviews'])in[len(path),len(path)-1];assert native['sourceNameEvidence']['sourceLabelAnchorPixel']==authority['sourceLabelAnchorPixel']and native['sourceNameEvidence']['wholeFineUnitEvidence']==authority['sourceWholeUnitIdentityEvidence']
    for vertex,(x,y)in zip(authority['vertexReviews'],path):assert vertex['sourcePixel']==[x,y]and vertex['literalOriginalRgbMatches']and vertex['independentOuterStrokeAssessment']=='supported_original_outer_graphic_stroke'and vertex['originalRgb']==rgb[9][y,x].tolist()
    boundary_whole_evidence=authority['sourceWholeUnitIdentityEvidence'];assert area==18.5
   else:
    assert name in ['Murom','Köztemető'];authority=next(q for q in hatchqa['records']if q['sourceName']==name);candidate=next(q for q in read('manual-hatched-stroke-candidates.json')['records']if q['sourceName']==name);assert authority['sourceWholeFineUnitIdentitySupported']and authority['allBoundarySectorsVisuallyApproved']and authority['completeLiteralSourceContourCertified']and authority['sourceContourApprovedForInferredDerivation'];assert authority['sourcePixelPath']==path and authority['approvedPixelGeometry']==g and authority['sourcePixelPathSha256']==jhash(path);assert candidate['sourcePixelPath']==path
    assert all(q['matchesActualOuterGraphicBoundary']and not q['usesInternalHatchAsShortcut']and not q['unselectedBlankBridgeObserved']for q in authority['boundarySectorReviews']);assert len(authority['boundarySectorReviews'])==len(native['sourceSegmentProvenance'])
    assert len(path)==len(authority['allPathOriginalRgb']);assert native['sourceNameEvidence']==authority
    for (x,y),v in zip(path,authority['allPathOriginalRgb']):assert stroke[y,x]and rgb[12][y,x].tolist()==v
    chain=[]
    for seg in native['sourceSegmentProvenance']:
     pts=seg['literalOriginalStrokePixels'];assert pts[0]==seg['start']and pts[-1]==seg['end'];assert not chain or chain[-1]==pts[0];chain.extend(pts if not chain else pts[1:])
    assert chain==path;inside_ids=set();outside_expected=0
    x0,y0,x1,y1=poly.bounds
    for y in range(math.ceil(y0),math.floor(y1)+1):
     for x in range(math.ceil(x0),math.floor(x1)+1):
      if poly.contains(Point(x,y))and labels[y,x]:inside_ids.add(int(labels[y,x]))
    assert inside_ids==set(native['sourceComponentIdsWithinManualContour'])and not inside_ids&oldids
    for cid in inside_ids:
     yy,xx=np.nonzero(labels==cid);assert all(poly.covers(Point(int(x),int(y)))for y,x in zip(yy,xx))
    boundary_whole_evidence=authority['nameAndWholeShapeVisualEvidence']+' '+authority['source12OuterBoundaryVisualEvidence'];assert not authority['imageEdgeOrCropClosureInvented']
   details={'sourceFigure':figure,'literalOrderedPathVertexCountIncludingClosure':len(path),'manualPixelCenterRingArea':area,'allPathVerticesLiteralOriginalRgbChecked':True,'allConsecutiveStepsOriginal8Neighbour':True,'simpleRingIndependentlyCheckedByIntegerDeterminants':True,'orderedPathExactlyMatchesPeerApprovedFullContour':True,'wholeFineBoundaryAuthorityEvidence':boundary_whole_evidence,'wholeFineBoundaryApprovedBeyondMaskMembership':True,'sourceImageOrCropClosureInvented':False,'pixelRestorationOrMaskModificationUsed':False}
  density_rings=[];world_rings=[];matrix=D if figure==12 else B
  for ring in g['coordinates']:
   xy=np.asarray(ring,dtype=float);hom=np.c_[xy,np.ones(len(xy))];den=hom if figure==12 else hom@A;density_rings.append(den[:,:2].tolist());en=hom@matrix;lon,lat=t.transform(en[:,0],en[:,1]);world_rings.append(np.c_[lon,lat])
  actual_density=r['densityFramePixelGeometry'];assert actual_density['type']=='Polygon'and len(actual_density['coordinates'])==1;density_error=float(np.max(np.abs(np.asarray(actual_density['coordinates'][0])-np.asarray(density_rings[0]))));assert density_error<1e-12
  actualworld=f['geometry'];assert actualworld['type']=='Polygon'and len(actualworld['coordinates'])==1;error=float(np.max(np.abs(np.asarray(actualworld['coordinates'][0])-world_rings[0])));assert error<1e-12;world=shape(actualworld);density_poly=shape(actual_density);assert world.is_valid and not world.interiors and density_poly.is_valid;sourcegeoms.append(density_poly);worldgeoms.append(world)
  assert props['boundaryKind']=='inferred_area'and props['candidateBoundaryKind']=='neighbourhood'and props['estimated']is True and props['canonicalNameIsNeighborhood']is False and props['sourceContourIsObserved']is True and props['sourceIsHardBoundary']is False and props['sourceIsOfficial']is False and props['usableForAddressAssignment']is False and props['claimedAbsoluteAccuracy']is None and props['claimedAbsoluteAccuracyMetres']is None and props['externalSourceOutlineChanged']is False
  assert props['georeferencingStatus']=='frozen_first_cohort_estimated_geographic_alignment_not_verified'and r['geographicPlacementVerified']is False
  records.append({'name':name,'id':f['id'],'sourceMethod':method,**details,'nativeSourceGeometryArea':poly.area,'independentDensityFrameMaximumVertexDifferencePixels':density_error,'independentProjectionMaximumVertexDifferenceDegrees':error,'strictJsValidation':jby[f['id']],'geographicPlacementVerified':False,'primaryApproval':False,'claimedAbsoluteAccuracy':None})
 assert free_count==2 and manual_count==3 and len(used)==3
 newnew_source=max(sourcegeoms[i].intersection(g).area for i in range(5)for g in sourcegeoms[:i]);newold_source=max(g.intersection(o).area for g in sourcegeoms for o in oldsource);newnew_world=max(worldgeoms[i].intersection(g).area for i in range(5)for g in worldgeoms[:i]);newold_world=max(g.intersection(o).area for g in worldgeoms for o in oldworld)
 assert newnew_source==newold_source==newnew_world==newold_world==0.0
 assert all(sha(q)==h for q,h in hashes.items())
 return {'schemaVersion':1,'reviewDate':'2026-11-14','reviewer':'Independent remaining_pixel_audit agent','verdict':'pass_five_observed_source_contours_inferred_only_zero_primary','scope':'Independent separate face audits for two original free cells and literal ordered-path/RGB/full-boundary-authority audits for three manual source contours, projection, strict geometry and all60 admitted-source overlap checks. No producer code imported or invoked.','sourceFeatureCount':5,'originalFreeCellContourCount':2,'manualWholeStrokeContourCount':3,'candidateFineNames':5,'primaryApprovedCount':0,'originalFigure12FreeCellCount':221,'approvedRestoredOriginalMaskPixels':3,'totalFreeCellRawUnitFaces':rawfacecount,'totalFreeCellInterpretedUnitFaces':interpretedfacecount,'freeCellExternalSourceFaceChanges':0,'strictJsValidCount':5,'strictJsRejectedCount':0,'independentWholeFineBoundaryReviewCheckedForEveryManualPath':True,'allAuthorityAndNameReviewNativeCropHashesVerified':True,'allCentralNameReviewNativeCropsOriginalPixelExact':True,'newNewDensityFrameMaximumOverlapPixelsSquared':newnew_source,'newAdmitted60DensityFrameMaximumOverlapPixelsSquared':newold_source,'newNewWorldMaximumOverlapDegreesSquared':newnew_world,'newAdmitted60WorldMaximumOverlapDegreesSquared':newold_world,'oldAdmittedReferenceCount':60,'oldAdmittedReferenceHashesUnchanged':True,'independentHomogeneousDensityToEovMatrix':D.tolist(),'frozenSourceMatricesByteIdenticalToBothAdmittedCohorts':True,'anyNewGeoreferenceModelFitted':False,'sourceMembershipOrInternalRmsUsedAsAbsoluteAccuracyEvidence':False,'footprintCreatedByMaskIntersectionSubtractionComplementClippingOrRepair':False,'sourceImageOrCropClosingEdgeInvented':False,'geographicPlacementVerified':False,'claimedAbsoluteAccuracy':None,'claimedAbsoluteAccuracyMetres':None,'usableForAddressAssignment':False,'networkUsed':False,'producerFilesModified':False,'inputFingerprints':[{'path':q.name,'sha256':h}for q,h in hashes.items()],'records':records}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--write-report',action='store_true');args=ap.parse_args();result=audit();text=enc(result);target=P/'independent-final-gap-review.json'
 if args.check:assert target.read_text()==text
 else:target.write_text(text)
 print(enc({k:result[k]for k in ['verdict','sourceFeatureCount','originalFreeCellContourCount','manualWholeStrokeContourCount','strictJsValidCount','approvedRestoredOriginalMaskPixels','newAdmitted60DensityFrameMaximumOverlapPixelsSquared','newAdmitted60WorldMaximumOverlapDegreesSquared','claimedAbsoluteAccuracy']}))
