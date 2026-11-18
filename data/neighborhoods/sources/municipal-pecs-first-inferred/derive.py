#!/usr/bin/env python3
"""Frozen first Pécs batch: observed raster outlines, estimated geographic placement."""
from pathlib import Path
import argparse,hashlib,json,math,unicodedata
import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import shape,box,Polygon,Point,mapping
from shapely.ops import unary_union,transform
from pyproj import Transformer
P=Path(__file__).resolve().parent
URL='https://logoweb.pecs.hu/download/koncepcio/ITS.pdf'
SOURCE_PDF_SHA='995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1'

def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read(n):return json.loads((P/n).read_text())
def encoded(o):return json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.lower()) if c.isalnum())
def pixel_hash(points):return hashlib.sha256(json.dumps(sorted(points),separators=(',',':')).encode()).hexdigest()
def cells(mask):
 rectangles=[]
 for y in np.flatnonzero(mask.any(1)):
  row=np.r_[False,mask[y],False];e=np.flatnonzero(row[1:]!=row[:-1]);rectangles.extend(box(float(a)-.5,float(y)-.5,float(b)-.5,float(y)+.5) for a,b in zip(e[::2],e[1::2]))
 g=unary_union(rectangles)
 if g.geom_type!='Polygon' or not g.is_valid:raise ValueError('Invalid original source-cell union')
 return g

