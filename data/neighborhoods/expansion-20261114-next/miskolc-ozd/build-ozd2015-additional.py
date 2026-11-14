#!/usr/bin/env python3
"""Coarse source-derived city groups and named village footprints; no circular buffers."""
from pathlib import Path
import json,hashlib
import numpy as np
from shapely.geometry import shape,mapping,Polygon,Point
from shapely.ops import transform
from shapely.affinity import translate
from pyproj import Transformer
HERE=Path(__file__).resolve().parent
URL='https://www.ozd.hu/adat/Ozd_varos_honlapja_fajlok/Varoshaza/Tajekoztatok_es_felhivasok/Kozerdeku_adatok_es_informaciok/gazdasagi_informaciok/strategia_terv/2715-ozd-its-helyzetfeltaras-.pdf'
reg=json.loads((HERE/'ozd-2015-registration.json').read_text())
a=np.array(reg['matrixNative2015PixelToEov'])
to_ll=Transformer.from_crs(23700,4326,always_xy=True);to_eov=Transformer.from_crs(4326,23700,always_xy=True)
def eovgeom(g):
 def xy(x,y,z=None):
  x=np.asarray(x);y=np.asarray(y);return a[0,0]*x+a[1,0]*y+a[2,0],a[0,1]*x+a[1,1]*y+a[2,1]
 return transform(xy,g).simplify(8,preserve_topology=True)
features=[];native={}
for f in json.loads((HERE/'ozd-2015-native-pixel-polygons.geojson').read_text())['features']:
 name=f['properties']['name'];g=shape(f['geometry']);native[name]=g
 world=eovgeom(g)
 prop={'municipality':'Ózd','name':name,'method':'source_map_outline_coarse_registration_estimate','estimated':True,'quality':20,'sourceUrl':URL,'sourcePage':247,'sourceYear':2015,'sourceKind':'municipal_planning_city_group','semanticFootprint':True,'approximationNotes':'Actual four-colour source extent, traced from the 2015 municipal study. Coloured legends excluded. Source has built-up/function-oriented extents rather than complete administrative city land. Coarse affine image placement estimated from regional map labels; independent geographic accuracy not established. Distinct parent groups intentionally overlap finer named neighbourhoods. Not an official current cadastral boundary.','sourcePixelGeometryFile':'ozd-2015-native-pixel-polygons.geojson','registrationFile':'ozd-2015-registration.json','sourceSha256':hashlib.sha256((HERE/'ozd-megalapozo-2015.pdf').read_bytes()).hexdigest()}
 features.append({'type':'Feature','properties':prop,'geometry':mapping(transform(to_ll.transform,world))})
# The text pp252–253 describes Uraj and Szenna in separate narrow valleys,
# and the Uraj-patak road continuing towards Susa. Shape identity below is
# inferred from that topology, not an authoritative sub-boundary assertion.
parts=list(native['Északi városrész'].geoms)
susa=min(parts,key=lambda g:g.centroid.y)
uraj=min([g for g in parts if g.centroid.y>100],key=lambda g:g.centroid.y)
szenna=Polygon([(346,214),(336,221),(326,244),(329,265),(338,277),(341,294),(353,309),(365,300),(370,279),(376,273),(370,262),(374,251),(359,252),(359,224)])
choices=[('Susa',susa,[20.2464103,48.2724695],904032146,'north-west detached built-up island'),('Uraj',uraj,[20.2691454,48.248395],911925112,'northern narrow valley branch'),('Szenna',szenna,[20.2932858,48.2370431],None,'manually cut north-eastern residential valley arm')]
for name,pix,lonlat,oid,identity in choices:
 world=eovgeom(pix);x,y=to_eov.transform(*lonlat);world=translate(world,x-world.centroid.x,y-world.centroid.y)
 prop={'municipality':'Ózd','name':name,'method':'named_point_source_map_footprint_estimate','estimated':True,'quality':15,'sourceUrl':URL,'sourcePages':[247,252,253],'sourceYear':2015,'sourceKind':'inferred_neighbourhood_footprint','semanticFootprint':True,'approximationNotes':f'Estimated populated footprint only. {identity}; component/name association inferred from the source valley/road description. Source shape retained and approximately centred on the known locality point, because the coarse full-map georeferencing is unreliable at outlying villages. Not a circle, not a complete official or cadastral boundary. Source-based size and shape remain approximate.','sourceImageFile':'ozd-2015-p247-0.jpeg','placementPoint':lonlat,'componentNameAssociationInferred':True,'placementEstimated':True}
 if oid:prop['placementSourceUrl']=f'https://www.openstreetmap.org/node/{oid}'
 else:prop['placementSource']='existing local OSM place-node inventory'
 features.append({'type':'Feature','properties':prop,'geometry':mapping(transform(to_ll.transform,world))})
for f in features:
 g=shape(f['geometry']);assert g.is_valid and not g.is_empty and g.area>0
 assert g.bounds[0]>20 and g.bounds[2]<20.6 and g.bounds[1]>48 and g.bounds[3]<48.5
(HERE/'additional-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
summary={'featureCount':len(features),'municipality':'Ózd','broadPlanningGroups':4,'namedSourceFootprintEstimates':3,'circularBufferCount':0,'allValid':True,'geographicAccuracyEstablished':False,'doesNotChangeFrozenFirst50':True,'names':[f['properties']['name'] for f in features]}
(HERE/'additional-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
