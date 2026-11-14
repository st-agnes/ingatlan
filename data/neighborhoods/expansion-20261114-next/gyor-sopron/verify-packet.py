#!/usr/bin/env python3
"""Check spatial/schema integrity and pin the three final inputs, not accuracy."""
from pathlib import Path
from collections import Counter
import hashlib,json,unicodedata
from shapely.geometry import shape,Point
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
files=['sopron-features.geojson','gyor-surface-features.geojson','gyor-manual-features.geojson']
norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
all_features=[];seen=set();checks=[]
for name in files:
 fs=json.loads((HERE/name).read_text())['features'];all_features+=fs
 for f in fs:
  p=f['properties'];g=shape(f['geometry']);key=(norm(p['municipality']),norm(p['name']))
  assert key not in seen,('duplicate',key)
  seen.add(key)
  assert g.geom_type in ['Polygon','MultiPolygon'] and g.is_valid and not g.is_empty,p['name']
  assert 16<g.bounds[0]<g.bounds[2]<23 and 45<g.bounds[1]<g.bounds[3]<49,p['name']
  assert g.covers(Point(p['namePoint']['coordinates'])),p['name']
  assert 'circle' not in p['method'] and 'voronoi' not in p['method'],p['name']
  assert p.get('estimated') is True,p['name']
 checks.append({'path':str((HERE/name).relative_to(ROOT)),'sha256':hashlib.sha256((HERE/name).read_bytes()).hexdigest(),'features':len(fs)})
summary={'schemaVersion':1,'featureCount':len(all_features),'cities':dict(Counter(f['properties']['municipality'] for f in all_features)),
 'methods':dict(Counter(f['properties']['method'] for f in all_features)),'circleCount':0,'voronoiCount':0,
 'allValidPolygonal':True,'allOwnNamedPointsInside':True,'noNormalizedCityNameDuplicates':True,'absoluteAccuracyEstablished':False,
 'finalInputFiles':checks,'alternativesAreNotImportInputs':['surface-features.geojson','raw-surface-features.geojson'],
 'limit':'Valid rings, named-point inclusion and source-context preservation are integrity checks. They do not establish exact neighborhood boundaries or positional accuracy.'}
(HERE/'packet-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
