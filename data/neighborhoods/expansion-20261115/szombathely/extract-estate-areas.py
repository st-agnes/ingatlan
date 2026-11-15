from pathlib import Path
import json,osmium,tempfile
P=Path(__file__).parent
out=[]
class H(osmium.SimpleHandler):
 def way(self,w):
  t=dict(w.tags)
  if not (t.get('landuse') or t.get('building') or t.get('leisure')): return
  if len(w.nodes)<4 or w.nodes[0].ref != w.nodes[-1].ref:return
  if not w.nodes[0].location.valid():return
  lon,lat=w.nodes[0].lon,w.nodes[0].lat
  if not (16.585<lon<16.617 and 47.221<lat<47.233):return
  if not all(n.location.valid() for n in w.nodes):return
  out.append(dict(type='Feature',id=f'osm:way:{w.id}',properties=dict(sourceUrl=f'https://www.openstreetmap.org/way/{w.id}',osmId=w.id,tags=t,nodeRefs=[n.ref for n in w.nodes],objectVersion=w.version,objectTimestamp=str(w.timestamp)),geometry=dict(type='Polygon',coordinates=[[[n.lon,n.lat] for n in w.nodes]])))
with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
 H().apply_file('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf',locations=True,idx='sparse_file_array,'+tmp+'/index')
(P/'estate-source-areas.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=out),ensure_ascii=False))
print(len(out))
