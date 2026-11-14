#!/usr/bin/env python3
"""Extract literal local PBF source geometry. No requests; no generated boundaries."""
from pathlib import Path
import json,gzip,tempfile,hashlib
import osmium
from shapely import from_wkb
from shapely.geometry import shape,mapping
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];DATA=ROOT/'data/neighborhoods';PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
parents={f['properties']['name']:f for f in json.loads(gzip.decompress((DATA/'sources/country-osm/municipalities.geojson.gz').read_bytes()))['features'] if f['properties']['name'] in ['Gyula','Salgótarján','Hódmezővásárhely']}
bounds={n:shape(f['geometry']).bounds for n,f in parents.items()};targets=json.loads((HERE/'target-name-points.geojson').read_text())['features'];centers=[f['geometry']['coordinates'] for f in targets]
manifest=json.loads((DATA/'sources/country-osm/manifest.json').read_text());digest=manifest['input']['sha256'];factory=osmium.geom.WKBFactory();roads=[];areas=[];nodes=[];buildings=[]
def matching(bb):return [n for n,b in bounds.items() if not(bb[2]<b[0] or bb[0]>b[2] or bb[3]<b[1] or bb[1]>b[3])]
def source(obj,kind,ident,tags):return {'provider':'openstreetmap','osmType':kind,'osmId':ident,'url':f'https://www.openstreetmap.org/{kind}/{ident}','tags':tags,'version':obj.version,'timestamp':str(obj.timestamp),'pbfSha256':digest,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}
class Handler(osmium.SimpleHandler):
 def node(self,obj):
  tags=dict(obj.tags)
  if not(tags.get('place') or tags.get('name') in ['Batida','Szikáncs','Úrihegy','Űrhegy']):return
  c=[obj.location.lon,obj.location.lat];cities=matching([*c,*c])
  if cities or tags.get('name') in ['Batida','Szikáncs','Úrihegy','Űrhegy']:nodes.append({'type':'Feature','id':f'osm:node:{obj.id}','properties':{'name':tags.get('name'),'municipalities':cities,'source':source(obj,'node',obj.id,tags)},'geometry':{'type':'Point','coordinates':c}})
 def way(self,obj):
  tags=dict(obj.tags)
  if not any(tags.get(k) for k in ['highway','railway','waterway']):return
  try:
   pts=[(n.lon,n.lat) for n in obj.nodes]
   if len(pts)<2:return
   bb=[min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)];cities=matching(bb)
   if not cities:return
   g=from_wkb(bytes.fromhex(factory.create_linestring(obj)))
   if g.is_valid:roads.append({'type':'Feature','id':f'osm:way:{obj.id}','properties':{'name':tags.get('name'),'municipalities':cities,'source':source(obj,'way',obj.id,tags)},'geometry':mapping(g)})
  except (RuntimeError,ValueError):pass
 def area(self,obj):
  tags=dict(obj.tags)
  if not any(tags.get(k) for k in ['landuse','natural','leisure','building']):return
  try:
   g=from_wkb(bytes.fromhex(factory.create_multipolygon(obj)))
   if not g.is_valid:return
   cities=matching(g.bounds)
   if not cities:return
   if tags.get('building'):
    if not any(g.centroid.distance(__import__('shapely').geometry.Point(*c))<.008 for c in centers):return
    dest=buildings
   else:dest=areas
   kind='way' if obj.from_way() else 'relation';ident=obj.orig_id();dest.append({'type':'Feature','id':f'osm:{kind}:{ident}','properties':{'name':tags.get('name'),'municipalities':cities,'source':source(obj,kind,ident,tags)},'geometry':mapping(g)})
  except (RuntimeError,ValueError):pass
with tempfile.TemporaryDirectory(prefix='small-remaining-') as tmp:Handler().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('place','name','highway','railway','waterway','landuse','natural','leisure','building')])
for name,features in [('source-roads.geojson.gz',roads),('source-areas.geojson.gz',areas),('source-name-points.geojson',nodes),('source-buildings.geojson.gz',buildings),('source-municipalities.geojson',list(parents.values()))]:
 data=(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n').encode();(HERE/name).write_bytes(gzip.compress(data,mtime=0) if name.endswith('.gz') else data)
print(json.dumps({'roads':len(roads),'areas':len(areas),'buildings':len(buildings),'places':len(nodes)}),flush=True)
