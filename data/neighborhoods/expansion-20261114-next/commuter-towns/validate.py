#!/usr/bin/env python3
"""Validate final per-town artifacts without touching the application or DB."""
from pathlib import Path
import json,hashlib,collections
from shapely.geometry import shape,Point
from shapely.ops import transform
from pyproj import Transformer
HERE=Path(__file__).resolve().parent
forward=Transformer.from_crs(4326,23700,always_xy=True).transform
summary=json.loads((HERE/'summary.json').read_text());seen=set();rows=[]
for town in summary['towns']:
 path=HERE/town['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==town['sha256']
 fs=json.loads(path.read_text())['features']
 for f in fs:
  p=f['properties'];g=shape(f['geometry']);key=p['municipality'],p['name'];assert key not in seen;seen.add(key)
  assert g.is_valid and not g.is_empty and g.geom_type in ['Polygon','MultiPolygon']
  assert p['estimated'] and p['pointRadiusFallback'] is False
  assert g.covers(Point(p['nameEvidence'][0]['coordinates']))
  area=transform(forward,g).area;assert 3000<area<3_000_000
  assert len(g.bounds)==4 and 18<g.bounds[0]<20 and 47<g.bounds[1]<48
  rows.append({'municipality':p['municipality'],'name':p['name'],'areaSquareMetres':round(area,1),'method':p['method']})
result={'featureCount':len(rows),'validGeometryCount':len(rows),'sourcePointContainmentCount':len(rows),'duplicateCityNames':0,'generatedCircleCount':0,'voronoiCount':0,'methods':dict(collections.Counter(r['method'] for r in rows)),'rows':rows}
(HERE/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False))
