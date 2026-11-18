"""Extract exact statutory PDF vector paths and reproduce the recorded EOV registration.
Requires input municipal source hash recorded in tata-georeference-proof.json.
Does not infer quarter extents from residential landuse.
"""
import fitz,json,math
from pathlib import Path
from shapely.geometry import Polygon,MultiPolygon,LineString,shape,mapping
from shapely.ops import unary_union,transform,polygonize
from shapely.affinity import affine_transform
from pyproj import Transformer
from scipy.optimize import least_squares
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
p=fitz.open(str(Path(__file__).resolve().parent/'tata-map.source.pdf'))[0]
def rings(d):
 out=[];cs=[]
 for typ,a,b in d['items']:
  a=tuple(a);b=tuple(b)
  if cs and math.dist(a,cs[-1])>0.003:
   out.append(cs);cs=[]
  if not cs:cs=[a]
  cs.append(b)
 if cs:out.append(cs)
 return out
polys=[]
for i,d in enumerate(p.get_drawings()[:10]):
 rs=rings(d);print(i,'rings',[(len(r),math.dist(r[0],r[-1])) for r in rs])
 # Evenodd filled region constructed from each proper ring; symmetricdifference handles holes.
 poly=Polygon()
 for r in rs:
  pp=Polygon(r)
  if not pp.is_valid:
   # Interpret exact PDF filled path by noding crossings and retaining evenodd filled faces.
   def inside(x,y,rr):
    return sum(1 for (a,b),(c,e) in zip(rr,rr[1:]) if (b>y)!=(e>y) and x<(c-a)*(y-b)/(e-b)+a)%2==1
   faces=list(polygonize(unary_union(LineString(r))))
   pp=unary_union([face for face in faces if inside(face.representative_point().x,face.representative_point().y,r)])
   print('PDFfilledfaces',i,len(faces),pp.geom_type)
  poly=poly.symmetric_difference(pp)
 polys.append(poly)
city=unary_union(polys);print('city',city.is_valid,city.geom_type,city.bounds)
M=json.loads((ROOT/'.local/neighborhoods/country/municipalities.geojson').read_text())['features'];m=next(f for f in M if f['properties']['name']=='Tata');forward=Transformer.from_crs(4326,23700,always_xy=True).transform;official=transform(forward,shape(m['geometry']))
print('actual EOV bounds',official.bounds)
a0,b0,a1,b1=city.bounds;x0,y0,x1,y1=official.bounds
scale=(x1-x0)/(a1-a0);init=np.array([scale,0,0,-scale,x0-scale*a0,y1+scale*b0]);print('init',init)
cs=np.array([xy for poly in (city.geoms if city.geom_type=='MultiPolygon' else [city]) for xy in poly.exterior.coords]);target=official.boundary
# fixed source vertices to closest observed municipal boundary, affine fit then nearestpoint refinement.
def residual(v):
 xy=np.column_stack((v[0]*cs[:,0]+v[1]*cs[:,1]+v[4],v[2]*cs[:,0]+v[3]*cs[:,1]+v[5]))
 from shapely import points,distance
 return distance(points(xy),target)
fit=least_squares(residual,init,loss='soft_l1',f_scale=3,max_nfev=300,xtol=1e-12,ftol=1e-12,gtol=1e-12)
print('matrix',fit.x,'rms',np.sqrt(np.mean(residual(fit.x)**2)),'median',np.median(residual(fit.x)),'max',max(residual(fit.x)))
(ROOT/'.local/neighborhoods/tata-vector-fit.json').write_text(json.dumps({'affinePdfToEov':list(fit.x),'polygons':[mapping(x) for x in polys],'sourceCity':mapping(city),'municipality':m,'rmsM':float(np.sqrt(np.mean(residual(fit.x)**2))),'maxM':float(max(residual(fit.x)))}))
