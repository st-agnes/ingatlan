#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
from shapely.geometry import shape,mapping,LineString
from shapely.ops import unary_union,polygonize,transform
from shapely.affinity import affine_transform
from pyproj import Transformer,Geod
P=Path(__file__).resolve().parent;ROOT=P.parents[3]; GEOD=Geod(ellps='WGS84')
KURL='https://onkormanyzat.keszthely.hu/wp-content/uploads/document_library/12059/01_6.melleklet-_helyi_cselekvesi_terv-melleklet.pdf'
def write(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def feat(city,name,geom,method,url,note,**extra):
 if not geom.is_valid or geom.is_empty:raise ValueError(city+' '+name)
 p=dict(name=name,municipality=city,method=method,estimated=True,lowConfidence=True,confidence='low',sourceUrl=url,supportingUrls=[],approximationNote=note,boundaryKind='neighbourhood',usableForAddressAssignment=False,areaM2=round(abs(GEOD.geometry_area_perimeter(geom)[0])),**extra)
 return dict(type='Feature',id='estimated:west-planning:'+city+':'+name,properties=p,geometry=mapping(geom))
features=[]
T=P/'tata';source=shape(json.load(open(T/'source-native-path9.geojson'))['geometry']);proof=json.load(open(T/'source-registration.json'));eov=affine_transform(source,proof['affinePdfToEov']);poly=transform(Transformer.from_crs(23700,4326,always_xy=True).transform,eov)
features.append(feat('Tata','Külterületek',poly,'Reuse of exact native filled PDF drawing9, transformed with the archived source-map PDF-to-EOV registration and EOV-to-WGS84 projection.',proof['sourceUrl'],'The 2022 statutory map explicitly labels this large countryside unit in two places. Drawing9 is its actual native filled MultiPolygon with the separately numbered town-quarter exclusions, rather than a municipality-minus-current-quarter guess. Source geometry is native; registration to current OSM municipality remains approximate.',sourceDrawingIndex=9,sourcePeriod='2022 statutory quarter map',sourceDocuments=[dict(url=proof['sourceUrl'],path=str(T.relative_to(ROOT))+'/source-quarter-map2022.pdf',page=1)],quality='estimated-native-map-registration',lowConfidenceNativeRegistration=True))
K=P/'keszthely'
if (K/'source-ways.geojson').exists():
 fs=json.load(open(K/'source-ways.geojson'))['features'];city=shape(json.load(open(K/'municipality.geojson'))['features'][0]['geometry'])
 specs=[('Történelmi belváros',['Georgikon utca','Szalasztó utca','Rákóczi tér','Lovassy Sándor utca','Kazinczy Ferenc utca','Mártírok útja','Kossuth Lajos utca','Deák Ferenc utca']),('Szalasztó',['Kastély utca','Szalasztó utca','Rákóczi tér','Vásár tér','Cserszeg utca','Lehel utca'])]
 for name,names in specs:
  selected=[f for f in fs if f['properties']['name'] in names and shape(f['geometry']).intersects(city.buffer(0.0005))]
  faces=list(polygonize(unary_union([shape(f['geometry']) for f in selected])))
  if not faces:raise ValueError(name)
  poly=max(faces,key=lambda p:p.area) if name=='Történelmi belváros' else unary_union(faces)
  features.append(feat('Keszthely',name,poly,'Documentary municipal street-circuit interpretation: polygonize the archived current OSM centreline geometry of the explicitly enumerated boundary roads.',KURL,'Full source-defined quarter from the municipal local-action plan, printed page4. Street centrelines approximate road-side inclusion and source-period street topology. Kazinczy utca is normalized to the mapped Kazinczy Ferenc utca. No neighbourhood-point buffer, partial building footprint or parent-quarter substitution is used.',sourceLineIds=[f['id'] for f in selected],sourcePeriod='TOP-5.3.1-16-ZA1-2017-00010 municipal quarter descriptions; OSM2026-11-12',sourceUnitId='VK1' if name=='Történelmi belváros' else 'VK3',quality='estimated-documentary-street-circuit'))
for slug in ['keszthely','dombovar','tata','kormend']:
 for filename in ['additional-features.geojson','partial-rural-features.geojson']:
  extra=P/slug/filename
  if extra.exists(): features+=json.load(open(extra))['features']
seen=set()
for f in features:
 k=(f['properties']['municipality'],f['properties']['name'])
 if k in seen:raise ValueError('Duplicate name: '+str(k))
 seen.add(k)
 f['properties']['areaM2']=round(abs(GEOD.geometry_area_perimeter(shape(f['geometry']))[0]))
write('features.geojson',dict(type='FeatureCollection',features=features))
write('build-proof.json',dict(featureCount=len(features),crs='EPSG:4326',allValid=all(shape(f['geometry']).is_valid for f in features),nativeTataDrawingIndex=9,allEstimated=True,pointBuffersCreated=0,voronoiCellsCreated=0,inputSha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(P.rglob('*')) if f.is_file() and f.name in ['source-native-path9.geojson','source-registration.json','source-quarter-map2022.pdf','source-ways.geojson','source-areas.geojson','additional-features.geojson']}))
print('Generated',len(features),'valid estimated source-defined polygons.')
