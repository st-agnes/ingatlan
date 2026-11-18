#!/usr/bin/env python3
"""Offline build of explicitly rough source-derived neighbourhood polygons."""
from pathlib import Path
import json,hashlib
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,shape,mapping,Point
from shapely.ops import transform
H=Path(__file__).resolve().parent
URL='https://www.ozd.hu/adat/Ozd_varos_honlapja_fajlok/Varoshaza/Tajekoztatok_es_felhivasok/Integralt_Telepulesfejlesztesi_Strategia/%C3%93zd%20V%C3%A1ros%20Integr%C3%A1lt%20Telep%C3%BCl%C3%A9sfejleszt%C3%A9si%20Strat%C3%A9gi%C3%A1ja_2024_v%C3%A9gleges.pdf'
m=np.asarray(json.loads((H/'ozd-rough-registration.json').read_text())['matrixMasterPixelToEov'])
t=Transformer.from_crs(23700,4326,always_xy=True)
def convert(x,y,z=None):
 a=np.asarray([x,y]);v=m[:2].T@a+(m[2][:,None]if a.ndim==2 else m[2]);return t.transform(v[0],v[1])
points={f['name']:f for f in json.loads((H/'ozd-name-map-points.json').read_text())}
features=[]
for a in json.loads((H/'ozd-traces.json').read_text())['areas']:
 g=transform(convert,Polygon(a['points']));assert g.is_valid and g.area>0
 assert g.covers(Point(points[a['name']]['coordinates']))
 features.append({'type':'Feature','properties':{'name':a['name'],'municipality':'Ózd','method':'rough_manual_municipal_street_map_partition','estimated':True,'confidence':'low','qualityScore':10,'sourceUrl':URL,'sourceYear':2024,'sourcePages':[49,54],'sourceImage':'ozd-map-p54.jpeg','sourcePixelTraceFile':'ozd-traces.json','registrationFile':'ozd-rough-registration.json','approximationNote':a['note']+' Low-confidence approximate neighbourhood footprint; placement uses earlier approximate source-map registration without independent accuracy validation. Overlaps with larger or neighbouring areas are intentional. Not an official current boundary.','sourceNamePoint':points[a['name']],'radiusFallback':False},'geometry':mapping(g)})
for extra in ['ozd-outer-features.geojson','szekszard-features.geojson']:
 if (H/extra).exists():features+=json.loads((H/extra).read_text())['features']
for f in features:
 g=shape(f['geometry']);assert g.is_valid and g.geom_type in ['Polygon','MultiPolygon']and g.area>0
(H/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
summary={'featureCount':len(features),'byMunicipality':{c:sum(f['properties']['municipality']==c for f in features)for c in ['Ózd','Szekszárd']},'names':[{'municipality':f['properties']['municipality'],'name':f['properties']['name']}for f in features],'allValid':True,'estimatedCount':sum(f['properties']['estimated']for f in features),'circleOrPointRadiusCount':0,'modernAccuracyEstablished':False,'geographicCrs':'EPSG:4326','collectionDate':'2026-11-15'}
(H/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
