#!/usr/bin/env python3
"""Offline low-confidence placement of literal municipal planning-group outlines."""
from pathlib import Path
import json,gzip,hashlib
import numpy as np
from shapely.geometry import Polygon,Point,mapping,shape
from shapely.ops import transform
from pyproj import Transformer
H=Path(__file__).resolve().parent
URL='https://mako.hu/wp-content/uploads/2024/04/melleklet-fvs-mako-0706-fin-30.pdf'
PDF=H.parents[1]/'downloaded-sources/mako-fvs2024.pdf'
points={f['properties']['name']:f for f in json.loads(gzip.open(H.parent/'source-points.geojson.gz','rt').read())['features']}
controls={'Vertán':(293,373),'Újváros':(493,260),'Honvéd':(581,328),'Gerizdes':(533,586),'Bajcsy-Ráday':(414,650),'Ipari terület':(678,299),'Üdülőtelep':(338,783)}
to_eov=Transformer.from_crs(4326,23700,always_xy=True);to_ll=Transformer.from_crs(23700,4326,always_xy=True)
a=np.array([[x,y,1]for x,y in controls.values()]);b=np.array([to_eov.transform(*points[n]['geometry']['coordinates'])for n in controls]);matrix=np.linalg.lstsq(a,b,rcond=None)[0];residual=np.linalg.norm(a@matrix-b,axis=1)
def tr(x,y,z=None):
 x=np.asarray(x);y=np.asarray(y);return matrix[0,0]*x+matrix[1,0]*y+matrix[2,0],matrix[0,1]*x+matrix[1,1]*y+matrix[2,1]
sha=hashlib.sha256(PDF.read_bytes()).hexdigest();features=[];native=[];validation=[]
for r in json.loads((H/'source-traces.json').read_text())['areas']:
 pix=Polygon(r['points']);assert pix.is_valid,(r['name'],pix.is_valid)
 eov=transform(tr,pix);g=transform(to_ll.transform,eov);assert g.is_valid and g.area>0
 known=points[r['name']]['geometry']['coordinates'];assert g.covers(Point(known)),r['name']
 note='Rough manual trace of the actual coloured planning-group outline in municipal FVS figure43, printed page282. Source contains nine broad planning groups, not every historic quarter separately. Coarse affine placement uses seven approximate printed group-number positions and existing OSM neighbourhood points; label offset and background-map distortion remain unmeasured. Low-confidence source-derived estimate, not an official modern cadastral boundary. Broad groups intentionally overlap finer named neighbourhoods.'
 if r['name']=='Belváros':note+=' Belváros is associated approximately with the source Városközpont group based on the central Széchenyi/Csanád vezér tér description; the two names are not asserted to be exact-boundary synonyms.'
 if r['name']=='Üdülőtelep':note+=' Associated with source Maros-parti üdülőterület; the source describes the levee to the north and Maros River to the south.'
 p={'name':r['name'],'municipality':'Makó','sourceName':r['sourceName'],'sourceGroupNumber':r['number'],'method':'rough_manual_municipal_group_outline_coarse_georeference','estimated':True,'confidence':'low','qualityScore':15,'sourceUrl':URL,'sourceYear':2024,'sourcePage':282,'sourceFigure':43,'sourceSha256':sha,'sourceImage':'../fvs-p282-image1.jpeg','sourcePixelTraceFile':'source-traces.json','registrationFile':'registration.json','approximationNote':note,'radiusFallback':False}
 features.append({'type':'Feature','properties':p,'geometry':mapping(g)});native.append({'type':'Feature','properties':{'name':r['name'],'coordinateSpace':'Source-image pixels only; NOT WGS84'},'geometry':mapping(pix)})
 validation.append({'name':r['name'],'valid':True,'knownNamePointInside':True,'areaKm2':round(eov.area/1e6,5)})
(H/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
(H/'native-pixel-polygons.geojson').write_text(json.dumps({'type':'FeatureCollection','coordinateSpace':'Source-image pixels only; NOT WGS84','features':native},ensure_ascii=False,separators=(',',':'))+'\n')
reg={'coordinateSpace':'Source image945x841 pixel to EPSG:23700 affine','matrix':matrix.tolist(),'controls':[{'name':n,'sourcePixel':list(xy),'knownPoint':points[n]['geometry']['coordinates'],'sourceUrl':points[n]['properties']['source']['url'],'fitResidualMetres':float(err)}for(n,xy),err in zip(controls.items(),residual)],'rmsFitMetres':float(np.sqrt(np.mean(residual**2))),'independentAccuracyEstablished':False,'note':'Printed group-number positions are approximate placement controls, not surveyed junctions. Fit residual is not independent geographic accuracy.'}
(H/'registration.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n');(H/'summary.json').write_text(json.dumps({'featureCount':8,'allValid':True,'knownNamePointsCovered':8,'allEstimated':True,'circleCount':0,'sourcePdfSha256':sha,'rmsFitMetres':reg['rmsFitMetres'],'independentAccuracyEstablished':False,'features':validation},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'featureCount':8,'allValid':True,'rmsFitMetres':reg['rmsFitMetres']},ensure_ascii=False))
