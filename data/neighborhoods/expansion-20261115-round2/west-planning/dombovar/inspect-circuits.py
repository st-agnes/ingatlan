import json
from pathlib import Path
from shapely.geometry import shape
from shapely.ops import unary_union,polygonize
P=Path(__file__).parent;fs=json.load(open(P/'source-ways.geojson'))['features'];city=shape(json.load(open(P/'municipality.geojson'))['features'][0]['geometry'])
outer=['Erzsébet utca','Rákóczi utca','Teleki utca','Kesztyű utca','Köztársaság utca','Vörösmarty utca','Tóth Ede utca','Kölcsey utca','Kazinczy sor','Mikszáth Kálmán utca','Népköztársaság útja','Kórház utca','Kandó Kálmán utca','Berzsenyi utca','Dózsa György utca','Kossuth Lajos utca','Szabadság utca'];inner=['Szepessi utca','Széchenyi István utca','Ady Endre utca','Népköztársaság útja','Vörösmarty utca','Bajcsy-Zsilinszky utca','Jókai utca']
for name,names in [('outer',outer),('inner',inner)]:
 selected=[f for f in fs if (f['properties']['name'] in names or f['properties']['source']['tags'].get('old_name') in names) and shape(f['geometry']).intersects(city)]
 line=unary_union([shape(f['geometry']) for f in selected]);roundabouts=[f for f in fs if f['properties']['source']['tags'].get('junction')=='roundabout' and shape(f['geometry']).distance(line)<0.00025]
 selected+=roundabouts;polys=sorted(polygonize(unary_union([shape(f['geometry']) for f in selected])),key=lambda p:-p.area)
 print(name,'faces',[(round(p.area*8500000000),p.bounds) for p in polys[:10]],'missing',set(names)-{f['properties']['name'] for f in selected}-{f['properties']['source']['tags'].get('old_name') for f in selected})
