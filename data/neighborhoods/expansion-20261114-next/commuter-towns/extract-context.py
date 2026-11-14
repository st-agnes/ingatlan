#!/usr/bin/env python3
"""Retain offline source street fabric for five named commuter towns."""
from pathlib import Path
import gzip,json,hashlib,tempfile,osmium
from shapely import from_wkb
from shapely.geometry import shape,mapping

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
DATA=ROOT/'data/neighborhoods'
PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
CITIES=['Budaörs','Tatabánya','Dunakeszi','Szigetszentmiklós','Gödöllő']
def load(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def write(name,x):(HERE/name).write_text(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n')
manifest=load(DATA/'sources/country-osm/manifest.json');digest=manifest['input']['sha256']
assert hashlib.file_digest(PBF.open('rb'),'sha256').hexdigest()==digest
parents=[f for f in load(DATA/'sources/country-osm/municipalities.geojson.gz')['features'] if f['properties']['name'] in CITIES]
bounds={f['properties']['name']:shape(f['geometry']).bounds for f in parents}
labels=[f for f in load(DATA/'sources/country-osm/named-nodes.geojson.gz')['features'] if f['properties'].get('municipality') in CITIES]
fallback=[f for f in load(DATA/'expansion-20261114/inventory/provisional-fallback-features.geojson')['features'] if f['properties']['municipality'] in CITIES]
known=[f for f in load(DATA/'search-areas.geojson')['features'] if f['properties']['municipality'] in CITIES]
for name,fs in [('source-municipalities.geojson',parents),('source-labels.geojson',labels),('target-circles-reference.geojson',fallback),('prior-parent-features.geojson',known)]:write(name,{'type':'FeatureCollection','features':fs})
roads=[];surfaces=[];factory=osmium.geom.WKBFactory()
class Handler(osmium.SimpleHandler):
 def way(self,obj):
  tags=dict(obj.tags)
  eligible=tags.get('highway') in {'motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','unclassified','residential','living_street','service','track'} or tags.get('railway') in {'rail','light_rail','narrow_gauge'} or tags.get('waterway') in {'river','stream','canal'}
  surface=tags.get('landuse') in {'residential','industrial','allotments','forest','commercial','retail','recreation_ground','meadow','vineyard','orchard'} or tags.get('natural') in {'wood','water','scrub','grassland'}
  if not(eligible or surface):return
  try:
   coords=[(n.lon,n.lat) for n in obj.nodes]
   if len(coords)<2:return
   bb=(min(x for x,y in coords),min(y for x,y in coords),max(x for x,y in coords),max(y for x,y in coords))
   cities=[n for n,b in bounds.items() if not(bb[2]<b[0] or bb[0]>b[2] or bb[3]<b[1] or bb[1]>b[3])]
   if not cities:return
   geom=from_wkb(bytes.fromhex(factory.create_linestring(obj)))
   props={'name':tags.get('name'),'municipalities':cities,'source':{'provider':'openstreetmap','osmType':'way','osmId':obj.id,'url':'https://www.openstreetmap.org/way/'+str(obj.id),'tags':tags,'version':obj.version,'timestamp':str(obj.timestamp),'pbfSha256':digest,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}}
   f={'type':'Feature','id':'osm:way:'+str(obj.id),'properties':props,'geometry':mapping(geom)}
   if eligible:roads.append(f)
   if surface and coords[0]==coords[-1] and len(coords)>3:
    from shapely.geometry import Polygon
    poly=Polygon(coords)
    if poly.is_valid and not poly.is_empty:surfaces.append(dict(f,geometry=mapping(poly)))
  except (RuntimeError,ValueError):pass
with tempfile.TemporaryDirectory(prefix='commuter-map-source-') as td:
 Handler().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(td)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway','waterway','landuse','natural')])
for name,fs in [('source-barriers.geojson',roads),('source-landuse.geojson',surfaces)]:write(name,{'type':'FeatureCollection','features':fs})
write('source-summary.json',{'cities':CITIES,'roads':len(roads),'landuseSurfaces':len(surfaces),'namedPoints':len(labels),'targetReferenceCount':len(fallback),'pbfSha256':digest})
print(json.dumps({'roads':len(roads),'landuseSurfaces':len(surfaces),'targets':len(fallback)}),flush=True)
