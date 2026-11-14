from pathlib import Path
import json,numpy as np,shapely
from scipy import ndimage
from PIL import Image,ImageDraw
from shapely.geometry import box,mapping,shape
from shapely.ops import unary_union
P=Path(__file__).resolve().parent
CASES=[('Somoskő','source-p126-xref927',3,(445,20,535,100),'yellow'),('Rónafalu','source-p126-xref927',13,(565,255,625,320),'yellow'),('Rónabánya','source-p126-xref927',19,(615,307,667,354),'yellow'),('Zagyvaróna','source-p128-xref931',1,(475,265,575,401),'yellow'),('Beszterce lakótelep','source-p129-xref936',1,(294,230,412,348),'orange'),('Forgáchtelep','source-p133-xref946',1,(267,480,353,584),'yellow'),('Somlyóbánya','source-p133-xref950',1,(345,505,430,595),'yellow'),('Baglyasalja','source-p136-xref957',1,(145,397,268,602),'red')]

def geo(mask):
 rects=[]
 for y in np.flatnonzero(mask.any(1)):
  row=np.r_[False,mask[y],False];e=np.flatnonzero(row[1:]!=row[:-1]);rects.extend(box(float(a)-.5,float(y)-.5,float(b)-.5,float(y)+.5) for a,b in zip(e[::2],e[1::2]))
 out=unary_union(rects);assert out.is_valid and out.geom_type in ['Polygon','MultiPolygon'];return out

def fit_similarity(A,B):
 ac=A-A.mean(0);bc=B-B.mean(0);u,s,v=np.linalg.svd(ac.T@bc);r=u@v
 if np.linalg.det(r)<0:u[:,-1]*=-1;r=u@v
 scale=np.sum((ac@r)*bc)/np.sum(ac*ac);linear=scale*r;off=B.mean(0)-A.mean(0)@linear;return np.vstack([linear,off])

def color_mask(a,kind):
 if kind=='red':return(a[:,:,0]-a[:,:,1]>30)&(a[:,:,0]-a[:,:,2]>30)&((a[:,:,0]-a[:,:,1])>.68*(a[:,:,0]-a[:,:,2]))
 if kind=='orange':return(a[:,:,0]-a[:,:,2]>45)&(a[:,:,1]-a[:,:,2]>15)&(a[:,:,0]-a[:,:,1]>25)
 return(a[:,:,0]-a[:,:,2]>25)&(a[:,:,1]-a[:,:,2]>25)&((a[:,:,1]-a[:,:,2])>.65*(a[:,:,0]-a[:,:,2]))
main=np.array(Image.open(P/'source-p125-xref924.jpeg')).astype(int);records=[];features=[];preview=Image.fromarray(main.astype('uint8')).resize((1522,1770));draw=ImageDraw.Draw(preview)
for name,file,cid,roi,kind in CASES:
 rawdata=np.load(P/(file+'-color-diagnostic.npz'));region=rawdata['labels']==cid;assert not(region[0].any() or region[-1].any() or region[:,0].any() or region[:,-1].any());filled=ndimage.binary_fill_holes(region);raw=geo(region);source=geo(filled)
 a=np.array(Image.open(P/(file+'.jpeg'))).astype(int);holes=filled&~region;assert not((a.min(2)>230)&holes).any()
 target_mask=color_mask(main,kind);x0,y0,x1,y1=roi;roi_mask=np.zeros(target_mask.shape,bool);roi_mask[y0:y1,x0:x1]=True;target_mask&=roi_mask;labels,n=ndimage.label(target_mask,np.ones((3,3)));sizes=np.bincount(labels.ravel());sizes[0]=0;tid=int(sizes.argmax());target_region=labels==tid;target_filled=ndimage.binary_fill_holes(target_region);target=geo(target_filled)
 A=shapely.get_coordinates(source.boundary);C=np.c_[A,np.ones(len(A))];sb=np.array(source.centroid.coords[0]);tb=np.array(target.centroid.coords[0]);scale=(target.area/source.area)**.5;M=np.vstack([np.eye(2)*scale,tb-sb*scale])
 for i in range(150):
  pred=C@M;pp=shapely.points(pred);boundary=target.boundary;near=shapely.get_coordinates(shapely.line_interpolate_point(boundary,shapely.line_locate_point(boundary,pp)));err=np.linalg.norm(pred-near,axis=1);good=err<max(2,np.quantile(err,.9));new=fit_similarity(A[good],near[good])
  if np.max(np.abs(new-M))<1e-7:break
  M=new
 residual=shapely.distance(shapely.points(C@M),target.boundary)
 parts=[source] if source.geom_type=='Polygon' else list(source.geoms)
 for part in parts:
  xy=np.c_[np.array(part.exterior.coords),np.ones(len(part.exterior.coords))]@M;draw.line([tuple(p*2) for p in xy],fill='blue',width=2)
 t_y,t_x=np.where(target_region);row={'name':name,'sourceImage':file+'.jpeg','sourceOriginalColorComponentId':cid,'sourceImageSizePixels':[int(a.shape[1]),int(a.shape[0])],'rawColorPixelCount':int(region.sum()),'cartographicInteriorPixelCount':int(holes.sum()),'largestInteriorVoidOriginalPixels':int(max(np.bincount(ndimage.label(holes)[0].ravel())[1:],default=0)),'nearWhiteInteriorVoidPixels':0,'rawPixelGeometry':mapping(raw),'sourceOuterOutlinePixelGeometry':mapping(source),'sourceOutlineTouchesImageEdge':False,'mainImage':'source-p125-xref924.jpeg','mainCalibrationRoiPixels':list(roi),'mainOriginalColorComponentId':tid,'mainColorPixelCount':int(target_region.sum()),'mainSourceComponentBbox':[int(t_x.min()),int(t_y.min()),int(t_x.max()),int(t_y.max())],'mainCalibrationPixelGeometry':mapping(target),'matrixProfilePixelsToMainPixels':M.tolist(),'sameSourceContourRegistrationResidualMainPixels':np.percentile(residual,[0,50,80,90,95,100]).tolist(),'registrationIterations':i,'absoluteAccuracyMetres':None,'sourceInterpretationReviewRequired':True};records.append(row);features.append({'type':'Feature','properties':{'name':name,'coordinateSystem':'Original embedded profile-image pixels, NOT geographic coordinates','sourceImage':file+'.jpeg'},'geometry':mapping(source)})
 print(name,'parts',len(parts),'sourcepx',int(region.sum()),'holespx',int(holes.sum()),'mainpx',int(target_region.sum()),'M',M.tolist(),'res',np.percentile(residual,[50,90,100]).tolist(),flush=True)
