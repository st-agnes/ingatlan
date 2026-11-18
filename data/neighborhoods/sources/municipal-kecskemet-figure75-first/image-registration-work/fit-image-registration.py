#!/usr/bin/env python3
"""Portable photo-only Figure74 -> Figure75 fixed-grid NCC registration.

No world coordinates, names, source-quarter rings or geographical model is read.
Every grid search remains in the report, including rejected observations.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy.signal import fftconvolve
P=Path(__file__).resolve().parent
SRC=P/'figure74-p154-xref176.jpeg';DST=P/'figure75-p158-xref180.jpeg'
X=[208,272,336,400,464,528,656,848,912];Y=[1168,1232,1296]
PATCH=48;SIZE=48;OFFSET=np.array([-160.,-1136.]);PAD=18;THRESHOLD=.85

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(v):return(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def sums(a,h,w):
 c=np.pad(a,((1,0),(1,0))).cumsum(0).cumsum(1);return c[h:,w:]-c[:-h,w:]-c[h:,:-w]+c[:-h,:-w]
def build(check=False):
 a=Image.open(SRC).convert('L');b=np.asarray(Image.open(DST).convert('L'),dtype=float);records=[]
 for row,y in enumerate(Y):
  for col,x in enumerate(X):
   left=x-PATCH//2;top=y-PATCH//2;center=np.array([x-.5,y-.5]);t=np.asarray(a.crop((left,top,left+PATCH,top+PATCH)).resize((SIZE,SIZE),Image.Resampling.BICUBIC),dtype=float);t-=t.mean();norm=np.sqrt(np.sum(t*t));guess=center*(SIZE/PATCH)+OFFSET-(SIZE-1)/2;lx=max(0,int(guess[0])-PAD);ly=max(0,int(guess[1])-PAD);rx=min(b.shape[1],int(guess[0])+SIZE+PAD+1);ry=min(b.shape[0],int(guess[1])+SIZE+PAD+1);region=b[ly:ry,lx:rx]
   s=sums(region,SIZE,SIZE);v=np.maximum(sums(region*region,SIZE,SIZE)-s*s/(SIZE*SIZE),0);n=fftconvolve(region,t[::-1,::-1],mode='valid')/np.maximum(np.sqrt(v)*norm,1e-9);py,px=np.unravel_index(np.argmax(n),n.shape)
   def delta(v):
    d=v[0]-2*v[1]+v[2];return float(np.clip(.5*(v[0]-v[2])/d,-.5,.5))if abs(d)>1e-12 else 0.
   dx=delta(n[py,px-1:px+2])if 0<px<n.shape[1]-1 else 0.;dy=delta(n[py-1:py+2,px])if 0<py<n.shape[0]-1 else 0.;target=[lx+int(px)+dx+(SIZE-1)/2,ly+int(py)+dy+(SIZE-1)/2];coefficient=float(n[py,px]);edge=px in [0,n.shape[1]-1]or py in [0,n.shape[0]-1]
   records.append({'id':f'r{row}c{col}','sourcePatchCenter':center.tolist(),'sourcePatchBox':[left,top,left+PATCH,top+PATCH],'targetMatchedCenter':target,'targetSearchBox':[lx,ly,rx,ry],'targetTemplateSize':SIZE,'normalizedCrossCorrelation':coefficient,'peakOnSearchEdge':bool(edge),'trainingPartition':(row+col)%2==0,'usableTextureMatch':coefficient>=THRESHOLD and not edge})
 train=[r for r in records if r['usableTextureMatch']and r['trainingPartition']];held=[r for r in records if r['usableTextureMatch']and not r['trainingPartition']]
 if len(train)<4 or len(held)<4:raise ValueError('Insufficient independently held-out photographic matches; preserve diagnostic rather than approving relation')
 design=np.array([[*r['sourcePatchCenter'],1]for r in train]);targets=np.array([r['targetMatchedCenter']for r in train]);matrix=np.linalg.lstsq(design,targets,rcond=None)[0]
 for r in records:r['affinePredictionResidualPixels']=float(np.linalg.norm(np.array([*r['sourcePatchCenter'],1])@matrix-np.array(r['targetMatchedCenter'])))
 result={'schemaVersion':1,'sourceImage':'figure74-p154-xref176.jpeg','sourceImageSha256':sha(SRC),'targetImage':'figure75-p158-xref180.jpeg','targetImageSha256':sha(DST),'sourcePatchSizePixels':PATCH,'fixedTemplateSizePixels':SIZE,'initialScaleAndOffsetOnlyForLocalSearch':{'scale':SIZE/PATCH,'offset':OFFSET.tolist()},'predeclaredPlan':'registration-plan-before-fit.json','predeclaredPlanSha256':sha(P/'registration-plan-before-fit.json'),'method':'Actual grayscale photographic patches with one fixed bicubic template resize and local normalized cross correlation. Alternating fixed image grid assigns training/held-out status before model fitting; only training matches fit the affine. All searches, including rejected texture and search-edge peaks, remain archived. No geographical coordinates, quarter names, rings or geographic model participate. Subpixel residuals diagnose local image overlap, not absolute geographic accuracy.','usabilityThresholdNcc':THRESHOLD,'searchEdgePeaksUsable':False,'sourceToTargetAffineRows':matrix.tolist(),'searchCount':len(records),'trainingMatchCount':len(train),'heldOutMatchCount':len(held),'rejectedSearchCount':sum(not r['usableTextureMatch']for r in records),'maximumTrainingResidualTargetPixels':max(r['affinePredictionResidualPixels']for r in train),'maximumHeldOutResidualTargetPixels':max(r['affinePredictionResidualPixels']for r in held),'minimumUsableNcc':min(r['normalizedCrossCorrelation']for r in train+held),'records':records,'manualPreNccOrBlindPhysicalObservationClaimed':False,'geographicCoordinatesUsed':False,'neighborhoodNameOrBoundaryGeometryUsed':False,'georeferenceVerified':False,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False}
 data=enc(result);path=P/'image-registration.json'
 if check:
  if not path.exists()or path.read_bytes()!=data:raise ValueError('Stale image registration')
 else:
  path.write_bytes(data);im=Image.open(DST).convert('RGB');draw=ImageDraw.Draw(im)
  for r in records:
   xx,yy=r['targetMatchedCenter'];color=('red'if r['trainingPartition']else'yellow')if r['usableTextureMatch']else'gray';draw.ellipse((xx-3,yy-3,xx+3,yy+3),outline=color,width=1);draw.text((xx+3,yy),r['id'],fill=color)
  im.save(P/'texture-match-preview.png')
 print(json.dumps({k:result[k]for k in ['searchCount','trainingMatchCount','heldOutMatchCount','rejectedSearchCount','maximumTrainingResidualTargetPixels','maximumHeldOutResidualTargetPixels','minimumUsableNcc','sourceToTargetAffineRows']},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');build(p.parse_args().check)
