#!/usr/bin/env python3
from pathlib import Path
import json,tempfile
import osmium
from shapely.geometry import LineString,mapping

HERE=Path(__file__).resolve().parent
PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
features=[]
class Handler(osmium.SimpleHandler):
 def way(self,o):
  tags=dict(o.tags)
  if not (tags.get('highway') or tags.get('waterway') or tags.get('railway')=='rail'):return
  try:
   coords=[(n.lon,n.lat) for n in o.nodes]
   if not coords or not any(18.98<=x<=19.085 and 47.505<=y<=47.625 for x,y in coords):return
   if tags.get('highway') in {'footway','path','steps','service','cycleway','track','pedestrian'} and not tags.get('name'):return
   features.append({'type':'Feature','id':'osm:way:'+str(o.id),'geometry':mapping(LineString(coords)),
    'properties':{'name':tags.get('name'),'tags':tags,'sourceUrl':'https://www.openstreetmap.org/way/'+str(o.id),'version':o.version}})
  except (RuntimeError,ValueError):pass
with tempfile.TemporaryDirectory() as t:
 Handler().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(t)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','waterway','railway')])
(HERE/'obuda-source-roads.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
print('Source road ways',len(features))
