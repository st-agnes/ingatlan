import osmium,json,tempfile
from pathlib import Path
P=Path(__file__).parent;out=[]
class H(osmium.SimpleHandler):
 def way(self,w):
  t=w.tags
  if t.get('landuse') not in ['residential','farmyard','industrial']:return
  if len(w.nodes)<4 or w.nodes[0].ref!=w.nodes[-1].ref or not w.nodes[0].location.valid():return
  a=w.nodes[0]
  if not (18.05<a.lon<18.25 and 46.39<a.lat<46.47):return
  if not all(n.location.valid() for n in w.nodes):return
  out.append(dict(type='Feature',id=f'osm:way:{w.id}',properties=dict(sourceUrl=f'https://www.openstreetmap.org/way/{w.id}',tags=dict(w.tags),nodeRefs=[n.ref for n in w.nodes],objectVersion=w.version,objectTimestamp=str(w.timestamp)),geometry=dict(type='Polygon',coordinates=[[[n.lon,n.lat] for n in w.nodes]])))
with tempfile.TemporaryDirectory(dir='/tmp') as temp:H().apply_file('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf',locations=True,idx='sparse_file_array,'+temp+'/idx',filters=[osmium.filter.KeyFilter('landuse')])
(P/'source-rural-areas.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=out),ensure_ascii=False,indent=2)+'\n');print(len(out))
