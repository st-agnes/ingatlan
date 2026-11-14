#!/usr/bin/env python3
"""Diagnostic map cells to review; this file does not select publishable data."""
from pathlib import Path
import json,collections
from shapely.geometry import shape,mapping,Point
from shapely.ops import transform,unary_union,polygonize
from shapely.strtree import STRtree
from pyproj import Transformer
HERE=Path(__file__).resolve().parent
load=lambda f:json.loads((HERE/f).read_text())
forward=Transformer.from_crs(4326,23700,always_xy=True).transform
inverse=Transformer.from_crs(23700,4326,always_xy=True).transform
targets=load('target-circles-reference.geojson')['features'];road_features=load('source-barriers.geojson')['features'];parent_features=load('prior-parent-features.geojson')['features'];cities=load('source-municipalities.geojson')['features'];landuse=load('source-landuse.geojson')['features']
all_candidates=[]
for city_f in cities:
 city=city_f['properties']['name'];city_g=transform(forward,shape(city_f['geometry']))
 local=[f['properties'] for f in targets if f['properties']['municipality']==city]
 points=[Point(forward(*f['sourcePoint']['coordinates'])) for f in local];point_tree=STRtree(points)
 local_roads=[f for f in road_features if city in f['properties']['municipalities']]
 lines=[transform(forward,shape(f['geometry'])) for f in local_roads];line_tree=STRtree(lines)
 parents=[('Municipality',city_g,'municipality',None)]
 for f in parent_features:
  p=f['properties']
  if p['municipality']==city and p['method'] in ['source_polygon','map_or_text_estimate']:
   parents.append((p['name'],transform(forward,shape(f['geometry'])),p['method'],p.get('selectedSource')))
 for parent_name,parent,parent_method,parent_source in parents:
  used=[int(i) for i in line_tree.query(parent,predicate='intersects')]
  for level in ['major','local']:
   eligible=[i for i in used if level=='local' or local_roads[i]['properties']['source']['tags'].get('highway') in {'motorway','trunk','primary','secondary','tertiary','unclassified'} or local_roads[i]['properties']['source']['tags'].get('railway') or local_roads[i]['properties']['source']['tags'].get('waterway')]
   cells=list(polygonize(unary_union([parent.boundary]+[lines[i].intersection(parent) for i in eligible])))
   for cell in cells:
    if not city_g.covers(cell.representative_point()) or not parent.covers(cell.representative_point()) or not 3_000<cell.area<3_000_000:continue
    hit=[int(i) for i in point_tree.query(cell,predicate='covers')]
    if len(hit)!=1:continue
    target=local[hit[0]];name=target['name'];small=any(w in name.casefold() for w in ['lakópark','lakótelep']) or target['sourcePoint']['placeKind']=='neighbourhood'
    if small and cell.area>800_000:continue
    boundaries=[{'sourceId':local_roads[i]['id'],'name':local_roads[i]['properties'].get('name'),'tags':local_roads[i]['properties']['source']['tags']} for i in eligible if cell.boundary.intersection(lines[i]).length>15]
    all_candidates.append({'type':'Feature','geometry':mapping(transform(inverse,cell)),'properties':{'municipality':city,'name':name,'kind':'road_cell','level':level,'parent':parent_name,'parentMethod':parent_method,'parentSource':parent_source,'area':round(cell.area,1),'boundaryWays':boundaries,'sourcePoint':target['sourcePoint']}})
 for f in landuse:
  if city not in f['properties']['municipalities']:continue
  g=transform(forward,shape(f['geometry']));hit=[int(i) for i in point_tree.query(g,predicate='covers')]
  if len(hit)!=1 or not 3000<g.area<3_000_000:continue
  target=local[hit[0]]
  all_candidates.append({'type':'Feature','geometry':f['geometry'],'properties':{'municipality':city,'name':target['name'],'kind':'landuse_surface','area':round(g.area,1),'source':f['properties']['source'],'sourcePoint':target['sourcePoint']}})
 print(city,len([f for f in all_candidates if f['properties']['municipality']==city]),flush=True)
for i,f in enumerate(all_candidates):f['id']='candidate:'+str(i)
(HERE/'diagnostic-candidates.geojson').write_text(json.dumps({'type':'FeatureCollection','features':all_candidates},ensure_ascii=False,separators=(',',':'))+'\n')
summary={}
for f in all_candidates:
 p=f['properties'];summary.setdefault(p['municipality'],{}).setdefault(p['name'],[]).append({k:p.get(k) for k in ['kind','level','parent','area']}|{'id':f['id'],'boundaries':list(dict.fromkeys(w.get('name') or str(w['tags']) for w in p.get('boundaryWays',[])))})
(HERE/'diagnostic-candidates.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print('total',len(all_candidates),flush=True)
