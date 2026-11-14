#!/usr/bin/env python3
"""Independent original-pixel boundary inventory. Does not import producer code."""
from pathlib import Path
import json,hashlib,math,os
os.environ['PROJ_NETWORK']='OFF'
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy import ndimage
from shapely.geometry import LineString,Point,Polygon,mapping
from shapely.ops import polygonize
P=Path(__file__).resolve().parent;F=P.parent/'municipal-pecs-first-inferred';N=P.parent/'municipal-pecs-next'
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
def enc(q):return json.dumps(q,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def ph(q):return hashlib.sha256(json.dumps(sorted(q),separators=(',',':')).encode()).hexdigest()
def exposed(a):
 edges=set();missing=0;touch=False
 for y,x in np.transpose(np.nonzero(a)).tolist():
  for xx,yy,p,q in [(x,y-1,(2*x-1,2*y-1),(2*x+1,2*y-1)),(x+1,y,(2*x+1,2*y-1),(2*x+1,2*y+1)),(x,y+1,(2*x-1,2*y+1),(2*x+1,2*y+1)),(x-1,y,(2*x-1,2*y-1),(2*x-1,2*y+1))]:
   inside=0<=xx<a.shape[1]and 0<=yy<a.shape[0]
   if inside and a[yy,xx]:continue
   if q<p:p,q=q,p
   edges.add((*p,*q))
   if not inside:touch=True
   if not inside or not stroke[yy,xx]:missing+=1
 return edges,missing,touch
old=json.loads((F/'assignments.json').read_text())['records'];allrows=json.loads((N/'pecs-independent-name-cell-review.json').read_text())['records'];oldnames={r['sourceName']for r in old};oldids={r['reviewedSourceComponentId']for r in old};rows=[r for r in allrows if r['sourceName']not in oldnames and r.get('canUseUnchangedSourceCell')]
assert len(rows)==27 and not(oldids&{r['reviewedSourceComponentId']for r in rows})
im=Image.open(F/'pecs-p63-density.jpeg').convert('RGB');rgb=np.array(im,dtype=np.int64);stroke=((rgb.max(2)<200)&(rgb.max(2)-rgb.min(2)<110))|(rgb[:,:,0]<ndimage.median_filter(rgb[:,:,0],size=7)-16)
labels,count=ndimage.label(~stroke,structure=np.array([[0,1,0],[1,1,1],[0,1,0]]));assert count==221
crops=P/'independent-hole-crops';crops.mkdir(exist_ok=True)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15)
records=[];contact=[];index=[];holes_total=0
for row in rows:
 cid=row['reviewedSourceComponentId'];sx,sy=row['verifiedDensityInteriorPixel'];assert labels[sy,sx]==cid
 a=labels==cid;faces,missing,touch=exposed(a);lines=[LineString([(x0/2,y0/2),(x1/2,y1/2)])for x0,y0,x1,y1 in faces];polys=list(polygonize(lines));chosen=[p for p in polys if p.contains(Point(sx,sy))]
 assert len(chosen)==1,(cid,len(chosen));poly=chosen[0];assert poly.area==int(a.sum()),(cid,poly.area,a.sum())
 record={'sourceName':row['sourceName'],'sourceComponentId':cid,'seedPixel':[sx,sy],'originalIncludedPixelCount':int(a.sum()),'exposedUnitFaceCount':len(faces),'exposedFaceAdjacentOriginalMaskFailures':missing,'touchesImageEdge':touch,'polygonValid':poly.is_valid,'pixelAreaMatchesExactly':True,'pixelCellGeometry':mapping(poly),'holes':[]}
 for hi,ring in enumerate(poly.interiors):
  hole=Polygon(ring);x0,y0,x1,y1=hole.bounds;pixels=[[x,y]for y in range(math.ceil(y0),math.floor(y1)+1)for x in range(math.ceil(x0),math.floor(x1)+1)if hole.contains(Point(x,y))];assert len(pixels)==hole.area
  other=sorted({int(labels[y,x])for x,y in pixels if labels[y,x]not in [0,cid]});neighbours=sorted({int(labels[ny,nx])for x,y in pixels for nx,ny in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]if labels[ny,nx]not in [0,cid]})
  classification='one_pixel_mask_spot_requires_visual_review'if len(pixels)==1 else 'multi_pixel_hole_requires_explicit_source_graphics_or_extent_review'
  box=(max(0,math.floor(x0)-4),max(0,math.floor(y0)-4),min(im.width,math.ceil(x1)+5),min(im.height,math.ceil(y1)+5));native=im.crop(box);nativepath=crops/f'cell-{cid}-hole-{hi}-native.png';native.save(nativepath)
  scale=max(2,min(14,280//max(native.size)));zoom=native.resize((native.width*scale,native.height*scale),Image.Resampling.NEAREST)
  tile=Image.new('RGB',(max(330,zoom.width),zoom.height+43),'white');tile.paste(zoom,(0,43));dr=ImageDraw.Draw(tile);dr.text((3,2),f'{row["sourceName"]} / {cid} hole{hi}',font=font,fill='black');dr.text((3,22),f'{len(pixels)} px | box {box}',font=font,fill='black')
  contact.append(tile)
  hrec={'holeIndex':hi,'originalSourcePixelCount':len(pixels),'pixelSetSha256':ph(pixels),'pixelCellBounds':list(hole.bounds),'pixels':pixels,'allPixelsOriginalMask':all(bool(stroke[y,x])for x,y in pixels),'otherFreeCellIdsContained':other,'otherFreeCellIdsSideAdjacent':neighbours,'preflightClassification':classification,'restorationApproved':False,'nativeCrop':str(nativepath.relative_to(P)),'nativeCropSourcePixelBox':list(box),'nativeCropSha256':sha(nativepath)}
  record['holes'].append(hrec);index.append({'cell':cid,'name':row['sourceName'],'hole':hi,'pixelCount':len(pixels),'bounds':list(hole.bounds),'other':other,'neighbours':neighbours});holes_total+=1
 records.append(record)
# Contact pages use fixed rows so every small graphics hole can be inspected.
paths=[]
for k in range(0,len(contact),24):
 subset=contact[k:k+24];width=4*max(t.width for t in subset);rowheights=[max(t.height for t in subset[j:j+4])for j in range(0,len(subset),4)];sheet=Image.new('RGB',(width,sum(rowheights)),'#dedede');y=0
 for j,rh in zip(range(0,len(subset),4),rowheights):
  for col,tile in enumerate(subset[j:j+4]):sheet.paste(tile,(col*(width//4),y))
  y+=rh
 name=f'independent-holes-contact-{k//24+1}.png';sheet.save(P/name);paths.append({'path':name,'sha256':sha(P/name),'holeIndicesInOrderedInventory':[k,min(k+24,len(contact))]})
report={'schemaVersion':1,'reviewDate':'2026-11-14','scope':'Independent original source-mask cells and exposed grid-face polygonization preflight. No author union implementation imported; no pixel restoration, transform, repair or new geographic geometry.','sourceInputs':[{'path':str(q.relative_to(P.parent.parent.parent.parent)),'sha256':sha(q)}for q in [F/'pecs-p63-density.jpeg',F/'assignments.json',N/'pecs-independent-name-cell-review.json']],'sourceMask':'(maxRGB<200 and maxRGB-minRGB<110) OR R<median_filter(R,7)-16','freeCellConnectivity':4,'originalFreeCellCount':int(count),'candidateCellCount':len(records),'candidateCellsDisjointFromFrozenIds':True,'originalRawHoleCount':holes_total,'originalRawHolePixelCount':sum(h['originalSourcePixelCount']for r in records for h in r['holes']),'holesContainingOtherFreeCellCount':sum(bool(h['otherFreeCellIdsContained'])for r in records for h in r['holes']),'holesSideAdjacentOtherFreeCellCount':sum(bool(h['otherFreeCellIdsSideAdjacent'])for r in records for h in r['holes']),'allCandidatesClosedWithinSourceRaster':all(not r['touchesImageEdge']for r in records),'allExposedFacesAdjacentOriginalMask':all(not r['exposedFaceAdjacentOriginalMaskFailures']for r in records),'records':records,'contactSheets':paths,'holeIndex':index,'restorationDecisionsAreNotYetApproved':True,'claimedAbsoluteAccuracy':None,'geographicPlacementVerified':False,'primaryApproval':False,'networkUsed':False}
(P/'remaining-pixel-preflight.json').write_text(enc(report));print(enc({k:report[k]for k in ['candidateCellCount','originalRawHoleCount','originalRawHolePixelCount','holesContainingOtherFreeCellCount','holesSideAdjacentOtherFreeCellCount','allCandidatesClosedWithinSourceRaster','allExposedFacesAdjacentOriginalMask']}));print(enc(index))
