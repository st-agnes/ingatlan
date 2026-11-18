#!/usr/bin/env python3
"""Digitally retain literal historic enclosures, placed by a coarse label-based fit."""
from pathlib import Path
import json,gzip,hashlib
import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import Polygon,box,mapping,Point
from shapely.ops import unary_union,transform
from pyproj import Transformer
H=Path(__file__).resolve().parent
URL='https://epa.oszk.hu/01600/01609/00016/pdf/MFME_EPA01609_1972_1973_1_041-081.pdf'
IM='historic-p40-image0.jpeg'
PDF=H.parent/'downloaded-sources/mako-historic-museum-study.pdf'
ps={f['properties']['name']:f for f in json.loads(gzip.open(H/'source-points.geojson.gz','rt').read())['features']}
controls={'Buják':(208,629),'Zsidó városrész':(394,555),'Orosz fertály':(496,573),'Kelemenhíd':(122,557),'Bánom':(178,530),'Honvéd':(628,514),'Táncsics telep':(445,255),'Dózsa-telep':(714,697),'Lesi':(251,784),'Belváros':(323,611)}
to_eov=Transformer.from_crs(4326,23700,always_xy=True);to_ll=Transformer.from_crs(23700,4326,always_xy=True)
a=np.array([[x,y,1]for x,y in controls.values()]);b=np.array([to_eov.transform(*ps[n]['geometry']['coordinates'])for n in controls]);m=np.linalg.lstsq(a,b,rcond=None)[0];res=np.linalg.norm(a@m-b,axis=1)
def to_ground(x,y,z=None):
 x=np.asarray(x);y=np.asarray(y);return m[0,0]*x+m[1,0]*y+m[2,0],m[0,1]*x+m[1,1]*y+m[2,1]
# Figure numbers are retained literally; modern scope may be larger than the source estate.
rows=[('Buják',(210,640),1,'Buják (1700)'),('Zsidó városrész',(392,556),3,'Zsidó fertály (1740s)'),('Orosz fertály',(492,574),4,'Orosz fertály (1743)'),('Cigánybécs',(587,465),8,'Cigánybécs (1811)'),('Kelemenhíd',(122,558),11,'Kelemenhíd (1861)'),('Vágóhíd',(322,331),12,'Vágóhíd (1861)'),('Kenyérváró',(204,444),14,'Kenyérvárói munkásházak (1907–12)'),('Sovány',(283,418),15,'Soványi munkásházak (1907–12)'),('Ardics',(128,482),17,'Ardicsi munkásházak (Vertán-telep, 1924–27)'),('Bánom',(178,536),21,'Bánom (1949–)'),('Újhegy',(75,610),23,'Kisujhegy / Ószegedi út menti házak'),('Lesi',(251,786),24,'Lesi, scattered historic development'),('Kenderföld',(187,404),31,'Kenderföld')]
manual=[('Táncsics telep',18,'Táncsics-telep (Bonczos-telep, 1940)',[[431,250],[452,249],[458,252],[458,266],[451,269],[431,268]]),('Oncsa-házak',19,'ONCSA houses (1942–)',[[350,260],[391,260],[391,264],[429,264],[429,271],[350,270]]),('Dózsa-telep',20,'Dózsa-telep (Levente-telep, 1942–46)',[[704,690],[719,690],[719,696],[733,696],[733,707],[716,707],[716,703],[704,703]]),('Ingó',26,'Ingó, scattered historic development',[[91,632],[101,629],[114,636],[114,646],[98,641],[91,640]])]
im=np.array(Image.open(H/IM).convert('L'));labels,count=ndimage.label(im>180)
features=[];native=[];proof=[]
def emit(name,num,source_name,pixel,origin,seed=None):
 assert pixel.is_valid and not pixel.is_empty and pixel.geom_type in ['Polygon','MultiPolygon']
 ground=transform(to_ground,pixel);geo=transform(to_ll.transform,ground)
 note=f'Literal historic map footprint from Tóth Ferenc, Makó településtörténeti vázlata, figure30, printed p79 (PDF p40). Source legend {num}: {source_name}. The source describes town growth up to the early1970s; older estate/fringe footprints may be much smaller than, or offset from, the modern conventional neighbourhood. Shape retained from the actual source enclosure, rather than a point radius. Coarse affine placement uses ten approximate map-label/locality controls; fit residual is not independent geographic accuracy. This is a low-confidence historical footprint estimate, not a complete current or cadastral boundary.'
 if name=='Ardics':note+=' Association uses the explicitly named Ardics worker-house area only; no global equivalence between modern Ardics and Vertán telep is asserted.'
 p={'name':name,'municipality':'Makó','method':'historical_source_map_enclosure_estimate','estimated':True,'confidence':'low','qualityScore':10,'sourceUrl':URL,'sourceYear':1974,'sourcePdfPage':40,'sourcePrintedPage':79,'sourceFigure':30,'sourceLegendNumber':num,'sourceLegendName':source_name,'sourceSha256':hashlib.sha256(PDF.read_bytes()).hexdigest(),'sourcePixelGeometryFile':'historic-native-pixel-polygons.geojson','sourceImage':IM,'registrationFile':'historic-registration.json','approximationNote':note,'radiusFallback':False,'semanticFootprint':True,'currentWholeQuarterExtentEstablished':False}
 features.append({'type':'Feature','properties':p,'geometry':mapping(geo)})
 native.append({'type':'Feature','properties':{'name':name,'sourceLegendNumber':num,'sourceLegendName':source_name,'coordinateSpace':'source image pixels, NOT WGS84','extraction':origin,'seedPixel':seed},'geometry':mapping(pixel)})
 proof.append({'name':name,'sourceLegendNumber':num,'extraction':origin,'areaKm2':round(ground.area/1e6,6),'knownModernNamePointInside':geo.covers(Point(ps[name]['geometry']['coordinates'])),'valid':True})
