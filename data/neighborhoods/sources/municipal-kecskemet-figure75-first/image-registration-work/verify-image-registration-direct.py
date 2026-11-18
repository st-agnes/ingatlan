#!/usr/bin/env python3
"""Recompute NCC by direct strided-window arithmetic; no producer-code import."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from PIL import Image
from shapely.geometry import MultiPoint,mapping
P=Path(__file__).resolve().parent

def sha(n):return hashlib.sha256((P/n).read_bytes()).hexdigest()
def encode(v):return(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def run(check=False):
 r=json.loads((P/'image-registration.json').read_text());plan=json.loads((P/'registration-plan-before-fit.json').read_text());a=Image.open(P/r['sourceImage']).convert('L');b=np.asarray(Image.open(P/r['targetImage']).convert('L'),dtype=float);rows=[];max_coefficient=0.;max_center=0.
 if sha(r['sourceImage'])!=r['sourceImageSha256']or sha(r['targetImage'])!=r['targetImageSha256']:raise ValueError('image hash differs')
 if r['predeclaredPlanSha256']!=sha('registration-plan-before-fit.json'):raise ValueError('plan hash differs')
 for q in r['records']:
  left,top,right,bottom=q['sourcePatchBox'];size=q['targetTemplateSize'];center=[(left+right-1)/2,(top+bottom-1)/2]
  if (right-left,bottom-top)!=(plan['sourcePatchSizePixels'],)*2 or size!=plan['fixedTemplateSizePixels']or center!=q['sourcePatchCenter']:raise ValueError('fixed patch differs')
  row,col=[int(v)for v in q['id'][1:].split('c')]
  if q['trainingPartition']!=((row+col)%2==0)or center!=[plan['sourceGridX'][col]-.5,plan['sourceGridY'][row]-.5]:raise ValueError('fixed grid partition differs')
  template=np.asarray(a.crop((left,top,right,bottom)).resize((size,size),Image.Resampling.BICUBIC),dtype=float);template-=template.mean();norm=np.sqrt(np.sum(template*template));lx,ly,rx,ry=q['targetSearchBox'];windows=sliding_window_view(b[ly:ry,lx:rx],(size,size));sums=windows.sum(axis=(-1,-2));squares=np.einsum('ijxy,ijxy->ij',windows,windows,optimize=False);variance=np.maximum(squares-sums*sums/(size*size),0);numerator=np.einsum('ijxy,xy->ij',windows,template,optimize=False);ncc=numerator/np.maximum(np.sqrt(variance)*norm,1e-9);py,px=np.unravel_index(np.argmax(ncc),ncc.shape);coefficient=float(ncc[py,px])
  def delta(v):
   denominator=v[0]-2*v[1]+v[2];return float(np.clip(.5*(v[0]-v[2])/denominator,-.5,.5))if abs(denominator)>1e-12 else 0.
  dx=delta(ncc[py,px-1:px+2])if 0<px<ncc.shape[1]-1 else 0.;dy=delta(ncc[py-1:py+2,px])if 0<py<ncc.shape[0]-1 else 0.;matched=np.array([lx+px+dx+(size-1)/2,ly+py+dy+(size-1)/2]);edge=px in [0,ncc.shape[1]-1]or py in [0,ncc.shape[0]-1];usable=coefficient>=plan['usabilityThresholdNcc']and not edge
  coefficient_error=abs(coefficient-q['normalizedCrossCorrelation']);center_error=float(np.max(np.abs(matched-np.array(q['targetMatchedCenter']))));max_coefficient=max(max_coefficient,coefficient_error);max_center=max(max_center,center_error)
  if coefficient_error>1e-9 or center_error>1e-6 or usable!=q['usableTextureMatch']or bool(edge)!=q['peakOnSearchEdge']:raise ValueError('direct search mismatch '+q['id'])
  rows.append({'id':q['id'],'usableTextureMatch':bool(usable),'trainingPartition':q['trainingPartition'],'directNcc':coefficient,'directMatchedCenter':matched.tolist()})
 train=[q for q in r['records']if q['usableTextureMatch']and q['trainingPartition']];held=[q for q in r['records']if q['usableTextureMatch']and not q['trainingPartition']];matrix=np.linalg.lstsq(np.array([[*q['sourcePatchCenter'],1]for q in train]),np.array([q['targetMatchedCenter']for q in train]),rcond=None)[0]
 if not np.array_equal(matrix,np.array(r['sourceToTargetAffineRows'])):raise ValueError('recomputed affine differs')
 preliminary=json.loads((P/'exploratory-scale-search.json').read_text())['records']
 def overlap_area(a,b):return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
 held_preliminary_overlap=sum(overlap_area(q['sourcePatchBox'],v['sourcePatchBox'])for q in held for v in preliminary)
 if held_preliminary_overlap:raise ValueError('An accepted held-out patch overlaps a preliminary scale patch')
 final_grid_overlap=sum(overlap_area(q['sourcePatchBox'],v['sourcePatchBox'])for j,q in enumerate(r['records'])for v in r['records'][j+1:])
 if final_grid_overlap:raise ValueError('Fixed final grid patches overlap')
 for q in r['records']:
  error=float(np.linalg.norm(np.array([*q['sourcePatchCenter'],1])@matrix-np.array(q['targetMatchedCenter'])))
  if abs(error-q['affinePredictionResidualPixels'])>1e-10:raise ValueError('recomputed residual differs')
 result={'schemaVersion':1,'status':'PASS_LOCAL_PHOTOGRAPHIC_OVERLAP_ONLY','verificationMethod':'Direct strided-window dot products, sums and sums of squares, rather than producer FFT convolution. Independently implemented numeric path; same agent as producer, not a blind separate visual review.','provenanceSha256':{n:sha(n)for n in ['figure74-p154-xref176.jpeg','figure75-p158-xref180.jpeg','fit-image-registration.py','registration-plan-before-fit.json','image-registration.json','exploratory-scale-search.json','verify-image-registration-direct.py']},'directSearchCount':len(rows),'trainingCount':len(train),'heldOutCount':len(held),'rejectedCount':len(rows)-len(train)-len(held),'maximumNccCoefficientDisagreement':max_coefficient,'maximumPeakCenterDisagreementPixels':max_center,'trainingAffineRecomputedExactly':True,'heldOutMatchesUsedInFit':False,'acceptedHeldOutSourcePatchOverlapWithPreliminaryScaleSearchSquarePixels':held_preliminary_overlap,'pairwiseFinalGridSourcePatchOverlapSquarePixels':final_grid_overlap,'maximumHeldOutResidualTargetPixels':max(q['affinePredictionResidualPixels']for q in held),'sourceMatchedTextureHullOriginalFigure74Pixels':mapping(MultiPoint([q['sourcePatchCenter']for q in train+held]).convex_hull),'targetMatchedTextureHullOriginalFigure75Pixels':mapping(MultiPoint([q['targetMatchedCenter']for q in train+held]).convex_hull),'records':rows,'allRejectedSearchesRemainInProducerReport':True,'manualPreNccOrBlindPhysicalObservationClaimed':False,'separateBlindPhysicalReviewer':False,'geographicCoordinatesNamesOrQuarterGeometryUsed':False,'fullFigure75ImageCoverageValidated':False,'geographicRegistrationVerified':False,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,'limits':'A local shared-photograph relation does not establish full image identity, photography date, geographic calibration, boundary extent or accuracy. Source quarter graphic highlighting differs and some labels/linework obscure photo texture.'};data=encode(result);f=P/'direct-verification.json'
 if check:
  if f.read_bytes()!=data:raise ValueError('stale direct verification')
 else:f.write_bytes(data)
 print(json.dumps({k:result[k]for k in ['status','directSearchCount','trainingCount','heldOutCount','rejectedCount','maximumNccCoefficientDisagreement','maximumPeakCenterDisagreementPixels','maximumHeldOutResidualTargetPixels']},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');run(p.parse_args().check)
