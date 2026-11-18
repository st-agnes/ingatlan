#!/usr/bin/env python3
"""Verify page-to-page alignment using actual paired native CAD line segments.
No name point is used; both endpoints of each control are archived source points.
"""
import fitz,json,numpy as np,hashlib,gzip
from pathlib import Path
from scipy.spatial import cKDTree
P=Path(__file__).resolve().parent;doc=fitz.open(P/'source-pages1-2.pdf');reg=json.loads((P/'registration.json').read_text());M=np.array(reg.get('coarseScopePage1ToPage2Matrix',reg['page1PdfPointsToPage2PdfPointsMatrix']))

def segments(page,box,width):
 out=[];ds=page.get_drawings()
 for i,d in enumerate(ds):
  c=d.get('color')
  if c is None or max(c)-min(c)>.001 or d['width']>width or d.get('fill') is not None:continue
  for j,item in enumerate(d['items']):
   if item[0]!='l':continue
   a=np.array(item[1]);b=np.array(item[2]);mid=(a+b)/2
   if not(box[0]<mid[0]<box[2] and box[1]<mid[1]<box[3]) or np.linalg.norm(a-b)<3:continue
   out.append({'drawingIndex':i,'segmentIndex':j,'coordinates':[a.tolist(),b.tolist()]})
 return out
print('Reading original source CAD segments on both pages',flush=True)
first=segments(doc[0],[420,330,750,650],.3);second=segments(doc[1],[380,295,765,670],.2);print('eligible native segments',len(first),len(second),flush=True)
a=np.array([s['coordinates'] for s in first]);b=np.array([s['coordinates'] for s in second]);tree=cKDTree(b.mean(axis=1));pairs=[]
for iteration in range(12):
 pred=np.c_[a.reshape(-1,2),np.ones(a.size//2)]@M;pred=pred.reshape(-1,2,2);dist,indices=tree.query(pred.mean(axis=1),k=8);pairs=[]
 for i in range(len(a)):
  options=[]
  for j in indices[i]:
   both=b[j];f=np.linalg.norm(pred[i]-both,axis=1);r=np.linalg.norm(pred[i]-both[::-1],axis=1)
   rev=r.sum()<f.sum();errors=r if rev else f;options.append((float(np.max(errors)),int(j),rev))
  score,j,rev=min(options)
  if score<(.65 if iteration==0 else .35):pairs.append((i,j,rev))
 assert len(pairs)>=6,'Insufficient real CAD segment controls; do not force alignment.'
 A=np.array([p for i,j,rev in pairs for p in a[i]]);B=np.array([p for i,j,rev in pairs for p in (b[j][::-1] if rev else b[j])]);new=np.linalg.lstsq(np.c_[A,np.ones(len(A))],B,rcond=None)[0];delta=np.max(np.abs(new-M));M=new
 if delta<1e-10:break
res=np.linalg.norm(np.c_[A,np.ones(len(A))]@M-B,axis=1)
records=[]
for i,j,rev in pairs:
 bcoords=b[j][::-1] if rev else b[j];errors=np.linalg.norm(np.c_[a[i],np.ones(2)]@M-bcoords,axis=1)
 records.append({'page1':first[i],'page2':second[j],'page2EndpointOrderReversed':bool(rev),'pairedEndpointResidualsPage2PdfPoints':errors.tolist()})
assert len(records)>=12 and float(np.quantile(res,.95))<.3
result={'schemaVersion':1,'sourcePdfSha256':hashlib.sha256((P/'source-pages1-2.pdf').read_bytes()).hexdigest(),'method':'Actual grey/black thin native line segments in the same city map area, paired by agreement of both original endpoints after coarse source-scope registration; robust iteration fits one affine page1-to-page2 matrix. Both unmodified native segment IDs/endpoints are preserved. This verifies the cross-page CAD geometry alignment, not independent geographic accuracy.','initialScopeAlignmentMatrix':reg.get('coarseScopePage1ToPage2Matrix',reg['page1PdfPointsToPage2PdfPointsMatrix']),'page1PdfPointsToPage2PdfPointsMatrix':M.tolist(),'matchedActualSourceSegmentPairs':len(records),'matchedActualEndpointPairs':2*len(records),'pairedEndpointResidualPercentilesPage2PdfPoints':{str(q):float(np.percentile(res,q)) for q in [0,50,80,90,95,99,100]},'eligibleNativeGreyBlackSegmentCounts':[len(first),len(second)],'iterationCount':iteration+1,'usedGeographicNameCoordinates':False,'controlPairs':records}
payload=(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode();compressed=gzip.compress(payload,mtime=0);(P/'cross-page-cad-controls.json.gz').write_bytes(compressed)
summary={k:v for k,v in result.items() if k!='controlPairs'};summary['fullControlPairsArchive']='cross-page-cad-controls.json.gz';summary['fullControlPairsArchiveSha256']=hashlib.sha256(compressed).hexdigest()
mids=np.array([np.array(r['page1']['coordinates']).mean(axis=0) for r in records]);selected=[0]
while len(selected)<24:
 nearest=np.min(np.linalg.norm(mids[:,None,:]-mids[selected][None,:,:],axis=2),axis=1);idx=int(np.argmax(nearest));selected.append(idx)
summary['geographicallySpreadSourceExamples']=[dict(records[i],fullArchiveControlPairIndex=i) for i in selected]
(P/'cross-page-cad-controls.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='geographicallySpreadSourceExamples'},ensure_ascii=False),flush=True)
