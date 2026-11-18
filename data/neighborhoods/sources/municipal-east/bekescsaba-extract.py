from PIL import Image,ImageFilter
import numpy as np,json,pathlib
from collections import deque
im=Image.open('.local/neighborhoods/nationwide-docs/originals/bekescsaba-map.webp').convert('RGB');a=np.asarray(im).astype(int);r,g,b=[a[:,:,i] for i in range(3)]
def close(m,k=5):
 return np.asarray(Image.fromarray((m*255).astype('uint8')).filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.MinFilter(k)))>0
def components(mask):
 seen=np.zeros(mask.shape,dtype=bool);out=[]
 for y,x in np.argwhere(mask):
  if seen[y,x]:continue
  q=deque([(y,x)]);seen[y,x]=True;pts=[]
  while q:
   yy,xx=q.popleft();pts.append((yy,xx))
   for ny,nx in [(yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)]:
    if 0<=ny<mask.shape[0] and 0<=nx<mask.shape[1] and mask[ny,nx] and not seen[ny,nx]:seen[ny,nx]=True;q.append((ny,nx))
  if len(pts)>80:out.append(pts)
 return sorted(out,key=len,reverse=True)
ms={'brightgreen':(g-r>60)&(b-r<20),'palegreen':(g-r>23)&(g-r<=60)&(b-r<24)&(g-b>22),'teal':(g-r>28)&(b-r>=20)&(g-b>8),'municipality':((g-r)>9)&((g-b)>-7)}
res={}
for n,m in ms.items():
 m=close(m);comps=components(m);res[n]=[]
 for pts in comps:
  yy,xx=np.asarray(pts).T;res[n].append({'pixelCount':len(pts),'bounds':[int(min(xx)),int(min(yy)),int(max(xx)),int(max(yy))],'pixels':pts})
 print(n,[(p['pixelCount'],p['bounds']) for p in res[n]],flush=True)
pathlib.Path('.local/neighborhoods/east-geometry/bekescsaba-raster-components.json').write_text(json.dumps(res,default=int))