def build():
 rgb=np.asarray(Image.open(P/'pecs-p63-density.jpeg').convert('RGB')).astype(int);mask=((rgb.max(2)<200)&(rgb.max(2)-rgb.min(2)<110))|(rgb[:,:,0]<ndimage.median_filter(rgb[:,:,0],size=7)-16);labels,n=ndimage.label(~mask)
 raw={r['sourceComponentId']:r for r in read('raw-pixel-cells.json')['records']};assignments=read('assignments.json')['records'];decisions=read('pecs-cartographic-hole-decisions.json');assert decisions['sourceImageSha256']==sha(P/'pecs-p63-density.jpeg');by_hole={r['sourcePixelSetSha256']:r for r in decisions['records']};a=np.array(read('pecs-image-alignment.json')['matrixNamesPixelsToDensityPixels']);b=np.array(read('pecs-registration-northwest-only-diagnostic.json')['matrixPixelToEov']);inv=np.linalg.inv(a[:2]);to_geo=Transformer.from_crs(23700,4326,always_xy=True)
 def geographic(x,y,z=None):
  nx=(x-a[2,0])*inv[0,0]+(y-a[2,1])*inv[1,0];ny=(x-a[2,0])*inv[0,1]+(y-a[2,1])*inv[1,1]
  return to_geo.transform(nx*b[0,0]+ny*b[1,0]+b[2,0],nx*b[0,1]+ny*b[1,1]+b[2,1])
 features=[];proof=[];restored_total=0;seen=set()
 for r in assignments:
  cid=r['reviewedSourceComponentId'];name=r['sourceName'];assert cid not in seen;seen.add(cid);seed=r['verifiedDensityInteriorPixel'];assert int(labels[seed[1],seed[0]])==cid
  region=labels==cid;assert not(region[0].any() or region[-1].any() or region[:,0].any() or region[:,-1].any());raw_polygon=shape(raw[cid]['pixelCellGeometry']);assert cells(region).equals(raw_polygon);interpreted=region.copy();restorations=[]
  for ring in raw_polygon.interiors:
   hole=Polygon(ring);x0,y0,x1,y1=hole.bounds;pixels=[[x,y] for y in range(math.ceil(y0),math.floor(y1)+1) for x in range(math.ceil(x0),math.floor(x1)+1) if hole.contains(Point(x,y))];h=pixel_hash(pixels);decision=by_hole[h];assert decision['restorationApproved'] and decision['sourceComponentId']==cid;xs,ys=np.array(pixels,dtype=int).T;assert mask[ys,xs].all() and not labels[ys,xs].any()
   for x,y in pixels:
    assert all(int(labels[ny,nx]) in (0,cid) for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)))
   interpreted[ys,xs]=True;restorations.append({'sourcePixelSetSha256':h,'pixels':pixels,'classification':decision['classification'],'originalRomanLabel':decision['originalRomanLabel']});restored_total+=len(pixels)
  pixel=cells(interpreted);assert not pixel.interiors;assert Polygon(raw_polygon.exterior).symmetric_difference(pixel).area==0;world=transform(geographic,pixel);assert world.is_valid
  kind='planning_unit' if r['semanticKind']=='planning_unit' else 'neighbourhood'
  props={'name':name,'municipality':'Pécs','boundaryKind':'inferred_area','candidateBoundaryKind':kind,'estimated':True,'canonicalNameIsNeighborhood':False,'sourceContourIsObserved':True,'sourceCellId':cid,'sourceNameEvidence':r,'cartographicRestoredPixelCount':sum(len(h['pixels']) for h in restorations),'externalSourceOutlineChanged':False,'georeferencingStatus':'estimated_geographic_alignment_not_verified','georeferencingIsApproximate':True,'claimedAbsoluteAccuracyMetres':None,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,'reviewStatus':'estimated_candidate_not_verified','sourcePeriod':'2021 municipal ITS publication;2011 census figures,2014 map-production annotation; original boundary survey date unknown','method':'Actual closed fine source-cell outer outline from original Figure12 raster, named by independent literal Figure9 label/shape review. Only exact independently approved one-pixel classification artifacts and Roman caption glyphs restored at source-pixel stage; raw cells retained. Every external source edge unchanged. Geographic placement is explicitly estimated: frozen Figure12→Figure9 affine registration then northwestern gray-perimeter-based EOV transform, not independently validated ground control. No repair, clipping, buffer, invented closing edge, current-name-point-derived extent or constituent polygon cloning.','evidenceUrls':[URL],'sourceDocuments':[{'url':URL,'sha256':SOURCE_PDF_SHA,'pdfPageOneBased':63,'printedPage':56,'figure':12},{'url':URL,'sha256':SOURCE_PDF_SHA,'pdfPageOneBased':48,'printedPage':41,'figure':9}],'placementUncertainty':'The northwestern fit extrapolates toward the southeast. Independent later source-perimeter checks disagree by up to about350m; this is not an accuracy certificate. Road-control investigation is outside this frozen batch.','license':'Municipal map reuse rights unverified; ODbL for archived OSM calibration evidence.'}
  features.append({'type':'Feature','id':'pecs-first:'+norm(name),'geometry':mapping(world),'properties':props});proof.append({'name':name,'sourceCellId':cid,'sourceInteriorSeedPixel':seed,'rawPixelCount':int(region.sum()),'restoredSourcePixelCount':int(interpreted.sum()-region.sum()),'rawPixelCellGeometry':mapping(raw_polygon),'interpretedPixelCellGeometry':mapping(pixel),'restorations':restorations,'allExternalSourceEdgesUnchanged':True,'sourceImageEdgeClosureInvented':False,'worldGeometryValid':world.is_valid,'geographicPlacementVerified':False})
 assert len(features)==33 and len(seen)==33 and restored_total==1076
 for i,f in enumerate(features):
  for other in features[:i]:assert shape(f['geometry']).intersection(shape(other['geometry'])).area<1e-16
 names=['pecs-p63-density.jpeg','pecs-p48-names.jpeg','assignments.json','raw-pixel-cells.json','pecs-cartographic-hole-decisions.json','pecs-image-alignment.json','pecs-registration-northwest-only-diagnostic.json'];inputs=[{'path':name,'sha256':sha(P/name)} for name in names]
 return {'type':'FeatureCollection','status':'estimated_geographic_placement_only','features':features},{'schemaVersion':1,'frozenBatch':True,'sourceCellCount':33,'candidateFineNames':32,'candidatePlanningUnits':1,'primaryApprovedCount':0,'placementVerified':False,'usableForAddressAssignment':False,'sourceImageSha256':sha(P/'pecs-p63-density.jpeg'),'sourceMask':'(maxRGB<200 and maxRGB-minRGB<110) OR R<median_filter(R,7)-16','allSourceCellCount':int(n),'cartographicRestorationPixelCount':restored_total,'inputs':inputs,'records':proof}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();fc,pr=build()
 for name,v in {'source-inferred.geojson':fc,'conversion-proof.json':pr}.items():
  t=encoded(v)
  if args.check:assert(P/name).read_text()==t,name
  else:(P/name).write_text(t)
 print(encoded({'features':33,'candidateFineNames':32,'candidatePlanningUnits':1,'primary':0,'placementVerified':False,'check':args.check}))
if __name__=='__main__':main()
