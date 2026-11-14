#!/usr/bin/env python3
"""Retain literal OSM housing-estate, airport and industrial-area footprints."""
from pathlib import Path
import json,hashlib
from shapely.geometry import shape
HERE=Path(__file__).resolve().parent
source=HERE/'context-source-areas.geojson';rows={f['id']:f for f in json.loads(source.read_text())['features']}
spec=[
 ('osm:relation:2763405','Kecskemét','Kecskeméti Katonai Repülőtér',['MH 59. Szentgyörgyi Dezső Repülőbázis']),
 ('osm:relation:21208975','Kecskemét','Mercedes ipartelepek',['Mercedes-Benz és környező ipartelepek']),
 ('osm:relation:21208976','Kecskemét','Nyugati ipartelepek',['Nyugati ipartelep','Nyugati iparterület']),
 ('osm:relation:2763384','Kecskemét','Déli ipartelepek',['Déli ipartelep']),
 ('osm:relation:2763387','Kecskemét','Keleti ipartelepek',['Keleti ipartelep']),
 ('osm:way:402120271','Debrecen','Füredi Kapu lakópark',[]),
 ('osm:way:486940500','Debrecen','City Gardens lakópark',[]),
 ('osm:way:850490997','Debrecen','Szoboszlói Úti Lakópark',[]),
 ('osm:way:1181067797','Debrecen','Dóczy-park',[]),
 ('osm:relation:5385714','Debrecen','Daniella Ipari Park',[]),
 ('osm:way:1500195261','Debrecen','Hétvezér Ipari Park',[])
]
features=[]
for ident,city,name,aliases in spec:
    original=rows[ident];assert shape(original['geometry']).is_valid
    old=original['properties']['source'];p={'name':name,'municipality':city,'aliases':aliases,
       'sourceName':old['tags'].get('name'),'method':'source_polygon','estimated':False,'semanticFootprint':True,
       'boundaryKind':'named_source_area','qualityScore':55,'sourceUrl':old['url'],'source':old,
       'sourceGeometryUnmodified':True,'sourceGeometrySha256':hashlib.sha256(json.dumps(original['geometry'],separators=(',',':')).encode()).hexdigest(),
       'approximationNote':'Exact original OSM named housing-estate, industrial-area or airport outline retained. Its named footprint may differ from a broader historical quarter extent. Singular/plural industrial names and the military airfield/base names are searchable variants of the same local facility/area. No circle or generated edges.',
       'pointRadiusFallback':False}
    features.append({'type':'Feature','id':'native-next:'+ident,'properties':p,'geometry':original['geometry']})
(HERE/'native-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
print(json.dumps({'featureCount':len(features),'names':[f['properties']['name'] for f in features]},ensure_ascii=False))
