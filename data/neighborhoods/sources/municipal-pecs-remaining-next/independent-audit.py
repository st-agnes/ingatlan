#!/usr/bin/env python3
"""Independent pixel-face, restoration, projection and strict-topology audit.
No producer union/conversion implementation is imported or invoked.
"""
from pathlib import Path
import argparse,json,hashlib,math,subprocess,os,unicodedata
os.environ['PROJ_NETWORK']='OFF'
import fitz
import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import shape,Polygon,Point
from pyproj import Transformer
P=Path(__file__).resolve().parent
EXPECTED={'pecs-p63-density.jpeg':'08ec2a2ffe63222113424c7353ab502399b20b4e8d41f7262545ee4483283788','pecs-p48-names.jpeg':'75758682472a880dee3488068f324d3feb4ba916237de33d36734696ed1d78f8'}
FROZEN='3de4d89461e243563c5bd99d2bc33914f6ca059bdc97548e8f7ee0b41c968a95'
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
def load(n):return json.loads((P/n).read_text())
def enc(q):return json.dumps(q,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def ph(q):return hashlib.sha256(json.dumps(sorted(q),separators=(',',':')).encode()).hexdigest()
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.lower())if c.isalnum())
def faces(a,stroke):
 out=set();missing=0;touch=False
 for y,x in np.transpose(np.nonzero(a)).tolist():
  for xx,yy,p,q in [(x,y-1,(2*x-1,2*y-1),(2*x+1,2*y-1)),(x+1,y,(2*x+1,2*y-1),(2*x+1,2*y+1)),(x,y+1,(2*x-1,2*y+1),(2*x+1,2*y+1)),(x-1,y,(2*x-1,2*y-1),(2*x-1,2*y+1))]:
   inside=0<=xx<a.shape[1]and 0<=yy<a.shape[0]
   if inside and a[yy,xx]:continue
   if q<p:p,q=q,p
   out.add((*p,*q));touch|=not inside
   missing+=not inside or not stroke[yy,xx]
 return out,int(missing),touch

