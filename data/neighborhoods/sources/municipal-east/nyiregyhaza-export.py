from PIL import Image,ImageFilter
import numpy as np,json,pathlib,hashlib,shutil
from collections import deque
from shapely.geometry import Polygon,Point,shape,mapping,box
from shapely.ops import unary_union,nearest_points,transform
from pyproj import Transformer
root=pathlib.Path('data/neighborhoods/sources/municipal-east');tmp=pathlib.Path('.local/neighborhoods/east-geometry');a=np.asarray(Image.open(tmp/'nyiregyhaza-source-image.jpeg').convert('RGB')).astype(float)
seeds={1:(324,250),2:(365,245),3:(310,302),4:(240,230),5:(323,202),6:(259,133),7:(371,143),8:(503,283),9:(390,460),10:(164,351)}
palette=np.array([np.median(a[y-3:y+4,x-3:x+4],axis=(0,1)) for x,y in seeds.values()]);dist=np.linalg.norm(a[:,:,None,:]-palette[None,None,:,:],axis=3);cls=np.argmin(dist,axis=2)+1;valid=(np.min(dist,axis=2)<48)&~np.all(a>235,axis=2)
def largest(mask):
 seen=np.zeros(mask.shape,bool);best=[]
 for y,x in np.argwhere(mask):
  if seen[y,x]:continue
  q=deque([(int(y),int(x))]);seen[y,x]=True;pts=[]
  while q:
   yy,xx=q.popleft();pts.append((yy,xx))
   for ny,nx in [(yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)]:
    if 0<=ny<mask.shape[0] and 0<=nx<mask.shape[1] and mask[ny,nx] and not seen[ny,nx]:seen[ny,nx]=True;q.append((ny,nx))
  if len(pts)>len(best):best=pts
 return best

def contour(pts):
 rows={}
 for y,x in pts:rows.setdefault(y,[]).append(x)
 rects=[]
 for y,xs in rows.items():
  xs=sorted(xs);start=last=xs[0]
  for x in xs[1:]:
   if x>last+1:rects.append(box(start,y,last+1,y+1));start=x
   last=x
  rects.append(box(start,y,last+1,y+1))
 g=unary_union(rects)
 if g.geom_type=='MultiPolygon':g=max(g.geoms,key=lambda p:p.area)
 return Polygon(g.exterior).simplify(.5,preserve_topology=True)
gs={}
for n in range(1,11):
 m=np.asarray(Image.fromarray(((cls==n)&valid).astype('uint8')*255).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3)))>0
 pts=largest(m);gs[n]=contour(pts);print('cluster',n,'pixels',len(pts),'bounds',gs[n].bounds,flush=True)
# Actual image city-outline follows the union of observed cluster-color footprints; fill only interior map text/roads.
outer=unary_union(list(gs.values()));outer=Polygon(max(outer.geoms,key=lambda p:p.area).exterior) if outer.geom_type=='MultiPolygon' else Polygon(outer.exterior)
# The regions have thin unclassified purple borders. A3-pixel close affects the outline only to connect the observed adjacent regions.
m=np.asarray(Image.fromarray(valid.astype('uint8')*255).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5)))>0
outer=contour(largest(m))
source=np.array([outer.exterior.interpolate(t,normalized=True).coords[0] for t in np.linspace(0,1,700,endpoint=False)])
mun=next(f for f in json.load(open('.local/neighborhoods/country/municipalities.geojson'))['features'] if f['properties']['name']=='Nyíregyháza');fwd=Transformer.from_crs(4326,23700,always_xy=True);rev=Transformer.from_crs(23700,4326,always_xy=True);target=transform(fwd.transform,shape(mun['geometry'])).boundary
xmin,ymin,xmax,ymax=target.bounds;pxmin,pymin,pxmax,pymax=outer.bounds;A=np.array([[(xmax-xmin)/(pxmax-pxmin),0],[0,-(ymax-ymin)/(pymax-pymin)]]);b=np.array([xmin-A[0,0]*pxmin,ymax-A[1,1]*pymin])
for it in range(40):
 pp=source@A.T+b;near=np.array([nearest_points(Point(*pt),target)[1].coords[0] for pt in pp]);dd=np.linalg.norm(near-pp,axis=1);keep=dd<np.percentile(dd,95);beta=np.linalg.lstsq(np.column_stack([source[keep],np.ones(sum(keep))]),near[keep],rcond=None)[0];A=beta[:2].T;b=beta[2]
