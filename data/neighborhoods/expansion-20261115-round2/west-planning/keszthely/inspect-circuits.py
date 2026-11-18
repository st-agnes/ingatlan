import json
from pathlib import Path
from shapely.geometry import shape,Point,LineString
from shapely.ops import unary_union,polygonize
P=Path(__file__).parent
fs=json.load(open(P/'source-ways.geojson'))['features']; city=shape(json.load(open(P/'municipality.geojson'))['features'][0]['geometry'])
specs=[('Történelmi belváros',['Georgikon utca','Szalasztó utca','Rákóczi tér','Lovassy Sándor utca','Kazinczy Ferenc utca','Mártírok útja','Kossuth Lajos utca','Deák Ferenc utca']),('Szalasztó',['Kastély utca','Szalasztó utca','Rákóczi tér','Vásár tér','Cserszeg utca','Lehel utca']),('Kertváros és Vadaskert',['Napfény sor','Hévízi út']),('Északi és keleti lakóterületek',['Bécsi kapu utca','Hévízi út','Károly Gyula utca','Tompa Mihály utca','Goldmark Károly utca','Szegfű utca','Rezi út','Csapás út','Szent Imre árok','Tapolcai út','Lovassy Sándor utca','Rákóczi tér','Vásár tér','Cserszeg utca','Lehel utca','Sopron utca','Bástya utca','Pál utca','Balassa Bálint utca']),('Északi városrész',['Tompa Mihály utca','Goldmark Károly utca','Szegfű utca','Rezi út','Csapás út','Szent Imre árok','Tapolcai út'])]
for name,names in specs:
 f=[f for f in fs if f['properties']['name'] in names and shape(f['geometry']).intersects(city.buffer(0.0005))]
 if name in ['Kertváros és Vadaskert','Északi városrész']:
  f+= [f for f in fs if f['properties']['source']['tags'].get('ref')=='71']
 lines=[shape(f['geometry']) for f in f]
 if name in ['Kertváros és Vadaskert','Északi városrész','Északi és keleti lakóterületek']:
  for pp in (city.geoms if city.geom_type=='MultiPolygon' else[city]):lines.append(LineString(pp.exterior.coords))
 polys=sorted(polygonize(unary_union(lines)),key=lambda p:-p.area)
 print(name,'lines',len(f),'polygons',[(round(p.area*8500000000),tuple(round(c,5) for c in p.bounds)) for p in polys[:8]],'missing',set(names)-{x['properties']['name'] for x in f})
