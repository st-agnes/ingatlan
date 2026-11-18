#!/usr/bin/env python3
"""Match unchanged grey cadastral/road texture between two archived municipal maps."""
from pathlib import Path
import json,random
import numpy as np
from PIL import Image
from scipy.signal import fftconvolve
from scipy.ndimage import uniform_filter
HERE=Path(__file__).resolve().parent
src=np.asarray(Image.open(HERE/'ozd-2015-p247-0.jpeg').convert('RGB')).astype(float)
dst=np.asarray(Image.open(HERE/'ozd-map-p54.jpeg').convert('RGB')).astype(float)
def roads(a):
 gray=a.mean(2);colour=a.max(2)-a.min(2);return np.where(colour<20,255-gray,0).astype(np.float32)
s,d=roads(src),roads(dst)
# Distributed low-colour patches cover actual grey streets/parcels; filled wards
# and text labels are not treated as a geographic control source.
patches=[]
for y in range(35,s.shape[0]-35,45):
 for x in range(35,s.shape[1]-35,45):
  p=s[y-18:y+19,x-18:x+19]
  colour=(src[y-18:y+19,x-18:x+19].max(2)-src[y-18:y+19,x-18:x+19].min(2)>20).mean()
  if colour<.02 and p.std()>12:patches.append((float(p.std()),x,y))
patches=sorted(patches,reverse=True)[:28]
allmatches=[]
for std,x,y in patches:
 best=None
 original=s[y-18:y+19,x-18:x+19]
 for scale in [1.25,1.4,1.55,1.7,1.85,2.0]:
  n=round(37*scale);n+=n%2==0
  patch=np.asarray(Image.fromarray(original).resize((n,n),Image.Resampling.BILINEAR));patch=patch-patch.mean();norm=np.linalg.norm(patch)
  corr=fftconvolve(d,patch[::-1,::-1],mode='same')
  mean=uniform_filter(d,size=n);meansq=uniform_filter(d*d,size=n);den=np.sqrt(np.maximum((meansq-mean*mean)*n*n,1))*norm
  score=corr/den;score[:n]=score[-n:]=-1;score[:,:n]=score[:,-n:]=-1
  yy,xx=np.unravel_index(np.argmax(score),score.shape);c=float(score[yy,xx])
  if best is None or c>best['correlation']:best={'source':[x,y],'target':[int(xx),int(yy)],'scale':scale,'correlation':c}
 allmatches.append(best)
 print(best,flush=True)
# RANSAC uses spatial agreement; photographic correlations are registration
# evidence only, never an independent absolute geographic accuracy claim.
best=[];matrix=None;random.seed(2015)
for attempt in range(2500):
 rows=random.sample(allmatches,3);X=np.array([[*p['source'],1] for p in rows]);Y=np.array([p['target'] for p in rows])
 try:m=np.linalg.solve(X,Y)
 except np.linalg.LinAlgError:continue
 singular=np.linalg.svd(m[:2])[1]
 if singular.min()<.8 or singular.max()>2.8 or singular.max()/singular.min()>1.5 or np.linalg.det(m[:2])<=0:continue
 valid=[p for p in allmatches if np.linalg.norm(np.array([*p['source'],1])@m-p['target'])<12 and p['correlation']>.3]
 if len(valid)>len(best):best=valid;matrix=m
if len(best)>=4:
 matrix=np.linalg.lstsq(np.array([[*p['source'],1] for p in best]),np.array([p['target'] for p in best]),rcond=None)[0]
result={'method':'Photographic road/parcels normalized cross-correlation and affine consensus, not ground-truth accuracy','matches':allmatches,'inliers':best,'matrixSourceToMasterPixels':matrix.tolist() if matrix is not None else None}
(HERE/'ozd-2015-frame-match.json').write_text(json.dumps(result,indent=2)+'\n');print('inliers',len(best),'matrix',matrix,flush=True)