for name,(x,y),num,source_name in rows:
 label=int(labels[y,x]);assert label>0
 mask=ndimage.binary_fill_holes(labels==label);assert mask.sum()<25000
 spans=[]
 for row in np.where(mask.any(axis=1))[0]:
  xs=np.where(mask[row])[0]
  for run in np.split(xs,np.where(np.diff(xs)>1)[0]+1):spans.append(box(int(run[0]),int(row),int(run[-1]+1),int(row+1)))
 pixel=unary_union(spans).simplify(.25,preserve_topology=True)
 emit(name,num,source_name,pixel,'digitally extracted white enclosed region; internal map labels filled',[x,y])
for name,num,source_name,coords in manual:emit(name,num,source_name,Polygon(coords),'manual source outline trace of small literal estate footprint')
reg={'image':IM,'imageSize':[974,1418],'matrixSourcePixelToEov':m.tolist(),'controls':[{'name':n,'approximateMapLabelPixel':list(xy),'namePoint':ps[n]['geometry']['coordinates'],'sourceUrl':ps[n]['properties']['source']['url'],'fitResidualMetres':float(r)}for(n,xy),r in zip(controls.items(),res)],'rmsFitMetres':float(np.sqrt(np.mean(res**2))),'independentAccuracyEstablished':False,'note':'Historical source footprints retained; modern name points are placement hints, not boundary proof. Modern point exclusion is explicitly allowed and reported.'}
(H/'historic-registration.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
(H/'historic-native-pixel-polygons.geojson').write_text(json.dumps({'type':'FeatureCollection','coordinateSpace':'Source pixels only; NOT WGS84','features':native},ensure_ascii=False,separators=(',',':'))+'\n')
(H/'historic-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
(H/'historic-extraction-proof.json').write_text(json.dumps({'features':proof,'sourceThreshold':180,'connectivity':4,'internalLabelHolesFilled':True,'independentModernAccuracyEstablished':False},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'features':len(features),'digitallyExtracted':len(rows),'manualSmallSourceOutlines':len(manual),'rmsFitMetres':reg['rmsFitMetres'],'knownModernNamePointsInside':sum(x['knownModernNamePointInside']for x in proof)},ensure_ascii=False))
