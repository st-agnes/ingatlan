#!/usr/bin/env python3
import json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.signal import fftconvolve
P=Path(__file__).resolve().parent
SRC=Path('/workspace/ingatlan/data/neighborhoods/sources/municipal-kecskemet-outer-next/figure79-source.jpeg')
DST=P.parents[2]/'figure78-p166-xref204.jpeg'
A=Image.open(SRC).convert('L');B=np.asarray(Image.open(DST).convert('L')).astype(float)
def sums(a,h,w):
 c=np.pad(a,((1,0),(1,0))).cumsum(axis=0).cumsum(axis=1)
 return c[h:,w:]-c[:-h,w:]-c[h:,:-w]+c[:-h,:-w]
patch=A.crop((1450,1120,1514,1184));result=[]
for scale in np.arange(.8,1.01,.0125):
 size=round(64*scale);t=np.asarray(patch.resize((size,size),Image.Resampling.BICUBIC)).astype(float);t-=t.mean();den=np.sqrt((t*t).sum());s=sums(B,size,size);v=np.maximum(0,sums(B*B,size,size)-s*s/(size*size));norm=np.sqrt(v)*den;ncc=fftconvolve(B,t[::-1,::-1],mode='valid')/np.maximum(norm,1e-9);y,x=np.unravel_index(np.argmax(ncc),ncc.shape);result.append({'scale':float(scale),'templateSize':size,'correlation':float(ncc[y,x]),'targetTopLeft':[int(x),int(y)]})
print(json.dumps(sorted(result,key=lambda r:-r['correlation'])[:10],indent=2));(P/'clear-template-scale-search.json').write_text(json.dumps({'sourcePatchBox':[1450,1120,1514,1184],'matches':sorted(result,key=lambda r:-r['correlation'])},indent=2)+'\n')
