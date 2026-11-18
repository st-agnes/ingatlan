"""Reproduce the recorded PDF-to-EOV registration and municipal-boundary overlay.
Only four closed, unambiguous statutory residential paths were exported.
"""
import json,fitz,math
import numpy as np
from pathlib import Path
from shapely.geometry import Polygon,Point,shape,LineString,mapping
from shapely.ops import unary_union,transform,nearest_points
from shapely.affinity import affine_transform
from shapely import points,distance
from pyproj import Transformer
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[4]
OWN=Path(__file__).resolve().parent
P=fitz.open(str(OWN/'tatabanya-map.source.pdf'))[0];ds=P.get_drawings();source=[]
for ix,d in enumerate(ds):
 c=d.get('color')
 if ix in [1286,1815,3277,3696,4284,4557,4558,4836,4851,5527,5528,5529,5530,5531,6326]:
  source.extend(tuple(item[j]) for item in d['items'] if item[0]=='l' for j in [1,2])
cs=np.unique(np.array(source),axis=0);print('sourcevertices',len(cs),cs.min(axis=0),cs.max(axis=0))
M=json.loads((ROOT/'.local/neighborhoods/country/municipalities.geojson').read_text())['features'];m=next(f for f in M if f['properties']['name']=='Tatabánya');municipality=transform(Transformer.from_crs(4326,23700,always_xy=True).transform,shape(m['geometry']));target=municipality.boundary
print('EOV bounds',municipality.bounds)
x0,y0,x1,y1=municipality.bounds;a0,b0=cs.min(axis=0);a1,b1=cs.max(axis=0);sx=(x1-x0)/(a1-a0);sy=(y1-y0)/(b1-b0);init=np.array([sx,0,0,-sy,x0-sx*a0,y1+sy*b0]);print('initial',init)
def coords(v,xy):return np.column_stack((v[0]*xy[:,0]+v[1]*xy[:,1]+v[4],v[2]*xy[:,0]+v[3]*xy[:,1]+v[5]))
def residual(v,xy):return distance(points(coords(v,xy)),target)
v=init
for threshold in [180,100,60,40,30]:
 selected=cs[residual(v,cs)<threshold];print('selected',threshold,len(selected))
 fit=least_squares(lambda v:residual(v,selected),v,loss='soft_l1',f_scale=3,max_nfev=150,xtol=1e-12,ftol=1e-12,gtol=1e-12);v=fit.x
 print('fit',v,'RMS',np.sqrt(np.mean(residual(v,selected)**2)))
print('final',v)
actual_pdf=[np.linalg.solve(np.array([[v[0],v[1]],[v[2],v[3]]]),(np.array(pp.exterior.coords)-np.array([v[4],v[5]])).T).T for pp in (municipality.geoms if municipality.geom_type=='MultiPolygon' else [municipality])]
# Overlay source-defined municipal boundary fit for independent visual comparison.
from PIL import Image,ImageDraw
im=Image.frombytes('RGB',[int(P.rect.width),int(P.rect.height)],P.get_pixmap().samples);draw=ImageDraw.Draw(im);
for part in actual_pdf:draw.line([tuple(x) for x in part],fill='magenta',width=2)
im.save(str(ROOT/'.local/neighborhoods/tatabanya-register.png'))
(ROOT/'.local/neighborhoods/tatabanya-registration.json').write_text(json.dumps(dict(affinePdfToEov=list(v),calibrationPdfPoints=selected.tolist(),calibrationRmsM=float(np.sqrt(np.mean(residual(v,selected)**2))),municipality=m)))
