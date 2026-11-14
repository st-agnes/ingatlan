#!/usr/bin/env python3
"""Observed source-cell and explicitly approved manual-stroke gap contours; inferred placement only."""
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
def load(n):return json.loads((P/n).read_text())
def sha(n):return hashlib.sha256((P/n).read_bytes()).hexdigest()
def enc(d):return json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.lower())if c.isalnum())
def ph(q):return hashlib.sha256(json.dumps(sorted(q),separators=(',',':')).encode()).hexdigest()
def pathhash(q):return hashlib.sha256(json.dumps(q,separators=(',',':')).encode()).hexdigest()
def cells(a):
 r=[]
 for y in np.flatnonzero(a.any(1)):
  z=np.r_[False,a[y],False];e=np.flatnonzero(z[1:]!=z[:-1]);r.extend(box(float(x)-.5,float(y)-.5,float(b)-.5,float(y)+.5)for x,b in zip(e[::2],e[1::2]))
 g=unary_union(r);assert g.geom_type=='Polygon'and g.is_valid
 return g

def build():
 rgb=np.array(Image.open(P/'pecs-p63-density.jpeg').convert('RGB')).astype(int);stroke=((rgb.max(2)<200)&(rgb.max(2)-rgb.min(2)<110))|(rgb[:,:,0]<ndimage.median_filter(rgb[:,:,0],7)-16);labels,n=ndimage.label(~stroke);assert n==221
 first=load('admitted-cohort-exclusions.json');oldids={r['sourceCellId']for r in first['records']};oldnames={r['sourceName']for r in first['records']};names=load('independent-kisbalokany-siklosi-name-review.json')['records'];holes=load('central-cell-cartographic-hole-decisions.json');approved={r['sourcePixelSetSha256']:r for r in holes['records']};native=[];rawcells=[]
 for r in names:
  cid=r['reviewedSourceComponentId'];name=r['sourceName'];seed=r['verifiedDensityInteriorPixel'];assert cid not in oldids and name not in oldnames and int(labels[seed[1],seed[0]])==cid;reg=labels==cid;g=cells(reg);assert g.area==reg.sum();interpreted=reg.copy();restorations=[]
  for ring in g.interiors:
   hole=Polygon(ring);a,b,c,d=hole.bounds;pixels=[[x,y]for y in range(math.ceil(b),math.floor(d)+1)for x in range(math.ceil(a),math.floor(c)+1)if hole.contains(Point(x,y))];h=ph(pixels);dec=approved[h];assert dec['restorationApproved']and dec['sourceComponentId']==cid
   assert all(stroke[y,x]and labels[y,x]==0 and all(labels[yy,xx]in(0,cid)for xx,yy in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)])for x,y in pixels)
   for x,y in pixels:interpreted[y,x]=True
   restorations.append({'sourcePixelSetSha256':h,'pixels':pixels,'classification':dec['classification']})
  final=cells(interpreted);assert not final.interiors and Polygon(g.exterior).equals(final);assert not(reg[0].any()or reg[-1].any()or reg[:,0].any()or reg[:,-1].any())
  rawcells.append({'sourceName':name,'sourceCellId':cid,'rawOriginalPixelCount':int(reg.sum()),'rawPixelCellGeometry':mapping(g),'interpretedPixelCellGeometry':mapping(final),'restorations':restorations,'externalSourceEdgesChanged':False})
  native.append({'sourceName':name,'sourceCellId':cid,'method':'original_closed_figure12_free_cell_with_exact_approved_internal_spots','sourceFigure':12,'sourcePdfPageOneBased':63,'sourceImage':'pecs-p63-density.jpeg','sourceImageSha256':sha('pecs-p63-density.jpeg'),'nativePixelGeometry':mapping(final),'sourceNameEvidence':r,'sourceContourAuthority':'independent-kisbalokany-siklosi-name-review.json','rawPixelCount':int(reg.sum()),'restoredOriginalPixelCount':sum(len(h['pixels'])for h in restorations),'sourceQuarterWholeExtentApproved':True})
 islands=load('independent-manual-islands-review.json')
 for r in islands['records']:
  if not r['sourceContourApprovedForInferredDerivation']:continue
  assert r['sourceName']=='M utca'and r['completeLiteralSourceContourCertified']and r['simpleRingIndependentlyVerified'];g=shape(r['approvedPixelGeometry']);assert g.is_valid and g.area==r['sourcePixelCenterRingArea']
  native.append({'sourceName':r['sourceName'],'sourceCellId':None,'sourceManualTraceId':'figure9-M-utca-original-stroke-centres','method':'manual_closed_original_graphic_stroke_pixel_centres','sourceFigure':9,'sourcePdfPageOneBased':48,'sourceImage':'pecs-p48-names.jpeg','sourceImageSha256':sha('pecs-p48-names.jpeg'),'nativePixelGeometry':r['approvedPixelGeometry'],'literalStrokePixelPath':r['path'],'strokePixelPathSha256':pathhash(r['path']),'sourceNameEvidence':{'sourceLabelAnchorPixel':r['sourceLabelAnchorPixel'],'wholeFineUnitEvidence':r['sourceWholeUnitIdentityEvidence']},'sourceContourAuthority':'independent-manual-islands-review.json','sourceQuarterWholeExtentApproved':True,'sourceGraphicReadingLimit':'Selected representative path within thick rasterized original graphic; no surveyed/subpixel precision or error bound asserted.'})
 manual=load('manual-hatched-stroke-candidates.json');review=load('independent-manual-hatched-review.json');byqa={r['sourceName']:r for r in review['records']}
 for r in manual['records']:
  qa=byqa[r['sourceName']];assert qa['sourceContourApprovedForInferredDerivation'];g=shape(r['pixelGeometry']);assert g.is_valid and not g.interiors and r['allPathPixelsAreOriginalDeclaredStroke']and r['allSuccessivePathPixels8Adjacent']and not r['repeatedNonClosingVertices']and not r['otherFreeCellIdsInside']
  native.append({'sourceName':r['sourceName'],'sourceCellId':None,'sourceComponentIdsWithinManualContour':[int(x)for x in r['expectedFragmentCoverage']],'sourceManualTraceId':'figure12-'+norm(r['sourceName'])+'-original-stroke-centres','method':'manual_closed_original_graphic_stroke_pixel_centres','sourceFigure':12,'sourcePdfPageOneBased':63,'sourceImage':'pecs-p63-density.jpeg','sourceImageSha256':sha('pecs-p63-density.jpeg'),'nativePixelGeometry':r['pixelGeometry'],'literalStrokePixelPath':r['sourcePixelPath'],'strokePixelPathSha256':pathhash(r['sourcePixelPath']),'sourceSegmentProvenance':r['sourceSegmentProvenance'],'sourceNameEvidence':qa,'sourceContourAuthority':'independent-manual-hatched-review.json','sourceQuarterWholeExtentApproved':True,'sourceGraphicReadingLimit':'Manual representative route through actual thick original outer-stroke pixels; junction/printing-width ambiguity unquantified. Thematic hatch strokes remain interior and are not treated as quarter separators.'})
 assert len(native)==5 and not({r['sourceName']for r in native}&oldnames)
 A=np.array(load('pecs-image-alignment.json')['matrixNamesPixelsToDensityPixels']);B=np.array(load('pecs-registration-northwest-only-diagnostic.json')['matrixPixelToEov']);inv=np.linalg.inv(A[:2]);t=Transformer.from_crs(23700,4326,always_xy=True)
 def density_names(x,y):return ((x-A[2,0])*inv[0,0]+(y-A[2,1])*inv[1,0],(x-A[2,0])*inv[0,1]+(y-A[2,1])*inv[1,1])
 def names_geo(x,y,z=None):return t.transform(x*B[0,0]+y*B[1,0]+B[2,0],x*B[0,1]+y*B[1,1]+B[2,1])
 def density_geo(x,y,z=None):return names_geo(*density_names(x,y))
 def names_density(x,y,z=None):return (x*A[0,0]+y*A[1,0]+A[2,0],x*A[0,1]+y*A[1,1]+A[2,1])
 features=[];proof=[]
 for r in native:
  g=shape(r['nativePixelGeometry']);world=transform(names_geo if r['sourceFigure']==9 else density_geo,g);density=transform(names_density,g)if r['sourceFigure']==9 else g;assert world.is_valid and not world.interiors
  props={'name':r['sourceName'],'municipality':'Pécs','boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','estimated':True,'canonicalNameIsNeighborhood':False,'sourceContourIsObserved':True,'sourceContourType':r['method'],'sourceCellId':r['sourceCellId'],'sourceManualTraceId':r.get('sourceManualTraceId'),'sourceComponentIdsWithinManualContour':r.get('sourceComponentIdsWithinManualContour',[]),'sourceNativePixelGeometrySha256':hashlib.sha256(json.dumps(r['nativePixelGeometry'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),'sourceContourAuthority':r['sourceContourAuthority'],'sourceQuarterWholeExtentApproved':True,'sourceNameEvidence':r['sourceNameEvidence'],'sourceGraphicReadingLimit':r.get('sourceGraphicReadingLimit'),'cartographicRestoredPixelCount':r.get('restoredOriginalPixelCount',0),'externalSourceOutlineChanged':False,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,'reviewStatus':'estimated_candidate_not_verified','georeferencingStatus':'frozen_first_cohort_estimated_geographic_alignment_not_verified','georeferencingIsApproximate':True,'claimedAbsoluteAccuracy':None,'claimedAbsoluteAccuracyMetres':None,'sourcePeriod':'2021 municipal ITS publication;2011 census themes and2014 map-production annotation; original boundary survey date unknown','method':'Actual distinct original closed Figure12 source cell or independently approved manual closed route through original quarter-outline stroke pixels. Every source segment retained with provenance. Same frozen first-cohort pixel-to-EOV estimate; no new geographic controls/model, repair, clipping, snap, buffer, inferred city complement or current-name-point extent.','sourceDocuments':[{'url':URL,'sha256':PDFSHA,'pdfPageOneBased':r['sourcePdfPageOneBased'],'figure':r['sourceFigure']}],'evidenceUrls':[URL],'placementUncertainty':'Inherited geographic placement remains unverified; actual printed-stroke interpretation and historical/current footprint differences are unquantified. No absolute error radius asserted.','license':'Municipal map reuse rights unverified; ODbL for archived OSM calibration evidence.'}
  f={'type':'Feature','id':'pecs-final-gap:'+norm(r['sourceName']),'geometry':mapping(world),'properties':props};features.append(f);proof.append({'name':r['sourceName'],'sourceFigure':r['sourceFigure'],'sourceMethod':r['method'],'nativePixelGeometry':r['nativePixelGeometry'],'densityFramePixelGeometry':mapping(density),'worldGeometryValid':True,'geographicPlacementVerified':False})
 oldworld=[shape(f['geometry'])for prefix in ['first','remaining']for f in load(prefix+'-source-inferred.geojson')['features']];newworld=[shape(f['geometry'])for f in features];oldpixel=[shape(r['interpretedPixelCellGeometry'])for prefix in ['first','remaining']for r in load(prefix+'-conversion-proof.json')['records']];newpixel=[shape(r['densityFramePixelGeometry'])for r in proof]
 world_overlap=max(g.intersection(o).area for g in newworld for o in oldworld);pixel_overlap=max(g.intersection(o).area for g in newpixel for o in oldpixel);within=max([g.intersection(h).area for i,g in enumerate(newworld)for h in newworld[:i]]or[0]);assert world_overlap<1e-16 and pixel_overlap<1e-8 and within<1e-16,(world_overlap,pixel_overlap,within)
 return {'type':'FeatureCollection','status':'estimated_geographic_placement_only','claimedAbsoluteAccuracy':None,'features':features},{'schemaVersion':1,'sourceFeatureCount':5,'sourceNativeContourRecords':native,'records':proof,'exactApprovedMaskPixelsRestored':3,'newNewWorldMaximumOverlapDegreesSquared':within,'newAdmitted60WorldMaximumOverlapDegreesSquared':world_overlap,'newAdmitted60SourceFrameMaximumOverlapPixelsSquared':pixel_overlap,'geographicPlacementVerified':False,'primaryApprovedCount':0,'claimedAbsoluteAccuracy':None,'newGeographicModelFitted':False,'oldCohortsOrRootFilesModified':False},{'schemaVersion':1,'records':rawcells}

def main():
 a=argparse.ArgumentParser();a.add_argument('--check',action='store_true');args=a.parse_args();fc,p,raw=build()
 for n,d in [('source-inferred.geojson',fc),('conversion-proof.json',p),('central-raw-pixel-cells.json',raw)]:
  s=enc(d)
  if args.check:assert(P/n).read_text()==s,n
  else:(P/n).write_text(s)
 print(json.dumps({'sourceFeatures':5,'primary':0,'claimedAbsoluteAccuracy':None,'overlapWithAdmitted60':p['newAdmitted60WorldMaximumOverlapDegreesSquared'],'check':args.check}))
if __name__=='__main__':main()
