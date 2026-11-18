import numpy as np,json,hashlib
from PIL import Image
from pathlib import Path
from scipy import ndimage
import shapely
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent
im=np.array(Image.open(P/'zalaegerszeg-p12-image0.jpeg').convert('RGB')).astype(int)
m=(im[:,:,0]<135)&(im[:,:,1]-im[:,:,0]>30)&(im[:,:,2]-im[:,:,0]>30)&(im[:,:,1]>65)
l,n=ndimage.label(m,np.ones((3,3)));boxes=ndimage.find_objects(l);sizes=np.bincount(l.ravel());cent=[];ids=[]
for i,b in enumerate(boxes,1):
 if 15<=sizes[i]<=230 and b and b[0].stop-b[0].start<=32 and b[1].stop-b[1].start<=32:
  yy,xx=np.where(l[b]==i);cent.append([float(xx.mean()+b[1].start),float(yy.mean()+b[0].start)]);ids.append(i)
g=transform(Transformer.from_crs(4326,23700,always_xy=True).transform,shape(json.loads((P/'zalaegerszeg-calibration-municipality.geojson').read_text())['geometry']))
border=max(g.geoms,key=lambda x:x.area).exterior
ys,xs=np.where(m);x0,y0,x1,y1=xs.min(),ys.min(),xs.max(),ys.max();e0,n0,e1,n1=border.bounds;sx=(e1-e0)/(x1-x0);sy=(n1-n0)/(y1-y0)
M=np.array([[sx,0],[0,-sy],[e0-x0*sx,n1+y0*sy]])
A=np.c_[np.array(cent),np.ones(len(cent))]
initial=shapely.distance(shapely.points(A@M),border);keep=initial<180
print('components',n,'small',len(cent),'initialnear',sum(keep),'initpercentiles',np.percentile(initial[keep],[0,50,90,100]))
A=A[keep];used=np.array(cent)[keep]
for i in range(80):
 pred=A@M;pp=shapely.points(pred);near=shapely.get_coordinates(shapely.line_interpolate_point(border,shapely.line_locate_point(border,pp)));err=np.linalg.norm(pred-near,axis=1);fit=err<min(100,np.quantile(err,.9));new=np.linalg.lstsq(A[fit],near[fit],rcond=None)[0]
 if np.max(np.abs(new-M))<1e-6:break
 M=new
err=shapely.distance(shapely.points(A@M),border)
print('iterations',i,'residual',np.percentile(err,[0,50,80,90,95,99,100]),'matrix',M.tolist())
(P/'zalaegerszeg-registration.json').write_text(json.dumps({'method':'Robust affine matching of actual small source-color dash component centroids to the contemporary municipal perimeter. This is a registration diagnostic, not independent boundary accuracy.','matrixPixelToEov':M.tolist(),'dashComponentCentersPixels':used.tolist(),'residualsM':err.tolist(),'sourceMaskRule':'R<135,G-R>30,B-R>30,G>65; eight-neighbor components15..230pixels, boundingdimension<=32px; initialmunicipalproximity<180m','initialBboxPixel':[int(x0),int(y0),int(x1),int(y1)],'iterations':i,'absoluteBoundaryAccuracyM':None},ensure_ascii=False,indent=2)+'\n')
np.savez_compressed(P/'zalaegerszeg-mask.npz',mask=m,labels=l)
