import json,tempfile,osmium
from pathlib import Path
P=Path(__file__).parent
lines=[];areas=[]
class H(osmium.SimpleHandler):
 def way(self,w):
  t=dict(w.tags)
  if not (t.get('highway') or t.get('waterway') or t.get('railway') or t.get('landuse') or t.get('leisure') or t.get('historic')):return
  if not w.nodes or not w.nodes[0].location.valid():return
  lon,lat=w.nodes[0].lon,w.nodes[0].lat
  if not (17.21<lon<17.32 and 47.83<lat<47.91):return
  if not all(n.location.valid() for n in w.nodes):return
  coords=[[n.lon,n.lat] for n in w.nodes];closed=w.nodes[0].ref==w.nodes[-1].ref and len(coords)>3
  isarea=closed and (t.get('landuse') or t.get('leisure') or t.get('historic'))
  f=dict(type='Feature',id=f'osm:way:{w.id}',properties=dict(name=t.get('name',''),source=dict(osmType='way',osmId=w.id,tags=t,nodeRefs=[n.ref for n in w.nodes],objectVersion=w.version,objectTimestamp=str(w.timestamp),url=f'https://www.openstreetmap.org/way/{w.id}')),geometry=dict(type='Polygon' if isarea else 'LineString',coordinates=[coords] if isarea else coords))
  (areas if isarea else lines).append(f)
with tempfile.TemporaryDirectory(dir='/tmp') as temp:H().apply_file('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf',locations=True,idx='sparse_file_array,'+temp+'/idx')
for n,f in [('source-ways.geojson',lines),('source-areas.geojson',areas)]: (P/n).write_text(json.dumps(dict(type='FeatureCollection',features=f),ensure_ascii=False))
print(len(lines),len(areas))
