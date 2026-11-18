import json
from pathlib import Path
from shapely.geometry import shape,mapping
from shapely.ops import unary_union,polygonize
P=Path(__file__).resolve().parent;F=json.loads((P/'all-local-roads.geojson').read_text())['features']
S={'Petőfiváros I.':(['Csalánosi út','Szüret utca','Tópart utca','Vízmű utca','Izsáki út'],['Dunaföldvári út']),'Petőfiváros II.':(['Csalánosi út','Szüret utca','Tópart utca','Vízmű utca','Sutus sor','Széles köz'],[])}
for name,(core,extra) in S.items():
 sel=[f for f in F if f['properties']['name']in core+extra and (f['properties']['name']!='Vízmű utca' or f['properties']['source']['tags']['highway']=='secondary')];context=unary_union([shape(f['geometry'])for f in sel]);sel += [f for f in F if not f['properties']['name'] and f['properties']['source']['tags']['highway']not in ['steps','footway','path','cycleway','platform','corridor','construction','proposed'] and shape(f['geometry']).distance(context)<.0008]
 g=[shape(f['geometry'])for f in sel];cells=list(polygonize(unary_union(g)));print(name,'cells',len(cells))
 for i,p in enumerate(cells):
  if p.area<.000002:continue
  used=[f for f,l in zip(sel,g)if p.boundary.intersection(l).length>1e-10];ns={f['properties']['name']for f in used}
  print('candidate',i,round(p.area*8e9),sorted(ns));(P/(name.replace(' ','-')+'-'+str(i)+'-diagnostic.geojson')).write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':name,'names':sorted(ns),'diagnosticOnly':True,'ways':[f['id']for f in used]},'geometry':mapping(p)}]},ensure_ascii=False,indent=2)+'\n')
