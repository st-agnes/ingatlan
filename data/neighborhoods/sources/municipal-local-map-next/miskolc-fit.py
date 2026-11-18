from pathlib import Path
from PIL import Image,ImageDraw
import json,numpy as np,shapely
from scipy import ndimage
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent
im=np.array(Image.open(P/'miskolc-p228-original.jpeg')).astype(int)
m=(im[:,:,2]-im[:,:,0]>40)&(im[:,:,1]-im[:,:,0]>24)&(im[:,:,2]>70)
free,n=ndimage.label(~m);outside=free==free[550,500]
labels,n=ndimage.label(m,np.ones((3,3)));sizes=np.bincount(labels.ravel());sizes[0]=0;big=labels==sizes.argmax()
outer=big&ndimage.binary_dilation(outside,np.ones((3,3)))
y,x=np.where(outer);sel=(y>5)&(x>5)&(x<879)&(y<440)
x=x[sel];y=y[sel];A=np.c_[x,y,np.ones(len(x))]
to=Transformer.from_crs(4326,23700,always_xy=True).transform;g=transform(to,shape(json.loads((P/'miskolc-calibration-municipality.geojson').read_text())['geometry']));b=max(g.geoms,key=lambda v:v.area).exterior
ys,xs=np.where(big);xx0,yy0,xx1,yy1=xs.min(),ys.min(),xs.max(),ys.max();e0,n0,e1,n1=b.bounds
M=np.array([[(e1-e0)/(xx1-xx0),0],[0,-(n1-n0)/(yy1-yy0)],[e0-xx0*(e1-e0)/(xx1-xx0),n1+yy0*(n1-n0)/(yy1-yy0)]])
for i in range(100):
 pred=A@M;pp=shapely.points(pred);near=shapely.get_coordinates(shapely.line_interpolate_point(b,shapely.line_locate_point(b,pp)));err=np.linalg.norm(pred-near,axis=1);ok=err<min(350,np.quantile(err,.85));new=np.linalg.lstsq(A[ok],near[ok],rcond=None)[0]
 if np.max(np.abs(new-M))<1e-6:break
 M=new
err=shapely.distance(shapely.points(A@M),b)
print('controls',len(A),'iter',i,'matrix',M.tolist(),'percentile',np.percentile(err,[0,50,80,90,95,99,100]).tolist())
reg={'method':'Robust closest-perimeter affine registration from actual original source cyan outer-stroke pixel centers to the archived current OSM municipality in EOV. Registration residuals are not independent absolute boundary accuracy. Source pixels within five pixels of the image top are excluded from fitting; no quarter cell touches a raster edge.','matrixPixelToEov':M.tolist(),'sourceCyanMask':'B-R>40,G-R>24,B>70, original JPEG','sourceOuterStrokePixels':np.c_[x,y].tolist(),'residualsM':err.tolist(),'iterations':i,'sourceImageSizePixels':[884,557],'absoluteBoundaryAccuracyM':None,'independentInteriorControls':0}
(P/'miskolc-registration.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
# Preview current perimeter projected into original source image; preserve mismatches.
back=(np.array(b.coords)-M[2])@np.linalg.inv(M[:2]);out=Image.open(P/'miskolc-p228-original.jpeg').convert('RGB').resize((1768,1114));draw=ImageDraw.Draw(out);draw.line([tuple(v*2) for v in back],fill='red',width=2);out.save(P/'miskolc-registration-preview.png')
