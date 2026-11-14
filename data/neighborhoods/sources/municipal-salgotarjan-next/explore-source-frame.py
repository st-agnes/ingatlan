from pathlib import Path
from PIL import Image,ImageDraw
from scipy import ndimage
import numpy as np,json,shapely
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent
im=np.array(Image.open(P/'source-p125-xref924.jpeg')).astype(int)
foreground=im.min(2)<248;yy,xx=np.indices(foreground.shape);foreground[(yy>495)&(xx>470)]=False
lab,n=ndimage.label(foreground,np.ones((3,3)));sz=np.bincount(lab.ravel());sz[0]=0;big=lab==sz.argmax();fill=ndimage.binary_fill_holes(big);outer=big&ndimage.binary_dilation(~fill,np.ones((3,3)));ys,xs=np.where(outer);keep=(xs>5)&(xs<755)&(ys>5)&(ys<850)&~((ys>485)&(xs>460));xs=xs[keep];ys=ys[keep];A=np.c_[xs,ys,np.ones(len(xs))]
g=transform(Transformer.from_crs(4326,23700,always_xy=True).transform,shape(json.loads((P/'calibration-municipality.geojson').read_text())['geometry']));border=max(g.geoms,key=lambda p:p.area).exterior
by,bx=np.where(fill);x0,y0,x1,y1=bx.min(),by.min(),bx.max(),by.max();e0,n0,e1,n1=border.bounds
M=np.array([[(e1-e0)/(x1-x0),0],[0,-(n1-n0)/(y1-y0)],[e0-x0*(e1-e0)/(x1-x0),n1+y0*(n1-n0)/(y1-y0)]])
for i in range(150):
 pred=A@M;pp=shapely.points(pred);near=shapely.get_coordinates(shapely.line_interpolate_point(border,shapely.line_locate_point(border,pp)));err=np.linalg.norm(pred-near,axis=1);ok=err<min(500,np.quantile(err,.85))
 if ok.sum()<20:raise ValueError('Insufficient actual source-perimeter matches')
 new=np.linalg.lstsq(A[ok],near[ok],rcond=None)[0]
 if np.max(np.abs(new-M))<1e-5:break
 M=new
err=shapely.distance(shapely.points(A@M),border)
print('foreground',n,'largest',int(big.sum()),'filled',int(fill.sum()),'bbox',[int(x0),int(y0),int(x1),int(y1)],'worldbbox',border.bounds,'controls',len(A),'err',np.percentile(err,[0,50,80,90,95,100]).tolist(),'M',M.tolist(),flush=True)
reg={'EXPLORATORY_ONLY_NOT_VERIFIED_GEOGRAPHIC_PLACEMENT':True,'sourceImage':'source-p125-xref924.jpeg','method':'Original non-white cadastral foreground outer component, legend excluded, real edge pixels more than5px from image frame; approximate registration diagnostic against current municipality. The original map/city scope correspondence still requires independent confirmation. This is not export geometry.','matrixPixelToEov':M.tolist(),'actualSourcePixelControls':A[:,:2].tolist(),'residualsMetres':err.tolist(),'absoluteAccuracyMetres':None}
(P/'exploratory-frame-registration.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n');out=Image.open(P/'source-p125-xref924.jpeg').convert('RGB').resize((1522,1770));d=ImageDraw.Draw(out);back=(np.array(border.coords)-M[2])@np.linalg.inv(M[:2]);d.line([tuple(p*2) for p in back],fill='red',width=2);out.save(P/'exploratory-frame-registration.png');Image.fromarray((fill*255).astype('uint8')).save(P/'exploratory-cadastral-silhouette.png')
for file in ['source-p126-xref927.jpeg','source-p128-xref931.jpeg','source-p129-xref936.jpeg','source-p133-xref950.jpeg','source-p133-xref946.jpeg','source-p136-xref957.jpeg']:
 a=np.array(Image.open(P/file)).astype(int);maxc=a.max(2);minc=a.min(2)
 if 'p136' in file:mask=(a[:,:,0]-a[:,:,1]>30)&(a[:,:,0]-a[:,:,2]>30)
 elif 'p129' in file:mask=(a[:,:,0]-a[:,:,2]>45)&(a[:,:,1]-a[:,:,2]>15)
 else:mask=(a[:,:,0]-a[:,:,2]>25)&(a[:,:,1]-a[:,:,2]>25)
 ids,c=ndimage.label(mask,np.ones((3,3)));sizes=np.bincount(ids.ravel());print(file,'colorComponents',sorted([int(v) for v in sizes[1:] if v>50],reverse=True)[:12],flush=True)
 np.savez_compressed(P/(file.replace('.jpeg','-color-diagnostic.npz')),mask=mask,labels=ids)
