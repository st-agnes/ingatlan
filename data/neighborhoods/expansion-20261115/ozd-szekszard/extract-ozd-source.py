#!/usr/bin/env python3
import osmium,json,hashlib,gzip
from pathlib import Path
H=Path(__file__).resolve().parent
PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
roads=[];areas=[]
class Hdl(osmium.SimpleHandler):
 def way(self,w):
  line=any(k in w.tags for k in ['highway','railway','waterway']);area=len(w.nodes)>3 and w.nodes[0].ref==w.nodes[-1].ref and any(k in w.tags for k in ['landuse','natural','leisure','building'])
  if not line and not area:return
  try:x,y=w.nodes[0].lon,w.nodes[0].lat
  except osmium.InvalidLocationError:return
  if not (20.20<=x<=20.39 and 48.17<=y<=48.29):return
  try:cs=[[n.lon,n.lat]for n in w.nodes]
  except osmium.InvalidLocationError:return
  f={'type':'Feature','properties':{'name':w.tags.get('name'),'tags':dict(w.tags),'osmWayId':w.id,'sourceUrl':f'https://www.openstreetmap.org/way/{w.id}','nodeRefs':[n.ref for n in w.nodes],'version':w.version,'timestamp':str(w.timestamp)},'geometry':{'type':'LineString' if line else 'Polygon','coordinates':cs if line else [cs]}}
  (roads if line else areas).append(f)
Hdl().apply_file(str(PBF),locations=True)
for k,fs in [('roads',roads),('areas',areas)]:
 with gzip.GzipFile(str(H/f'ozd-source-{k}.geojson.gz'),'wb',mtime=0)as archive:archive.write((json.dumps({'type':'FeatureCollection','features':fs},ensure_ascii=False,separators=(',',':'))+'\n').encode())
print(len(roads),'roads',len(areas),'closed source surfaces')
