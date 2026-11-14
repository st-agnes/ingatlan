#!/usr/bin/env python3
"""Additional observed Pecs raster cells with unchanged, explicitly unverified placement."""
from pathlib import Path
import argparse,json,hashlib,math,os,unicodedata
os.environ['PROJ_NETWORK']='OFF'
import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import Polygon,Point,box,shape,mapping
from shapely.ops import unary_union,transform
from pyproj import Transformer
P=Path(__file__).resolve().parent
URL='https://logoweb.pecs.hu/download/koncepcio/ITS.pdf';PDFSHA='995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1'
def read(n):return json.loads((P/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encode(d):return json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.lower())if c.isalnum())
def phash(p):return hashlib.sha256(json.dumps(sorted(p),separators=(',',':')).encode()).hexdigest()
def cells(region):
 rects=[]
 for y in np.flatnonzero(region.any(1)):
  r=np.r_[False,region[y],False];e=np.flatnonzero(r[1:]!=r[:-1]);rects.extend(box(float(x)-.5,float(y)-.5,float(z)-.5,float(y)+.5)for x,z in zip(e[::2],e[1::2]))
 g=unary_union(rects);assert g.geom_type=='Polygon'and g.is_valid
 return g

def raw_build():
 rgb=np.array(Image.open(P/'pecs-p63-density.jpeg').convert('RGB')).astype(int);stroke=((rgb.max(2)<200)&(rgb.max(2)-rgb.min(2)<110))|(rgb[:,:,0]<ndimage.median_filter(rgb[:,:,0],size=7)-16);labels,n=ndimage.label(~stroke)
 excluded=read('first-cohort-exclusions.json');excludedids={r['sourceCellId']for r in excluded['records']};excludednames={norm(r['sourceName'])for r in excluded['records']}|{r['normalizedName']for r in read('published-name-exclusions.json')['records']};assign=read('provisional-remaining-assignments.json')['records'];records=[];holes=[];seen=set()
 for r in assign:
  cid=r['reviewedSourceComponentId'];seed=r['verifiedDensityInteriorPixel'];name=r['sourceName'];assert cid not in excludedids|seen and norm(name)not in excludednames;seen.add(cid);assert int(labels[seed[1],seed[0]])==cid
  reg=labels==cid;assert not(reg[0].any()or reg[-1].any()or reg[:,0].any()or reg[:,-1].any());g=cells(reg);assert g.area==reg.sum();y,x=np.nonzero(reg)
  records.append({'sourceName':name,'sourceComponentId':cid,'verifiedInteriorPixel':seed,'includedOriginalPixelCount':int(reg.sum()),'bboxPixelCenters':[int(x.min()),int(y.min()),int(x.max()),int(y.max())],'pixelCellGeometry':mapping(g),'touchesImageEdge':False})
  for i,ring in enumerate(g.interiors):
   h=Polygon(ring);a,b,c,d=h.bounds;pts=[[x,y]for y in range(math.ceil(b),math.floor(d)+1)for x in range(math.ceil(a),math.floor(c)+1)if h.contains(Point(x,y))];other=sorted({int(labels[y,x])for x,y in pts if labels[y,x]not in (0,cid)})
   holes.append({'sourceName':name,'sourceComponentId':cid,'rawHoleIndex':i,'sourcePixelSetSha256':phash(pts),'sourcePixelCount':len(pts),'sourcePixelBounds':list(h.bounds),'pixels':pts,'allPixelsAreOriginalMask':all(stroke[y,x]for x,y in pts),'otherFreeSourceCellIdsContained':other,'otherFreeSourceCellIdsSideAdjacent':sorted({int(labels[ny,nx])for x,y in pts for nx,ny in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]if labels[ny,nx]not in (0,cid)})})
 return stroke,labels,{'schemaVersion':1,'sourceImage':'pecs-p63-density.jpeg','sourceImageSha256':sha(P/'pecs-p63-density.jpeg'),'sourceMask':'(maxRGB<200 and maxRGB-minRGB<110) OR R<median_filter(R,7)-16','fourConnectedFreeCellCount':int(n),'firstCohortSourceCellIdsExcluded':sorted(excludedids),'records':records},{'schemaVersion':1,'sourceImageSha256':sha(P/'pecs-p63-density.jpeg'),'scope':'Exact internal original-cell voids; inventory is not restoration approval.','records':holes}

