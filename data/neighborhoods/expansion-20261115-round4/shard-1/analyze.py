#!/usr/bin/env python3
from pathlib import Path
import json,gzip,unicodedata
from shapely.geometry import shape,Point
from shapely.ops import transform
from pyproj import Transformer
H=Path(__file__).resolve().parent;CTX=H.parent/'contexts';task=json.load(open(H/'target-selection.json'))
fwd=Transformer.from_crs(4326,23700,always_xy=True).transform
def load(p):return json.load(gzip.open(p,'rt')) if p.suffix=='.gz' else json.load(open(p))
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
records=[];i=0
for city in task['municipalities']:
 c=CTX/city['contextKey'];areas=load(c/'areas.geojson.gz')['features'];roads=load(c/'roads.geojson.gz')['features'];labels=load(c/'labels.geojson')['features'];addresses=load(c/'addresses.geojson.gz')['features']
 ash=[shape(f['geometry']) for f in areas]
 for row in city['targets']:
  p=Point(row['pointCandidates'][0]['coordinates']) if row['pointCandidates'] else None
  a=[]
  for f,g in zip(areas,ash):
   if p and g.covers(p) or f['properties'].get('name') and norm(f['properties']['name'])==row['nameKey']:
    tags=f['properties']['tags'];a.append({'id':f['id'],'name':f['properties'].get('name'),'tags':{k:v for k,v in tags.items() if k in ['name','place','landuse','natural','leisure','amenity','building','water']},'areaM2':round(transform(fwd,g).area),'containsOtherLabelCount':sum(g.covers(shape(l['geometry'])) for l in labels if l['properties']['name']!=row['name']),'coversPoint':bool(p and g.covers(p))})
  addr=[f for f in addresses if any(norm(str(f['properties']['tags'].get(k,'')))==row['nameKey'] for k in ['addr:place','addr:suburb'])]
  records.append({'index':i,'municipality':city['municipality'],'contextKey':city['contextKey'],'name':row['name'],'nameKey':row['nameKey'],'point':list(p.coords)[0] if p else None,'areas':sorted(a,key=lambda x:x['areaM2']),'matchingAddressCount':len(addr),'matchingAddressIds':[f['id'] for f in addr]})
  i+=1
(H/'analysis.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
for x in records:print(x['index'],x['municipality'],x['name'],'addr',x['matchingAddressCount'],'areas',[(a['id'],a['name'],a['tags'],a['areaM2'],a['containsOtherLabelCount']) for a in x['areas']])
