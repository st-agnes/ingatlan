import json,pathlib,hashlib,shutil,numpy as np
from shapely.geometry import shape,Polygon,box,Point,mapping
from shapely.ops import unary_union,nearest_points,transform
from pyproj import Transformer
root=pathlib.Path('data/neighborhoods/sources/municipal-east');tmp=pathlib.Path('.local/neighborhoods/east-geometry');j=json.loads((tmp/'bekescsaba-raster-components.json').read_text())
def contour(comp):
 rows={}
 for y,x in comp['pixels']:rows.setdefault(y,[]).append(x)
 rects=[]
 for y,xs in rows.items():
  xs=sorted(xs);start=last=xs[0]
  for x in xs[1:]:
   if x>last+1:rects.append(box(start,y,last+1,y+1));start=x
   last=x
  rects.append(box(start,y,last+1,y+1))
 g=unary_union(rects)
 if g.geom_type=='MultiPolygon':g=max(g.geoms,key=lambda p:p.area)
 return Polygon(g.exterior).simplify(.65,preserve_topology=True)
outer=contour(j['municipality'][0]);source=np.array([outer.exterior.interpolate(t,normalized=True).coords[0] for t in np.linspace(0,1,700,endpoint=False)])
mun=next(f for f in json.load(open('.local/neighborhoods/country/municipalities.geojson'))['features'] if f['properties']['name']=='Békéscsaba')
fwd=Transformer.from_crs(4326,23700,always_xy=True);rev=Transformer.from_crs(23700,4326,always_xy=True);mg=transform(fwd.transform,shape(mun['geometry']));target=mg.boundary
xmin,ymin,xmax,ymax=target.bounds;pxmin,pymin,pxmax,pymax=outer.bounds
A=np.array([[(xmax-xmin)/(pxmax-pxmin),0],[0,-(ymax-ymin)/(pymax-pymin)]]);b=np.array([xmin-A[0,0]*pxmin,ymax-A[1,1]*pymin])
for n in range(35):
 pp=source@A.T+b;near=np.array([nearest_points(Point(*pt),target)[1].coords[0] for pt in pp]);dist=np.linalg.norm(near-pp,axis=1);keep=dist<np.percentile(dist,95);beta=np.linalg.lstsq(np.column_stack([source[keep],np.ones(sum(keep))]),near[keep],rcond=None)[0];A=beta[:2].T;b=beta[2]
print('fit',A.tolist(),b.tolist(),'residuals',np.percentile(dist,[50,95,100]).tolist(),flush=True)
def georef(x,y,z=None):return rev.transform(A[0,0]*np.asarray(x)+A[0,1]*np.asarray(y)+b[0],A[1,0]*np.asarray(x)+A[1,1]*np.asarray(y)+b[1])
# These six solid-color footprints are separately labelled in the actual municipal image.
parts=[('Erzsébethely (Jamina)','brightgreen',[0,2]),('Mezőmegyer','brightgreen',[1]),('Központ','palegreen',[0]),('Gerla','palegreen',[1]),('József Attila lakótelep (Lencsési)','teal',[0]),('Fényes','teal',[1])]
url='https://bekescsaba.hu/uploads/files/images/Teljes-varos-kitoeltoett.webp';src=pathlib.Path('.local/neighborhoods/nationwide-docs/originals/bekescsaba-map.webp');sha=hashlib.sha256(src.read_bytes()).hexdigest();res={'median':float(np.median(dist)),'p95':float(np.percentile(dist,95)),'max':float(max(dist))};features=[];pixelPaths=[]
rawGeometries={name:unary_union([contour(j[color][i]) for i in ii]) for name,color,ii in parts}
for name,color,ii in parts:
 g=rawGeometries[name]
 if name=='Központ':g=g.difference(unary_union([rawGeometries[n] for n in ['Erzsébethely (Jamina)','József Attila lakótelep (Lencsési)']]))
 geo=transform(georef,g);assert geo.is_valid
 pixelPaths.append({'name':name,'class':color,'componentNumbers':ii,'geometry':mapping(g)})
 features.append({'type':'Feature','id':'municipal:bekescsaba:raster:'+str(len(features)+1),'properties':{'name':name,'municipality':'Békéscsaba','boundaryKind':'neighbourhood','method':'municipal_raster_color_footprint_digitization_affine_georeferencing','evidenceUrls':[url,'https://bekescsaba.hu/terkepek',mun['properties']['source']['url']],'sourceDocuments':[{'url':url,'sha256':sha}],'controlPoints':{'method':'Affine fit of the image municipality outline to the actual OSM municipal boundary in EPSG23700','affineToEov':{'matrix':A.tolist(),'offset':b.tolist()},'boundaryMatchResidualMeters':res,'targetOsmRelationId':mun['properties']['source']['osmId']},'quality':{'status':'coarse_raster_digitization_review_required','sourceResolutionPixels':[936,662],'estimatedMetersPerPixel':float(np.mean(np.linalg.svd(A,compute_uv=False))),'boundaryMatchP95Meters':res['p95'],'independentInteriorControlVerified':False,'geometryValid':True},'reviewNotes':['Boundaries follow the six actual colored footprints of the municipal image; rural cyan regions are not attributed by proximity.','Color-mask classification and five-pixel closing fill text/road interruptions; boundary uncertainty is at least3sourcepixels. Tiny central-mask overlaps at touching brightgreen/teal footprints are removed with those distinct color footprints taking priority.','No Google basemap geometry is used. Municipal map image is independent of the Google iframe on its landing page.','The raster map has no publication date and no established reuse license; this remains an auditable research artifact.'],'licenseStatus':'source_map_reuse_not_established; OSM controls ODbL-1.0','usableForAddressAssignment':False},'geometry':mapping(geo)})
out=root/'bekescsaba-map-derived.geojson';out.write_text(json.dumps({'type':'FeatureCollection','name':'Békéscsaba municipal map colored neighborhood footprints','features':features},ensure_ascii=False,separators=(',',':'))+'\n');shutil.copyfile(src,root/'bekescsaba-quarters-map.webp');(root/'bekescsaba-pixel-paths.json').write_text(json.dumps({'sourceSha256':sha,'paths':pixelPaths},ensure_ascii=False,separators=(',',':'))+'\n')
proof={'schemaVersion':1,'sourceUrl':url,'sourceSha256':sha,'featureCount':len(features),'method':'Threshold color components, close5pixels, trace observed pixel-cell boundaries, simplify0.65pixel, subtract small central-mask overlap against distinct brightgreen/teal footprints, fit actual municipal outline to OSM inEOV','maskThresholds':{'brightgreen':'G-R>60 and B-R<20','palegreen':'23<G-R<=60 and B-R<24 and G-B>22','teal':'G-R>28 and B-R>=20 and G-B>8','municipality':'G-R>9 and G-B>-7'},'affineToEov':{'matrix':A.tolist(),'offset':b.tolist()},'boundaryMatchResidualMeters':res,'sourceLabelFootprints':pixelPaths,'allValid':True,'usableForAddressAssignment':False,'licenseEstablished':False,'files':[]}
for p in [out,root/'bekescsaba-quarters-map.webp',root/'bekescsaba-pixel-paths.json']:
 bb=p.read_bytes();proof['files'].append({'path':p.name,'bytes':len(bb),'sha256':hashlib.sha256(bb).hexdigest()})
(root/'bekescsaba-geometry-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print('wrote',len(features),out,flush=True)
