#!/usr/bin/env python3
"""Freeze already archived OSM road fabric around the remaining Budapest names."""
from pathlib import Path
import json,gzip,hashlib
from shapely.geometry import shape,box
HERE=Path(__file__).resolve().parent
OLD=HERE.parents[1]/'expansion-20261114-next'/'budapest-remaining'
INV=HERE.parents[1]/'expansion-20261114'/'inventory'/'priority-cities.json'
names=next(a['missingNames'] for a in json.loads(INV.read_text())['cities'] if a['municipality']=='Budapest')
pts=[f for f in json.loads((OLD/'name-points.geojson').read_text())['features'] if f['properties']['name'] in names]
def dump(p,o):p.write_text(json.dumps(o,ensure_ascii=False,separators=(',',':'))+'\n')
dump(HERE/'name-points.geojson',{'type':'FeatureCollection','features':pts})
parents=json.loads((OLD/'parent-features.geojson').read_text())['features']
dump(HERE/'parent-features.geojson',{'type':'FeatureCollection','features':[f for f in parents if any(shape(f['geometry']).covers(shape(p['geometry'])) for p in pts)]})
for src in OLD.glob('*-source-roads.geojson.gz'):
 fs=[]
 for f in json.loads(gzip.open(src,'rt').read())['features']:
  g=shape(f['geometry'])
  if any(g.intersects(box(p['geometry']['coordinates'][0]-.018,p['geometry']['coordinates'][1]-.012,p['geometry']['coordinates'][0]+.018,p['geometry']['coordinates'][1]+.012)) for p in pts):fs.append(f)
 out=HERE/src.name
 with gzip.GzipFile(filename=str(out),mode='wb',mtime=0) as z:z.write((json.dumps({'type':'FeatureCollection','features':fs},ensure_ascii=False,separators=(',',':'))+'\n').encode())
 print(src.name,len(fs),flush=True)
dump(HERE/'source-manifest.json',{'date':'2026-11-15','sources':[{'path':str(p.relative_to(HERE.parents[3])),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [INV,OLD/'name-points.geojson',OLD/'parent-features.geojson',*OLD.glob('*-source-roads.geojson.gz')]],'note':'Saved actual OSM road geometries, reused without full country scan. ODbL-1.0, © OpenStreetMap contributors.'})
