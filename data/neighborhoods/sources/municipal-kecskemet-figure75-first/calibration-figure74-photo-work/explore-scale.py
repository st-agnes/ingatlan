#!/usr/bin/env python3
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.signal import fftconvolve
P=Path(__file__).resolve().parent

def sha(n):return hashlib.sha256((P/n).read_bytes()).hexdigest()
def sums(a,h,w):
 c=np.pad(a,((1,0),(1,0))).cumsum(0).cumsum(1);return c[h:,w:]-c[:-h,w:]-c[h:,:-w]+c[:-h,:-w]
def run(check=False):
 a=Image.open(P/'figure73-p143-xref172.jpeg').convert('L');b=np.asarray(Image.open(P/'figure74-p154-xref176.jpeg').convert('L'),dtype=float);records=[]
 for patch in [(670,115,734,179),(648,295,712,359)]:
  choices=[];box=[100,850,360,1150];lx,ly,rx,ry=box;region=b[ly:ry,lx:rx]
  for size in range(38,52):
   t=np.asarray(a.crop(patch).resize((size,size),Image.Resampling.BICUBIC),dtype=float);t-=t.mean();s=sums(region,size,size);v=np.maximum(sums(region*region,size,size)-s*s/(size*size),0);n=fftconvolve(region,t[::-1,::-1],mode='valid')/np.maximum(np.sqrt(v)*np.sqrt(np.sum(t*t)),1e-9);y,x=np.unravel_index(np.argmax(n),n.shape);choices.append({'templateSize':size,'scale':size/64,'normalizedCrossCorrelation':float(n[y,x]),'targetTopLeft':[int(lx+x),int(ly+y)]})
  records.append({'sourcePatchBox':patch,'targetSearchBox':box,'choices':choices})
 r={'schemaVersion':1,'scope':'Preliminary photo-only fixed-patch scale search. Every scale result retained; no output is a fitted or held-out final control.','sourceImageSha256':sha('figure73-p143-xref172.jpeg'),'targetImageSha256':sha('figure74-p154-xref176.jpeg'),'records':records,'geographicCoordinatesOrNamesOrQuarterGeometryUsed':False,'absoluteAccuracyMeters':None};data=(json.dumps(r,indent=2)+'\n').encode();target=P/'exploratory-scale-search.json'
 if check:
  if target.read_bytes()!=data:raise ValueError('stale exploratory search')
 else:target.write_bytes(data)
 print(json.dumps([{'patch':r['sourcePatchBox'],'best':max(r['choices'],key=lambda x:x['normalizedCrossCorrelation'])}for r in records],indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');run(p.parse_args().check)
