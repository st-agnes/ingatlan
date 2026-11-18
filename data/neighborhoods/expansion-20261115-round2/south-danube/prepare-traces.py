#!/usr/bin/env python3
"""Convert saved human map traces to WGS84 and record intersecting native roads.
Input vertices were manually selected from the archived context renders.
"""
from pathlib import Path
import json,gzip
from shapely.geometry import Polygon,shape
H=Path(__file__).resolve().parent
def load(n):
 p=H/n;return json.load(gzip.open(p,'rt')) if n.endswith('.gz') else json.loads(p.read_text())
roads=load('source-roads.geojson.gz')['features']
traces=[]
for x in load('pixel-traces.json')['traces']:
 reg=load(x['view']+'-context-registration.json');b=reg['bounds'];scale=reg['scale'];cos=reg['longitudeScaleCosine'];ox,oy=reg['originPixel']
 cs=[[round(b[0]+(u-ox)/scale/cos,9),round(b[1]+(oy-v)/scale,9)] for u,v in x['pixels']]
 if cs[0]!=cs[-1]:cs.append(cs[0])
 g=Polygon(cs)
 if not g.is_valid:raise ValueError('invalid pixel trace '+x['name'])
 hits=[f for f in roads if x['municipality'] in f['properties'].get('municipalities',[]) and shape(f['geometry']).intersects(g)]
 hits.sort(key=lambda f: (0 if f['properties'].get('name') else 1,f['id']))
 traces.append({k:v for k,v in {**x,'coordinates':cs,'sourceWayIds':[f['id'] for f in hits],'mapRegistrationFile':x['view']+'-context-registration.json'}.items() if k!='pixels'})
(H/'trace-specifications.json').write_text(json.dumps({'schemaVersion':1,'traces':traces},ensure_ascii=False,indent=2)+'\n')
print('trace count',len(traces))