# Joint registration for the two fields on one unbroken lower map panel.
joint=[r for r in records if r['name'] in ['Rónafalu','Rónabánya']]
if len(joint)==2:
 source_union=unary_union([shape(r['sourceOuterOutlinePixelGeometry']) for r in joint]);target_union=unary_union([shape(r['mainCalibrationPixelGeometry']) for r in joint]);JA=shapely.get_coordinates(source_union.boundary);JC=np.c_[JA,np.ones(len(JA))];JM=np.array(joint[0]['matrixProfilePixelsToMainPixels'])
 for ji in range(150):
  pred=JC@JM;pp=shapely.points(pred);near=shapely.get_coordinates(shapely.line_interpolate_point(target_union.boundary,shapely.line_locate_point(target_union.boundary,pp)));err=np.linalg.norm(pred-near,axis=1);ok=err<max(2,np.quantile(err,.9));new=fit_similarity(JA[ok],near[ok])
  if np.max(np.abs(new-JM))<1e-7:break
  JM=new
 for r in joint:
  src=shape(r['sourceOuterOutlinePixelGeometry']);A2=shapely.get_coordinates(src.boundary);err=shapely.distance(shapely.points(np.c_[A2,np.ones(len(A2))]@JM),shape(r['mainCalibrationPixelGeometry']).boundary);r['matrixProfilePixelsToMainPixels']=JM.tolist();r['sameSourceContourRegistrationResidualMainPixels']=np.percentile(err,[0,50,80,90,95,100]).tolist();r['sharedSourcePanel']='Original p126 lower panel: one continuous cadastral image for Rónafalu and Rónabánya; one shared similarity transform, never separately rotated.'
 print('joint Róna panel matrix',JM.tolist(),'res',[(r['name'],r['sameSourceContourRegistrationResidualMainPixels'][1:]) for r in joint],flush=True)
# Rebuild the diagnostic from the final transforms.
preview=Image.fromarray(main.astype('uint8')).resize((1522,1770));draw=ImageDraw.Draw(preview)
for r in records:
 g=shape(r['sourceOuterOutlinePixelGeometry']);parts=[g] if g.geom_type=='Polygon' else list(g.geoms);m=np.array(r['matrixProfilePixelsToMainPixels'])
 for part in parts:
  xy=np.c_[np.array(part.exterior.coords),np.ones(len(part.exterior.coords))]@m;draw.line([tuple(v*2) for v in xy],fill='blue',width=2)
(P/'profile-source-pixel-contours.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,indent=2)+'\n');(P/'profile-main-correspondence-review.json').write_text(json.dumps({'schemaVersion':1,'reviewRequired':True,'geographicOutput':False,'method':'Actual source-color component outer outlines, retaining every external source edge; interior cadastral/colour-mask void interpretation is provisional and explicit. Similarity registration between actual matching profile and overview source contours, no name-point geographic controls.','records':records},ensure_ascii=False,indent=2)+'\n');preview.save(P/'profile-main-correspondence-preview.png')
