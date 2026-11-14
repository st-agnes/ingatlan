"""Offline refinement; never alters the archived native profile contours.

Run from repository root with PYTHONPATH=.local/geodata python3 <this file>.
The result is a source-to-source registration diagnostic, NOT a verified georef.
"""
from pathlib import Path
import json
import numpy as np
import shapely
from scipy import ndimage
from PIL import Image, ImageDraw
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

P = Path(__file__).resolve().parent

def geo(mask):
    rects = []
    for y in np.flatnonzero(mask.any(1)):
        e = np.flatnonzero(np.r_[False, mask[y], False][1:] != np.r_[False, mask[y], False][:-1])
        rects.extend(box(float(a)-.5, float(y)-.5, float(b)-.5, float(y)+.5) for a,b in zip(e[::2],e[1::2]))
    g = unary_union(rects)
    assert g.is_valid
    return g

def fit_similarity(A, B):
    ac, bc = A-A.mean(0), B-B.mean(0)
    u,s,v = np.linalg.svd(ac.T@bc)
    r = u@v
    if np.linalg.det(r)<0:
        u[:,-1]*=-1
        r=u@v
    linear = np.sum((ac@r)*bc)/np.sum(ac*ac)*r
    return np.vstack([linear, B.mean(0)-A.mean(0)@linear])

def nearest(g, a):
    pts = shapely.points(a)
    return shapely.get_coordinates(shapely.line_interpolate_point(g, shapely.line_locate_point(g,pts)))

def residual(a, m, target):
    return shapely.distance(shapely.points(np.c_[a,np.ones(len(a))]@m), target.boundary)

old=json.loads((P/'profile-main-correspondence-review.json').read_text())['records']
main=np.array(Image.open(P/'source-p125-xref924.jpeg')).astype(int)
r,g,b=np.moveaxis(main,-1,0)
yellow=(r-b>25)&(g-b>25)&((g-b)>.65*(r-b))
yellow_without_green=yellow&((g-r)<8)
orange=(r-b>45)&(g-b>15)&(r-g>25)
red=(r-g>30)&(r-b>30)&((r-g)>.68*(r-b))&((r-b)>.6*r)
rois={'Forgáchtelep':(235,455,350,590),'Baglyasalja':(145,400,280,610)}
records=[]
for row in old:
    name=row['name'];source=shape(row['sourceOuterOutlinePixelGeometry'])
    roi=rois.get(name,tuple(row['mainCalibrationRoiPixels']))
    mask=red if name=='Baglyasalja' else orange if name=='Beszterce lakótelep' else yellow_without_green if name=='Forgáchtelep' else yellow
    limited=np.zeros(mask.shape,bool);x0,y0,x1,y1=roi;limited[y0:y1,x0:x1]=mask[y0:y1,x0:x1]
    labels,n=ndimage.label(limited,np.ones((3,3)));sizes=np.bincount(labels.ravel());sizes[0]=0;cid=int(sizes.argmax());region=labels==cid
    ys,xs=np.where(region)
    assert xs.min()>x0 and xs.max()<x1-1 and ys.min()>y0 and ys.max()<y1-1,(name,'ROI crops target')
    target=geo(ndimage.binary_fill_holes(region))
    A=shapely.get_coordinates(source.boundary);C=np.c_[A,np.ones(len(A))]
    s=(target.area/source.area)**.5;M=np.vstack([np.eye(2)*s,np.array(target.centroid.coords[0])-np.array(source.centroid.coords[0])*s])
    # This changes registration only; target mask never replaces source geometry.
    for i in range(300):
        pred=C@M;near=nearest(target.boundary,pred)
        err=np.linalg.norm(pred-near,axis=1);keep=err<max(2,np.quantile(err,.95))
        new=fit_similarity(A[keep],near[keep])
        if np.max(np.abs(new-M))<1e-8: break
        M=new
    records.append({'name':name,'sourceRecordPath':'profile-main-correspondence-review.json','sourceImage':row['sourceImage'],'mainImage':'source-p125-xref924.jpeg','mainCalibrationRoiPixels':list(roi),'mainSourceComponentBbox':[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())],'mainColorPixelCount':int(region.sum()),'mainCalibrationPixelGeometry':mapping(target),'matrixProfilePixelsToMainPixels':M.tolist(),'residualPercentilesMainPixels':{'percentiles':[0,50,80,90,95,100],'values':np.percentile(residual(A,M,target),[0,50,80,90,95,100]).tolist()},'registrationIterations':i,'targetRoiClipsComponent':False,'geographicRegistrationValidated':False,'absoluteAccuracyMetres':None})