res={'median':float(np.median(dd)),'p95':float(np.percentile(dd,95)),'max':float(max(dd))};print('fit residual',res,flush=True)
def georef(x,y,z=None):return rev.transform(A[0,0]*np.asarray(x)+A[0,1]*np.asarray(y)+b[0],A[1,0]*np.asarray(x)+A[1,1]*np.asarray(y)+b[1])
defs=json.load(open(root/'nyiregyhaza-boundary-definitions.json'))['definitions'];src=pathlib.Path('.local/neighborhoods/nationwide-docs/originals/nyiregyhaza-its.pdf');sha=hashlib.sha256(src.read_bytes()).hexdigest();url='https://uj.nyiregyhaza.hu/lib/rend_terv/its/felulvizsg/220804_its_jovahagyott_its.pdf';features=[];pixels=[]
for d in defs:
 n=d['sourceNumber'];g=gs[n];geo=transform(georef,g);assert geo.is_valid
 pixels.append({'number':n,'name':d['name'],'geometry':mapping(g)})
 features.append({'type':'Feature','id':'municipal:nyiregyhaza:its:'+str(n),'properties':{'name':d['name'],'municipality':'Nyíregyháza','boundaryKind':'planning_unit','method':'original_embedded_raster_color_region_digitization_affine_georeferencing','containedNeighborhoodNames':d['containedNames'],'evidenceUrls':[url,mun['properties']['source']['url']],'sourceDocuments':[{'url':url,'sha256':sha,'page':15,'referenceDate':'2022-07'}],'controlPoints':{'method':'Affine image-municipality-outline fit to actual municipal OSM boundary in EPSG23700','affineToEov':{'matrix':A.tolist(),'offset':b.tolist()},'boundaryMatchResidualMeters':res,'targetOsmRelationId':mun['properties']['source']['osmId']},'quality':{'status':'coarse_historical_planning_raster_review_required','sourceResolutionPixels':[598,583],'estimatedMetersPerPixel':float(np.mean(np.linalg.svd(A,compute_uv=False))),'boundaryMatchP95Meters':res['p95'],'independentInteriorControlVerified':False,'geometryValid':True},'reviewNotes':['One polygon follows each actual source numbered color region. Does not divide the25 nested quarter names by proximity.','Region masks use sampled source fill colors, RGB distance<48,3pixel closing, and original pixel-cell boundary tracing.','Thin source outlines and map text create at least3pixel boundary uncertainty; gaps between source outlines are retained.','Source2022 planning group boundaries and source map reuse rights need review before production assignment.'],'licenseStatus':'source_map_reuse_not_established; OSM controls ODbL-1.0','usableForAddressAssignment':False},'geometry':mapping(geo)})
out=root/'nyiregyhaza-planning-units.geojson';out.write_text(json.dumps({'type':'FeatureCollection','name':'Nyíregyháza2022 ITS planning groups from actual map','features':features},ensure_ascii=False,separators=(',',':'))+'\n');shutil.copyfile(src,root/'nyiregyhaza-its-2022.pdf');shutil.copyfile(tmp/'nyiregyhaza-source-image.jpeg',root/'nyiregyhaza-source-map.jpeg');(root/'nyiregyhaza-pixel-paths.json').write_text(json.dumps({'sourceSha256':sha,'palette':palette.tolist(),'pixelPaths':pixels},ensure_ascii=False,separators=(',',':'))+'\n')
proof={'schemaVersion':1,'sourceUrl':url,'sourceSha256':sha,'sourcePdfPage':15,'featureCount':10,'boundaryKind':'planning_unit','sourceRasterSize':[598,583],'sourcePdfImageXref':125,'palette':palette.tolist(),'affineToEov':{'matrix':A.tolist(),'offset':b.tolist()},'boundaryMatchResidualMeters':res,'allValid':True,'usableForAddressAssignment':False,'files':[]}
for p in [out,root/'nyiregyhaza-its-2022.pdf',root/'nyiregyhaza-source-map.jpeg',root/'nyiregyhaza-pixel-paths.json']:
 bb=p.read_bytes();proof['files'].append({'path':p.name,'bytes':len(bb),'sha256':hashlib.sha256(bb).hexdigest()})
(root/'nyiregyhaza-geometry-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print('wrote10',flush=True)
