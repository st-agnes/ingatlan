#!/usr/bin/env python3
"""Freeze the manually inspected exact 37 source-pixel hole sets only."""
from pathlib import Path
import json,hashlib,os
os.environ['PROJ_NETWORK']='OFF'
import numpy as np
from PIL import Image
from scipy import ndimage
P=Path(__file__).resolve().parent;F=P.parent/'municipal-pecs-first-inferred'
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
def enc(q):return json.dumps(q,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
pre=json.loads((P/'remaining-pixel-preflight.json').read_text());im=Image.open(F/'pecs-p63-density.jpeg').convert('RGB');rgb=np.asarray(im,dtype=np.int64)
mask=((rgb.max(2)<200)&(rgb.max(2)-rgb.min(2)<110))|(rgb[:,:,0]<ndimage.median_filter(rgb[:,:,0],7)-16);labels,n=ndimage.label(~mask);assert n==221
caption={(50,1):(85,'V','V character in the original Roman planning-area caption'),(50,2):(12,'V','Period at the original V. planning-area caption'),(48,0):(169,'VI','Original VI. planning-area caption'),(105,0):(110,'X','Original X. planning-area caption'),(95,1):(12,'VII','Period of the VII. caption which lies to the right of its final vertical stroke')}
records=[];restored=mask.copy();used=set()
for cell in pre['records']:
 for h in cell['holes']:
  cid=cell['sourceComponentId'];key=(cid,h['holeIndex']);count=h['originalSourcePixelCount'];pix=h['pixels'];assert h['allPixelsOriginalMask']and not h['otherFreeCellIdsContained']and not h['otherFreeCellIdsSideAdjacent']
  if key in caption:
   expected,roman,part=caption[key];assert count==expected
   classification='original_roman_planning_caption_graphics';finding=part+'. Independently inspected in original nearest-neighbour source crop/contact; the black glyph or period has the regular printed caption form, not an enclosed geographic boundary. Exact mask pixels only; no permission to alter caption strokes connected to the external contour.'
  else:
   assert count in [1,2];roman=None;classification='one_or_two_pixel_local_contrast_or_jpeg_mask_artifact';finding='Independently inspected in original nearest-neighbour source crop/contact. This exact one/two-pixel spot follows the surrounding rendered mapped fill or edge antialias texture and has no separately enclosed geographic contour or independent free-source cell. It is a mask classification artifact, not evidence of an enclave.'
  for x,y in pix:
   assert (x,y)not in used and mask[y,x]and labels[y,x]==0;used.add((x,y));restored[y,x]=False
   assert all(int(labels[yy,xx])in [0,cid]for xx,yy in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)])
  records.append({'sourceComponentId':cid,'sourceNameAtReview':cell['sourceName'],'rawHoleIndexAtReview':h['holeIndex'],'sourcePixelSetSha256':h['pixelSetSha256'],'sourcePixelCount':count,'sourcePixelCellBounds':h['pixelCellBounds'],'classification':classification,'originalRomanLabel':roman,'restorationApproved':True,'reviewFinding':finding,'sourceCropNativeImage':h['nativeCrop'],'sourceCropSha256':h['nativeCropSha256'],'noOtherFreeSourceCellContained':True,'noOtherFreeSourceCellSideAdjacent':True,'onlyPixelSideInterpretationAllowed':True,'externalSourceEdgesMayChange':False,'geographicClippingBufferingOrRepairAuthorised':False})
after,k=ndimage.label(~restored);assert k==221;maps=[]
for i in range(1,n+1):
 j=np.unique(after[labels==i]);assert len(j)==1;maps.append(int(j[0]))
assert len(set(maps))==221
out={'schemaVersion':1,'reviewer':'Independent remaining_pixel_audit agent','reviewDate':'2026-11-14','sourceImageSha256':sha(F/'pecs-p63-density.jpeg'),'scope':'Explicit manual review of these exact 37 source pixel-hole sets for the remaining 27 Pecs cells only. Raw cell geometry retained separately; no geographic accuracy, current legal footprint or name semantics approval.','reviewedContactSheets':pre['contactSheets'],'additionalRomanContext':{'path':'independent-uszogi-roman-context.png','sourcePixelBox':[625,515,730,590],'nearestNeighbourScale':8,'sha256':sha(P/'independent-uszogi-roman-context.png')},'allEnumeratedRawHolePixelsOriginalMask':True,'otherMappedFreeSourceCellsSwallowed':0,'otherMappedFreeSourceCellsSideAdjacent':0,'decisionsAreNotGenericPermissionForUnreviewedFutureHoles':True,'records':records,'summary':{'holeCount':len(records),'restoredExactOriginalSourcePixelCount':len(used),'oneOrTwoPixelArtifactHoleCount':sum(r['classification'].startswith('one_or_two')for r in records),'romanCaptionHoleCount':sum(r['classification'].startswith('original_roman')for r in records),'freeCellCountBefore':n,'freeCellCountAfter':k,'originalFreeCellMappingRemainsOneToOne':True},'interpretationLimit':'Only these exact SHA-identified source mask pixels may be restored; all source external faces must remain unchanged and be independently checked on resulting output. No arbitrary closure, edge movement, snap, repair or fill is approved.','claimedAbsoluteAccuracy':None,'usableForAddressAssignment':False,'networkUsed':False}
assert out['summary']['holeCount']==37 and len(used)==422 and out['summary']['oneOrTwoPixelArtifactHoleCount']==32 and out['summary']['romanCaptionHoleCount']==5
(P/'cartographic-hole-decisions.json').write_text(enc(out));print(enc(out['summary']))
