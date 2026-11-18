#!/usr/bin/env python3
"""Preserve actual physical source map for four eastern municipalities."""
from pathlib import Path
import json,gzip,tempfile,time,hashlib
import osmium
from shapely import from_wkb
from shapely.geometry import mapping,shape
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent;DATA=ROOT/'data/neighborhoods';PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
CITIES=['Hosszúpályi','Monostorpályi','Mátészalka','Orosháza'];HASH='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def write(n,v):(OUT/n).write_text(json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n')
parents=[f for f in read(DATA/'sources/country-osm/municipalities.geojson.gz')['features'] if f['properties']['name'] in CITIES];bbs={f['properties']['name']:shape(f['geometry']).bounds for f in parents}
labels=[f for f in read(DATA/'sources/country-osm/named-nodes.geojson.gz')['features'] if f['properties'].get('municipality') in CITIES]
write('source-municipalities.geojson',{'type':'FeatureCollection','features':parents});write('source-labels.geojson',{'type':'FeatureCollection','features':labels})
targets=[r for r in read(DATA/'expansion-20261114/inventory/known-names.json')['names'] if r['municipality'] in CITIES and not r['hasCollectedPolygon']];write('targets.json',targets)
factory=osmium.geom.WKBFactory();areas=[];roads=[];start=time.monotonic()
def relevant(bb):return [city for city,b in bbs.items() if not(bb[2]<b[0] or bb[0]>b[2] or bb[3]<b[1] or bb[1]>b[3])]
def feature(obj,g,typ,ident,tags,cities):return {'type':'Feature','id':f'osm:{typ}:{ident}','properties':{'tags':tags,'name':tags.get('name'),'municipalities':cities,'sourceUrl':f'https://www.openstreetmap.org/{typ}/{ident}','version':obj.version,'timestamp':str(obj.timestamp),'pbfSha256':HASH},'geometry':mapping(g)}
class H(osmium.SimpleHandler):
 def way(self,obj):
  tags=dict(obj.tags)
  if not(tags.get('highway') or tags.get('railway') in {'rail','light_rail','narrow_gauge'} or tags.get('waterway') in {'river','stream','canal','ditch','drain'}):return
  try:
   pts=[(n.lon,n.lat) for n in obj.nodes]
   if len(pts)<2:return
   bb=(min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts));cities=relevant(bb)
   if not cities:return
   g=from_wkb(bytes.fromhex(factory.create_linestring(obj)))
   if not g.is_empty and g.is_valid:roads.append(feature(obj,g,'way',obj.id,tags,cities))
  except (RuntimeError,ValueError):pass
 def area(self,obj):
  tags=dict(obj.tags)
  if not(tags.get('landuse') or tags.get('leisure') or tags.get('natural') in {'wood','water','scrub','grassland','wetland'}):return
  try:
   g=from_wkb(bytes.fromhex(factory.create_multipolygon(obj)))
   if g.is_empty or not g.is_valid:return
   cities=relevant(g.bounds)
   if not cities:return
   areas.append(feature(obj,g,'way' if obj.from_way() else 'relation',obj.orig_id(),tags,cities))
  except (RuntimeError,ValueError):pass
with tempfile.TemporaryDirectory(prefix='east-small-map-') as tmp:H().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('landuse','leisure','natural','highway','railway','waterway')])
write('source-areas.geojson',{'type':'FeatureCollection','features':areas,'pbfSha256':HASH,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'});write('source-lines.geojson',{'type':'FeatureCollection','features':roads,'pbfSha256':HASH,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'})
print(json.dumps({'areas':len(areas),'lines':len(roads),'labels':len(labels),'seconds':round(time.monotonic()-start,1)}),flush=True)
