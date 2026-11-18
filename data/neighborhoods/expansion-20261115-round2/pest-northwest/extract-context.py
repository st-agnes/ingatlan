#!/usr/bin/env python3
"""Freeze exact selected source ways. Cached Gödöllő first; one scan for uncached towns."""
from pathlib import Path
import json,gzip,hashlib,tempfile,osmium
from shapely.geometry import shape,Polygon
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];D=ROOT/'data/neighborhoods'
CITIES=['Szentendre','Gödöllő','Budakeszi','Piliscsaba','Pomáz','Dabas']
PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
digest='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
def load(p):return json.loads(gzip.open(p,'rt').read()) if p.suffix=='.gz' else json.loads(p.read_text())
def dump(fn,o):(HERE/fn).write_text(json.dumps(o,ensure_ascii=False,separators=(',',':'))+'\n')
def zipdump(fn,fs):
 with (HERE/fn).open('wb') as out:
  with gzip.GzipFile(filename='',fileobj=out,mode='wb',mtime=0) as z:z.write((json.dumps({'type':'FeatureCollection','features':fs},ensure_ascii=False,separators=(',',':'))+'\n').encode())
targets=[x for x in load(D/'expansion-20261114/inventory/known-names.json')['names'] if x['municipality'] in CITIES and not x['hasCollectedPolygon']]
dump('target-selection.json',targets)
parents=[f for f in load(D/'sources/country-osm/municipalities.geojson.gz')['features'] if f['properties']['name'] in CITIES]
dump('source-municipalities.geojson',{'type':'FeatureCollection','features':parents})
known=[f for f in load(D/'search-areas.geojson')['features'] if f['properties']['municipality'] in CITIES]
dump('prior-polygons.geojson',{'type':'FeatureCollection','features':known})
bounds={f['properties']['name']:shape(f['geometry']).bounds for f in parents if f['properties']['name']!='Gödöllő'}
roads=[];surfaces=[]
old=D/'expansion-20261114-next/commuter-towns'
for src,dst in [('source-barriers.geojson',roads),('source-landuse.geojson',surfaces)]:
 for f in load(old/src)['features']:
  if 'Gödöllő' in f['properties'].get('municipalities',[]):dst.append(f)
class Handler(osmium.SimpleHandler):
 def way(self,w):
  t=dict(w.tags);road=bool(t.get('highway') or t.get('railway') or t.get('waterway'))
  area=bool(t.get('landuse') or t.get('natural') or t.get('amenity') or t.get('tourism') or t.get('leisure') or t.get('military'))
  if not(road or area):return
  try:cs=[[n.lon,n.lat] for n in w.nodes]
  except osmium.InvalidLocationError:return
  if len(cs)<2:return
  bb=[min(c[0] for c in cs),min(c[1] for c in cs),max(c[0] for c in cs),max(c[1] for c in cs)]
  towns=[n for n,b in bounds.items() if not(bb[2]<b[0] or bb[0]>b[2] or bb[3]<b[1] or bb[1]>b[3])]
  if not towns:return
  pr={'name':t.get('name'),'municipalities':towns,'source':{'provider':'openstreetmap','url':'https://www.openstreetmap.org/way/'+str(w.id),'osmType':'way','osmId':w.id,'tags':t,'version':w.version,'timestamp':str(w.timestamp),'pbfSha256':digest,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}}
  f={'type':'Feature','id':'osm:way:'+str(w.id),'properties':pr,'geometry':{'type':'LineString','coordinates':cs}}
  if road:roads.append(f)
  if area and len(cs)>3 and cs[0]==cs[-1]:
   g=Polygon(cs)
   if g.is_valid and not g.is_empty:surfaces.append(dict(f,geometry={'type':'Polygon','coordinates':[cs]}))
with tempfile.TemporaryDirectory(prefix='pest-nw-source-') as td:
 Handler().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(td)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway','waterway','landuse','natural','amenity','tourism','leisure','military')])
zipdump('source-roads.geojson.gz',roads);zipdump('source-surfaces.geojson.gz',surfaces)
dump('source-summary.json',{'municipalities':CITIES,'targetCount':len(targets),'sourceWayCount':len(roads),'surfaceCount':len(surfaces),'pbfSha256':digest,'cachedGodolloSource':'data/neighborhoods/expansion-20261114-next/commuter-towns','note':'Complete original way coordinates retained; no clipping or generated point shapes.'})
print('roads',len(roads),'surfaces',len(surfaces),'targets',len(targets),flush=True)
