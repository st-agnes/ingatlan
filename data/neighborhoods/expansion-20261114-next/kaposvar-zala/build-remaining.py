#!/usr/bin/env python3
from pathlib import Path
import json,gzip
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,box,Point,mapping,shape,MultiPolygon
from shapely.ops import transform,unary_union
from shapely.validation import make_valid

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
spec=json.loads((HERE/'remaining-traces.json').read_text());reg=json.loads((HERE/'kapos-north-registration.json').read_text());to_wgs=Transformer.from_crs(23700,4326,always_xy=True);to_eov=Transformer.from_crs(4326,23700,always_xy=True)
features=[]
def kapgeo(x,y,z=None):return to_wgs.transform(reg['originEov'][0]+x/reg['scalePixelsPerMetre'],reg['originEov'][1]+(reg['height']-y)/reg['scalePixelsPerMetre'])
points={p['name']:p for p in reg['labels']}
for row in spec['kaposNorth']:
 g=transform(kapgeo,Polygon(row['points']));assert g.is_valid
 features.append({'type':'Feature','id':'next-kapos-north:'+row['name'],'geometry':mapping(g),'properties':{'name':row['name'],'municipality':'Kaposvár','method':'map_road_parcel_inferred_area','estimated':True,'qualityScore':20,'candidateBoundaryKind':'neighbourhood','source':{'provider':'osm-road-map-inference','path':reg['sourcePath']},'nameEvidence':points[row['name']]['source'],'approximationNote':'Rural local area manually inferred from actual retained roads/tracks and named-place position. Road-side parcel groups guide coarse dividing links; no printed/legal boundary claimed.','absoluteAccuracyMetres':None}})
source=ROOT/'data/neighborhoods/sources/municipal-local-map-next'
matrix=np.array(json.loads((source/'zalaegerszeg-registration.json').read_text())['matrixPixelToEov']);linear=matrix[:2,:].T;offset=matrix[2,:]
def zpixels(x,y,z=None):
 east,north=to_eov.transform(x,y);a=np.asarray(east);b=np.asarray(north);q=np.stack([a-offset[0],b-offset[1]]);v=np.linalg.inv(linear)@q.reshape(2,-1)
 if np.ndim(a)==0:return v[0,0],v[1,0]
 return v[0].reshape(a.shape),v[1].reshape(a.shape)
def zgeo(x,y,z=None):return to_wgs.transform(x*matrix[0,0]+y*matrix[1,0]+matrix[2,0],x*matrix[0,1]+y*matrix[1,1]+matrix[2,1])
municipalities=json.loads(gzip.decompress((ROOT/'data/neighborhoods/sources/country-osm/municipalities.geojson.gz').read_bytes()))['features'];city=next(f for f in municipalities if f['properties']['name']=='Zalaegerszeg');frame=transform(zpixels,shape(city['geometry']))
names=['Belváros','Ola','Landorhegy','Páterdomb','Kertváros','Iparterület','Csácsbozsok','Vorhota','Zalabesenyő','Botfa','Bazita','Ebergény','Szenterzsébethegy']
old=[transform(zpixels,shape(f['geometry'])) for f in json.loads((HERE/'zala-urban-reference.geojson').read_text())['features']]
new=[transform(zpixels,shape(f['geometry'])) for f in json.loads((HERE/'features.geojson').read_text())['features'] if f['properties'].get('sourceSubdivisionKind')=='parent' or f['properties']['name'] in ['Ola','Landorhegy']]
urban=unary_union(old+new)
for row in spec['zalaOuter']:
 g=frame.intersection(box(*row['pixelClip'])).difference(urban)
 parts=list(g.geoms) if hasattr(g,'geoms') else [g];point=Point(row['printedLabel']);parts=sorted([p for p in parts if p.area>5],key=lambda p:p.distance(point));g=transform(zgeo,parts[0])
 if not g.is_valid:g=make_valid(g)
 assert g.is_valid and not g.is_empty
 features.append({'type':'Feature','id':'next-zala-outer:'+row['name'],'geometry':mapping(g),'properties':{'name':row['name'],'municipality':'Zalaegerszeg','method':'municipal_map_sector_inferred_area','estimated':True,'qualityScore':20,'candidateBoundaryKind':'planning_unit','sourceUnitNumber':row['unit'],'sourcePeriod':'2014-2020 ITS statistical groups','source':{'provider':'municipal-map-and-osm-frame-inference','url':'https://zalaegerszeg.hu/wp-content/uploads/2023/05/Zalaegerszeg_ITS.pdf','path':'data/neighborhoods/sources/municipal-local-map-next/zalaegerszeg-p12-image0.jpeg'},'approximationNote':spec['zalaOuterNote'],'absoluteAccuracyMetres':None}})
(HERE/'remaining-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
(HERE/'remaining-summary.json').write_text(json.dumps({'featureCount':len(features),'countsByMunicipality':{'Kaposvár':4,'Zalaegerszeg':4},'radiusFallbackCount':0,'allStructurallyValid':True,'note':'Four rural road/parcel interpretations and four broad source-era planning groups; not exact official fine boundaries.'},ensure_ascii=False,indent=2)+'\n')
print('8 remaining-area estimates')
