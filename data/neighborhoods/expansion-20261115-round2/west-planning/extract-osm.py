import json,tempfile,osmium,gzip
from pathlib import Path
P=Path(__file__).parent
bounds={'keszthely':(17.17,46.70,17.31,46.84),'dombovar':(18.05,46.30,18.25,46.44),'tata':(18.22,47.56,18.46,47.73),'kormend':(16.52,46.96,16.67,47.06)}
lines={n:[] for n in bounds};areas={n:[] for n in bounds}
class H(osmium.SimpleHandler):
 def way(self,w):
  t=w.tags
  if not (t.get('highway') or t.get('waterway') or t.get('railway') or t.get('landuse') or t.get('leisure') or t.get('historic')):return
  if not w.nodes or not w.nodes[0].location.valid():return
  coord=w.nodes[0];cities=[n for n,(a,b,c,d) in bounds.items() if a<coord.lon<c and b<coord.lat<d]
  if not cities:return
  if not all(n.location.valid() for n in w.nodes):return
  tags=dict(t);cs=[[n.lon,n.lat] for n in w.nodes];closed=w.nodes[0].ref==w.nodes[-1].ref and len(cs)>3;isarea=closed and(tags.get('landuse') or tags.get('leisure') or tags.get('historic'))
  f=dict(type='Feature',id=f'osm:way:{w.id}',properties=dict(name=tags.get('name',''),source=dict(osmType='way',osmId=w.id,tags=tags,nodeRefs=[n.ref for n in w.nodes],objectVersion=w.version,objectTimestamp=str(w.timestamp),url=f'https://www.openstreetmap.org/way/{w.id}')),geometry=dict(type='Polygon' if isarea else 'LineString',coordinates=[cs] if isarea else cs))
  for n in cities:(areas if isarea else lines)[n].append(f)
with tempfile.TemporaryDirectory(dir='/tmp') as temp:H().apply_file('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf',locations=True,idx='sparse_file_array,'+temp+'/idx')
for city in bounds:
 dest=P/city;dest.mkdir(exist_ok=True)
 for name,fs in [('source-ways.geojson',lines[city]),('source-areas.geojson',areas[city])]: (dest/name).write_text(json.dumps(dict(type='FeatureCollection',features=fs),ensure_ascii=False))
 print(city,len(lines[city]),len(areas[city]))