# The Róna lower panel is one continuous map: preserve one jointly fitted matrix.
joint=[row for row in records if row['name'] in ['Rónafalu','Rónabánya']]
sources={row['name']:shape(row['sourceOuterOutlinePixelGeometry']) for row in old}
su=unary_union([sources[row['name']] for row in joint]);tu=unary_union([shape(row['mainCalibrationPixelGeometry']) for row in joint]);A=shapely.get_coordinates(su.boundary);C=np.c_[A,np.ones(len(A))];M=np.array(joint[0]['matrixProfilePixelsToMainPixels'])
for i in range(300):
    pred=C@M;near=nearest(tu.boundary,pred);err=np.linalg.norm(pred-near,axis=1);keep=err<max(2,np.quantile(err,.95));new=fit_similarity(A[keep],near[keep])
    if np.max(np.abs(new-M))<1e-8: break
    M=new
for row in joint:
    row['matrixProfilePixelsToMainPixels']=M.tolist();row['sharedContinuousPanel']='Original p126 lower Rónafalu and Rónabánya panel';row['residualPercentilesMainPixels']['values']=np.percentile(residual(shapely.get_coordinates(sources[row['name']].boundary),M,shape(row['mainCalibrationPixelGeometry'])),[0,50,80,90,95,100]).tolist()

preview=Image.fromarray(main.astype('uint8')).resize((1522,1770));draw=ImageDraw.Draw(preview)
for row in records:
    src=sources[row['name']];parts=[src] if src.geom_type=='Polygon' else src.geoms;M=np.array(row['matrixProfilePixelsToMainPixels'])
    for part in parts:
        a=np.array(part.exterior.coords);xy=np.c_[a,np.ones(len(a))]@M;draw.line([tuple(v*2) for v in xy],fill='blue',width=2)
    print(row['name'],row['mainSourceComponentBbox'],row['residualPercentilesMainPixels']['values'][1:],flush=True)
out={'schemaVersion':1,'status':'SOURCE_TO_SOURCE_REGISTRATION_ONLY_GEOGRAPHICAL_PLACEMENT_STILL_INFERRED','originalNativeContoursUnchanged':True,'method':'Similarity ICP of actual source-color contours, 95th-percentile outlier diagnostic trim. Complete target ROIs. Rónafalu/Rónabánya share a continuous-panel transform. No name points used as controls.','targetColorRules':{'yellow':'r-b>25 AND g-b>25 AND g-b>.65*(r-b); additionally g-r<8 for Forgáchtelep only to separate adjacent green unit. Other yellow bodies are isolated in their ROIs.','orange':'r-b>45 AND g-b>15 AND r-g>25','red':'r-g>30 AND r-b>30 AND r-g>.68*(r-b) AND r-b>.6*r; separates stronger red Baglyasalja from adjacent pale salmon Rákóczi unit'},'supersededDiagnostic':'profile-main-correspondence-review.json remains archived; its yellow mask admitted green and red mask admitted salmon; Forgách/Baglyasalja ROIs cropped targets. Only registration replaced.','records':records,'absoluteAccuracyMetres':None,'primaryLayerAdmission':False,'usableForAddressAssignment':False}
(P/'profile-main-registration-refined.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
preview.save(P/'profile-main-registration-refined.png')
