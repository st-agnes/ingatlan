#!/usr/bin/env python3
"""Choose one source alternative per literal municipality/name within this packet."""
from pathlib import Path
import json,hashlib,unicodedata
from collections import defaultdict,Counter
from shapely.geometry import shape
HERE=Path(__file__).resolve().parent
norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
sources=['parent-features.geojson','native-features.geojson','road-cell-features.geojson'];groups=defaultdict(list)
for priority,file in enumerate(sources):
    for i,f in enumerate(json.loads((HERE/file).read_text())['features']):
        p=f['properties'];groups[(p['municipality'],norm(p['name']))].append((priority,file,i,f))
features=[];alternatives=[]
for key,rows in sorted(groups.items()):
    rows.sort(key=lambda x:(x[0],x[2]));chosen=rows[0][3];p=chosen['properties']
    aliases={n for _,_,_,f in rows for n in f['properties'].get('aliases',[])}
    aliases|={f['properties']['name'] for _,_,_,f in rows if f['properties']['name']!=p['name']}
    p['aliases']=sorted(aliases)
    p['producerAlternatives']=[{'path':str((HERE/file).relative_to(HERE.parents[3])),'featureIndex':i,
       'geometrySha256':hashlib.sha256(json.dumps(f['geometry'],separators=(',',':')).encode()).hexdigest()}
       for _,file,i,f in rows]
    assert shape(chosen['geometry']).is_valid and not shape(chosen['geometry']).is_empty
    features.append(chosen)
    if len(rows)>1:alternatives.append({'municipality':key[0],'name':p['name'],'alternatives':p['producerAlternatives']})
out={'type':'FeatureCollection','features':features};content=json.dumps(out,ensure_ascii=False,separators=(',',':'))+'\n'
(HERE/'features.geojson').write_text(content)
summary={'inputAlternativeCount':sum(len(x) for x in groups.values()),'featureCount':len(features),
  'municipalities':dict(Counter(f['properties']['municipality'] for f in features)),
  'methods':dict(Counter(f['properties']['method'] for f in features)),
  'radiusFallbackCount':0,'allGeometriesValid':True,'sourceAlternativesKeptInOriginalFiles':True,
  'selectionOrder':['municipal source-parent component union','literal named OSM estate/industrial/airport outline','rough physical street cell'],
  'duplicateAlternatives':alternatives,'sha256':{file:hashlib.sha256((HERE/file).read_bytes()).hexdigest() for file in sources},
  'outputSha256':hashlib.sha256(content.encode()).hexdigest(),
  'notes':['Road cells are source-informed approximate footprints, not observed whole-quarter borders.',
           'Nested differently named source-parent areas may overlap.',
           'Nativeindustrial singular/plural and military-airfield aliases are passed to root deduplication.']}
(HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:summary[k] for k in ['inputAlternativeCount','featureCount','municipalities','methods','outputSha256']},ensure_ascii=False))
