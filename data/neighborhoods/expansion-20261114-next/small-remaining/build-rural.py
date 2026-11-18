#!/usr/bin/env python3
"""Keep literal named/source rural surfaces, with explicit point-to-surface association."""
from pathlib import Path
import json,gzip,hashlib,unicodedata
from shapely.geometry import shape,mapping
from shapely.ops import unary_union,transform
from pyproj import Transformer
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];to=Transformer.from_crs(4326,23700,always_xy=True).transform
load=lambda p:json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())['features']
areas=load(HERE/'source-areas.geojson.gz');buildings=load(HERE/'source-buildings.geojson.gz');rows={f['id']:f for f in areas+buildings};nodes=load(HERE/'source-name-points.geojson');parents={f['properties']['name']:shape(f['geometry']) for f in load(HERE/'source-municipalities.geojson')}
spec=[
 {'city':'Gyula','name':'Mályvádi Őstölgyes','ids':['osm:way:1026826129'],'literalNamed':True,'note':'Literal named nature-reserve footprint. The geographical name is already present as a point-only neighbourhood reference; no artificial urban subdivision is implied.'},
 {'city':'Gyula','name':'Dénesmajor','ids':['osm:way:'+str(x)for x in [1417496682,1417665403,1417496680,1417665404,1417496679,1417665406,1417665405,1417496681,492530852,492530848]],'note':'Union of actual detached residential parcels along the same village street fabric (Árvíz/Keszi/Solymos/Mályvádi/Gelvács streets). Public road gaps remain gaps. Adjacent farmyards and surrounding agricultural fields are excluded.'},
 {'city':'Gyula','name':'Városerdő','ids':['osm:way:348012114','osm:way:441461663'],'note':'The two adjacent mapped residential surfaces of the detached Városerdő estate. The namepoint is8m outside the source residential boundary on its access street; no buffer is added merely to contain it.'},
 {'city':'Gyula','name':'Mályvádi erdészkolónia','ids':['osm:way:1466325910','osm:way:438364775'],'note':'The mapped small park/clearing at the namepoint and its nearby mapped forest-colony building. This is a coarse clearing-and-house search footprint, not the surrounding23.7km² forest and not an official whole-colony border.'},
 {'city':'Salgótarján','name':'Csókáspuszta','ids':['osm:relation:7575544'],'note':'Actual farmyard footprint containing the same-name placepoint; this represents the built-up farmstead, not an invented broad hill/forest district.'},
 {'city':'Salgótarján','name':'Ponyipuszta','ids':['osm:relation:18731460','osm:relation:18731461','osm:relation:18731458'],'note':'The immediately adjacent residential, industrial and farmyard source surfaces around the Ponyipuszta placepoint and Építők utca. Broader surrounding forest and separate Művésztelep/Felsőponyi areas are excluded.'},
 {'city':'Hódmezővásárhely','name':'Batida','ids':['osm:relation:2540316'],'note':'Literal detached village residential footprint matched to the actual hamlet namepoint, rather than placing the schematic distant-village inset from the older KSH map.'},
 {'city':'Hódmezővásárhely','name':'Szikáncs','ids':['osm:relation:14007220'],'note':'Literal detached village residential footprint matched to its actual hamlet namepoint. The same-name railway halt is excluded as a name control.'}
]
(HERE/'rural-selection.json').write_text(json.dumps({'areas':spec,'noCircleOrBuffer':True},ensure_ascii=False,indent=2)+'\n')
features=[]
for a in spec:
 raw=[rows[i]for i in a['ids']];geom=unary_union([shape(f['geometry'])for f in raw]);assert geom.is_valid and not geom.is_empty
 same=[f for f in nodes if f['properties'].get('name')==a['name'] and f['properties']['source']['tags'].get('place') in ['suburb','neighbourhood','quarter','hamlet','village','locality','farm'] and parents[a['city']].covers(shape(f['geometry']))];assert same,a['name'];point=same[0];literal=a.get('literalNamed',False)
 p={'name':a['name'],'municipality':a['city'],'method':'source_polygon' if literal else 'named_source_footprint','estimated':not literal,'semanticFootprint':True,'boundaryKind':'named_source_area' if literal else 'source_built_up_or_clearing_footprint','qualityScore':55 if literal else 25,'pointRadiusFallback':False,'sourceGeometryUnmodified':len(raw)==1,'nativeSourceComponentsRetained':True,'sourceUrl':raw[0]['properties']['source']['url'],'source':{'provider':'openstreetmap-native-surface-association','path':str((HERE/'source-areas.geojson.gz').relative_to(ROOT)),'sha256':hashlib.sha256((HERE/'source-areas.geojson.gz').read_bytes()).hexdigest(),'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},'sourceComponents':[{'id':f['id'],'source':f['properties']['source'],'geometrySha256':hashlib.sha256(json.dumps(f['geometry'],separators=(',',':')).encode()).hexdigest()}for f in raw],'nameEvidence':point,'namePointDistanceMetres':round(transform(to,geom).distance(transform(to,shape(point['geometry']))),1),'areaSquareMetres':round(transform(to,geom).area,1),'approximationNote':a['note']+' Geometry follows only the selected native surfaces; association with the broader place name is inferred unless the source polygon itself has that literal name. This can exclude roads/gaps and omit a larger historical extent; it is not a circle, hull or Voronoi cell.'}
 features.append({'type':'Feature','id':'small-remaining:'+a['city']+':'+a['name'],'properties':p,'geometry':mapping(geom)})
(HERE/'rural-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n');print(json.dumps({'count':len(features),'names':[f['properties']['name']for f in features]},ensure_ascii=False))
