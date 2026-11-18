#!/usr/bin/env python3
import json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.signal import fftconvolve
P=Path(__file__).resolve().parent
A=Image.open(P/'figure74-p154-xref176.jpeg').convert('L')
B=np.asarray(Image.open(P/'figure75-p158-xref180.jpeg').convert('L').crop((0,0,1700,650)),dtype=float)
def sums(a,n):
 c=np.pad(a,((1,0),(1,0))).cumsum(0).cumsum(1);return c[n:,n:]-c[:-n,n:]-c[n:,:-n]+c[:-n,:-n]
records=[]
for x,y in [(600,1250),(750,1250)]:
 box=(x-32,y-32,x+32,y+32);patch=A.crop(box)
 for n in range(40,101,4):
  t=np.asarray(patch.resize((n,n),Image.Resampling.BICUBIC),dtype=float);t-=t.mean();s=sums(B,n);variance=np.maximum(0,sums(B*B,n)-s*s/(n*n));r=fftconvolve(B,t[::-1,::-1],mode='valid')/np.maximum(np.sqrt(variance)*np.sqrt((t*t).sum()),1e-9);py,px=np.unravel_index(np.argmax(r),r.shape)
  records.append({'sourcePatchBox':box,'templateSize':n,'scale':n/64,'ncc':float(r[py,px]),'targetTopLeft':[int(px),int(py)],'targetSearchBox':[0,0,1700,650]})
result={'schemaVersion':1,'scope':'Exploratory source-photo scale/offset search only; not fitted or held-out validation. All attempted sizes retained.','records':records,'geographicDataNamesOrQuarterRingsUsed':False}
(P/'exploratory-scale-search.json').write_text(json.dumps(result,indent=2)+'\n')
for x,y in [(600,1250),(750,1250)]:
 print(json.dumps(sorted([r for r in records if r['sourcePatchBox'][0]==x-32],key=lambda r:-r['ncc'])[:4]))
