import json
from pathlib import Path
from shapely.geometry import shape,mapping
from shapely.ops import transform,unary_union,nearest_points
from pyproj import Transformer
OUT=Path(__file__).resolve().parent
F=json.loads((OUT/'szentes-local-lines.geojson').read_text())['features']
PROJECT=Transformer.from_crs(4326,23700,always_xy=True).transform
UNPROJECT=Transformer.from_crs(23700,4326,always_xy=True).transform
NAMES=['Kurca','Arany János utca','Bajcsy-Zsilinszky utca','Deák Ferenc utca','Apponyi tér','Baross utca','Kolozsvár utca','Attila út','Koszta József utca','Zrínyi utca','Villogó utca','Somogyi Béla utca','Szilfa utca','Vásárhelyi út','Nyíri köz','Kisér utca','Szent Anna utca']
D={}
for n in NAMES:
 fs=[x for x in F if x['properties']['name']==n and x['properties']['source']['tags'].get('highway') not in ['footway','cycleway','path','steps']]
 D[n]=unary_union([transform(PROJECT,shape(x['geometry'])) for x in fs])
report=[]
for i,n in enumerate(NAMES):
 n2=NAMES[(i+1)%len(NAMES)];a,b=D[n],D[n2]
 hit=a.intersection(b);p,q=nearest_points(a,b)
 row={'from':n,'to':n2,'distanceM':a.distance(b),'intersection':mapping(transform(UNPROJECT,hit)),'nearest':[list(transform(UNPROJECT,p).coords)[0],list(transform(UNPROJECT,q).coords)[0]]}
 report.append(row)
 print(n,'--',n2,round(a.distance(b),2),hit.wkt)
(OUT/'szentes-belvaros-first-graph-audit.json').write_text(json.dumps({'sourceCircuit':'Official IVS street/river chain; current OSM named centerlines audited only. No polygon created.','pairs':report},ensure_ascii=False,indent=2)+'\n')
