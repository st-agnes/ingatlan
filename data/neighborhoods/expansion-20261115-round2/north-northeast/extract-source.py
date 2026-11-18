#!/usr/bin/env python3
from pathlib import Path
import json,gzip,osmium
H=Path(__file__).resolve().parent;P=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
B={'gyongyos':(19.88,47.73,20.01,47.845),'satoraljaujhely':(21.60,48.35,21.68,48.43),'kalocsa':(18.94,46.50,19.06,46.57)}
rows={n:{'roads':[],'areas':[]}for n in B}
class Handler(osmium.SimpleHandler):
 def way(self,w):
  road=any(k in w.tags for k in ['highway','railway','waterway']);area=len(w.nodes)>3 and w.nodes[0].ref==w.nodes[-1].ref and any(k in w.tags for k in ['landuse','natural','building','leisure'])
  if not road and not area:return
  try:x,y=w.nodes[0].lon,w.nodes[0].lat
  except osmium.InvalidLocationError:return
  for city,(west,south,east,north)in B.items():
   if not(west<=x<=east and south<=y<=north):continue
   try:cs=[[n.lon,n.lat]for n in w.nodes]
   except osmium.InvalidLocationError:continue
   f={'type':'Feature','properties':{'name':w.tags.get('name'),'tags':dict(w.tags),'osmWayId':w.id,'sourceUrl':f'https://www.openstreetmap.org/way/{w.id}','nodeRefs':[n.ref for n in w.nodes],'version':w.version,'timestamp':str(w.timestamp)},'geometry':{'type':'LineString'if road else'Polygon','coordinates':cs if road else[cs]}}
   rows[city]['roads'if road else'areas'].append(f)
Handler().apply_file(str(P),locations=True)
for city,kinds in rows.items():
 for kind,features in kinds.items():
  with gzip.GzipFile(str(H/f'{city}-source-{kind}.geojson.gz'),'wb',mtime=0)as g:g.write((json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n').encode())
 print(city,{k:len(v)for k,v in kinds.items()})
