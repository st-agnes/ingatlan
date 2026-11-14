"""Exact source raster interiors; Ságod thematic-mask result remains quarantined."""
from pathlib import Path
import json,numpy as np
from PIL import Image
from shapely.geometry import box,mapping
from shapely.ops import unary_union
P=Path(__file__).resolve().parent
for name,label,xref,seed in [('neszele','Neszele',768,(180,180)),('sagod','Ságod',769,(300,100))]:
 a=np.array(Image.open(P/f'p138-xref{xref}.jpeg').convert('RGB'));mask=a.max(2)<120;labels=np.zeros(mask.shape,int);cs=[]
 for sy,sx in zip(*np.where(mask)):
  if labels[sy,sx]:continue
  lab=len(cs)+1;q=[(sy,sx)];labels[sy,sx]=lab;cells=[]
  while q:
   y,x=q.pop();cells.append((y,x))
   for dy in [-1,0,1]:
    for dx in [-1,0,1]:
     yy,xx=y+dy,x+dx
     if 0<=yy<a.shape[0] and 0<=xx<a.shape[1] and mask[yy,xx] and not labels[yy,xx]:labels[yy,xx]=lab;q.append((yy,xx))
  cs.append(cells)
 big=max(range(len(cs)),key=lambda i:len(cs[i]));stroke=labels==big+1;inside=np.zeros(stroke.shape,bool);q=[seed];inside[seed]=True
 while q:
  y,x=q.pop()
  for dy,dx in [(0,1),(0,-1),(1,0),(-1,0)]:
   yy,xx=y+dy,x+dx
   if 0<=yy<a.shape[0] and 0<=xx<a.shape[1] and not stroke[yy,xx] and not inside[yy,xx]:inside[yy,xx]=True;q.append((yy,xx))
 assert not (inside[0].any() or inside[-1].any() or inside[:,0].any() or inside[:,-1].any())
 np.savez(P/f'{name}-mask.npz',stroke=stroke,inside=inside)
 b=a.copy();b[stroke]=[255,0,0];b[inside]=(b[inside].astype(int)*.5+np.array([0,180,255])*.5).astype('uint8');Image.fromarray(b).resize((a.shape[1]*2,a.shape[0]*2)).save(P/f'{name}-literal-mask-preview.png')
 runs=[]
 for y,row in enumerate(inside):
  xs=np.flatnonzero(row);groups=np.split(xs,np.where(np.diff(xs)>1)[0]+1)
  for g in groups:
   if len(g):runs.append(box(int(g[0]),y,int(g[-1])+1,y+1))
 g=unary_union(runs);assert g.is_valid and g.geom_type=='Polygon'
 prop={'name':label,'coordinateSpace':'Native image pixel cell corners, y down','sourceUnitNumber':16,'sourceQuarterIdentity':name,'sourceImageXref':xref,'method':'Four-neighbor interior of largest eight-neighbor dark component, max(R,G,B)<120. Exact source-cell union; no buffers, snapping, closure bridges, clipping or geometric repair.','observedSourceMask':True,'sourceContourObserved':name=='neszele','estimatedContour':False,'literalThematicMaskNotAdmitted':name=='sagod','quarantined':name=='sagod'}
 if name=='sagod':prop['quarantineReason']='Dark connected component contains thematic green-element fills/borders; its three holes and edge slits are not established neighborhood exclusions. No geographic candidate generated.'
 f={'type':'Feature','id':f'zalaegerszeg-ziffa2025:unit16:{name}:source-pixels','properties':prop,'geometry':mapping(g)}
 (P/f'{name}-literal-source-pixels.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[f]},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'name':label,'strokePixels':int(stroke.sum()),'insidePixels':int(inside.sum()),'valid':g.is_valid,'holes':len(g.interiors),'quarantined':name=='sagod'}))
