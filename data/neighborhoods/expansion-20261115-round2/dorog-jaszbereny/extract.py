#!/usr/bin/env python3
"""Archive actual OSM road/landuse/building/address evidence in two bounded towns."""
import gzip, hashlib, json, tempfile
from pathlib import Path
import osmium
from shapely.geometry import shape, mapping, box

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
BOXES={'Dorog':(18.705,47.695,18.76,47.75),'Jászberény':(19.80,47.425,19.97,47.535)}
SHA='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
def save(name,o):
 b=(json.dumps(o,ensure_ascii=False,separators=(',',':'))+'\n').encode()
 (HERE/name).write_bytes(gzip.compress(b,mtime=0) if name.endswith('.gz') else b)
def town(lon,lat):
 for city,(x1,y1,x2,y2) in BOXES.items():
  if x1<=lon<=x2 and y1<=lat<=y2:return city

class Collector(osmium.SimpleHandler):
 def __init__(self):
  super().__init__();self.roads=[];self.areas=[];self.buildings=[];self.addresses=[]
 def node(self,n):
  city=town(n.location.lon,n.location.lat)
  if city and (n.tags.get('addr:street') or n.tags.get('addr:place')):
   self.addresses.append({'type':'Feature','id':'osm:node:'+str(n.id),'properties':{'municipality':city,'tags':dict(n.tags),'sourceUrl':'https://www.openstreetmap.org/node/'+str(n.id)},'geometry':{'type':'Point','coordinates':[n.location.lon,n.location.lat]}})
 def way(self,w):
  tags=dict(w.tags)
  if not any(k in tags for k in ['highway','railway','waterway','landuse','natural','building']):return
  try:
   if not len(w.nodes):return
   city=town(w.nodes[0].lon,w.nodes[0].lat)
   if not city:return
   coords=[[n.lon,n.lat] for n in w.nodes]
   if len(coords)<2:return
   f={'type':'Feature','id':'osm:way:'+str(w.id),'properties':{'municipality':city,'name':tags.get('name'),'tags':tags,'sourceUrl':'https://www.openstreetmap.org/way/'+str(w.id),'pbfSha256':SHA,'objectVersion':w.version},'geometry':{'type':'LineString','coordinates':coords}}
   if tags.get('highway') or tags.get('railway') or tags.get('waterway'):self.roads.append(f)
   if len(coords)>=4 and coords[0]==coords[-1] and any(k in tags for k in ['landuse','natural','building']):
    f={**f,'geometry':{'type':'Polygon','coordinates':[coords]}}
    if shape(f['geometry']).is_valid:
     (self.buildings if tags.get('building') else self.areas).append(f)
  except (RuntimeError,ValueError):pass

def main():
 c=Collector()
 with tempfile.TemporaryDirectory(prefix='dorog-jasz-osm-') as d:
  c.apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(d)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway','waterway','landuse','natural','building','addr:street','addr:place')])
 for name,rows in [('source-roads.geojson.gz',c.roads),('source-areas.geojson.gz',c.areas),('source-buildings.geojson.gz',c.buildings),('source-addresses.geojson.gz',c.addresses)]:save(name,{'type':'FeatureCollection','features':rows})
 inventory=json.loads((ROOT/'data/neighborhoods/expansion-20261114/inventory/known-names.json').read_text())['names']
 save('baseline-targets.json',{'targets':[r for r in inventory if r['municipality'] in BOXES and not r['hasCollectedPolygon']]})
 mun=json.loads((ROOT/'data/neighborhoods/sources/municipality-reference/municipalities.geojson').read_text())['features']
 selected=[f for f in mun if f['properties'].get('name') in BOXES or f['properties'].get('municipality') in BOXES]
 existing={f['properties'].get('name',f['properties'].get('municipality')) for f in selected}
 country=json.loads(gzip.decompress((ROOT/'data/neighborhoods/sources/country-osm/municipalities.geojson.gz').read_bytes()))['features']
 selected.extend(f for f in country if f['properties'].get('name',f['properties'].get('municipality')) in set(BOXES)-existing)
 save('source-municipalities.geojson',{'type':'FeatureCollection','features':selected})
 save('source-manifest.json',{'source':'https://download.geofabrik.de/europe/hungary.html','snapshotDate':'2026-11-12T21:23:05Z','pbfSha256':SHA,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','bounds':BOXES,'counts':{k:len(getattr(c,k)) for k in ['roads','areas','buildings','addresses']}})
 print({k:len(getattr(c,k)) for k in ['roads','areas','buildings','addresses']})
if __name__=='__main__':main()
