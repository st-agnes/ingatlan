from PIL import Image,ImageDraw
import numpy as np,json
from collections import deque,Counter
from pathlib import Path
from shapely.geometry import box,mapping
from shapely.ops import unary_union
p=Path(__file__).resolve().parent;a=np.array(Image.open(p/'p141-xref778.jpeg').convert('RGB'))
mask=np.max(a,axis=2)<120
seen=np.zeros(mask.shape,np.int32);comps=[]
for y,x in np.argwhere(mask):
 if seen[y,x]:continue
 lab=len(comps)+1;stack=[(int(y),int(x))];seen[y,x]=lab;pts=[]
 while stack:
  yy,xx=stack.pop();pts.append((yy,xx))
  for dy in [-1,0,1]:
   for dx in [-1,0,1]:
    y2,x2=yy+dy,xx+dx
    if 0<=y2<a.shape[0] and 0<=x2<a.shape[1] and mask[y2,x2] and not seen[y2,x2]:seen[y2,x2]=lab;stack.append((y2,x2))
 comps.append(pts)
print('components',[(j+1,len(c),(min(x for y,x in c),min(y for y,x in c),max(x for y,x in c),max(y for y,x in c))) for j,c in sorted(enumerate(comps),key=lambda z:-len(z[1]))[:8]])
big=max(range(len(comps)),key=lambda i:len(comps[i]));stroke=seen==big+1
free=~stroke;inside=np.zeros(free.shape,bool);stack=[(220,160)];inside[220,160]=True
while stack:
 yy,xx=stack.pop()
 for dy,dx in [(1,0),(-1,0),(0,1),(0,-1)]:
  y2,x2=yy+dy,xx+dx
  if 0<=y2<a.shape[0] and 0<=x2<a.shape[1] and free[y2,x2] and not inside[y2,x2]:inside[y2,x2]=True;stack.append((y2,x2))
print('area',inside.sum(),'touch edge', bool(inside[0].any() or inside[-1].any() or inside[:,0].any() or inside[:,-1].any()))
b=a.copy();b[stroke]=[255,0,0];b[inside]=(b[inside].astype(int)*.5+np.array([0,180,255])*.5).astype(np.uint8);Image.fromarray(b).resize((710,902)).save(p/'hathaz-contour-extraction-preview.png');np.savez(p/'hathaz-mask.npz',stroke=stroke,inside=inside)

runs=[]
for y in range(inside.shape[0]):
 xs=np.flatnonzero(inside[y]);groups=np.split(xs,np.where(np.diff(xs)>1)[0]+1)
 for g in groups:
  if len(g):runs.append(box(int(g[0]),y,int(g[-1])+1,y+1))
g=unary_union(runs)
assert g.is_valid and g.geom_type=='Polygon' and len(g.interiors)==0 and g.area==55438
f={'type':'Feature','id':'municipal-zalaegerszeg-ziffa2025:unit17:hathaz:source-raster','properties':{'name':'Hatház','sourceUnitNumber':17,'coordinateSpace':'native image pixels, y downward; pixel cells have integer bounds','sourcePdfPageOneBased':141,'sourceImageXref':778,'contourMethod':'Four-neighbor free interior enclosed by largest eight-neighbor dark boundary component, RGB maximum <120. Exact union of pixel cells. No buffers, snapping, repairs or gap caps.','estimatedContour':False,'containsNoWorldPlacement':True},'geometry':mapping(g)}
(p/'hathaz-observed-source-pixels.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[f]},ensure_ascii=False,indent=2)+'\n')