def full_build(stroke,labels,raw,hole_inventory):
 assignments=read('assignments.json')['records'];byraw={r['sourceComponentId']:r for r in raw['records']};approvals=read('cartographic-hole-decisions.json');assert approvals['sourceImageSha256']==sha(P/'pecs-p63-density.jpeg');bydecision={r['sourcePixelSetSha256']:r for r in approvals['records']};holes={}
 for r in hole_inventory['records']:holes.setdefault(r['sourceComponentId'],[]).append(r)
 a=np.array(read('pecs-image-alignment.json')['matrixNamesPixelsToDensityPixels']);b=np.array(read('pecs-registration-northwest-only-diagnostic.json')['matrixPixelToEov']);inv=np.linalg.inv(a[:2]);to_geo=Transformer.from_crs(23700,4326,always_xy=True)
 def geo(x,y,z=None):
  nx=(x-a[2,0])*inv[0,0]+(y-a[2,1])*inv[1,0];ny=(x-a[2,0])*inv[0,1]+(y-a[2,1])*inv[1,1]
  return to_geo.transform(nx*b[0,0]+ny*b[1,0]+b[2,0],nx*b[0,1]+ny*b[1,1]+b[2,1])
 features=[];proof=[];restoredtotal=0
 for r in assignments:
  cid=r['reviewedSourceComponentId'];name=r['sourceName'];original=shape(byraw[cid]['pixelCellGeometry']);reg=labels==cid;interpreted=reg.copy();restore=[]
  for h in holes.get(cid,[]):
   dec=bydecision.get(h['sourcePixelSetSha256'])
   if not dec or not dec['restorationApproved']:continue
   assert dec['sourceComponentId']==cid and h['allPixelsAreOriginalMask']and not h['otherFreeSourceCellIdsContained']and not h['otherFreeSourceCellIdsSideAdjacent']
   xs,ys=np.array(h['pixels']).T;interpreted[ys,xs]=True;restoredtotal+=len(xs);restore.append({'sourcePixelSetSha256':h['sourcePixelSetSha256'],'sourcePixelCount':len(xs),'classification':dec['classification'],'pixels':h['pixels']})
  pixel=cells(interpreted);assert Polygon(original.exterior).equals(Polygon(pixel.exterior));world=transform(geo,pixel);assert world.is_valid
  kind={'neighbourhood_source_candidate':'neighbourhood','planning_unit':'planning_unit','local_area':'local_area'}[r['semanticKind']]
  props={'name':name,'municipality':'Pécs','boundaryKind':'inferred_area','candidateBoundaryKind':kind,'estimated':True,'canonicalNameIsNeighborhood':False,'sourceContourIsObserved':True,'sourceCellId':cid,'sourceNameEvidence':r,'cartographicRestoredPixelCount':sum(h['sourcePixelCount']for h in restore),'residualSourceHoleCount':len(pixel.interiors),'externalSourceOutlineChanged':False,'georeferencingStatus':'estimated_geographic_alignment_not_verified','georeferencingIsApproximate':True,'claimedAbsoluteAccuracyMetres':None,'claimedAbsoluteAccuracy':None,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,'reviewStatus':'estimated_candidate_not_verified','sourcePeriod':'2021 municipal ITS publication;2011 census figures,2014 map-production annotation; original boundary survey date unknown','method':'Additional actual closed original Figure12 pixel cell, named by independent literal Figure9 label/shape review. Only explicitly reviewed exact cartographic void pixels may be restored; raw cell retained and outer boundary unchanged. Frozen first-cohort Figure12-to-Figure9 and northwestern-perimeter EOV placement reused as unverified estimate. No new georeferencing, footprint invention, repair, clipping, snap, buffer, image-edge closure or constituent cloning.','evidenceUrls':[URL],'sourceDocuments':[{'url':URL,'sha256':PDFSHA,'pdfPageOneBased':63,'printedPage':56,'figure':12},{'url':URL,'sha256':PDFSHA,'pdfPageOneBased':48,'printedPage':41,'figure':9}],'placementUncertainty':'Same explicitly unverified northwest-only placement as frozen first cohort. Later checks do not approve absolute registration; no absolute error radius asserted.','license':'Municipal map reuse rights unverified; ODbL for archived OSM calibration evidence.'}
  features.append({'type':'Feature','id':'pecs-remaining:'+norm(name),'geometry':mapping(world),'properties':props});proof.append({'name':name,'sourceCellId':cid,'sourceInteriorSeedPixel':r['verifiedDensityInteriorPixel'],'rawPixelCount':int(reg.sum()),'restoredSourcePixelCount':int(interpreted.sum()-reg.sum()),'rawPixelCellGeometry':mapping(original),'interpretedPixelCellGeometry':mapping(pixel),'restorations':restore,'allExternalSourceEdgesUnchanged':True,'sourceImageEdgeClosureInvented':False,'residualSourceHoles':len(pixel.interiors),'worldGeometryValid':world.is_valid,'geographicPlacementVerified':False})
 for i,f in enumerate(features):
  for g in features[:i]:assert shape(f['geometry']).intersection(shape(g['geometry'])).area<1e-16
 names=['pecs-p63-density.jpeg','pecs-p48-names.jpeg','assignments.json','raw-pixel-cells.json','cartographic-hole-decisions.json','pecs-image-alignment.json','pecs-registration-northwest-only-diagnostic.json','first-cohort-exclusions.json','published-name-exclusions.json']
 return {'type':'FeatureCollection','status':'estimated_geographic_placement_only','claimedAbsoluteAccuracy':None,'features':features},{'schemaVersion':1,'sourceCellCount':len(features),'candidateFineNames':sum(f['properties']['candidateBoundaryKind']=='neighbourhood'for f in features),'candidatePlanningUnits':sum(f['properties']['candidateBoundaryKind']=='planning_unit'for f in features),'candidateLocalAreas':sum(f['properties']['candidateBoundaryKind']=='local_area'for f in features),'primaryApprovedCount':0,'placementVerified':False,'claimedAbsoluteAccuracyMetres':None,'sourceMask':raw['sourceMask'],'allSourceCellCount':raw['fourConnectedFreeCellCount'],'cartographicRestorationPixelCount':restoredtotal,'inputs':[{'path':n,'sha256':sha(P/n)}for n in names],'records':proof}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--raw-only',action='store_true');a=ap.parse_args();stroke,labels,raw,holes=raw_build();outputs={'raw-pixel-cells.json':raw,'cartographic-hole-inventory.json':holes}
 if not a.raw_only:
  fc,pr=full_build(stroke,labels,raw,holes);outputs.update({'source-inferred.geojson':fc,'conversion-proof.json':pr})
 for n,d in outputs.items():
  s=encode(d)
  if a.check:assert(P/n).read_text()==s,n
  else:(P/n).write_text(s)
 print(json.dumps({'rawCells':len(raw['records']),'rawHoles':len(holes['records']),'rawOnly':a.raw_only,'check':a.check}))
if __name__=='__main__':main()
