import json
from pathlib import Path
from shapely.geometry import shape,mapping
from shapely.ops import unary_union,polygonize
F=json.load(open('data/neighborhoods/sources/municipal-offline-next/kecskemet-all-local-roads.geojson'))['features']
S={'Városközpont':(['Dobó István körút','Horváth Döme körút','Batthyány utca','Csányi János körút','Koháry István körút','Hornyik János körút','Gáspár András körút'],['Bajcsy-Zsilinszky Endre körút','Piaristák tere','Széchenyi tér','Szilády Károly utca','Kölcsey utca']), 'Kossuthváros':(['Kossuth körút','Tizedes utca','Magyar utca','Batthyány utca','Horváth Döme körút','Mezei utca'],['Forrás utca','Rávágy tér','Bajcsy-Zsilinszky Endre körút']), 'Árpádváros':(['Dobó István körút','Magyar utca','Tizedes utca','Árpád körút','Petőfi Sándor utca'],['Batthyány utca','Forrás utca','Rávágy tér'])}
for name,(core,extra) in S.items():
 named=[f for f in F if f['properties']['name'] in core+extra]
 context=unary_union([shape(f['geometry']) for f in named]);selected=named+[f for f in F if not f['properties']['name'] and f['properties']['source']['tags']['highway'] not in ['steps','footway','path','cycleway','corridor','platform'] and shape(f['geometry']).distance(context)<.0008]
 geoms=[shape(f['geometry']) for f in selected];cells=list(polygonize(unary_union(geoms)));matches=[]
 for p in cells:
  used=[f for f,g in zip(selected,geoms) if p.boundary.intersection(g).length>1e-10];names={f['properties']['name'] for f in used}
  if set(core)<=names:
   matches.append({'type':'Feature','properties':{'name':name,'names':sorted(names),'sourceWays':[f['id'] for f in used]},'geometry':mapping(p)})
 print(name,'cells',len(cells),'matches',len(matches))
 for i,f in enumerate(matches):
  print(i,f['properties']['names']);Path(f'data/neighborhoods/sources/municipal-offline-more/{name}-candidate-{i}.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[f]},ensure_ascii=False,indent=2)+'\n')