def ringfaces(g):
 assert g['type']=='Polygon';out=set();duplicates=0
 for ring in g['coordinates']:
  xy=np.asarray(ring)*2;assert np.array_equal(xy,np.rint(xy));xy=np.rint(xy).astype(int);assert np.all(xy%2==1)and np.array_equal(xy[0],xy[-1])
  for a,b in zip(xy[:-1],xy[1:]):
   delta=b-a;assert(delta[0]==0)!=(delta[1]==0);length=int(abs(delta[0])+abs(delta[1]));assert length>0 and length%2==0;step=np.sign(delta)*2
   for i in range(length//2):
    p,q=tuple(a+i*step),tuple(a+(i+1)*step)
    if q<p:p,q=q,p
    e=(*p,*q);duplicates+=e in out;out.add(e)
 return out,duplicates

def strict(fc):
 module=(P/'strict-validator-snapshot.mjs').as_uri();prog="import fs from 'node:fs';import {validateGeometry} from "+json.dumps(module)+";const f=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(f.features.map(x=>({id:x.id,name:x.properties.name,...validateGeometry(x.geometry)}))));"
 r=subprocess.run(['node','--input-type=module','-e',prog],input=json.dumps(fc),text=True,capture_output=True,check=True,cwd=P);return json.loads(r.stdout)

def audit():
 names=['source-inferred.geojson','conversion-proof.json','raw-pixel-cells.json','assignments.json','cartographic-hole-inventory.json','cartographic-hole-decisions.json','pecs-p63-density.jpeg','pecs-p48-names.jpeg','pecs-image-alignment.json','pecs-registration-northwest-only-diagnostic.json','first-cohort-exclusions.json','published-name-exclusions.json','strict-validator-snapshot.mjs','independent-audit.py','pecs-source-extraction-proof.json','pecs-source-selected-pages.pdf']
 name_review=load('independent-name-review.json');names+=['first-cohort-geometry-reference.geojson','first-cohort-assignments-reference.json','first-cohort-conversion-reference.json','independent-name-review.json','recovered-name-cell-review.json','semantic-source-review.json'];names+=sorted({c['path']for r in name_review['records']for c in r['nativeSourceCropEvidence']});paths=[P/n for n in names];before={q:sha(q)for q in paths};assert sha(P/'first-cohort-geometry-reference.geojson')==FROZEN
 for n,h in EXPECTED.items():assert sha(P/n)==h
 source_proof=load('pecs-source-extraction-proof.json');assert source_proof['originalPdfSha256']=='995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1';assert sha(P/source_proof['subsetPath'])==source_proof['subsetSha256'];excerpt=fitz.open(P/source_proof['subsetPath']);source_images=[]
 for page_number,image_name in [(48,'pecs-p48-names.jpeg'),(63,'pecs-p63-density.jpeg')]:
  page=excerpt[source_proof['subsetOriginalPagesOneBased'].index(page_number)];embedded=[excerpt.extract_image(v[0])['image']for v in page.get_images(full=True)];assert(P/image_name).read_bytes()in embedded;source_images.append({'originalPdfPageOneBased':page_number,'image':image_name,'sourceJpegSha256':sha(P/image_name),'archivedPdfExcerptImageByteIdentical':True,'matchesKnownOriginalEmbeddedImageHash':True})
 assert sha(P/'strict-validator-snapshot.mjs')=='abf1b564180d9b33593f9ce0d711eb996bf8f3a1d9cbb03b7527167ac515f3d7'
 fc,proof,raw,assign,decisions=map(load,['source-inferred.geojson','conversion-proof.json','raw-pixel-cells.json','assignments.json','cartographic-hole-decisions.json'])
 assert fc['status']=='estimated_geographic_placement_only'and proof['primaryApprovedCount']==0 and proof['placementVerified']is False
 assert len(fc['features'])==len(proof['records'])==len(raw['records'])==len(assign['records'])==27
 for v in proof['inputs']:assert sha(P/v['path'])==v['sha256']
 oldfc=load('first-cohort-geometry-reference.geojson');oldassign=load('first-cohort-assignments-reference.json')['records'];oldproof=load('first-cohort-conversion-reference.json');oldids={r['reviewedSourceComponentId']for r in oldassign};oldnames={norm(r['sourceName'])for r in oldassign}
 ids={r['reviewedSourceComponentId']for r in assign['records']};newnames={norm(r['sourceName'])for r in assign['records']};assert len(ids)==27 and not ids&oldids and not newnames&oldnames
 assert not newnames&{r['normalizedName']for r in load('published-name-exclusions.json')['records']}
 exclusions=load('first-cohort-exclusions.json');assert exclusions['frozenFirstGeometrySha256']==FROZEN and exclusions['frozenAssignmentSha256']==sha(P/'first-cohort-assignments-reference.json');assert{r['sourceCellId']for r in exclusions['records']}==oldids
 sourceimages={9:Image.open(P/'pecs-p48-names.jpeg').convert('RGB'),12:Image.open(P/'pecs-p63-density.jpeg').convert('RGB')};name_by_id={r['reviewedSourceComponentId']:r for r in name_review['records']};assert len(name_by_id)==27
 for named in name_review['records']:
  for crop in named['nativeSourceCropEvidence']:
   actual=Image.open(P/crop['path']).convert('RGB');expected=sourceimages[crop['figure']].crop(crop['sourcePixelBox']);assert actual.size==expected.size and actual.tobytes()==expected.tobytes()and sha(P/crop['path'])==crop['sha256']
 rgb=np.asarray(sourceimages[12],dtype=np.int64);stroke=((rgb.max(2)<200)&(rgb.max(2)-rgb.min(2)<110))|(rgb[:,:,0]<ndimage.median_filter(rgb[:,:,0],7)-16);labels,count=ndimage.label(~stroke,structure=np.array([[0,1,0],[1,1,1],[0,1,0]]));assert count==221
 byraw={r['sourceComponentId']:r for r in raw['records']};byproof={r['sourceCellId']:r for r in proof['records']};byassign={r['reviewedSourceComponentId']:r for r in assign['records']};approved={r['sourcePixelSetSha256']:r for r in decisions['records']};assert len(approved)==37
 a=np.asarray(load('pecs-image-alignment.json')['matrixNamesPixelsToDensityPixels']);b=np.asarray(load('pecs-registration-northwest-only-diagnostic.json')['matrixPixelToEov']);oldinputhashes={v['path']:v['sha256']for v in oldproof['inputs']};assert sha(P/'pecs-image-alignment.json')==oldinputhashes['pecs-image-alignment.json'];assert sha(P/'pecs-registration-northwest-only-diagnostic.json')==oldinputhashes['pecs-registration-northwest-only-diagnostic.json'];A=np.c_[a,[0.,0.,1.]];B=np.c_[b,[0.,0.,1.]];density_to_eov=np.linalg.inv(A)@B;t=Transformer.from_crs(23700,4326,always_xy=True)
 validations=strict(fc);assert len(validations)==27;js={r['id']:r for r in validations}
 oldrestored={tuple(p)for r in oldproof['records']for h in r['restorations']for p in h['pixels']};assert len(oldrestored)==1076
 oldall=np.isin(labels,list(oldids));
 for x,y in oldrestored:assert stroke[y,x];oldall[y,x]=True
 newall=np.zeros(labels.shape,dtype=bool);changedstroke=stroke.copy();allrestored=set();useddecisions=set();records=[];geoms=[];rawtotal=interpretedtotal=0
 for f in fc['features']:
  p=f['properties'];cid=p['sourceCellId'];r=byproof[cid];assignment=byassign[cid];assert p['name']==r['name']==assignment['sourceName']==byraw[cid]['sourceName'];sx,sy=assignment['verifiedDensityInteriorPixel'];assert labels[sy,sx]==cid
  named=name_by_id[cid];assert assignment==named and named['canUseUnchangedSourceCell']and named['sourceFigure9NameReadingIndependentlyChecked']and named['sourceFineShapeAndAdjacencyComparedToFigure12']
  included=labels==cid;assert ph([[int(x),int(y)]for y,x in np.transpose(np.nonzero(included))])==named['sourceComponentPixelSetSha256']
  assert not included[0].any()and not included[-1].any()and not included[:,0].any()and not included[:,-1].any()
  rawg=r['rawPixelCellGeometry'];assert rawg==byraw[cid]['pixelCellGeometry'];actual=shape(rawg);assert actual.is_valid and actual.area==int(included.sum())==r['rawPixelCount']==byraw[cid]['includedOriginalPixelCount'];saved,dup=ringfaces(rawg);exposed,missing,touch=faces(included,stroke);assert saved==exposed and not dup and not missing and not touch
  interpreted=included.copy();removed=set();restore_report=[];reported={h['sourcePixelSetSha256']:h for h in r['restorations']}
  for ring in actual.interiors:
   hole=Polygon(ring);x0,y0,x1,y1=hole.bounds;pix=[[x,y]for y in range(math.ceil(y0),math.floor(y1)+1)for x in range(math.ceil(x0),math.floor(x1)+1)if hole.contains(Point(x,y))];assert hole.area==len(pix);h=ph(pix);decision=approved[h];pr=reported[h];assert decision['restorationApproved']and decision['sourceComponentId']==cid;assert sorted(pr['pixels'])==sorted(pix)and pr['sourcePixelCount']==len(pix)and pr['classification']==decision['classification'];assert h not in useddecisions;useddecisions.add(h)
   for x,y in pix:
    assert stroke[y,x]and labels[y,x]==0 and(x,y)not in allrestored and(x,y)not in oldrestored;assert all(int(labels[yy,xx])in[0,cid]for xx,yy in[(x-1,y),(x+1,y),(x,y-1),(x,y+1)]);interpreted[y,x]=True;changedstroke[y,x]=False;allrestored.add((x,y))
   boundary,dup=ringfaces({'type':'Polygon','coordinates':[list(ring.coords)]});assert not dup;removed|=boundary;restore_report.append({'sourcePixelSetSha256':h,'pixelCount':len(pix),'classification':decision['classification'],'allOriginalMask':True,'otherMappedFreeCellContainedOrTouched':False})
  assert len(reported)==len(restore_report);igs=r['interpretedPixelCellGeometry'];g=shape(igs);assert g.is_valid and not g.interiors;outer,dup=ringfaces({'type':'Polygon','coordinates':[rawg['coordinates'][0]]});saved,dup2=ringfaces(igs);recomputed,missing,touch=faces(interpreted,stroke);assert saved==outer==recomputed==exposed-removed and not dup and not dup2 and not missing and not touch
  assert g.area==int(interpreted.sum())and int(interpreted.sum()-included.sum())==r['restoredSourcePixelCount']==p['cartographicRestoredPixelCount'];assert not np.any(newall&interpreted)and not np.any(oldall&interpreted);newall|=interpreted
  projected=[]
  for ring in igs['coordinates']:
   xy=np.asarray(ring);en=np.c_[xy,np.ones(len(xy))]@density_to_eov;lon,lat=t.transform(en[:,0],en[:,1]);projected.append(np.c_[lon,lat])
  actualworld=f['geometry'];assert actualworld['type']=='Polygon'and len(actualworld['coordinates'])==len(projected)==1;err=float(np.max(np.abs(np.asarray(actualworld['coordinates'][0])-projected[0])));assert err<1e-12;world=shape(actualworld);assert world.is_valid and not world.interiors;geoms.append(world)
  assert p['boundaryKind']=='inferred_area'and p['estimated']is True and p['canonicalNameIsNeighborhood']is False and p['sourceIsHardBoundary']is False and p['usableForAddressAssignment']is False and p['claimedAbsoluteAccuracyMetres']is None and p.get('claimedAbsoluteAccuracy')is None;assert p['georeferencingStatus']=='estimated_geographic_alignment_not_verified'and p['externalSourceOutlineChanged']is False and r['sourceImageEdgeClosureInvented']is False and r['geographicPlacementVerified']is False
  assert p['candidateBoundaryKind']=={'neighbourhood_source_candidate':'neighbourhood','planning_unit':'planning_unit','local_area':'local_area'}[assignment['semanticKind']]
  assert js[f['id']]['valid'];rawtotal+=len(exposed);interpretedtotal+=len(saved);records.append({'id':f['id'],'name':p['name'],'sourceCellId':cid,'originalIncludedPixelCount':int(included.sum()),'rawExposedUnitFaces':len(exposed),'rawFaceMismatchCount':0,'restoredExactOriginalPixelCount':int(interpreted.sum()-included.sum()),'restorations':restore_report,'interpretedExposedUnitFaces':len(saved),'interpretedFaceMismatchCount':0,'externalSourceFacesChanged':0,'residualHoles':0,'pixelOverlapWithOldOrOtherNewCells':0,'worldProjectionMaximumErrorDegrees':err,'geosValid':True,'strictJsValidation':js[f['id']],'geographicPlacementVerified':False,'primaryApproval':False})
 assert len(allrestored)==422 and len(useddecisions)==37 and not allrestored&oldrestored and not np.any(oldall&newall)
 after,n=ndimage.label(~changedstroke);assert n==221;correspondence=[]
 for i in range(1,222):
  j=np.unique(after[labels==i]);assert len(j)==1;correspondence.append(int(j[0]))
 assert len(set(correspondence))==221
 maxnew=max([geoms[i].intersection(g).area for i in range(len(geoms))for g in geoms[:i]]or[0]);oldworld=[shape(f['geometry'])for f in oldfc['features']];maxold=max(g.intersection(o).area for g in geoms for o in oldworld);assert maxnew<1e-16 and maxold<1e-16
 assert all(sha(q)==h for q,h in before.items())and sha(P/'first-cohort-geometry-reference.geojson')==FROZEN
 return {'schemaVersion':1,'reviewDate':'2026-11-14','reviewer':'Independent remaining_pixel_audit agent','verdict':'pass_source_pixels_transform_topology_inferred_only_zero_primary','scope':'Independent original mask/grid-face audit, exact cartographic restoration, frozen affine arithmetic, strict geometry, and disjointness with all 33 frozen first-cohort cells. Literal name semantics reviewed separately.','producerUnionOrTransformCodeImportedOrInvoked':False,'sourceFeatureCount':27,'candidateFineNames':sum(f['properties']['candidateBoundaryKind']=='neighbourhood'for f in fc['features']),'candidatePlanningUnits':sum(f['properties']['candidateBoundaryKind']=='planning_unit'for f in fc['features']),'candidateLocalAreas':sum(f['properties']['candidateBoundaryKind']=='local_area'for f in fc['features']),'sourceImages':source_images,'originalFreeCellCount':221,'allRawExposedFacesAdjacentOriginalMask':True,'allSourceContoursClosedInsideRaster':True,'freeCellCountAfterExplicitRestoration':221,'freeCellMappingRemainsOneToOne':True,'totalRawExposedUnitFaces':rawtotal,'totalInterpretedExposedUnitFaces':interpretedtotal,'allRawAndInterpretedFaceSetsIndependentlyVerified':True,'independentLiteralNameReviewAssignmentsAndPixelHashesMatched':True,'allNameReviewNativeCropsPixelExact':True,'restoredHoleCount':37,'restoredExactOriginalPixelCount':422,'externalSourceFacesChanged':0,'sourceImageEdgeClosureInvented':False,'strictJsValidCount':sum(r['valid']for r in validations),'strictJsRejectedCount':sum(not r['valid']for r in validations),'newCellsPixelOverlapWithFrozen33':0,'newRestorePixelOverlapWithFrozen1076RestoredPixels':0,'maximumNewNewWorldOverlapDegreesSquared':maxnew,'maximumNewFrozenWorldOverlapDegreesSquared':maxold,'frozenFirstGeometrySha256':FROZEN,'frozenFirstGeometryHashUnchanged':True,'independentHomogeneousDensityToEovMatrix':density_to_eov.tolist(),'geographicPlacementVerified':False,'primaryApprovedCount':0,'claimedAbsoluteAccuracy':None,'claimedAbsoluteAccuracyMetres':None,'usableForAddressAssignment':False,'networkUsed':False,'producerFilesModified':False,'inputFingerprints':[{'path':q.name,'sha256':before[q]}for q in paths],'frozenComparisonInputs':[{'path':q.name,'sha256':sha(q)}for q in [P/'first-cohort-geometry-reference.geojson',P/'first-cohort-assignments-reference.json',P/'first-cohort-conversion-reference.json']],'records':records}

def main():
 a=argparse.ArgumentParser();a.add_argument('--check',action='store_true');a.add_argument('--write-report',action='store_true');args=a.parse_args();out=audit();text=enc(out);target=P/'independent-pixel-review.json'
 if args.check:assert target.read_text()==text
 else:target.write_text(text)
 print(enc({k:out[k]for k in ['verdict','sourceFeatureCount','strictJsValidCount','restoredHoleCount','restoredExactOriginalPixelCount','newCellsPixelOverlapWithFrozen33','maximumNewNewWorldOverlapDegreesSquared','maximumNewFrozenWorldOverlapDegreesSquared','claimedAbsoluteAccuracy']}))
if __name__=='__main__':main()
