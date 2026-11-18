import osmium,json
from pathlib import Path
P=Path(__file__).parent;out=[]
class H(osmium.SimpleHandler):
 def node(self,n):
  name=n.tags.get('name','')
  if name not in ['Szilfás','Kiskonda','Nagykonda','Szarvasd','Perekac','Mászlony']:return
  if not(18.04<n.lon<18.30 and 46.30<n.lat<46.47):return
  out.append(dict(type='Feature',id=f'osm:node:{n.id}',properties=dict(name=name,sourceUrl=f'https://www.openstreetmap.org/node/{n.id}',tags=dict(n.tags),objectVersion=n.version,objectTimestamp=str(n.timestamp)),geometry=dict(type='Point',coordinates=[n.lon,n.lat])))
H().apply_file('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf',filters=[osmium.filter.EntityFilter(osmium.osm.NODE),osmium.filter.KeyFilter('name')])
(P/'source-rural-labels.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=out),ensure_ascii=False,indent=2)+'\n');print([(f['properties']['name'],f['geometry']['coordinates']) for f in out])
