#!/usr/bin/env python3
"""One focused local road/closed-landuse-way scan; no network or area assembly."""
from pathlib import Path
import json,gzip,tempfile,time
import osmium
from shapely.geometry import LineString,Polygon,mapping
P=Path(__file__).resolve().parent;ROOT=P.parents[3];D=ROOT/'data/neighborhoods';PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf');BB=(22.025,48.18,22.145,48.27);HASH='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
def write(n,v):(P/n).write_text(json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n')
parents=json.loads(gzip.decompress((D/'sources/country-osm/municipalities.geojson.gz').read_bytes()))['features'];parent=next(f for f in parents if f['properties']['name']=='Kisvárda');write('source-municipality.geojson',{'type':'FeatureCollection','features':[parent]})
(P/'source-boundary-definitions.json').write_bytes((D/'sources/municipal-east/kisvarda-boundary-definitions.json').read_bytes())
lines=[];areas=[];start=time.monotonic()
class H(osmium.SimpleHandler):
 def way(self,w):
  t=dict(w.tags)
  if not(t.get('highway') or t.get('railway') or t.get('waterway') or t.get('landuse') or t.get('leisure')):return
  if not w.nodes or not w.nodes[0].location.valid():return
  pts=[(n.lon,n.lat) for n in w.nodes if n.location.valid()]
  if len(pts)<2:return
  xs,ys=zip(*pts)
  if max(xs)<BB[0] or min(xs)>BB[2] or max(ys)<BB[1] or min(ys)>BB[3]:return
  closed=w.nodes[0].ref==w.nodes[-1].ref and len(pts)>3
  isarea=closed and(t.get('landuse') or t.get('leisure'))
  g=Polygon(pts) if isarea else LineString(pts)
  if g.is_empty or not g.is_valid:return
  p={'name':t.get('name'),'tags':t,'sourceUrl':f'https://www.openstreetmap.org/way/{w.id}','version':w.version,'timestamp':str(w.timestamp),'pbfSha256':HASH}
  (areas if isarea else lines).append({'type':'Feature','id':f'osm:way:{w.id}','properties':p,'geometry':mapping(g)})
with tempfile.TemporaryDirectory(prefix='kisvarda-focused-') as tmp:H().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway','waterway','landuse','leisure')])
meta={'type':'FeatureCollection','pbfSha256':HASH,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'};write('source-lines.geojson',{**meta,'features':lines});write('source-areas.geojson',{**meta,'features':areas});print(json.dumps({'lines':len(lines),'areas':len(areas),'seconds':round(time.monotonic()-start,1)}),flush=True)
