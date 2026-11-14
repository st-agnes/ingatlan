import fitz,json,pathlib,numpy as np,hashlib
from shapely.geometry import shape,LineString,Polygon,mapping
from shapely.ops import transform,unary_union,polygonize,nearest_points
from shapely import get_coordinates
from pyproj import Transformer
base=pathlib.Path('.local/neighborhoods/east-geometry')
p=fitz.open('.local/neighborhoods/nationwide-docs/originals/eger-map.pdf')[0];ds=p.get_drawings()
outer=[]
for i in range(164771,164780):
 for it in ds[i]['items']:
  assert it[0]=='l'
  outer.append(LineString([tuple(it[1]),tuple(it[2])]))
pdfline=unary_union(outer)
source=np.asarray([pdfline.interpolate(t,normalized=True).coords[0] for t in np.linspace(0,1,1200,endpoint=False)])
mun=next(f for f in json.load(open('.local/neighborhoods/country/municipalities.geojson'))['features'] if f['properties']['name']=='Eger')
fwd=Transformer.from_crs(4326,23700,always_xy=True);rev=Transformer.from_crs(23700,4326,always_xy=True)
mg=transform(fwd.transform,shape(mun['geometry']));target=mg.boundary
xmin,ymin,xmax,ymax=target.bounds;pxmin,pymin,pxmax,pymax=pdfline.bounds
A=np.array([[(xmax-xmin)/(pxmax-pxmin),0],[0,-(ymax-ymin)/(pymax-pymin)]])
b=np.array([xmin-A[0,0]*pxmin,ymax-A[1,1]*pymin])
for n in range(35):
 pp=source@A.T+b
 nearest=np.array([nearest_points(__import__('shapely').geometry.Point(*pt),target)[1].coords[0] for pt in pp])
 distances=np.linalg.norm(nearest-pp,axis=1)
 mask=distances<np.percentile(distances,90)
 q=np.column_stack([source[mask],np.ones(sum(mask))]);beta=np.linalg.lstsq(q,nearest[mask],rcond=None)[0]
 A=beta[:2].T;b=beta[2]
print('Affine',A.tolist(),b.tolist(),'distance median/95/max',np.percentile(distances,[50,95,100]).tolist(),flush=True)
# Retain actual filled planning paths; no contour generated from textual locations.
colors=[(.6,.8,0),(.749,0,1),(1,.749,0),(.4,.8,.8)]
selected=[]
for i,d in enumerate(ds):
 if not d.get('fill') or not any(np.linalg.norm(np.array(d['fill'])-np.array(c))<.002 for c in colors):continue
 if len(d['items'])<5 or any(it[0]!='l' for it in d['items']):continue
 lines=[LineString([tuple(it[1]),tuple(it[2])]) for it in d['items']]
 # 0.001PDFpoint precision normalization removes only float serialization noise (<1cm on ground).
 from shapely import set_precision
 faces=list(polygonize(unary_union([set_precision(l,.001) for l in lines])))
 if not faces:continue
 geom=unary_union(faces)
 if geom.area<50:continue
 selected.append((i,geom))
print('extracted',len(selected),flush=True)
# Keep PDF positions for review; source labels decoded separately from searchable text.
rows=[]
for i,g in selected:
 x,y=g.representative_point().coords[0]
 nearby=[]
 for blk in p.get_text('blocks'):
  bx0,by0,bx1,by1,txt,*_=blk
  if g.covers(__import__('shapely').geometry.Point((bx0+bx1)/2,(by0+by1)/2)):
   nearby.append(txt.strip())
 rows.append({'pdfDrawingIndex':i,'bounds':list(g.bounds),'areaPdfPoints':g.area,'nearbyText':nearby,'pdfGeometry':mapping(g)})
(base/'eger-vector-paths.json').write_text(json.dumps({'affineToEov':{'matrix':A.tolist(),'offset':b.tolist()},'boundaryMatchResidualMeters':{'median':float(np.median(distances)),'p95':float(np.percentile(distances,95)),'max':float(max(distances))},'paths':rows},ensure_ascii=False,indent=2))
for r in rows:print(r['pdfDrawingIndex'],round(r['areaPdfPoints']),r['nearbyText'],flush=True)
