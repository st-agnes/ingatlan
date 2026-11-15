#!/usr/bin/env python3
"""Extract eight actual source-map enclosures and apply a rough label-based affine fit."""
from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image
from scipy import ndimage
from pyproj import Transformer
from shapely.geometry import box,Point,mapping
from shapely.ops import unary_union,transform
H=Path(__file__).resolve().parent
URL='https://szekszard.mcp.hu/application/files/3317/6786/2831/Szekszard_SUMP_Felulvizsgalat_Final.pdf'
IMAGE='szekszard-sump-p49-image2.png'
PDF=H.parent/'downloaded-sources/szekszard-sump-final.pdf'
SHA='b4c5c0b8829e22bb5ba740f7826225f7672984d9cfc731bf82a7d608576da4bb'
assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA
points={f['properties']['name']:f for f in json.loads((H/'szekszard-source-points.geojson').read_text())['features']}
seeds={'Bakta':(157,331),'Bottyánhegy':(158,181),'Csatár':(143,427),'Felsőváros':(78,221),'Iparterület':(289,233),'Parászta':(145,96),'Szőlőhegy':(125,544),'Városközpont':(210,230)}
controls={'Bakta':(157,324),'Bottyánhegy':(159,174),'Csatár':(146,417),'Felsőváros':(78,214),'Parászta':(147,90),'Szőlőhegy':(129,539)}
to_eov=Transformer.from_crs(4326,23700,always_xy=True);to_ll=Transformer.from_crs(23700,4326,always_xy=True)
a=np.array([[x,y,1]for x,y in controls.values()]);b=np.array([to_eov.transform(*points[n]['geometry']['coordinates'])for n in controls]);matrix=np.linalg.lstsq(a,b,rcond=None)[0]
residual=np.linalg.norm(a@matrix-b,axis=1)
def to_ground(x,y,z=None):
 x=np.asarray(x);y=np.asarray(y);return matrix[0,0]*x+matrix[1,0]*y+matrix[2,0],matrix[0,1]*x+matrix[1,1]*y+matrix[2,1]
im=np.array(Image.open(H/IMAGE).convert('L'));labels,count=ndimage.label(im>220)
features=[];native=[];proof=[]
for name,(x,y)in seeds.items():
 label=int(labels[y,x]);assert label!=int(labels[0,0])and label>0
 mask=ndimage.binary_fill_holes(labels==label);spans=[]
 for row in np.where(mask.any(axis=1))[0]:
  xs=np.where(mask[row])[0]
  for run in np.split(xs,np.where(np.diff(xs)>1)[0]+1):spans.append(box(int(run[0]),int(row),int(run[-1]+1),int(row+1)))
 pixel=unary_union(spans).simplify(.25,preserve_topology=True)
 assert pixel.geom_type=='Polygon'and pixel.is_valid
 native.append({'type':'Feature','properties':{'name':name,'coordinateSpace':'source image pixel, x right, y down; NOT WGS84','seedPixel':[x,y],'connectedComponent':label},'geometry':mapping(pixel)})
 ground=transform(to_ground,pixel);geo=transform(to_ll.transform,ground)
 assert geo.is_valid and geo.area>0
 if name in points:assert geo.covers(Point(points[name]['geometry']['coordinates']))
 note='Actual enclosed quarter outline extracted from the municipal 2025 SUMP figure13 (printed page49), reproduced from the city townscape handbook. Source map is schematic, without coordinate grid. A coarse affine fit uses six approximate printed quarter-label locations and existing OSM name points; label offsets and map distortion are not independently measured. This is an approximate historical/source-map quarter extent, not an official modern cadastral boundary. Raster number labels inside the enclosure were filled; genuine outer source outline retained. Overlap with finer or broader areas is intentional.'
 features.append({'type':'Feature','properties':{'name':name,'municipality':'Szekszárd','method':'source_map_raster_enclosure_coarse_georeference_estimate','estimated':True,'confidence':'low','qualityScore':20,'sourceUrl':URL,'sourceYear':2025,'sourcePage':49,'sourceFigure':13,'sourceSha256':SHA,'sourceImage':IMAGE,'sourcePixelGeometryFile':'szekszard-native-pixel-polygons.geojson','registrationFile':'szekszard-registration.json','approximationNote':note,'radiusFallback':False},'geometry':mapping(geo)})
 proof.append({'name':name,'regionLabel':label,'seedPixel':[x,y],'whitePixelCount':int((labels==label).sum()),'outerFootprintPixelCount':int(mask.sum()),'areaKm2':round(ground.area/1e6,5),'valid':True})
reg={'image':IMAGE,'imageSize':[int(im.shape[1]),int(im.shape[0])],'matrixSourcePixelToEov':matrix.tolist(),'controls':[{'name':name,'sourceLabelPixel':list(xy),'osmPoint':points[name]['geometry']['coordinates'],'sourceUrl':points[name]['properties']['source']['url'],'fitResidualMetres':float(err)}for(name,xy),err in zip(controls.items(),residual)],'rmsFitMetres':float(np.sqrt(np.mean(residual**2))),'independentAccuracyEstablished':False,'note':'Label-based placement is a low-confidence estimate. Fit residual is not independent geographic accuracy.'}
(H/'szekszard-registration.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
(H/'szekszard-native-pixel-polygons.geojson').write_text(json.dumps({'type':'FeatureCollection','coordinateSpace':'Source-image pixels ONLY; not WGS84','features':native},ensure_ascii=False,separators=(',',':'))+'\n')
(H/'szekszard-extraction-proof.json').write_text(json.dumps({'sourceImageSha256':hashlib.sha256((H/IMAGE).read_bytes()).hexdigest(),'grayscaleWhiteThreshold':220,'connectivity':4,'internalTextHolesFilled':True,'simplificationPixels':.25,'quarterOutlines':proof},ensure_ascii=False,indent=2)+'\n')
features+=json.loads((H/'szekszard-extra-features.geojson').read_text())['features']
(H/'szekszard-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
print(json.dumps({'features':len(features),'sourceMapEnclosures':len(native),'rmsFitMetres':reg['rmsFitMetres'],'independentAccuracyEstablished':False},ensure_ascii=False))
