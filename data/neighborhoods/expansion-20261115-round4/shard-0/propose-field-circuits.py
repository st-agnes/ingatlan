#!/usr/bin/env python3
from pathlib import Path
import json,gzip
from shapely.geometry import shape,Point,mapping
from shapely.ops import unary_union,polygonize,transform
from pyproj import Transformer
P=Path(__file__).resolve().parent;C=P.parent/'contexts';tasks=json.load(open(P/'assignment.json'))['municipalities'];remaining={(r['municipality'],r['name']) for r in json.load(open(P/'unresolved.json'))['remainingNames']};T=Transformer.from_crs(4326,23700,always_xy=True).transform
rows=[];outputs=[]
for c in tasks:
 todo=[t for t in c['targets'] if (c['municipality'],t['name']) in remaining]
 if not todo:continue
 cp=C/c['contextKey'];roads=json.load(gzip.open(cp/'roads.geojson.gz','rt'))['features'];areas=json.load(gzip.open(cp/'areas.geojson.gz','rt'))['features'];lines=[];sources=[]
 for f in roads:
  tags=f['properties']['tags']
  if tags.get('highway') in ['footway','steps','pedestrian','platform','cycleway'] or tags.get('railway') in ['abandoned','razed','disused']:continue
  if tags.get('highway') or tags.get('waterway') or tags.get('railway'):
   lines.append(shape(f['geometry']));sources.append(('roads',f))
 for f in areas:
  tags=f['properties']['tags'];g=shape(f['geometry'])
  if tags.get('natural')=='mountain_range':continue
  if tags.get('landuse') in ['forest','farmland','residential','meadow','vineyard','allotments','orchard','farmyard','industrial'] or tags.get('natural') in ['wood','grassland','water','wetland','scrub']:
   if g.area<2e-7:continue
   lines.append(g.boundary);sources.append(('areas',f))
 polygons=list(polygonize(unary_union(lines)))
 for t in todo:
  if not t['pointCandidates']:continue
  pt=Point(t['pointCandidates'][0]['coordinates']);matches=[g for g in polygons if g.covers(pt)]
  if not matches:print('NO',c['municipality'],t['name']);continue
  g=min(matches,key=lambda g:g.area);area=round(transform(T,g).area)
  if area<5000 or area>15000000:print('SKIP',c['municipality'],t['name'],area);continue
  border=g.boundary;ids=[]
  for typ,f in sources:
   h=shape(f['geometry']);h=h.boundary if typ=='areas' else h
   if h.distance(border)<1e-10:ids.append(dict(kind=typ,id=f['id'],name=f['properties']['name'],tags=f['properties']['tags']))
  outputs.append(dict(type='Feature',id=c['contextKey']+':'+t['name'],properties=dict(municipality=c['municipality'],name=t['name'],areaM2=area,reviewStatus='PROPOSAL_ONLY_NOT_COLLECTED',boundarySources=ids),geometry=mapping(g)))
  print('CANDIDATE',c['municipality'],t['name'],area,'sources',len(ids),[(f['id'],f['name']) for f in ids[:12]])
(P/'field-circuit-proposals.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=outputs),ensure_ascii=False,indent=2)+'\n')
