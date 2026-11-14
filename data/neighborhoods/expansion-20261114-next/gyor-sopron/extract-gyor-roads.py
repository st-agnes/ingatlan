#!/usr/bin/env python3
"""Local OSM streets for manual neighborhood inference; no network requests."""
import json, tempfile
from pathlib import Path
import osmium
HERE=Path(__file__).resolve().parent
features=[]
class Reader(osmium.SimpleHandler):
 def way(self,w):
  t=dict(w.tags)
  if not (t.get('highway') or t.get('waterway') or t.get('railway')):return
  try:cs=[[n.lon,n.lat] for n in w.nodes]
  except osmium.InvalidLocationError:return
  if not any(17.55<x<17.80 and 47.60<y<47.75 for x,y in cs):return
  features.append({'type':'Feature','id':'osm:way:'+str(w.id),'geometry':{'type':'LineString','coordinates':cs},'properties':{'name':t.get('name'),'source':{'url':'https://www.openstreetmap.org/way/'+str(w.id),'osmType':'way','osmId':w.id,'tags':t,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','geometryUnmodified':True,'pbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'}}})
with tempfile.TemporaryDirectory() as tmp:
 Reader().apply_file('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf',locations=True,idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','waterway','railway')])
(HERE/'gyor-source-roads.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
print('Győr mapped roads/rail/waterway sources',len(features),flush=True)
