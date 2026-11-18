#!/usr/bin/env python3
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy.signal import fftconvolve
P=Path(__file__).resolve().parent
SRC=P/'figure73-p143-xref172.jpeg';DST=P/'figure76-p161-xref184.jpeg'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(v):return(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def local_sums(a,h,w):
 c=np.pad(a,((1,0),(1,0))).cumsum(0).cumsum(1);return c[h:,w:]-c[:-h,w:]-c[h:,:-w]+c[:-h,:-w]
def build(check=False):
 A=Image.open(SRC).convert('L');B=np.asarray(Image.open(DST).convert('L')).astype(float)
 records=[];patchsize=64;template_size=69;scale=template_size/patchsize;offset=np.array([349.,-703.])
 for row,y in enumerate([760,888,1016,1144,1272,1360]):
  for col,x in enumerate([150,278,406,534,662,790,918]):
   left=x-patchsize//2;top=y-patchsize//2;center=np.array([x-.5,y-.5]);template=np.asarray(A.crop((left,top,left+patchsize,top+patchsize)).resize((template_size,template_size),Image.Resampling.BICUBIC)).astype(float);template-=template.mean();normt=np.sqrt((template*template).sum())
   predicted=center*scale+offset;guess=predicted-(template_size-1)/2;lx=max(0,int(guess[0])-18);ly=max(0,int(guess[1])-18);rx=min(B.shape[1],int(guess[0])+template_size+19);ry=min(B.shape[0],int(guess[1])+template_size+19);region=B[ly:ry,lx:rx]
   sums=local_sums(region,template_size,template_size);var=np.maximum(0,local_sums(region*region,template_size,template_size)-sums*sums/(template_size**2));ncc=fftconvolve(region,template[::-1,::-1],mode='valid')/np.maximum(np.sqrt(var)*normt,1e-9);py,px=np.unravel_index(np.argmax(ncc),ncc.shape);sub=[]
   for k,(u,v)in enumerate([(px,py),(py,px)]):
    arr=ncc if k==0 else ncc.T
    if 0<u<arr.shape[1]-1:
     before,middle,after=arr[v,u-1:u+2];den=before-2*middle+after;delta=.5*(before-after)/den if abs(den)>1e-12 else 0
    else:delta=0
    sub.append(float(np.clip(delta,-.5,.5)))
   target=[lx+int(px)+sub[0]+(template_size-1)/2,ly+int(py)+sub[1]+(template_size-1)/2]
   records.append({'id':f'r{row}c{col}','sourcePatchCenter':center.tolist(),'sourcePatchBox':[left,top,left+patchsize,top+patchsize],'targetMatchedCenter':target,'targetSearchBox':[lx,ly,rx,ry],'targetTemplateSize':template_size,'normalizedCrossCorrelation':float(ncc[py,px]),'trainingPartition':(row+col)%2==0,'usableTextureMatch':float(ncc[py,px])>=.85})
 train=[r for r in records if r['usableTextureMatch']and r['trainingPartition']];held=[r for r in records if r['usableTextureMatch']and not r['trainingPartition']]
 x=np.array([r['sourcePatchCenter']for r in train]);y=np.array([r['targetMatchedCenter']for r in train]);matrix=np.linalg.lstsq(np.c_[x,np.ones(len(x))],y,rcond=None)[0]
 for r in records:r['affinePredictionResidualPixels']=float(np.linalg.norm(np.array([*r['sourcePatchCenter'],1])@matrix-r['targetMatchedCenter']))
 result={'schemaVersion':1,'sourceImageSha256':sha(SRC),'targetImageSha256':sha(DST),'sourcePatchSizePixels':patchsize,'fixedTemplateSizePixels':template_size,'initialScaleAndOffsetOnlyForLocalSearch':{'scale':scale,'offset':offset.tolist()},'method':'NCC of actual grayscale photographic texture patches after one fixed bicubic template resize. No neighborhood names, boundary rings or world coordinates participate. An alternating grid partition is fitted; the other usable patches are held out. Subpixel peak interpolation is a local image-correlation diagnostic, not boundary accuracy.','usabilityThresholdNcc':.85,'sourceToTargetAffineRows':matrix.tolist(),'trainingMatchCount':len(train),'heldOutMatchCount':len(held),'maximumTrainingResidualTargetPixels':max(r['affinePredictionResidualPixels']for r in train),'maximumHeldOutResidualTargetPixels':max(r['affinePredictionResidualPixels']for r in held),'minimumUsableNcc':min(r['normalizedCrossCorrelation']for r in train+held),'records':records,'geographicCoordinatesUsed':False,'neighborhoodNameOrBoundaryGeometryUsed':False,'georeferenceVerified':False,'absoluteAccuracyMeters':None}
 data=enc(result);path=P/'image-registration.json'
 if check:
  if not path.exists()or path.read_bytes()!=data:raise ValueError('Stale registration diagnostic')
 else:
  path.write_bytes(data);im=Image.open(DST).convert('RGB');draw=ImageDraw.Draw(im)
  for r in records:
   if r['usableTextureMatch']:
    xx,yy=r['targetMatchedCenter'];draw.ellipse((xx-4,yy-4,xx+4,yy+4),outline='red'if r['trainingPartition']else'yellow',width=2);draw.text((xx+5,yy),r['id'],fill='yellow')
  im.save(P/'texture-match-preview.png')
 print(json.dumps({k:result[k]for k in['trainingMatchCount','heldOutMatchCount','maximumTrainingResidualTargetPixels','maximumHeldOutResidualTargetPixels','minimumUsableNcc','sourceToTargetAffineRows']},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');build(p.parse_args().check)
